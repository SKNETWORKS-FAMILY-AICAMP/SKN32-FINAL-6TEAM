# -*- coding: utf-8 -*-
"""게스트(로그인 안 한 웹 사용자)의 제한 — 여행 1개 · 계획 기간 상한 · 감시 불가. `[결정 2026-10-04 사용자 「나머지는 니 제한대로」]` D-CS-011 §3

★게스트 = **웹으로 만든 사용자**(`customers.external_id` 가 `web:` 로 시작) 중 **소셜 계정이 하나도 안 붙은** 사용자. 에이전트 API 로 만든 고객과 시드는 게스트가 아니다.
  게스트가 소셜 계정을 `link` 하면 그 순간부터 회원이다(여행도 그대로).
★수치는 가드레일 `web_guard.guest.*` — 코드에 숫자를 두지 않는다.
★「여행 만들기 하루 1건」(`web.trip_create.*`)은 **사용자 단위**라 새 게스트를 만들면 우회된다 — 그래서 한도와 별개로 「게스트 총 1개」를 사용자 행 잠금으로 막는다(동시 생성까지).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.settings import get_guardrails

KST = ZoneInfo("Asia/Seoul")


def _aware(moment: datetime) -> datetime:
    """시각 없는 값은 한국 시각으로 본다(일정 시각은 한국 시각으로 받는다)."""
    return moment if moment.tzinfo else moment.replace(tzinfo=KST)


#: SQL 조각 — `{a}` 는 `trips` 별칭. 「감시해도 되는 여행」 = 게스트의 것이 **아닌** 것.
#: ★`LIKE 'web:%'` 대신 `left(…,4)` — 매개변수를 넘기는 질의에서 `%` 를 겹쳐 쓰지 않으려고.
_GUEST_OWNER = ("EXISTS (SELECT 1 FROM customers gc WHERE gc.customer_id={a}.customer_id AND left(gc.external_id, 4) = 'web:') "
                "AND NOT EXISTS (SELECT 1 FROM web_social_links gl WHERE gl.tenant_id={a}.tenant_id AND gl.customer_id={a}.customer_id)")


def not_guest_sql(alias: str = "t") -> str:
    """`WHERE … AND {이 조각}` — 게스트가 소유한 여행을 **감시 · 알림 대상에서 뺀다.**"""
    return "NOT (" + _GUEST_OWNER.format(a=alias) + ")"


def is_guest(conn, *, tenant_id: str, customer_id: UUID | str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT left(external_id, 4) = 'web:' AND NOT EXISTS (SELECT 1 FROM web_social_links l WHERE l.tenant_id=c.tenant_id "
                    "AND l.customer_id=c.customer_id) FROM customers c WHERE c.tenant_id=%s AND c.customer_id=%s",
                    (tenant_id, customer_id))
        row = cur.fetchone()
    return bool(row and row[0])


class GuestLimit(HTTPException):
    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(403, {"error": {"code": code, "message": message, "login_required": True, **detail}})


def check_new_trip(conn, *, tenant_id: str, customer_id: UUID | str, starts: Iterable[datetime], ends: Iterable[datetime],
                   now: datetime | None = None) -> None:
    """게스트가 **새 여행을 만들기 전**에 부른다 — 같은 트랜잭션 안에서. 사용자 행을 잠가(`FOR UPDATE`) 동시에 두 개가 만들어지지 않게 한다.
    걸리면 403 `guest_limit`(본문 `login_required: true` — 화면이 「로그인하면 더 만들 수 있어요」를 보인다). 게스트가 아니면 아무것도 안 한다."""
    guard = get_guardrails()
    with conn.cursor() as cur:
        cur.execute("SELECT left(external_id, 4) = 'web:' AND NOT EXISTS (SELECT 1 FROM web_social_links l WHERE l.tenant_id=c.tenant_id "
                    "AND l.customer_id=c.customer_id) FROM customers c WHERE c.tenant_id=%s AND c.customer_id=%s FOR UPDATE OF c",
                    (tenant_id, customer_id))
        row = cur.fetchone()
        if not (row and row[0]):
            return
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        existing = int(cur.fetchone()[0])
    cap = int(guard.get("web_guard.guest.max_trips"))
    if existing >= cap:
        raise GuestLimit("guest_trip_limit", f"로그인하지 않으면 여행을 {cap}개까지 만들 수 있어요", cap=cap, existing=existing)
    starts, ends = [_aware(m) for m in starts if m is not None], [_aware(m) for m in ends if m is not None]
    if not starts:
        return
    today = (now or datetime.now().astimezone())
    start_max = int(guard.get("web_guard.guest.trip_start_max_days"))
    if min(starts) > today + timedelta(days=start_max):
        raise GuestLimit("guest_trip_too_far", f"로그인하지 않으면 오늘부터 {start_max}일 안에 시작하는 여행만 만들 수 있어요", limit_days=start_max)
    length_max = int(guard.get("web_guard.guest.trip_length_max_days"))
    span = (max(ends or starts) - min(starts)).total_seconds() / 86400
    if span > length_max:
        raise GuestLimit("guest_trip_too_long", f"로그인하지 않으면 {length_max}일 안의 여행만 만들 수 있어요", limit_days=length_max)


__all__ = ["GuestLimit", "check_new_trip", "is_guest", "not_guest_sql"]
