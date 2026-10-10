# -*- coding: utf-8 -*-
"""SerpApi Google Hotels 를 한국 설정(gl=kr · hl=ko · KRW)으로 한 번 불러, 무엇이 오는지 본다. `[2026-10-10]`

- 키: ACOP_SERPAPI_API_KEY(환경변수 또는 `.env.apikeys`). 출력하지 않는다. 한 번 = 1회(무료 월 250회), `--detail` 은 1회 더.
- 응답 원문은 저장하지 않는다. 항목 이름 · 개수 · 앞의 몇 곳만 출력한다.

실행 위치: final_project_cs
  python -m scripts.probe_serpapi_hotels 서울 명동 2026-11-06 2026-11-09 --adults 2
  python -m scripts.probe_serpapi_hotels "롯데호텔 서울" 2026-11-06 2026-11-09 --detail    # 첫 곳의 판매처별 가격(1회 더)
"""
from argparse import ArgumentParser
from datetime import datetime
import platform
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from scripts.probe_serpapi_flights import URL, load_key


def call(params, key):
    started = time.perf_counter()
    try:
        response = httpx.get(URL, params={**params, "api_key": key}, timeout=90)
    except httpx.HTTPError as exc:
        raise SystemExit(f"[호출] 연결 실패 · {type(exc).__name__}")
    took = time.perf_counter() - started
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code != 200 or body.get("error"):
        raise SystemExit(f"[호출] HTTP {response.status_code} · {took:.2f}초 · 오류 {str(body.get('error'))[:300]}")
    return body, took


def host(url):
    return urlsplit(str(url or "")).netloc or "없음"


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+", help="검색어(지역 · 숙소 이름) 뒤에 체크인 · 체크아웃 날짜")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--list", type=int, default=5)
    parser.add_argument("--detail", action="store_true", help="첫 곳의 property_token 으로 상세(판매처별 가격)를 한 번 더(1회 더 씀)")
    args = parser.parse_args()
    *words, check_in, check_out = args.query
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")
    key = load_key()
    base = {"engine": "google_hotels", "q": " ".join(words), "check_in_date": check_in, "check_out_date": check_out,
            "adults": args.adults, "currency": "KRW", "hl": "ko", "gl": "kr"}
    body, took = call(base, key)
    meta = body.get("search_metadata") or {}
    rows = body.get("properties") or []
    print(f"[검색] {took:.2f}초 · 상태 {meta.get('status')} · {len(rows)}곳 · 최상위 항목 {sorted(body)[:14]}")
    print(f"[검색] google_hotels_url {'있음' if meta.get('google_hotels_url') else '없음'}: {meta.get('google_hotels_url') or ''}")
    for number, row in enumerate(rows[:args.list], start=1):
        rate = row.get("rate_per_night") or {}
        total = row.get("total_rate") or {}
        gps = row.get("gps_coordinates") or {}
        print(f"  {number}. {row.get('name')} · 유형 {row.get('type')} · 1박 {rate.get('extracted_lowest')} · 전체 {total.get('extracted_lowest')} · "
              f"평점 {row.get('overall_rating')}({row.get('reviews')}) · 성급 {row.get('extracted_hotel_class')} · "
              f"좌표 {'있음' if gps else '없음'} · 링크 호스트 {host(row.get('link'))}")
        print(f"      항목 {sorted(row)}")
        if row.get("prices"):
            print(f"      prices {[(p.get('source'), (p.get('rate_per_night') or {}).get('extracted_lowest'), host(p.get('link'))) for p in row['prices'][:6]]}")
    if not args.detail:
        return
    token = next((row.get("property_token") for row in rows if row.get("property_token")), None)
    if not token:
        print("[상세] property_token 없음")
        return
    body, took = call({**base, "property_token": token}, key)
    prices = body.get("prices") or []
    featured = body.get("featured_prices") or []
    print(f"[상세] {took:.2f}초 · {body.get('name')} · prices {len(prices)}개 · featured_prices {len(featured)}개 · 최상위 항목 {sorted(body)[:20]}")
    for item in [*featured, *prices][:12]:
        rate = item.get("rate_per_night") or {}
        print(f"  · {item.get('source')} · 1박 {rate.get('extracted_lowest')} · 공식 {item.get('official')} · 링크 호스트 {host(item.get('link'))}")


if __name__ == "__main__":
    main()
