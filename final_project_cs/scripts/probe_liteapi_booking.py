"""LiteAPI 샌드박스 숙소 예약 한 바퀴: 요금 → 가예약(prebook) → 예약(book) → 취소.

키는 환경변수나 `.env.apikeys`(커밋 안 함)의 ACOP_LITEAPI_API_KEY, 없으면 실행 중 입력.
샌드박스 키(sand_)가 아니면 멈춘다.
응답은 저장하지 않고 숫자·상태만 출력한다.

    python -m scripts.probe_liteapi_booking
    python -m scripts.probe_liteapi_booking --no-book      # 가예약까지만
    python -m scripts.probe_liteapi_booking --keep         # 예약 후 취소하지 않음
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

API = "https://api.liteapi.travel/v3.0"
BOOK = "https://book.liteapi.travel/v3.0"


def call(method: str, url: str, key: str, body: dict | None = None, timeout: float = 30.0) -> tuple[int, dict, float]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-API-Key", key)
    req.add_header("accept", "application/json")
    if data is not None:
        req.add_header("content-type", "application/json")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    elapsed = time.perf_counter() - started
    try:
        payload = json.loads(raw) if raw else {}
    except ValueError:
        payload = {}
    return status, payload, elapsed


def error_text(payload: dict) -> str:
    err = payload.get("error")
    if isinstance(err, dict):
        return f"{err.get('code')} {err.get('message') or err.get('description') or ''}".strip()
    return str(err or "")[:200]


KEY_NAME = "ACOP_LITEAPI_API_KEY"
KEY_FILE = Path(__file__).resolve().parents[1] / ".env.apikeys"


def load_key() -> str:
    """환경변수 → `.env.apikeys` → 입력 순. 값은 출력하지 않는다."""
    value = os.environ.get(KEY_NAME, "").strip()
    if value:
        print(f"키: 환경변수 {KEY_NAME}")
        return value
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            name, sep, raw = line.partition("=")
            if sep and name.strip() == KEY_NAME and raw.strip().strip('"'):
                print(f"키: {KEY_FILE.name} 의 {KEY_NAME}")
                return raw.strip().strip('"')
    return getpass.getpass("LiteAPI 샌드박스 키(입력은 보이지 않음): ").strip()


def stamp(label: str) -> None:
    print(f"\n[{label}] {datetime.now():%Y-%m-%d %H:%M:%S}")


def pick_offer(hotels: list[dict]) -> tuple[dict, dict, dict] | None:
    """환불 가능(RFN) 중 가장 싼 offer, 없으면 전체 중 가장 싼 offer."""
    best: tuple[float, bool, dict, dict, dict] | None = None
    for hotel in hotels:
        for room in hotel.get("roomTypes") or []:
            rates = room.get("rates") or []
            if not room.get("offerId") or not rates:
                continue
            amount = (room.get("offerRetailRate") or {}).get("amount")
            if not isinstance(amount, (int, float)):
                continue
            refundable = all((r.get("cancellationPolicies") or {}).get("refundableTag") == "RFN" for r in rates)
            rank = (not refundable, float(amount))
            if best is None or rank < (best[1], best[0]):
                best = (float(amount), not refundable, hotel, room, rates[0])
    if best is None:
        return None
    return best[2], best[3], best[4]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkin", default="2026-11-06")
    ap.add_argument("--checkout", default="2026-11-09")
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--nationality", default="KR")
    ap.add_argument("--lat", type=float, default=37.5663, help="기본: 서울시청")
    ap.add_argument("--lng", type=float, default=126.9779)
    ap.add_argument("--radius", type=int, default=3000, help="미터")
    ap.add_argument("--rates-timeout", type=int, default=6)
    ap.add_argument("--no-book", action="store_true")
    ap.add_argument("--keep", action="store_true", help="예약 후 취소하지 않음")
    args = ap.parse_args()

    key = load_key()
    if not key.startswith("sand_"):
        print("샌드박스 키(sand_)가 아니라서 멈춥니다.")
        return 2

    print(f"기기 {socket.gethostname()} · 조건 {args.checkin}~{args.checkout} 성인 {args.adults} 국적 {args.nationality} "
          f"· 중심 {args.lat},{args.lng} 반경 {args.radius}m")

    # 1. 요금
    stamp("요금")
    status, payload, sec = call("POST", f"{API}/hotels/rates", key, {
        "latitude": args.lat, "longitude": args.lng, "radius": args.radius,
        "occupancies": [{"adults": args.adults}],
        "currency": "KRW", "guestNationality": args.nationality,
        "checkin": args.checkin, "checkout": args.checkout,
        "timeout": args.rates_timeout,
    }, timeout=args.rates_timeout + 20)
    hotels = payload.get("data") or []
    print(f"HTTP {status} · {sec:.2f}초 · 요금 온 숙소 {len(hotels)}곳")
    if status != 200 or not hotels:
        print("오류:", error_text(payload))
        return 1
    picked = pick_offer(hotels)
    if picked is None:
        print("고를 수 있는 offer 없음")
        return 1
    hotel, room, rate = picked
    offer_amount = (room.get("offerRetailRate") or {}).get("amount")
    print(f"고른 것: 숙소 {hotel.get('hotelId')} · 객실 '{rate.get('name')}' · "
          f"{(rate.get('cancellationPolicies') or {}).get('refundableTag')} · {rate.get('boardName')} · {offer_amount}")

    # 2. 가예약
    stamp("가예약")
    status, payload, sec = call("POST", f"{BOOK}/rates/prebook", key,
                                {"offerId": room["offerId"], "usePaymentSdk": False})
    pre = payload.get("data") or {}
    print(f"HTTP {status} · {sec:.2f}초")
    if status != 200 or not pre.get("prebookId"):
        print("오류:", error_text(payload))
        return 1
    print(f"prebookId 있음 · 가격 {pre.get('price')} {pre.get('currency')} · 차이 {pre.get('priceDifferencePercent')}% "
          f"· 취소조건 변경 {pre.get('cancellationChanged')} · 식사 변경 {pre.get('boardChanged')} "
          f"· 결제 방식 {pre.get('paymentTypes')}")
    if args.no_book:
        return 0

    # 3. 예약 (가짜 투숙객, 시험 결제)
    stamp("예약")
    person = {"firstName": "Test", "lastName": "Guest", "email": "test.guest@example.com"}
    status, payload, sec = call("POST", f"{BOOK}/rates/book", key, {
        "prebookId": pre["prebookId"],
        "clientReference": f"probe-{uuid.uuid4().hex[:12]}",
        "holder": {**person, "phone": "+821000000000"},
        "guests": [{"occupancyNumber": 1, **person}],
        "payment": {"method": "ACC_CREDIT_CARD"},
    }, timeout=60)
    booked = payload.get("data") or {}
    print(f"HTTP {status} · {sec:.2f}초 · sandbox={payload.get('sandbox')}")
    if status != 200 or not booked.get("bookingId"):
        print("오류:", error_text(payload))
        return 1
    print(f"bookingId 있음 · 상태 {booked.get('status')} · 가격 {booked.get('price')} {booked.get('currency')} "
          f"· 숙소 확인번호 {'있음' if booked.get('hotelConfirmationCode') else '없음'} "
          f"· 무료취소 기한 {booked.get('lastFreeCancellationDate')}")
    if args.keep:
        return 0

    # 4. 취소
    stamp("취소")
    status, payload, sec = call("PUT", f"{BOOK}/bookings/{booked['bookingId']}", key, timeout=30)
    data = payload.get("data") or {}
    print(f"HTTP {status} · {sec:.2f}초 · 상태 {data.get('status')} · 취소 수수료 {data.get('cancellation_fee')} "
          f"· 환불 {data.get('refund_amount')} {data.get('currency')}")
    if status != 200:
        print("오류:", error_text(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
