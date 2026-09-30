"""TourAPI areaBasedList2 로 서울 전체 목록을 분류(lclsSystm1)별로 끝 페이지까지 받는다.

- 키는 .env.apikeys 의 ACOP_TOUR_API_KEY → ACOP_DATA_GO_KR_KEY 순으로 읽고, 출력하지 않는다.
- 분류마다 pageNo 를 totalCount 에 닿을 때까지 돌린다(예전에 일부만 받은 원인이 페이지 제한이었다).
- 결과는 data_processing/tourapi_seoul_list.csv 에 저장하고, 기존 activity_total_data.csv 에 없는
  contentid(신규 후보)가 분류별로 몇 건인지 요약한다. 기존 CSV 는 건드리지 않는다.

사용:
    python scripts/fetch_tourapi_list.py            # 전체 분류
    python scripts/fetch_tourapi_list.py --only EV  # 한 분류만(시험)
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "app/modules/travel_ops/activity/data_processing"
OUT_PATH = DATA_DIR / "tourapi_seoul_list.csv"
TOTAL_PATH = DATA_DIR / "activity_total_data.csv"
APIKEYS = ROOT / ".env.apikeys"
BASE = "https://apis.data.go.kr/B551011/KorService2/areaBasedList2"
CATEGORIES = ["EV", "EX", "HS", "LS", "NA", "VE", "SH"]
PAGE_SIZE = 1000
INTERVAL = 0.3
COLUMNS = ["contentid", "contenttypeid", "title", "addr1", "addr2", "areacode", "sigungucode", "mapx", "mapy",
           "firstimage", "cpyrhtDivCd", "lclsSystm1", "lclsSystm2", "lclsSystm3"]


def load_key() -> str:
    values = {}
    if APIKEYS.exists():
        for line in APIKEYS.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.partition("=")
            if sep and not name.lstrip().startswith("#"):
                values[name.strip()] = value.strip().strip("\"'")
    key = values.get("ACOP_TOUR_API_KEY") or values.get("ACOP_DATA_GO_KR_KEY") or ""
    if not key:
        sys.exit("TourAPI 키가 .env.apikeys 에 없습니다.")
    return urllib.parse.unquote(key) if "%" in key else key  # Encoding 키는 풀어서 쓴다


def call(key: str, params: dict) -> dict:
    query = urllib.parse.urlencode({"serviceKey": key, "MobileOS": "ETC", "MobileApp": "acop", "_type": "json", **params})
    try:
        with urllib.request.urlopen(f"{BASE}?{query}", timeout=30) as r:
            body = r.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"네트워크 오류: {getattr(e, 'reason', e)}")  # URL(키 포함)은 출력하지 않는다
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        sys.exit(f"JSON 이 아닌 응답(키 오류·한도 초과일 수 있음): {body[:200]}")
    header = payload.get("response", {}).get("header", {})
    if header.get("resultCode") != "0000":
        sys.exit(f"오류 응답: {header.get('resultCode')} {header.get('resultMsg')}")
    return payload["response"]["body"]


def is_seoul(row: dict) -> bool:
    return str(row.get("addr1") or "").strip().startswith("서울")


def fetch_category(key: str, cat: str) -> tuple[int, list[dict]]:
    """분류의 **전국** 목록을 끝까지 받아 주소가 서울로 시작하는 행만 남긴다.

    ★areaCode=1 로 받으면 서울 행의 대부분(약 87%)이 빠진다 — TourAPI 는 서울 주소여도
      지역코드가 비어 있는 행이 많다(2026-09-29 확인: 서울 주소 6,012건 중 코드 1은 771건).
    """
    rows: list[dict] = []
    received, page, total = 0, 1, None
    while total is None or received < total:
        body = call(key, {"lclsSystm1": cat, "numOfRows": PAGE_SIZE, "pageNo": page})
        total = int(body.get("totalCount") or 0)
        items = body.get("items") or {}
        item = items.get("item") if isinstance(items, dict) else None
        if not item:
            break
        batch = item if isinstance(item, list) else [item]
        received += len(batch)
        rows.extend(r for r in batch if is_seoul(r))
        page += 1
        time.sleep(INTERVAL)
    return total, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="한 분류만 받는다(예: EV)")
    args = ap.parse_args()
    key = load_key()
    cats = [args.only] if args.only else CATEGORIES

    got: dict[str, dict] = {}
    for cat in cats:
        total, rows = fetch_category(key, cat)
        for r in rows:
            got[str(r["contentid"])] = r
        print(f"{cat}: 전국 totalCount={total} / 서울 주소 행={len(rows)}")
    with OUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(COLUMNS)
        for r in got.values():
            w.writerow([str(r.get(c, "") or "") for c in COLUMNS])
    print(f"저장: {OUT_PATH.name} ({len(got)}행)")

    have = {r["contentid"] for r in csv.DictReader(TOTAL_PATH.open(encoding="utf-8-sig", newline=""))}
    new = [r for r in got.values() if str(r["contentid"]) not in have]
    print(f"\n기존 CSV에 없는 신규 후보: {len(new)}건")
    by_cat = collections.Counter(r.get("lclsSystm1", "") for r in new)
    for cat in cats:
        print(f"  {cat}: 신규 {by_cat.get(cat, 0)}")
    if "SH" in cats:
        print("\n쇼핑(SH) 세부 분류(lclsSystm3)별 신규:")
        for code, n in collections.Counter(r.get("lclsSystm3", "") for r in new if r.get("lclsSystm1") == "SH").most_common():
            print(f"  {code}: {n}")


if __name__ == "__main__":
    main()
