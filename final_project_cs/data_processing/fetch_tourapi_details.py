# -*- coding: utf-8 -*-
"""TourAPI 검색 결과 CSV 에 상세 정보(개요·홈페이지·영업시간·휴무)를 붙여 기본 20컬럼 CSV 로 만든다.

사용(실행은 키를 가진 사람이 **자기 PC 에서** 한다):
    # 1) 먼저 2건만 호출해서 키·응답이 정상인지 본다
    python -m data_processing.fetch_tourapi_details --max-calls 2
    # 2) 나머지를 받는다. 하루 한도에 걸려 멈추면 다음 날 같은 명령을 다시 돌린다
    python -m data_processing.fetch_tourapi_details
    # 3) 호출 없이 이미 받은 것만으로 CSV 를 다시 만든다
    python -m data_processing.fetch_tourapi_details --build-only

입력(기본값): data_processing/tourapi_{oliveyoung,daiso,artbox}_seoul.csv — `searchKeyword2`
              응답(lDongRegnCd=11)을 `filter_tourapi_seoul.py` 로 옮긴 것.
출력:         data_processing/tourapi_{…}_seoul_enriched.csv — `activities_candidates_seoul_enriched.csv`
              와 같은 20컬럼.
캐시:         data_processing/tourapi_details_cache.jsonl — 받은 상세 응답 원본. **재개의 근거**다.

★왜 장소마다 호출하는가. 검색 결과에는 개요·홈페이지·영업시간이 없다. `detailCommon2`
  (개요·홈페이지·전화)와 `detailIntro2`(영업시간·휴무)는 한 번에 장소 하나만 받는다 —
  449곳이면 약 898번이다. 개발 계정 하루 한도(보통 1,000건)에 가깝다.
  그래서 받은 응답을 캐시에 한 줄씩 바로 쓰고, 다시 돌리면 **캐시에 있는 건 부르지 않는다.**

★키는 코드·출력 어디에도 남기지 않는다. `ACOP_TOUR_API_KEY` 환경변수, 없으면
  `final_project_cs/.env.apikeys`(gitignore 대상)에서 읽는다. 오류를 출력할 때도 요청 URL 은
  찍지 않는다 — URL 에 키가 들어 있다.

★실패를 성공처럼 넘기지 않는다. 오류 응답(한도 초과 포함)이나 JSON 이 아닌 응답을 받으면
  **그 자리에서 멈춘다.** 계속 부르면 한도만 더 태운다. 상세가 없는 장소는 해당 칸을
  비워 두고(모름) 건수를 따로 알린다.

컬럼 매핑(기본 20컬럼 기준):
    검색 결과 그대로   contentid contenttypeid title addr1 addr2 sigungucode mapx mapy
                       firstimage cpyrhtDivCd lclsSystm1 lclsSystm2 lclsSystm3
    detailCommon2      tel overview homepage
    detailIntro2       business_hours ← opentime, closed_days ← restdateshopping,
                       fee ← saleitemcost  (쇼핑(38) 응답의 필드 이름)
    비워 둠            event_period — 행사 기간 칸이라 쇼핑 응답에는 해당 항목이 없다
    ★enriched.csv 를 만든 담당자의 규칙을 따른다(2026-09-26 확인): 타입별 detailIntro2 응답에서
      영업시간·휴무·비용에 해당하는 필드를 원문 그대로 옮긴다. 예) 관광지(12) usetime/restdate,
      문화시설(14) usetimeculture/restdateculture/usefee, 행사(15) playtime/usetimefestival/
      eventstartdate~eventenddate. 지금 입력(올리브영·다이소·아트박스)은 전부 쇼핑(38)이라
      쇼핑 필드로 매칭한다.
    ※ sigungucode 는 검색 결과에서 비어 있다(areacode 가 없는 행들). 채우는 방법은 미정이라
      여기서는 원문(빈 값) 그대로 둔다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent   # 작업용 데이터는 이 폴더에 둔다
APIKEYS_FILE = PROJECT / ".env.apikeys"
CACHE_FILE = DATA_DIR / "tourapi_details_cache.jsonl"
DEFAULT_INPUTS = [DATA_DIR / f"tourapi_{brand}_seoul.csv" for brand in ("oliveyoung", "daiso", "artbox")]

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
#: 호출 사이 간격(초). ★짧은 시간에 몰아서 부르면 공급자가 막거나 늦게 답할 수 있어 띄운다.
#: 응답 대기(초). ★2026-09-26 실행에서 10초 대기로 read timeout 이 반복돼 둘 다 늘렸다.
CALL_INTERVAL_SECONDS = 0.5
TIMEOUT_SECONDS = 30

BASE_COLUMNS = ["contentid", "contenttypeid", "title", "addr1", "addr2", "sigungucode", "mapx", "mapy",
                "tel", "firstimage", "cpyrhtDivCd", "lclsSystm1", "lclsSystm2", "lclsSystm3", "overview",
                "homepage", "business_hours", "closed_days", "fee", "event_period"]
#: 검색 결과(searchKeyword2)에서 그대로 옮기는 컬럼. `tel` 은 검색 결과에서 늘 비어 있어 상세에서 받는다.
SEARCH_COLUMNS = ["contentid", "contenttypeid", "title", "addr1", "addr2", "sigungucode", "mapx", "mapy",
                  "firstimage", "cpyrhtDivCd", "lclsSystm1", "lclsSystm2", "lclsSystm3"]


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
def call_tourapi(operation: str, params: dict[str, str], service_key: str) -> dict[str, Any] | None:
    """상세 API 한 번. 항목 하나(dict)를 돌려주고, 공급자가 「없음」이라 하면 None.

    ★오류 응답은 None 으로 바꾸지 않고 멈춘다 — 「없음」과 「못 받음」을 섞으면 못 받은 장소가
      캐시에 「없음」으로 굳어 다시는 안 불린다.
    """
    query = urllib.parse.urlencode({"serviceKey": service_key, "MobileOS": "ETC", "MobileApp": "acop",
                                    "_type": "json", **params})
    try:
        with urllib.request.urlopen(f"{BASE_URL}/{operation}?{query}", timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as error:
        # ★error 에 URL 을 붙여 출력하지 않는다 — URL 에 키가 있다.
        raise StopFetching(f"{operation} 네트워크 오류: {getattr(error, 'reason', error)}") from None

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


def fetch_details(rows: list[dict[str, str]], service_key: str, max_calls: int | None) -> int:
    """캐시에 없는 상세만 부른다. 부른 횟수를 돌려준다."""
    cache = load_cache()
    calls = 0
    for row in rows:
        content_id, content_type_id = row["contentid"], row["contenttypeid"]
        # detailCommon2 는 contentTypeId 를 받지 않는다(넣으면 오류 — tour_api.py 실측 주석).
        # detailIntro2 는 반대로 contentTypeId 가 있어야 타입별 필드를 준다.
        for operation, params in (("detailCommon2", {"contentId": content_id}),
                                  ("detailIntro2", {"contentId": content_id,
                                                    "contentTypeId": content_type_id})):
            if (content_id, operation) in cache:
                continue
            if max_calls is not None and calls >= max_calls:
                return calls
            item = call_tourapi(operation, params, service_key)
            append_cache(content_id, operation, item)
            cache[(content_id, operation)] = item
            calls += 1
            time.sleep(CALL_INTERVAL_SECONDS)
    return calls


# ── CSV 만들기 ─────────────────────────────────────────────────
def to_base_row(search_row: dict[str, str], common: dict[str, Any] | None,
                intro: dict[str, Any] | None) -> dict[str, str]:
    """검색 결과 + 상세 두 개 → 기본 20컬럼. 상세가 없으면(미수집·공급자에 없음) 그 칸은 빈 값(모름)."""
    row = {column: "" for column in BASE_COLUMNS}
    row.update({column: search_row.get(column, "") for column in SEARCH_COLUMNS})
    common, intro = common or {}, intro or {}
    row["tel"] = str(common.get("tel") or "")
    row["overview"] = str(common.get("overview") or "")
    row["homepage"] = str(common.get("homepage") or "")
    row["business_hours"] = str(intro.get("opentime") or "")
    row["closed_days"] = str(intro.get("restdateshopping") or "")
    # 쇼핑 응답의 비용 항목은 판매 품목별 가격(saleitemcost)이다 — 입장료 칸(fee)에 이걸 옮긴다.
    row["fee"] = str(intro.get("saleitemcost") or "")
    return row


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_outputs(inputs: list[Path]) -> None:
    cache = load_cache()
    for path in inputs:
        rows = read_csv(path)
        out = path.with_name(path.stem + "_enriched.csv")
        base_rows = [to_base_row(row, cache.get((row["contentid"], "detailCommon2")),
                                 cache.get((row["contentid"], "detailIntro2"))) for row in rows]
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=BASE_COLUMNS)
            writer.writeheader()
            writer.writerows(base_rows)
        # ★캐시에 아예 없는 것(아직 안 부름)과 불렀지만 공급자가 비워 준 것을 나눠 센다.
        not_fetched = sum(1 for row in rows for op in ("detailCommon2", "detailIntro2")
                          if (row["contentid"], op) not in cache)
        no_hours = sum(1 for row in base_rows if not row["business_hours"])
        print(f"{out.name}: {len(base_rows)}건 · 아직 안 받은 상세 호출 {not_fetched}건 · "
              f"영업시간 빈 값 {no_hours}건")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inputs", type=Path, nargs="*", default=DEFAULT_INPUTS)
    ap.add_argument("--max-calls", type=int, default=None, help="이번 실행에서 부를 최대 횟수")
    ap.add_argument("--build-only", action="store_true", help="호출 없이 캐시로 CSV 만 만든다")
    args = ap.parse_args(argv)

    if not args.build_only:
        rows = [row for path in args.inputs for row in read_csv(path)]
        service_key = load_service_key()
        try:
            calls = fetch_details(rows, service_key, args.max_calls)
            print(f"이번 실행 호출 {calls}건")
        except StopFetching as stop:
            print(f"멈춤: {stop}\n→ 받은 것까지는 {CACHE_FILE.name} 에 남아 있다. 원인을 확인한 뒤 "
                  "같은 명령을 다시 돌리면 이어서 받는다")
    build_outputs(args.inputs)


if __name__ == "__main__":
    sys.exit(main())
