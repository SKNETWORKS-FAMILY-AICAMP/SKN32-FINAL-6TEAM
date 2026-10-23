"""서울 음식점 목록을 **법정동 코드**(`lDongRegnCd=11`)로 다시 받아 목록 원본에 없는 가게를 더한다. `[2026-10-05]`

왜.
    목록은 처음 `areaCode=1` 로 받았다(990곳). 그런데 관광공사 응답 대부분이 `areacode` 를 비워 두어 이 방법은 서울 음식점의
    약 60%만 가져온다(팀이 10/1 에 재서 1,595곳 중 946곳 — 토속촌삼계탕이 빠져 있었다). 법정동 코드로 받으면 빠짐이 없다.

하는 일.
    1  `areaBasedList2?lDongRegnCd=11&contentTypeId=39` 를 쪽마다 받아 `tourapi_서울_음식점_목록_법정동.json`(원본 그대로)에 쓴다.
    2  `tourapi_서울_음식점_목록.json` 에 없는 contentid 만 **뒤에 붙인다**. 기존 행은 바꾸지 않는다(사람이 검수한 시트가 contentid 로 이 행들을 가리킨다).
    3  기존 파일은 `_backup/<날짜_시각>_목록_법정동_전/` 로 먼저 복사한다.

얼마나 부르는가. 한 쪽 1,000행이면 두 번이다(관광공사 하루 한도 1,000건, 앱도 같은 키를 쓴다 — fetch_intro.py 머리말).
받은 뒤에는 `fetch_intro.py` 로 새 가게의 소개정보(영업시간 원문)를 받고 `rebuild.py` 를 다시 돈다.

사용법
    python scripts/dining/fetch_list_ldong.py --dry-run      몇 곳이 새로 나오는지만 본다(파일을 쓰지 않는다)
    python scripts/dining/fetch_list_ldong.py
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_intro as fi  # noqa: E402  — 키 읽기 · 부르기 · 오류 처리를 같이 쓴다

ENDPOINT = "https://apis.data.go.kr/B551011/KorService2/areaBasedList2"
PAGE = 1000
LIST = fi.LIST
LDONG = os.path.join(fi.DATA, "tourapi_서울_음식점_목록_법정동.json")


def fetch_page(key: str, page: int, get=fi.http_get) -> tuple[list[dict], int]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({
        "serviceKey": key, "MobileOS": "ETC", "MobileApp": "acop", "_type": "json",
        "lDongRegnCd": "11", "contentTypeId": "39", "numOfRows": PAGE, "pageNo": page, "arrange": "A"})
    try:
        data = json.loads(get(url))
    except json.JSONDecodeError:
        raise fi.Stop("JSON 이 아닌 응답") from None
    header = (data.get("response") or {}).get("header") or {}
    if str(header.get("resultCode", "")) != "0000":
        raise fi.Stop(f"오류 코드 {header.get('resultCode')}: {header.get('resultMsg')}")
    body = data["response"].get("body") or {}
    items = body.get("items") or {}
    rows = items.get("item") if isinstance(items, dict) else None
    if isinstance(rows, dict):
        rows = [rows]
    return rows or [], int(body.get("totalCount") or 0)


def fetch_all(key: str, get=fi.http_get) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        rows, total = fetch_page(key, page, get)
        out += rows
        if not rows or len(out) >= total:
            return out
        page += 1
        time.sleep(fi.PAUSE)


def merge(old: list[dict], fresh: list[dict]) -> tuple[list[dict], list[dict]]:
    """(합친 목록, 새로 붙은 행). 기존 행은 그대로 두고 없는 contentid 만 뒤에 붙인다."""
    known = {str(r["contentid"]) for r in old}
    added = [r for r in fresh if str(r["contentid"]) not in known]
    return old + added, added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    key = fi.service_key()
    if not key:
        sys.exit("관광공사 키가 없다(ACOP_TOUR_API_KEY)")
    try:
        fresh = fetch_all(key)
    except fi.Stop as exc:
        sys.exit(f"멈춤: {exc}")
    old = fi.load(LIST)
    merged, added = merge(old, fresh)
    gone = {str(r["contentid"]) for r in old} - {str(r["contentid"]) for r in fresh}
    print(f"법정동으로 받은 곳 {len(fresh)} · 기존 목록 {len(old)} · 새로 붙는 곳 {len(added)} · 기존에만 있는 곳 {len(gone)} → 합친 목록 {len(merged)}")
    if args.dry_run:
        return
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup = os.path.join(fi.DATA, "_backup", f"{stamp}_목록_법정동_전")
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(LIST, backup)
    with open(LDONG, "w", encoding="utf-8") as f:
        json.dump(fresh, f, ensure_ascii=False, indent=1)
    with open(LIST, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    print(f"백업 {backup}\n쓴 파일 {LDONG}\n쓴 파일 {LIST}")


if __name__ == "__main__":
    main()
