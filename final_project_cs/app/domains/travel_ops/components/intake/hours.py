# -*- coding: utf-8 -*-
"""확인 화면의 **운영시간 · 휴무일** 사실 — 읽은 장소가 그 날짜·시각에 열려 있나. `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`

★왜. 계획 읽기는 장소를 **찾기만** 했다. 운영시간 · 휴무는 등록 판정(`check_itinerary`)이 보지만 읽은 장소에는 운영시간이 안 붙어 있어
  (등록 몸통의 장소 속성에 없다 — 새벽 작업이 나중에 읽는다) 확인 화면에서는 한 번도 보이지 않았다. 목업은 장소마다
  「운영시간 · 휴무일」 검사 줄을 보여 준다 — 이 모듈이 그 사실을 **DB 에 이미 읽어 둔 값**에서 모은다.
★바깥을 부르지 않는다(관광공사 · 카카오 · 구글 호출 없음). 요청 자리는 DB 만 본다(2026-09-29 사용자 지시와 같다):
    ① 그 장소 행(`places` — 우리 장소 표 · 요식 원장에서 올린 식당) 의 속성  ② 관광공사 운영시간 표(`catalog_hours`, 새벽 작업)
    ③ 다른 여행에서 이미 읽어 둔 같은 관광공사 id 의 장소 행(14일 안)  ④ 요식 원장(`dining_state` — 식당만, 이름·150m 로 이은 곳 포함)
★모르는 것은 모른다고 돌려준다(`known=False` + 이유) — 「열려 있다」고 지어내지 않는다. 카카오로만 찾은 곳은 운영시간이 없다.
★판정은 **등록 판정과 같은 함수**(`itinerary_checks.check_itinerary`)가 한다 — 여기서는 사실만 모은다. 그래서 확인 화면의 「주의」와
  등록 때의 거절이 어긋나지 않는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

#: 다른 여행 장소 행에서 읽은 운영시간을 다시 쓰는 기간 — `catalog_pool.REUSE_DAYS` 와 같은 값
REUSE_DAYS = 14
#: 요식 원장에서 라스트오더 여유로 보는 분 — `replan.ORDER_MARGIN_MIN` 과 같은 값(탈락 기준 20분)
ORDER_MARGIN_MIN = 20
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass
class HoursFacts:
    """한 장소 · 한 날의 운영시간 사실. `attributes` 는 판정기(`check_itinerary`)가 읽는 모양(`hours_week` · `hours` · `break`)."""

    known: bool
    attributes: dict[str, Any] = field(default_factory=dict)
    source: str | None = None                  # tour_api | dining_ledger | places
    #: 요식 원장 판정 — 그 시각에 여는가(None = 모름) · 마지막 주문 여유 · 종료 임박 확인 필요
    open_at_slot: bool | None = None
    order_ok: bool | None = None
    needs_check: bool = False
    #: 모를 때 왜 모르나(화면 문장) — 「열려 있다」를 지어내지 않는다
    why_unknown: str | None = None
    #: 요일표로 펴지 않은 조건 원문(공휴일 등)
    conditions: list[str] = field(default_factory=list)


def _tenants(tenant_id: str) -> list[str]:
    """관광공사 목록 · 운영시간 표는 기본 테넌트에만 있다 — 그것도 본다(`catalog_pool._catalog_tenants` 와 같다)."""
    from app.core.settings import get_settings

    return list(dict.fromkeys([tenant_id, get_settings().tenant_id]))


def facts_for(conn, tenant_id: str, place: dict[str, Any] | None, kind: str, start: datetime | None,
              end: datetime | None) -> HoursFacts:
    """`place` = 읽은 장소 값(`{name, kind, latitude, longitude, place_id, content_id, source}`). 못 알면 `known=False` + 이유."""
    if not place:
        return HoursFacts(False, why_unknown="장소를 정하면 확인해요")
    if start is None:
        return HoursFacts(False, why_unknown="방문 시각을 알면 확인해요")
    attributes: dict[str, Any] = {}
    source: str | None = None
    core_id = str(place["place_id"]) if place.get("place_id") else None
    content_id = str(place["content_id"]) if place.get("content_id") else None
    if place.get("_hours"):
        # 후보를 모을 때 이미 읽어 붙인 운영시간(`catalog_pool.reuse_hours`) — 다시 찾지 않는다
        attributes, source = dict(place["_hours"]), "tour_api"
    elif core_id:
        attributes, row_source_id = _place_row(conn, tenant_id, core_id)
        if attributes:
            source = "places"
        content_id = content_id or row_source_id
    # ② 관광공사 운영시간 표 → ③ 다른 여행 장소 행
    if content_id and not (attributes.get("hours_week") or "hours" in attributes):
        week = _catalog_week(conn, tenant_id, content_id)
        if week:
            attributes, source = {**attributes, "hours_week": week}, "tour_api"
    out = HoursFacts(bool(attributes.get("hours_week") or "hours" in attributes), attributes, source)
    # ④ 요식 원장 — 식당만. ★`[2026-10-05]` 요식 원장이 식당의 정본이다. 그 여행의 장소 행(코어 장소)이 있으면 그 행으로(`dining_state`),
    #   아직 없으면(확인 화면 단계) 관광공사 번호 — 없으면 이름이 하나로 정해질 때 — 로 원장 가게를 바로 찾는다. 공용 장소 표에 올리지 않는다
    if kind == "dining":
        if core_id:
            _apply_ledger(conn, tenant_id, core_id, start, end, out)
        else:
            _apply_ledger_by_uid(conn, content_id, place, start, end, out)
    if not out.known:
        out.why_unknown = _why_unknown(place, kind, content_id)
    return out


def _why_unknown(place: dict[str, Any], kind: str, content_id: str | None) -> str:
    source = str(place.get("source") or "")
    if source == "dining_license":
        return "인허가(사업자 등록) 자료에서 찾은 식당이라 영업시간은 아직 몰라요"
    if source == "kakao" and not content_id:
        return "카카오 지도 정보에는 운영시간이 없어요"
    if content_id or source == "tour_api":
        return "관광공사 운영시간을 아직 읽지 못했어요"
    return "운영시간 정보를 아직 못 찾았어요"


def _place_row(conn, tenant_id: str, place_id: str) -> tuple[dict[str, Any], str | None]:
    with conn.cursor() as cur:
        cur.execute("SELECT attributes, COALESCE(source_content_id, attributes->>'source_content_id') FROM places "
                    "WHERE tenant_id=%s AND place_id=%s", (tenant_id, place_id))
        row = cur.fetchone()
    if row is None:
        return {}, None
    attributes = dict(row[0] or {})
    keep = {k: attributes[k] for k in ("hours_week", "hours", "break", "hours_read") if attributes.get(k)}
    return keep, (str(row[1]) if row[1] else None)


def _catalog_week(conn, tenant_id: str, content_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute("SELECT hours_week FROM catalog_hours WHERE tenant_id = ANY(%s) AND source='tour_api' "
                    "AND content_id=%s AND hours_week IS NOT NULL LIMIT 1", (_tenants(tenant_id), content_id))
        row = cur.fetchone()
        if row and row[0]:
            return dict(row[0])
        cur.execute(
            "SELECT attributes->'hours_week' FROM places WHERE tenant_id=%s AND attributes ? 'hours_week' "
            "AND attributes->'hours_week' <> '{}'::jsonb "
            "AND COALESCE(source_content_id, attributes->>'source_content_id') = %s "
            "AND (attributes->'hours_read'->>'read_at')::timestamptz > now() - make_interval(days => %s) "
            "ORDER BY attributes->'hours_read'->>'read_at' DESC LIMIT 1", (tenant_id, content_id, REUSE_DAYS))
        row = cur.fetchone()
    return dict(row[0]) if row and row[0] else None


def _apply_ledger(conn, tenant_id: str, core_id: str, start: datetime, end: datetime | None,
                  out: HoursFacts) -> None:
    from app.domains.travel_ops.instances.dining.ledger import dining_state

    try:
        # ★세이브포인트 안에서 부른다 — DB 오류가 바깥 트랜잭션을 망가뜨리지 않는다(바깥이 `conn.transaction()` 이면 `conn.rollback()` 은 금지다)
        with conn.transaction():
            state = dining_state(conn, tenant_id, core_id, start, end or start, order_margin_min=ORDER_MARGIN_MIN)
    except Exception as exc:                    # noqa: BLE001 — 원장 표가 없는 DB(시험 · 다른 조립)면 원장 없이 간다
        if type(exc).__name__ not in ("UndefinedTable", "UndefinedFunction", "InvalidSchemaName"):
            raise
        return
    if not state or not state.get("linked") or not state.get("available"):
        return
    _merge_state(state, start, out)


def _ledger_uid(conn, content_id: str | None, place: dict[str, Any]) -> str | None:
    """읽은 장소 → 원장 가게 번호. 관광공사 번호(`tourapi_kor_food`)가 하나의 가게로 이어질 때만, 번호가 없으면 이름이 원장에서 하나로 정해질 때만.
    둘 이상이면 고르지 않는다(모름) — 다른 가게의 영업시간으로 판정하는 것이 가장 나쁘다(`ledger.slot_verdicts` · `find_place_by_name` 과 같은 규칙)."""
    from app.domains.travel_ops.instances.dining.ledger import find_place_by_name

    if not content_id:
        found = find_place_by_name(conn, str(place.get("name") or ""))
        content_id = str(found["content_id"]) if found else None
    if not content_id:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT p.place_uid::text FROM dining.dn_place p WHERE p.record_status <> 'closed' AND p.place_uid IN "
                    "(SELECT r.place_uid FROM dining.dn_source_record r WHERE r.source_code = 'tourapi_kor_food' "
                    "AND r.external_id = %s AND r.match_status <> 'rejected') LIMIT 2", (content_id,))
        rows = cur.fetchall()
    return str(rows[0][0]) if len(rows) == 1 else None


def _apply_ledger_by_uid(conn, content_id: str | None, place: dict[str, Any], start: datetime, end: datetime | None,
                         out: HoursFacts) -> None:
    """장소 행이 아직 없는 식당의 원장 판정 — `dining.core_place_state` 와 같은 SQL 을 가게 번호로 바로 부른다. `[2026-10-05]`"""
    try:
        # ★세이브포인트 안에서 — DB 오류가 바깥 트랜잭션을 망가뜨리지 않는다
        with conn.transaction():
            uid = _ledger_uid(conn, content_id, place)
            if uid is None:
                return
            at = start if start.tzinfo else start.replace(tzinfo=_seoul())
            until = end or at
            if until.tzinfo is None:
                until = until.replace(tzinfo=_seoul())
            with conn.cursor() as cur:
                cur.execute("SELECT dining.open_at_slot(%s::uuid, %s, %s), dining.needs_last_order_check(%s::uuid, %s, %s), "
                            "dining.holiday_context(%s::uuid, %s), "
                            "dining.core_attributes(%s::uuid, (%s::timestamptz AT TIME ZONE 'Asia/Seoul')::date)",
                            (uid, at, until, uid, at, until, uid, at, uid, at))
                open_at, needs_check, holiday, attributes = cur.fetchone()
                order_ok = None
                if open_at is True:
                    cur.execute("SELECT dining.open_at_slot(%s::uuid, %s, %s)",
                                (uid, at + timedelta(minutes=ORDER_MARGIN_MIN), until))
                    order_ok = cur.fetchone()[0]
    except Exception as exc:                    # noqa: BLE001 — 원장 표가 없는 DB(시험 · 다른 조립)면 원장 없이 간다
        if type(exc).__name__ not in ("UndefinedTable", "UndefinedFunction", "InvalidSchemaName"):
            raise
        logger.warning("intake hours: dining ledger not readable reason=%s", type(exc).__name__)   # 원문 · 키 없이 종류만
        return
    _merge_state({"open_at_slot": open_at, "order_ok": order_ok, "needs_check": needs_check,
                  "attributes": attributes, "holiday_context": holiday}, start, out)


def _merge_state(state: dict[str, Any], start: datetime, out: HoursFacts) -> None:
    """원장 판정(`dining_state` 모양) → 사실. 두 길(장소 행 · 가게 번호)이 같은 규칙으로 합친다."""
    attrs = dict(state.get("attributes") or {})
    out.open_at_slot, out.order_ok, out.needs_check = state.get("open_at_slot"), state.get("order_ok"), bool(state.get("needs_check"))
    week: dict[str, Any] = dict(out.attributes.get("hours_week") or {})
    if attrs.get("closed"):
        week[_DAYS[start.astimezone(_seoul()).weekday() if start.tzinfo else start.weekday()]] = "closed"
        out.attributes = {**out.attributes, "hours_week": week}
        out.known, out.source = True, "dining_ledger"
    elif attrs.get("hours"):
        out.attributes = {**out.attributes, "hours": attrs["hours"], **({"break": attrs["break"]} if attrs.get("break") else {})}
        out.known, out.source = True, "dining_ledger"
    if state.get("holiday_context"):
        out.conditions.append(str(state["holiday_context"]))


def _seoul():
    from zoneinfo import ZoneInfo

    return ZoneInfo("Asia/Seoul")


def closed_weekdays(attributes: dict[str, Any]) -> list[str]:
    """요일표(`hours_week`)에서 쉬는 요일(한글 한 글자) — 표가 없으면 빈 목록."""
    week = attributes.get("hours_week")
    if not isinstance(week, dict):
        return []
    return ["월화수목금토일"[i] for i, key in enumerate(_DAYS) if week.get(key) == "closed"]


def week_known_all(attributes: dict[str, Any]) -> bool:
    """요일표가 7일을 모두 적었나 — 그래야 「쉬는 날이 없다」고 말할 수 있다."""
    week = attributes.get("hours_week")
    return isinstance(week, dict) and all(key in week for key in _DAYS)


def weekday_ko(day: date) -> str:
    return "월화수목금토일"[day.weekday()]
