# -*- coding: utf-8 -*-
"""TourAPI 상세(detailCommon2·detailIntro2) 호출의 공용 부품 — 키 읽기 · 캐시 · 호출. `fill_tourapi_details.py` 가 쓴다.

★키는 코드·출력 어디에도 남기지 않는다. `ACOP_TOUR_API_KEY` 환경변수, 없으면
  `final_project_cs/.env.apikeys`(gitignore 대상)에서 읽는다. 오류를 출력할 때도 요청 URL 은
  찍지 않는다 — URL 에 키가 들어 있다.

★실패를 성공처럼 넘기지 않는다. 오류 응답(한도 초과 포함)이나 JSON 이 아닌 응답을 받으면
  **그 자리에서 멈춘다.** 계속 부르면 한도만 더 태운다.
  네트워크 오류(응답을 못 받음)만 `RETRY_WAITS_SECONDS` 대로 기다렸다 다시 부르고, 그래도 안 되면 멈춘다.

★받은 응답은 캐시(`tourapi_details_cache.jsonl`)에 한 줄씩 바로 쓰고, 다시 돌리면 **캐시에 있는 건 부르지 않는다.**
  개발 계정 하루 한도(보통 1,000건)에 걸려 멈춰도 다음 날 이어서 받는다.

(옛 `fetch_tourapi_details.py` 에서 올리브영·다이소·아트박스 검색 결과에 상세를 붙여 CSV 를 만들던 부분은
 최종 데이터(`activity_total_data.csv`)에 반영이 끝나 지웠다. 이 부품은 그 파일에서 그대로 옮겼다.)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ★parents[6] = final_project_cs. data_processing/ 로 옮겨진 뒤 parents[5](= app/)로 남아 있어 키 파일을 못 찾았다(2026-10-11).
PROJECT = Path(__file__).resolve().parents[6]
DATA_DIR = Path(__file__).resolve().parent   # 작업용 데이터는 이 폴더에 둔다
APIKEYS_FILE = PROJECT / ".env.apikeys"
CACHE_FILE = DATA_DIR / "tourapi_details_cache.jsonl"

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
#: 호출 사이 간격(초). ★짧은 시간에 몰아서 부르면 공급자가 막거나 늦게 답할 수 있어 띄운다.
#: 응답 대기(초). ★2026-09-26 실행에서 10초 대기로 read timeout 이 반복돼 둘 다 늘렸다.
CALL_INTERVAL_SECONDS = 0.5
TIMEOUT_SECONDS = 30
#: 네트워크 오류(연결 안 됨·응답 없음)일 때만 다시 부르기 전 기다리는 초. 다 쓰면 멈춘다.
#: ★2026-10-12 하루에 세 번(293·72·10건째) WinError 10060 · read timeout 으로 멈췄고, 바로 curl 로 같은 호출을
#:   부르니 정상이었다 — 일시 끊김이라 기다렸다 다시 부른다. 오류 응답·한도 초과(=응답을 받은 경우)는 다시 안 부른다.
RETRY_WAITS_SECONDS = (10, 30, 60)


class StopFetching(RuntimeError):
    """더 부르면 안 되는 상황(오류 응답·한도 초과·네트워크 실패). 받은 것까지는 캐시에 남아 있다."""


# ── 키 ─────────────────────────────────────────────────────────
#: 키를 찾는 순서. ★프로젝트 규칙과 같다(`settings.py` · `base.py._public_data_key`) — data.go.kr
#: 공통 키 하나로 TourAPI 도 쓰고, `ACOP_TOUR_API_KEY` 는 다른 계정을 쓸 때만 채우는 덮어쓰기다.
KEY_NAMES = ("ACOP_TOUR_API_KEY", "ACOP_DATA_GO_KR_KEY")


def _read_apikeys_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if APIKEYS_FILE.exists():
        for line in APIKEYS_FILE.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.partition("=")
            if sep and not name.lstrip().startswith("#"):
                values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def load_service_key() -> str:
    """TourAPI 키를 읽는다. ★값을 출력하거나 반환값 외의 곳에 남기지 않는다.

    환경변수를 먼저 보고, 없으면 `.env.apikeys` 를 본다. 각각 KEY_NAMES 순서로 찾는다.
    """
    file_values = _read_apikeys_file()
    key = next((value for source in (os.environ, file_values) for name in KEY_NAMES
                if (value := source.get(name, "").strip())), "")
    if not key:
        raise SystemExit(f"TourAPI 키가 없다 — {APIKEYS_FILE.name} 의 ACOP_DATA_GO_KR_KEY(공통 키) 또는 "
                         "ACOP_TOUR_API_KEY 에 넣는다")
    # ★data.go.kr 은 Encoding 키(%2B 같은 문자 포함)와 Decoding 키를 둘 다 준다. 아래 urlencode 가
    #   한 번 더 인코딩하므로 Encoding 키는 먼저 풀어 둔다 — 안 그러면 이중 인코딩으로 인증이 실패한다.
    return urllib.parse.unquote(key) if "%" in key else key


# ── 캐시 ───────────────────────────────────────────────────────
def load_cache() -> dict[tuple[str, str], dict[str, Any] | None]:
    """(contentid, operation) → 받은 항목(없으면 None). 이 목록에 있으면 다시 부르지 않는다."""
    cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    if CACHE_FILE.exists():
        for line in CACHE_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                cache[(entry["contentid"], entry["operation"])] = entry["item"]
    return cache


def append_cache(content_id: str, operation: str, item: dict[str, Any] | None) -> None:
    # ★받는 즉시 한 줄씩 쓴다. 중간에 멈춰도 여기까지 받은 호출은 잃지 않는다(= 한도를 다시 안 쓴다).
    with CACHE_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"contentid": content_id, "operation": operation, "item": item,
                             "fetched_at": datetime.now(timezone.utc).isoformat()},
                            ensure_ascii=False) + "\n")


# ── 호출 ───────────────────────────────────────────────────────
def _fetch_body(url: str, operation: str) -> str:
    """응답 본문. 네트워크 오류면 `RETRY_WAITS_SECONDS` 대로 기다렸다 다시 부르고, 다 쓰면 멈춘다.

    ★HTTP 오류(`HTTPError` — 서버가 답은 했다)는 다시 부르지 않고 바로 멈춘다. 한도만 더 태울 수 있다.
    """
    for wait in (*RETRY_WAITS_SECONDS, None):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise StopFetching(f"{operation} HTTP 오류: {error.code} {error.reason}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            # ★error 에 URL 을 붙여 출력하지 않는다 — URL 에 키가 있다.
            reason = getattr(error, "reason", error)
            if wait is None:
                raise StopFetching(f"{operation} 네트워크 오류({len(RETRY_WAITS_SECONDS)}번 다시 불러도 실패): "
                                   f"{reason}") from None
            print(f"  {operation} 네트워크 오류 — {wait}초 뒤 다시 부른다: {reason}", flush=True)
            time.sleep(wait)
    raise AssertionError("unreachable")


def call_tourapi(operation: str, params: dict[str, str], service_key: str) -> dict[str, Any] | None:
    """상세 API 한 번. 항목 하나(dict)를 돌려주고, 공급자가 「없음」이라 하면 None.

    ★오류 응답은 None 으로 바꾸지 않고 멈춘다 — 「없음」과 「못 받음」을 섞으면 못 받은 장소가
      캐시에 「없음」으로 굳어 다시는 안 불린다.
    """
    query = urllib.parse.urlencode({"serviceKey": service_key, "MobileOS": "ETC", "MobileApp": "acop",
                                    "_type": "json", **params})
    body = _fetch_body(f"{BASE_URL}/{operation}?{query}", operation)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        # ★키 오류·한도 초과는 _type=json 을 줘도 XML 로 온다. 앞부분만 보여 준다(키는 들어 있지 않다).
        raise StopFetching(f"{operation} JSON 이 아닌 응답(키 오류·한도 초과일 수 있음): {body[:300]}") from None

    header = payload.get("response", {}).get("header", {})
    if header.get("resultCode") != "0000":
        raise StopFetching(f"{operation} 오류 응답: {header.get('resultCode')} {header.get('resultMsg')}")
    items = payload["response"].get("body", {}).get("items") or {}
    item = items.get("item") if isinstance(items, dict) else None
    if isinstance(item, list):
        item = item[0] if item else None
    return item
