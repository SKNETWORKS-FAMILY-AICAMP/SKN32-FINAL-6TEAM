"""LiteAPI 샌드박스 항공: 검색 → 확인(verify) → 가예약(prebook) → 예약(book) → 취소.

단계마다 옵션으로 켠다. 기본은 검색 + 확인까지.

    python -m scripts.probe_liteapi_flight                      # 검색 + 확인
    python -m scripts.probe_liteapi_flight --prebook            # + 가예약 (가짜 승객)
    python -m scripts.probe_liteapi_flight --prebook --book     # + 예약(시험 결제) + 취소
    python -m scripts.probe_liteapi_flight --origin NRT --dest ICN

키·출력 원칙은 probe_liteapi_booking 과 같다(키 값 출력 안 함, 응답 저장 안 함).
"""

from __future__ import annotations

import argparse
import socket
import sys
from collections import Counter

from scripts.probe_liteapi_booking import API, call, error_text, load_key, stamp


def detail(payload: dict) -> str:
    err = payload.get("error")
    text = error_text(payload)
    if isinstance(err, dict) and err.get("key"):
        text += f" (key={err.get('key')})"
    return text


def offer_rows(data: list[dict]) -> list[tuple[float, dict, dict]]:
    rows = []
    for item in data:
        for journey in item.get("journeys") or []:
            for offer in journey.get("offers") or []:
                total = ((offer.get("pricing") or {}).get("display") or {}).get("total")
                if isinstance(total, (int, float)) and offer.get("offerId"):
                    rows.append((float(total), journey, offer))
    rows.sort(key=lambda r: r[0])
    return rows


def provider_of(offer: dict) -> str:
    """응답의 provider 모양을 아직 모른다 — code/name 이 없으면 키 이름만 보여 준다."""
    prov = offer.get("provider")
    if isinstance(prov, dict):
        return str(prov.get("code") or prov.get("name") or f"키:{','.join(sorted(prov))}")
    return str(prov) if prov else "없음"


def describe(journey: dict) -> str:
    parts = []
    for seg in journey.get("segments") or []:
        carrier = (seg.get("carrier") or {}).get("marketingCode") or "?"
        number = (seg.get("flight") or {}).get("marketingNumber") or "?"
        parts.append(f"{carrier}{number} {seg.get('originCode')}→{seg.get('destinationCode')} "
                     f"{seg.get('departureTime')}~{seg.get('arrivalTime')}")
    return " / ".join(parts) or "구간 없음"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="ICN")
    ap.add_argument("--dest", default="NRT")
    ap.add_argument("--date", default="2026-11-06")
    ap.add_argument("--return-date", default="", help="비우면 편도")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--prebook", action="store_true")
    ap.add_argument("--book", action="store_true", help="--prebook 과 함께. 예약 후 바로 취소")
    ap.add_argument("--keep", action="store_true", help="예약 후 취소하지 않음")
    args = ap.parse_args()

    key = load_key()
    if not key.startswith("sand_"):
        print("샌드박스 키(sand_)가 아니라서 멈춥니다.")
        return 2

    legs = [{"origin": args.origin, "destination": args.dest, "date": args.date, "direction": "OUTBOUND"}]
    if args.return_date:
        legs.append({"origin": args.dest, "destination": args.origin, "date": args.return_date, "direction": "INBOUND"})
    print(f"기기 {socket.gethostname()} · {args.origin}→{args.dest} {args.date}"
          f"{' 왕복 ' + args.return_date if args.return_date else ' 편도'} · 성인 {args.adults}")

    # 1. 검색
    stamp("검색")
    status, payload, sec = call("POST", f"{API}/flights/rates", key, {
        "legs": legs, "adults": args.adults, "children": 0, "infants": 0,
        "currency": "KRW", "country": "KR",
        "sort": {"sortBy": "price", "sortOrder": "asc"},
    }, timeout=60)
    data = payload.get("data") or []
    rows = offer_rows(data)
    print(f"HTTP {status} · {sec:.2f}초 · 여정 {sum(len(d.get('journeys') or []) for d in data)}개 · offer {len(rows)}개")
    if status != 200 or not rows:
        print("오류:", detail(payload))
        return 1
    providers = Counter(provider_of(o) for _, _, o in rows)
    print("공급자별 offer:", dict(providers.most_common()))
    total, journey, offer = rows[0]
    print(f"최저가: {total:,.0f} · 공급자 {provider_of(offer)} · {describe(journey)}")

    # 2. 확인
    stamp("확인")
    status, payload, sec = call("POST", f"{API}/flights/verify", key, {"offerId": offer["offerId"]}, timeout=60)
    items = payload.get("data") or []
    print(f"HTTP {status} · {sec:.2f}초")
    if status != 200 or not items:
        print("오류:", detail(payload))
        return 1
    verified = items[0]
    display = ((verified.get("journey") or {}).get("pricing") or {}).get("display") or {}
    changes = verified.get("changes") or {}
    print(f"확인 가격 {display.get('total')} {display.get('currency')} · 가격 바뀜 {changes.get('priceChanged')} "
          f"· 만료 {(verified.get('journey') or {}).get('expiration')}")
    if not args.prebook:
        return 0

    # 3. 가예약 (가짜 승객)
    stamp("가예약")
    person = {"firstName": "Test", "lastName": "Guest"}
    # 가짜 여권 — 문서 예시 형식(documentType "passport", 번호 9자리, 만료 YYYY-MM-DD)
    passengers = [{**person, "birthday": "1990-01-01", "gender": "M", "nationality": "KR", "passengerType": 0,
                   "documentType": "passport", "documentNumber": f"M0000000{i}", "documentIssueCountry": "KR",
                   "documentExpiry": "2032-01-01"}
                  for i in range(args.adults)]
    status, payload, sec = call("POST", f"{API}/flights/prebooks", key, {
        "offerId": offer["offerId"], "usePaymentSdk": False,
        "contact": {**person, "email": "test.guest@example.com", "phoneNumber": "1000000000", "phoneCountryCode": "82"},
        "passengers": passengers,
    }, timeout=90)
    items = payload.get("data") or []
    print(f"HTTP {status} · {sec:.2f}초")
    if status != 200 or not items or not items[0].get("prebookId"):
        print("오류:", detail(payload))
        return 1
    pre = items[0]
    print(f"prebookId 있음 · 가격 {pre.get('price')} {pre.get('currency')} · 결제 방식 {pre.get('paymentTypes')}")
    if not args.book:
        return 0

    # 4. 예약 (시험 결제)
    stamp("예약")
    status, payload, sec = call("POST", f"{API}/flights/bookings", key, {
        "prebookId": pre["prebookId"], "payment": {"method": "ACC_CREDIT_CARD"},
    }, timeout=120)
    items = payload.get("data") or []
    booking = (items[0].get("booking") if items else None) or {}
    print(f"HTTP {status} · {sec:.2f}초")
    if status != 200 or not booking.get("bookingId"):
        print("오류:", detail(payload))
        return 1
    airline = ((booking.get("order") or {}).get("reference") or {}).get("airlineBookings") or []
    print(f"bookingId 있음 · 상태 {booking.get('status')} · 환경 {booking.get('providerEnvironment')} "
          f"· 총액 {(booking.get('pricing') or {}).get('totalAmount')} · 항공사 PNR {'있음' if airline else '없음'}")
    if args.keep:
        return 0

    # 5. 취소
    stamp("취소")
    status, payload, sec = call("POST", f"{API}/flights/bookings/{booking['bookingId']}/cancellations", key, timeout=60)
    data = payload.get("data") or {}
    print(f"HTTP {status} · {sec:.2f}초 · 상태 {data.get('status')} · 취소 수수료 {data.get('cancellation_fee')} "
          f"· 환불 {data.get('refund_amount')} {data.get('currency')}")
    if status not in (200, 202):
        print("오류:", detail(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
