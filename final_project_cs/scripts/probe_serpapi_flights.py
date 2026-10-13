# -*- coding: utf-8 -*-
"""SerpApi Google Flights 를 한국 설정(gl=kr · hl=ko · KRW)으로 한 번 불러, 무엇이 오는지 본다. `[2026-10-09]`

- 키: 환경변수 또는 `.env.apikeys`(커밋 안 함)의 ACOP_SERPAPI_API_KEY. 키는 주소의 api_key 로 가지만 **출력하지 않는다**.
- 무료는 월 250회다. 이 스크립트 한 번 = 1회, `--booking` 을 주면 1회 더(판매처 목록).
- 응답 원문은 저장하지 않는다. 항목 이름 · 개수 · 앞의 몇 편만 출력한다.

실행 위치: final_project_cs
  python -m scripts.probe_serpapi_flights ICN NRT 2026-10-20
  python -m scripts.probe_serpapi_flights GMP CJU 2026-10-20 --list 5
  python -m scripts.probe_serpapi_flights ICN NRT 2026-10-20 --booking     # 첫 편의 판매처 목록까지(2회)
"""
from argparse import ArgumentParser
from datetime import datetime
import os
from pathlib import Path
import platform
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

URL = "https://serpapi.com/search.json"
KEY_NAME = "ACOP_SERPAPI_API_KEY"
KEY_FILE = Path(__file__).resolve().parents[1] / ".env.apikeys"


def load_key():
    """환경변수 → .env.apikeys. 값은 출력하지 않는다."""
    value = os.environ.get(KEY_NAME, "").strip()
    if not value and KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            name, sep, raw = line.partition("=")
            if sep and name.strip() == KEY_NAME:
                value = raw.strip().strip('"')
    if not value:
        raise SystemExit(f"{KEY_NAME} 가 비어 있습니다(.env.apikeys 확인)")
    return value


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


def leg_text(segments):
    first, last = segments[0], segments[-1]
    numbers = "/".join(str(seg.get("flight_number") or "?").replace(" ", "") for seg in segments)
    return (f"{(first.get('departure_airport') or {}).get('id')} {(first.get('departure_airport') or {}).get('time')} → "
            f"{(last.get('arrival_airport') or {}).get('id')} {(last.get('arrival_airport') or {}).get('time')} {numbers}")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("destination")
    parser.add_argument("date", help="YYYY-MM-DD")
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--list", type=int, default=3, help="앞에서 몇 편을 출력할지")
    parser.add_argument("--booking", action="store_true", help="첫 편의 booking_token 으로 판매처 목록을 한 번 더 부른다(1회 더 씀)")
    args = parser.parse_args()
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")
    key = load_key()
    base = {"engine": "google_flights", "departure_id": args.origin.upper(), "arrival_id": args.destination.upper(),
            "outbound_date": args.date, "type": 2, "adults": args.adults, "currency": "KRW", "hl": "ko", "gl": "kr"}
    body, took = call(base, key)
    meta = body.get("search_metadata") or {}
    best, other = body.get("best_flights") or [], body.get("other_flights") or []
    print(f"[검색] {took:.2f}초 · 상태 {meta.get('status')} · 서버 처리 {meta.get('total_time_taken')}초 · "
          f"best {len(best)}개 · other {len(other)}개 · 최상위 항목 {sorted(body)[:14]}")
    print(f"[검색] google_flights_url {'있음' if meta.get('google_flights_url') else '없음'}: {meta.get('google_flights_url') or ''}")
    insights = body.get("price_insights") or {}
    if insights:
        print(f"[가격 참고] 최저 {insights.get('lowest_price')} · 수준 {insights.get('price_level')} · 보통 범위 {insights.get('typical_price_range')}")
    rows = [*best, *other]
    for number, row in enumerate(rows[:args.list], start=1):
        segments = row.get("flights") or []
        if not segments:
            continue
        print(f"  {number}. {segments[0].get('airline')} · {leg_text(segments)} · 총 {row.get('total_duration')}분 · "
              f"경유 {len(segments) - 1} · 가격 {row.get('price')} · 항목 {sorted(row)}")
        sold_by = [seg.get("ticket_also_sold_by") for seg in segments if seg.get("ticket_also_sold_by")]
        if sold_by:
            print(f"      ticket_also_sold_by {sold_by}")
    if not args.booking:
        return
    token = next((row.get("booking_token") for row in rows if row.get("booking_token")), None)
    if not token:
        print("[판매처] 결과에 booking_token 이 없습니다 — 판매처 목록을 부를 수 없음")
        return
    body, took = call({**base, "booking_token": token}, key)
    options = body.get("booking_options") or []
    print(f"[판매처] {took:.2f}초 · {len(options)}개 · 최상위 항목 {sorted(body)[:14]}")
    for option in options[:15]:
        part = option.get("together") or option.get("departing") or option
        request = part.get("booking_request") or {}
        host = urlsplit(str(request.get("url") or "")).netloc
        print(f"  · {part.get('book_with')} · 가격 {part.get('price')} · 항공사 판매 {part.get('airline')} · "
              f"booking_request 항목 {sorted(request)} · 주소 호스트 {host or '없음'} · post_data {'있음' if request.get('post_data') else '없음'}")


if __name__ == "__main__":
    main()
