# -*- coding: utf-8 -*-
"""게스트 정리 — 마지막 사용 뒤 오래된 **로그인 안 한 웹 사용자**의 데이터를 지운다. `[결정 2026-10-04 사용자]` D-CS-011 §2

옛 「빈 키 정리」(`web_guard.cleanup_idle_keys`, 2026-09-28 · 여행 0건인 키만, 기본 꺼짐)를 이것이 **대신한다** — 두 구현을 두지 않는다.

★대상 = 게스트(`guest_policy` — 웹으로 만든 사용자 중 소셜 계정이 안 붙은 사용자). 소셜 계정이 붙은 회원 · 에이전트 API 로 만든 고객 · 시드는 건드리지 않는다.
★「마지막 사용」 = 사용자 행 생성 · 키의 발급/사용 · 세션의 마지막 사용 중 **가장 늦은 때**. 계획서 링크 열람 · 자동 감시 · 외부 호출은 사용이 아니다.
★지우는 때: 마지막 사용 + `web.guest_idle_hours`(관리 콘솔 — 기본 168시간)가 지난 뒤. **단 일정이 남은 게스트**(마지막 일정 종료가 아직 안 지났거나 종료 뒤 유예 안)는
  `min(마지막 일정 종료, 마지막 사용 + web_guard.guest.trip_keep_max_days) + trip_grace_days` 까지 둔다 — 계획서 링크와 알림이 그때까지 산다(세션은 이미 끝났을 수 있다).
  상한이 「지금」이 아니라 「마지막 사용」 기준이라 날짜를 빌미로 영구히 남지 않는다. 일정 종료가 비어 있으면(항목의 `ends_at` 없음) 시작 시각을 종료로 본다.
★삭제는 사용자마다 **따로 한 트랜잭션** — 여행은 `trip_delete.delete_trip`(웹의 「여행 삭제」와 같은 함수) · 접수 · 세션 · 키 · 사용자 행(프로필은 CASCADE).
  사용자 행을 가리키는 외래키 14개 중 13개가 「가리키면 거부」(2026-10-04 서버 DB 조회)라, **Case 같은 기록이 가리키면 사용자 행만 남긴다**(이메일도 이름도 없는 무작위 `web:` 번호 한 줄 —
  `customers_kept` 로 센다). 다음 정리 때 또 시도해도 지울 것이 없다.
★지운 수 · 남긴 수 · 일정 때문에 둔 수를 센다(조용히 넘기지 않는다). 꺼져 있으면(`web.guest_cleanup_enabled`) 아무것도 안 지운다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.errors import ForeignKeyViolation

from app.core.settings import get_guardrails

from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.components.itinerary.trip_delete import delete_trip

_CANDIDATES = """
SELECT c.customer_id, x.last_seen, x.trips_end FROM customers c
CROSS JOIN LATERAL (
    SELECT GREATEST(
               c.created_at,
               COALESCE((SELECT max(GREATEST(k.created_at, COALESCE(k.last_used_at, k.created_at))) FROM web_user_keys k
                         WHERE k.tenant_id=c.tenant_id AND k.customer_id=c.customer_id), c.created_at),
               COALESCE((SELECT max(s.last_used_at) FROM web_sessions s
                         WHERE s.tenant_id=c.tenant_id AND s.customer_id=c.customer_id), c.created_at)) AS last_seen,
           (SELECT max(COALESCE(i.ends_at, i.starts_at)) FROM trips t
              JOIN itinerary_items i ON i.trip_id=t.trip_id AND i.version=t.latest_version AND i.tenant_id=t.tenant_id
             WHERE t.tenant_id=c.tenant_id AND t.customer_id=c.customer_id) AS trips_end
) x
WHERE c.tenant_id=%s AND left(c.external_id, 4) = 'web:'
  AND NOT EXISTS (SELECT 1 FROM web_social_links l WHERE l.tenant_id=c.tenant_id AND l.customer_id=c.customer_id)
  AND x.last_seen < %s
ORDER BY x.last_seen
LIMIT %s
"""


def _delete_one(conn, tenant_id: str, customer_id: UUID) -> dict[str, int]:
    done = {"trips": 0, "customer": 0, "kept": 0}
    with conn.cursor() as cur:
        cur.execute("SELECT trip_id FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        trips = [row[0] for row in cur.fetchall()]
    for trip_id in trips:
        if delete_trip(conn, tenant_id=tenant_id, customer_id=customer_id, trip_id=trip_id) is not None:
            done["trips"] += 1
    with conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))      # 여행이 안 된 접수(자식은 CASCADE)
        cur.execute("DELETE FROM web_sessions WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        cur.execute("DELETE FROM web_user_keys WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        cur.execute("DELETE FROM web_agent_keys WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))   # 연결을 푼 옛 회원이 가졌던(거둔) 에이전트 키
        try:
            with conn.transaction():                       # 저장점 — 가리키는 기록이 있으면 이 삭제만 되돌린다
                cur.execute("DELETE FROM customers WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
            done["customer"] = cur.rowcount
        except ForeignKeyViolation:
            done["kept"] = 1
    return done


def cleanup_guests(conn, tenant_id: str, now: datetime | None = None, *, limit: int = 200) -> dict[str, Any]:
    """만료된 게스트를 지운다 — `limit` 명까지(한 번에 오래 안 잡는다). 꺼져 있으면 `{"skipped": "disabled"}`."""
    limits = web_guard.values(tenant_id)
    if not limits["web.guest_cleanup_enabled"]:
        return {"skipped": "disabled"}
    guard = get_guardrails()
    now = web_guard._now(now)
    idle = timedelta(hours=int(limits["web.guest_idle_hours"]))
    grace = timedelta(days=int(guard.get("web_guard.guest.trip_grace_days")))
    keep_max = timedelta(days=int(guard.get("web_guard.guest.trip_keep_max_days")))
    out = {"candidates": 0, "held_for_trips": 0, "customers_deleted": 0, "customers_kept": 0, "trips_deleted": 0}
    with conn.cursor() as cur:
        cur.execute(_CANDIDATES, (tenant_id, now - idle, limit))
        rows = cur.fetchall()
    out["candidates"] = len(rows)
    for customer_id, last_seen, trips_end in rows:
        if trips_end is not None and now < min(trips_end, last_seen + keep_max) + grace:
            out["held_for_trips"] += 1
            continue
        with conn.transaction():
            done = _delete_one(conn, tenant_id, customer_id)
        out["trips_deleted"] += done["trips"]
        out["customers_deleted"] += done["customer"]
        out["customers_kept"] += done["kept"]
    return out


__all__ = ["cleanup_guests"]
