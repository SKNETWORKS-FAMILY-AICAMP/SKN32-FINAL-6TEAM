"""관광공사 목록 가운데 아직 소개정보(detailIntro2)를 받지 않은 음식점을 받아 원본에 더한다.

왜 원본에 더하는가.
    parse_hours.py, make_load_sql.py, make_attribute_sql.py 가 모두
    datasets/dining/processed/tourapi_음식점_소개정보.json 하나를 읽는다. 파일을 따로 두면 셋을 다 고쳐야 한다.
    행은 받은 그대로 두고, 우리가 붙이는 칸은 앞에 _ 를 붙인다(기존 200건과 같은 규칙).
        _title, _addr   목록에서 가져온 상호와 주소
        _region         기존 200건의 권역. 새로 받는 행은 권역이 없으므로 null 이다(033: hub 는 비어도 된다)
        _fetched_at     받은 시각. 기존 200건에는 없다

얼마나 부르는가.
    가게 하나에 한 번. 관광공사 하루 한도는 1,000건이고 앱도 같은 키를 쓴다(ACOP_RATE_TOUR_API_PER_DAY).
    그래서 기본 --limit 을 800 으로 둔다. 모자라면 다음 날 다시 돌리면 받은 것은 건너뛴다.
    열 건마다 파일에 쓴다. 중간에 끊겨도 받은 것은 남는다.

    한도 초과 같은 오류 코드가 오면 거기서 멈춘다. 계속 두들기지 않는다.

사용법
    python scripts/dining/fetch_intro.py --dry-run        몇 곳이 남았는지만 본다
    python scripts/dining/fetch_intro.py                  최대 800곳
    python scripts/dining/fetch_intro.py --limit 50

키는 ACOP_TOUR_API_KEY, 없으면 ACOP_DATA_GO_KR_KEY. 환경변수에 없으면 .env.apikeys 에서 읽는다.
받은 뒤에는 rebuild.py 로 parse_hours 부터 다시 돈다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = DINING_DATA
LIST = os.path.join(DATA, "tourapi_서울_음식점_목록.json")
INTRO = os.path.join(DATA, "tourapi_음식점_소개정보.json")

if hasattr(sys.stdout, "reconfigure"):      # 시험에서 불러올 때는 없다
    sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = "https://apis.data.go.kr/B551011/KorService2/detailIntro2"
KST = timezone(timedelta(hours=9))
TIMEOUT = 10
SAVE_EVERY = 10
PAUSE = 0.2                 # 초. 한도는 하루 단위지만 몰아서 두들기지 않는다
DEFAULT_LIMIT = 800


class Stop(RuntimeError):
    """더 부르면 안 되는 오류. 한도 초과, 키 오류 같은 것."""


# ──────────────────────────────────────────────────────────────
# 키
# ──────────────────────────────────────────────────────────────

def read_env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return out


def service_key(env: dict[str, str] | None = None) -> str:
    """서비스별 키 > 공통 키. base.py 의 _public_data_key 와 같은 순서다."""
    env = dict(env if env is not None else os.environ)
    if not (env.get("ACOP_TOUR_API_KEY") or env.get("ACOP_DATA_GO_KR_KEY")):
        env = {**read_env_file(os.path.join(ROOT, ".env.apikeys")), **env}
    key = env.get("ACOP_TOUR_API_KEY") or env.get("ACOP_DATA_GO_KR_KEY") or ""
    # 포털은 인코딩된 키와 풀린 키를 둘 다 준다. 한 번 풀어 두고 보낼 때 다시 싼다.
    return urllib.parse.unquote(key)


# ──────────────────────────────────────────────────────────────
# 부르기
# ──────────────────────────────────────────────────────────────

def request_url(key: str, content_id: str) -> str:
    return ENDPOINT + "?" + urllib.parse.urlencode({
        "serviceKey": key, "MobileOS": "ETC", "MobileApp": "acop", "_type": "json",
        "contentId": content_id, "contentTypeId": "39"})


def http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_response(text: str) -> dict[str, Any] | None:
    """응답에서 행 하나. 행이 없으면 None. 더 부르면 안 되는 오류면 Stop."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 키 오류, 한도 초과는 JSON 을 달라고 해도 XML 로 온다.
        raise Stop(f"JSON 이 아닌 응답: {text[:200]}") from None
    header = (data.get("response") or {}).get("header") or {}
    code = str(header.get("resultCode", ""))
    if code != "0000":
        raise Stop(f"오류 코드 {code}: {header.get('resultMsg')}")
    items = ((data["response"].get("body") or {}).get("items")) or {}
    rows = items.get("item") if isinstance(items, dict) else None
    if isinstance(rows, dict):
        rows = [rows]
    return rows[0] if rows else None


def fetch(key: str, content_id: str, get: Callable[[str], str] = http_get) -> dict[str, Any] | None:
    try:
        return parse_response(get(request_url(key, content_id)))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise Stop(f"HTTP {exc.code}") from exc
        raise


# ──────────────────────────────────────────────────────────────
# 파일
# ──────────────────────────────────────────────────────────────

def load(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(rows: list[dict[str, Any]], path: str) -> None:
    """임시 파일에 쓰고 바꿔 끼운다. 쓰다 끊겨도 원본이 반쯤 남지 않게."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def pending(listing: list[dict[str, Any]], intro: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """목록에 있고 소개정보에 없는 음식점. 목록 순서를 따른다."""
    have = {str(r.get("contentid")) for r in intro}
    return [r for r in listing
            if str(r.get("contentid")) not in have and str(r.get("contenttypeid")) == "39"]


def with_ours(row: dict[str, Any], item: dict[str, Any], at: datetime) -> dict[str, Any]:
    return {**row, "_title": item.get("title"), "_addr": item.get("addr1") or None,
            "_region": None, "_fetched_at": at.isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    listing, intro = load(LIST), load(INTRO)
    todo = pending(listing, intro)
    print(f"목록 {len(listing)} · 받은 것 {len(intro)} · 남은 것 {len(todo)} · 이번 {min(len(todo), args.limit)}")
    if args.dry_run or not todo:
        return 0

    key = service_key()
    if not key:
        print("ACOP_TOUR_API_KEY 도 ACOP_DATA_GO_KR_KEY 도 비어 있다.", file=sys.stderr)
        return 2

    got = empty = 0
    stopped: str | None = None
    for i, item in enumerate(todo[:args.limit], 1):
        cid = str(item["contentid"])
        try:
            row = fetch(key, cid)
        except Stop as exc:
            stopped = str(exc)
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  건너뜀 {cid}: {exc}")
            continue
        if row is None:
            empty += 1
            print(f"  소개정보 없음 {cid} {item.get('title')}")
        else:
            intro.append(with_ours(row, item, datetime.now(KST)))
            got += 1
        if i % SAVE_EVERY == 0:
            save(intro, INTRO)
            print(f"  {i}건 봄 · 받음 {got}")
        time.sleep(PAUSE)
    save(intro, INTRO)

    print(f"받음 {got} · 소개정보 없음 {empty} · 이제 {len(intro)}건")
    if stopped:
        print(f"멈췄다: {stopped}", file=sys.stderr)
        return 1
    print("다음: python scripts/dining/rebuild.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
