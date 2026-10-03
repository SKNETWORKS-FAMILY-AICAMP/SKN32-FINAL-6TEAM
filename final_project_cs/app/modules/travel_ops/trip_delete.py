# -*- coding: utf-8 -*-
"""여행 삭제 — **즉시 완전 삭제**. `[결정 2026-10-04 사용자 · uiux 요청서 「구현 지침」 8항]` D-CS-011

계약 `wiki/records/plans/2026-10-03_1920_웹_실서버_전환_백엔드_요청.md` · `wiki/external/rest-endpoints.md` 「여행 삭제」. 웹 `POST /v1/web/trips/{id}/delete` 와 **게스트 자동 정리**(`guest_cleanup.py`)가 같은 함수를 쓴다.

★한 트랜잭션 — 호출자가 `with conn.transaction():` 으로 감싼다. 소유자 확인과 함께 `trips` 행을 **잠근다**(`FOR UPDATE`). 남의 여행 · 없는 여행 · 이미 지운 여행은 모두 `False`(같은 404).
★외래키가 없어 **자동으로 안 지워지는 표는 이름을 대어 지운다**(아래 `_PURGE`). 새 표가 여행 번호를 들고 생기면 걸리는 시험이 있다(`tests/e2e/test_trip_delete.py`).
  `trips` 를 지우면 `itinerary_versions` · `itinerary_items` · `pending_changes` 는 CASCADE 로 따라 지워진다.
  `places.trip_scope`(이 여행 전용 장소 행 — 외부 값이라 다른 고객에게 재사용하면 안 된다)는 외래키가 없다 — 요청서 목록에 빠져 있던 것을 표 조회로 찾아 더했다.
★운영 쪽은 **지우지도 가리지도 않는다.** `case_events` 는 append-only 다. 그 여행을 가리키는 **열린 Case**(`state_json.subject_ref.id`)는 상태 전이표(`domain/events.py`)가 허용하는
  **정상 전이만으로 `cancelled` 까지 닫는다**(가장 짧은 길을 찾아 한 걸음씩 — 이유 `trip_deleted`). 해결(`resolved`)된 Case 는 기록이라 그대로 둔다.
★바깥함(`outbox`)의 그 여행 알림(`trip.notice`, `dedupe_key` 가 `{trip_id}:` 로 시작)은 **대기분만 취소가 아니라 전부 지운다** — 알림 문장에 일정이 실려 있다.
★`trip_id` 가 NULL 인 옛 접수 · 알림은 고객 번호만으로 지우지 않는다(여행과 연결이 확인된 행만).
"""
from __future__ import annotations

from collections import deque
from typing import Any
from uuid import UUID

from app.core.contracts import CaseStatus
from app.core.transition import transition_case
from app.domain.events import REQUIRED_PAYLOAD_KEYS, TRANSITIONS, EventType

REASON = "trip_deleted"
ACTOR_TYPE, ACTOR_ID = "system", "trip_delete"
#: 닫지 않는 상태 — 해결된 Case 는 기록이고, 취소된 Case 는 이미 닫혔다
_KEEP = frozenset({CaseStatus.RESOLVED, CaseStatus.CANCELLED})
#: (표, 여행 번호 칸) — `trips` 를 지우기 **전에** 지운다. 외래키가 없어 자동으로 안 지워지는 것들
_PURGE: tuple[tuple[str, str], ...] = (
    ("trip_chat_turns", "trip_id"),
    ("place_open_checks", "trip_id"),
    ("dining.dn_notice", "trip_id"),
)


def _path_to_cancelled(start: CaseStatus) -> list[EventType]:
    """전이표에서 `cancelled` 까지의 **가장 짧은 이벤트 열**(너비 우선, `resolved` 를 거치지 않는다). 없으면 빈 열."""
    queue: deque[tuple[CaseStatus, list[EventType]]] = deque([(start, [])])
    seen = {start}
    while queue:
        status, path = queue.popleft()
        if status is CaseStatus.CANCELLED:
            return path
        for (current, event), nxt in TRANSITIONS.items():
            # ★`resolved`(해결됨) 를 거치는 길은 쓰지 않는다 — 안 한 일을 「끝냈다」(`completed`)고 기록하게 된다. 에스컬레이션 → 취소로만 간다
            if current is status and nxt not in seen and nxt is not CaseStatus.RESOLVED:
                seen.add(nxt)
                queue.append((nxt, [*path, event]))
    return []


def close_cases(conn, *, tenant_id: str, customer_id: UUID, trip_id: UUID) -> int:
    """그 여행을 가리키는 **열린 Case** 를 정상 전이로 `cancelled` 까지 닫는다. 닫은 수를 돌려준다."""
    with conn.cursor() as cur:
        cur.execute("SELECT case_id, status::text, version FROM customer_cases WHERE tenant_id=%s AND customer_id=%s "
                    "AND state_json->'subject_ref'->>'id' = %s AND status::text NOT IN ('resolved','cancelled') "
                    "ORDER BY created_at FOR UPDATE", (tenant_id, customer_id, str(trip_id)))
        rows = cur.fetchall()
    closed = 0
    for case_id, status, version in rows:
        events = _path_to_cancelled(CaseStatus(status))
        if not events:                                    # 전이표에 길이 없다 — 조용히 넘기지 않는다
            raise RuntimeError(f"Case {case_id} 의 상태 {status} 에서 cancelled 로 가는 전이가 없다")
        for event in events:
            payload = {"reason": REASON, **{key: REASON for key in REQUIRED_PAYLOAD_KEYS.get(event, ())}}
            result = transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=version, event_type=event,
                                     payload=payload, actor_type=ACTOR_TYPE, actor_id=ACTOR_ID)
            version = result.version
        closed += 1
    return closed


def delete_trip(conn, *, tenant_id: str, customer_id: UUID, trip_id: UUID) -> dict[str, Any] | None:
    """여행 하나를 지운다. 없는 여행 · 남의 여행이면 None. 지운 것을 세어 돌려준다(조용히 넘기지 않는다)."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM trips WHERE tenant_id=%s AND trip_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, trip_id, customer_id))
        if cur.fetchone() is None:
            return None
    counts: dict[str, Any] = {"cases_closed": close_cases(conn, tenant_id=tenant_id, customer_id=customer_id, trip_id=trip_id)}
    with conn.cursor() as cur:
        cur.execute("DELETE FROM outbox WHERE tenant_id=%s AND topic='trip.notice' AND dedupe_key LIKE %s",
                    (tenant_id, f"{trip_id}:%"))
        counts["notices"] = cur.rowcount
        for table, column in _PURGE:
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s AND {column}=%s", (tenant_id, trip_id))
            counts[table] = cur.rowcount
        # 접수 — 이 여행으로 만든 것만(자식 `intake_sources` · `intake_claims` · `intake_reviews` 는 CASCADE)
        cur.execute("DELETE FROM trip_intakes WHERE tenant_id=%s AND trip_id=%s AND customer_id=%s", (tenant_id, trip_id, customer_id))
        counts["trip_intakes"] = cur.rowcount
        cur.execute("DELETE FROM trips WHERE tenant_id=%s AND trip_id=%s", (tenant_id, trip_id))
        counts["trips"] = cur.rowcount
        # 이 여행 전용 장소 — 일정 항목(`itinerary_items.place_id`)이 위 삭제로 사라진 뒤에만 지울 수 있다
        cur.execute("DELETE FROM places WHERE tenant_id=%s AND trip_scope=%s", (tenant_id, trip_id))
        counts["places"] = cur.rowcount
    return counts


__all__ = ["REASON", "close_cases", "delete_trip"]
