# -*- coding: utf-8 -*-
"""업체 예약 **변경 링크** — 예약 건별 토큰·주소와 그 화면이 담는 세 값 (v11 §12 DoD-16·17).

★**왜 링크인가.** 업체 예약은 우리가 바꾸지 않는다(v11 §4-C). 감지해서 우리 일정 버전은
  먼저 고쳐 두고, **업체 쪽 건은 고객이 직접 진행하도록 넘긴다.** 그 인계를 빈손으로 하지
  않으려고 「바꿀 항목 · 대안 · 차액」을 한 장에 정리해 주는 것이 이 링크다. 계획서 v11 §4-C
  통지 예시의 마지막 문장이 이것이다 — "항공권 변경은 아래 링크에서 진행해 주세요."

★**승인이 필요 없다.** 이 경로는 아무것도 쓰지 않는다 — 토큰은 비밀 키로 계산하고, 화면은
  DB 를 **읽기만** 한다. 공급자 원장(`supplier_bookings`)에는 SELECT 도 상태 표시용 한 번뿐이라
  등급 게이트(`booking_actions.require_simulated_tier`)의 대상이 아니다. 승인이 필요한 것은
  우리 예약을 `change_requested` 로 옮기는 **기록** 쪽이고 그건 `booking_actions.BookingChange`다.

★**모양은 계획서 링크(`plan_link.py`)를 본떴다** — 로그인 없음 · 여행별이 아니라 **예약별**
  HMAC 토큰 · 토큰이 틀리면 404(있는지도 말하지 않는다) · 토큰을 **저장하지 않는다**.

★★**차액을 지어내지 않는다**(v11 결정 15 · 근거 없는 문장 금지). 아래 「어디서 값을 얻나」에
  적은 자리에 값이 없으면 `difference_krw = None` 으로 두고 **무엇을 몰라서인지**를 함께 낸다.
  화면은 그 자리에 「확인되지 않았습니다」와 이유를 적는다. 0원으로도, 추정으로도 채우지 않는다.
  ☆같은 판단을 `replan.py:135` 가 이미 한다 — 가격을 모르면 `extra_cost_krw=None` + 사유.

어디서 값을 얻나
----------------
=========================  ==========================================================
바꿀 항목                  `bookings`(booking_no·kind·status·starts_at·party_size·
                           amount_cents) + `places.name`. 공급자 쪽 이름·참조는
                           `supplier_bookings`(supplier·supplier_ref·status)
대안                       이 예약에 걸린 **일정 항목의 `detail.alternates`** — 감시
                           루프가 재계획할 때 들고 둔 「다른 안」(`replan.alternate_record`).
                           ①1차 소스: `itinerary_items.booking_id` 가 이 예약을 가리키는 항목
                           ②대체 소스: 같은 장소(`bookings.place_id`)를 쓰는 최신 버전 항목
                           ★둘 다 없으면 **대안 0건**이다. 후보를 새로 계산하지 않는다 —
                             고객이 계획서에서 본 것과 다른 안이 여기 뜨면 안 된다
차액                       양쪽 **1인 가격**(`places.attributes.price_krw`)의 차 × 인원.
                           같은 소스끼리 비교한다 — 실제 결제액(`amount_cents`)과 카탈로그
                           가격을 섞어 빼면 무엇을 뺀 수인지 아무도 모른다. 결제액은
                           **따로** 「지금 결제된 금액」으로 보인다
=========================  ==========================================================
"""
from __future__ import annotations

import hashlib
import hmac
import html
from typing import Any
from uuid import UUID

from app.core import settings as settings_module

#: 화면에 이름을 그대로 내보내지 않는 내부 어휘(계획서 링크의 `_REASON_LABELS` 와 같은 이유).
_KIND_LABELS = {"activity": "활동", "dining": "식사", "mobility": "이동",
                "lodging": "숙소", "flight": "항공"}
_STATUS_LABELS = {"requested": "요청됨", "confirmed": "확정", "changed": "변경됨",
                  "change_requested": "변경 요청됨", "cancelled": "취소됨"}


def change_token(tenant_id: str, booking_id: UUID | str) -> str:
    """예약 한 건의 변경 링크 토큰. ★저장하지 않는다 — 맞춰 볼 때 다시 계산한다.

    ★`plan:` 과 다른 접두(`booking-change:`)를 쓴다. 같은 비밀 키에서 나오므로 접두가 같으면
      계획서 토큰으로 예약 화면이 열릴 수 있다.
    """
    secret = settings_module.get_settings().secret_key.encode()
    message = f"booking-change:{tenant_id}:{booking_id}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:32]


def change_url(tenant_id: str, booking_id: UUID | str) -> str:
    base = settings_module.get_settings().public_base_url.rstrip("/")
    return f"{base}/booking-change/{booking_id}?t={change_token(tenant_id, booking_id)}"


def _price_krw(attributes: Any) -> int | None:
    """1인 가격(원). ★없거나 숫자가 아니면 **모름**이다 — 0으로 읽지 않는다."""
    value = (attributes or {}).get("price_krw") if isinstance(attributes, dict) else None
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _booking_row(conn, *, tenant_id: str, booking_id: UUID | str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT b.booking_no, b.kind, b.status, b.starts_at, b.party_size, b.amount_cents, "
            "b.locked, b.place_id, p.name, p.attributes "
            "FROM bookings b LEFT JOIN places p ON p.place_id = b.place_id "
            "AND p.tenant_id = b.tenant_id WHERE b.tenant_id=%s AND b.booking_id=%s",
            (tenant_id, booking_id))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("booking_no", "kind", "status", "starts_at", "party_size", "amount_cents",
                     "locked", "place_id", "place_name", "place_attributes"), row))


def _supplier_row(conn, *, tenant_id: str, booking_id: UUID | str) -> dict[str, Any] | None:
    """공급자 쪽 이름·참조·상태. ★**읽기만** 한다 — 이 파일은 원장을 한 글자도 바꾸지 않는다."""
    with conn.cursor() as cur:
        cur.execute("SELECT supplier, supplier_ref, status FROM supplier_bookings "
                    "WHERE tenant_id=%s AND booking_id=%s", (tenant_id, booking_id))
        row = cur.fetchone()
    return None if row is None else dict(zip(("supplier", "supplier_ref", "status"), row))


def _item_row(conn, *, tenant_id: str, booking_id: UUID | str,
              place_id: Any) -> tuple[dict[str, Any] | None, str]:
    """이 예약에 걸린 **최신 버전** 일정 항목과 그것을 어떻게 찾았는지.

    ★1차 소스는 선언된 연결(`itinerary_items.booking_id`)이고, 대체 소스는 같은 장소다
      (결정 15 — 필요한 값마다 대체 소스를 둔다). 둘 다 못 찾으면 `(None, "none")` 이고
      화면은 「들고 있는 대안이 없다」고 적는다 — 후보를 새로 계산하지 않는다.
    """
    select = ("SELECT i.item_id, i.seq, i.title, i.starts_at, i.ends_at, i.detail, t.party_size, "
              "t.trip_id FROM itinerary_items i JOIN trips t ON t.tenant_id = i.tenant_id "
              "AND t.trip_id = i.trip_id AND t.latest_version = i.version "
              "WHERE i.tenant_id=%s AND ")
    columns = ("item_id", "seq", "title", "starts_at", "ends_at", "detail", "party_size", "trip_id")
    with conn.cursor() as cur:
        cur.execute(select + "i.booking_id=%s ORDER BY i.seq LIMIT 1", (tenant_id, booking_id))
        row = cur.fetchone()
        if row is not None:
            return dict(zip(columns, row)), "item_booking_id"
        if place_id is None:
            return None, "none"
        cur.execute(select + "i.place_id=%s ORDER BY i.seq LIMIT 1", (tenant_id, place_id))
        row = cur.fetchone()
    return (dict(zip(columns, row)), "item_place") if row is not None else (None, "none")


def _alternative_prices(conn, *, tenant_id: str, place_ids: list[str]) -> dict[str, int | None]:
    if not place_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute("SELECT place_id, attributes FROM places WHERE tenant_id=%s "
                    "AND place_id = ANY(%s)", (tenant_id, place_ids))
        return {str(place_id): _price_krw(attributes) for place_id, attributes in cur.fetchall()}


def change_view(conn, *, tenant_id: str, booking_id: UUID | str) -> dict[str, Any] | None:
    """변경 링크 화면이 담는 것 — **바꿀 항목 · 대안 · 차액**(DoD-17). 예약이 없으면 `None`.

    ★고객 id 를 싣지 않는다. 링크를 받은 사람에게 내부 id 를 보이지 않는다(계획서 링크와 같다).
    """
    booking = _booking_row(conn, tenant_id=tenant_id, booking_id=booking_id)
    if booking is None:
        return None
    supplier = _supplier_row(conn, tenant_id=tenant_id, booking_id=booking_id)
    item, source = _item_row(conn, tenant_id=tenant_id, booking_id=booking_id,
                             place_id=booking["place_id"])

    base_price = _price_krw(booking["place_attributes"])
    # ★인원은 예약의 것을 먼저 쓴다 — 여행 전체 인원과 다를 수 있다(한 활동만 두 명).
    heads = booking["party_size"] or (item or {}).get("party_size")
    records = list(((item or {}).get("detail") or {}).get("alternates") or [])
    prices = _alternative_prices(
        conn, tenant_id=tenant_id,
        place_ids=[str(r["place_id"]) for r in records if r.get("place_id")])

    alternatives = []
    for record in records:
        place_id = str(record["place_id"]) if record.get("place_id") else None
        alt_price = prices.get(place_id) if place_id else None
        difference: int | None = None
        unknown: str | None = None
        if base_price is None and alt_price is None:
            unknown = "지금 예약한 곳과 대안 모두 1인 가격이 확인되지 않았습니다"
        elif base_price is None:
            unknown = "지금 예약한 곳의 1인 가격이 확인되지 않았습니다"
        elif alt_price is None:
            unknown = "대안의 1인 가격이 확인되지 않았습니다"
        else:
            difference = (alt_price - base_price) * (heads or 1)
        alternatives.append({
            "key": record.get("key"), "name": record.get("option_label") or record.get("name"),
            "starts_at": record.get("starts_at"), "ends_at": record.get("ends_at"),
            "walk_min": record.get("walk_min"),
            "price_krw": alt_price,
            "difference_krw": difference,
            "difference_unknown": unknown,
        })

    return {
        "booking_no": booking["booking_no"],
        "kind": booking["kind"],
        "kind_label": _KIND_LABELS.get(booking["kind"], booking["kind"]),
        "status": booking["status"],
        "status_label": _STATUS_LABELS.get(booking["status"], booking["status"]),
        "starts_at": booking["starts_at"].isoformat() if booking["starts_at"] else None,
        "party_size": booking["party_size"],
        # ★`amount_cents` 는 원의 100배다(`verification_policy.py:49` 의 scale=100).
        "paid_krw": None if booking["amount_cents"] is None else booking["amount_cents"] // 100,
        "place": booking["place_name"],
        "price_krw": base_price,
        "supplier": supplier,
        "item": None if item is None else {
            "title": item["title"], "seq": item["seq"],
            "starts_at": item["starts_at"].isoformat() if item["starts_at"] else None,
            "ends_at": item["ends_at"].isoformat() if item["ends_at"] else None},
        "alternatives": alternatives,
        "alternatives_source": source,
        "heads": heads,
        # ★분모를 화면에 적는다 — 이 수가 무엇을 무엇으로 뺀 것인지 보이게(RULE.md §1.4).
        "difference_basis": ("1인 가격 차 × 인원 " + str(heads) + "명" if heads
                             else "1인 가격 차(인원이 확인되지 않아 1명 기준)"),
        "changeable_by": "supplier",     # ★우리가 바꾸지 않는다. 업체에서 진행한다
    }


def _won(amount: int) -> str:
    return f"{amount:,}원"


def _signed(amount: int) -> str:
    if amount == 0:
        return "차액 없음"
    return ("+" if amount > 0 else "−") + _won(abs(amount))


def render_change(view: dict[str, Any]) -> str:
    """변경 링크 화면. ★값이 없는 자리는 **비우지 않고** 「확인되지 않았습니다」라고 적는다."""
    esc = lambda value: html.escape(str(value or ""))       # noqa: E731
    unknown = '<span class="unknown">확인되지 않았습니다</span>'

    def when(starts: str | None, ends: str | None) -> str:
        if not starts:
            return unknown
        return esc(starts[:16].replace("T", " ")) + (f"–{esc(ends[11:16])}" if ends else "")

    facts = [("예약 번호", esc(view["booking_no"])),
             ("종류", esc(view["kind_label"])),
             ("현재 상태", esc(view["status_label"])),
             ("현재 시각", when(view["starts_at"], None)),
             ("장소", esc(view["place"]) if view["place"] else unknown),
             ("인원", f"{view['party_size']}명" if view["party_size"] else unknown),
             ("지금 결제된 금액", _won(view["paid_krw"]) if view["paid_krw"] is not None else unknown)]
    if view["supplier"]:
        facts.append(("업체", esc(view["supplier"]["supplier"])
                      + f' · 예약번호 {esc(view["supplier"]["supplier_ref"])}'))
    else:
        facts.append(("업체", unknown))
    if view["item"]:
        facts.append(("일정 항목", esc(view["item"]["title"]) + " · "
                      + when(view["item"]["starts_at"], view["item"]["ends_at"])))

    rows = "".join(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in facts)

    if view["alternatives"]:
        options = "".join(
            f'<li><div class="name">{esc(alt["name"])}</div>'
            f'<div class="when">{when(alt["starts_at"], alt["ends_at"])}</div>'
            + (f'<div class="diff">차액 {_signed(alt["difference_krw"])}'
               f'<span class="basis"> · {esc(view["difference_basis"])}</span></div>'
               if alt["difference_krw"] is not None else
               f'<div class="diff">차액 <span class="unknown">확인되지 않았습니다</span>'
               f'<span class="basis"> · {esc(alt["difference_unknown"])}</span></div>')
            + "</li>"
            for alt in view["alternatives"])
        options = f'<ul class="opts">{options}</ul>'
    else:
        options = ('<p class="unknown">지금 들고 있는 대안이 없습니다. '
                   '업체에 가능한 시간을 문의해 주세요.</p>')

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>예약 변경 — {esc(view['booking_no'])}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e1d8;--accent:#2f6f4f;--warn:#9a5b1f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161614;--fg:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7cc4a0;--warn:#d9a463}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:40rem;margin:0 auto;padding:1.25rem}}
h1{{font-size:1.3rem;margin:.2rem 0}} h2{{font-size:1rem;margin-top:1.5rem}}
.meta{{color:var(--muted);font-size:.85rem}}
table{{width:100%;border-collapse:collapse;margin:.75rem 0}}
th,td{{text-align:left;padding:.45rem .2rem;border-bottom:1px solid var(--line);vertical-align:top}}
th{{width:9rem;color:var(--muted);font-weight:400}}
ul.opts{{list-style:none;padding:0;margin:.5rem 0}}
.opts li{{padding:.6rem 0;border-bottom:1px solid var(--line)}}
.name{{font-weight:600}} .when,.basis{{color:var(--muted);font-size:.85rem}}
.diff{{color:var(--accent)}} .unknown{{color:var(--warn)}}
.note{{margin-top:1.5rem;padding:.75rem;border:1px solid var(--line);border-radius:.4rem;
      color:var(--muted);font-size:.9rem}}
</style></head><body><main>
<h1>예약 변경 안내</h1>
<div class="meta">이 예약은 업체에서 직접 변경해 주세요 — 저희가 대신 바꾸지 않습니다</div>
<h2>바뀔 항목</h2>
<table>{rows}</table>
<h2>대안</h2>
{options}
<p class="note">여행 일정 쪽은 이미 맞춰 두었습니다. 여기 적힌 차액은 장소의 1인 가격으로 계산한
것이며, 업체가 청구하는 변경 수수료는 포함하지 않습니다 — 알아내지 못한 값은 지어내지 않고
모른다고 적습니다.</p>
</main></body></html>"""


__all__ = ["change_token", "change_url", "change_view", "render_change"]
