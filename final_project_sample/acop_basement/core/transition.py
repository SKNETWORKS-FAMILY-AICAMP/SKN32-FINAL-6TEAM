"""`transition_case()` — Case 상태 변경의 **단일 진입점**.

★controller · API · worker 는 `customer_cases` 를 직접 UPDATE 하지 않는다.
  전부 이 함수를 부른다(v5 §5-3, CLAUDE.md §0.3).

한 transaction 안에서 다음을 함께 한다(v5 §6-4):
  1. 현재 version·status·tenant 확인
  2. 허용 전이 · payload schema 검증  (app/domain/case.py 의 순수 리듀서)
  3. `customer_cases` projection UPDATE ... WHERE version = :expected  ← 동시성 게이트
  4. `case_events` append (aggregate_version = 새 version)
  5. `outbox` insert

affected row 가 0이면 `StateConflict` 를 던진다. 셋 중 하나라도 실패하면 전부 롤백된다.

SQLAlchemy 모델에 기대지 않고 psycopg 로 직접 쓴다 —
Core 가 S-DB 스트림의 구현 세부에 묶이지 않게 하기 위해서다(docs/handoff/05).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Json

from acop_basement.core.contracts import CaseStatus, StateConflict
from acop_basement.domain.case import CaseProjection, apply_event, fold_events
from acop_basement.domain.events import EventType
from acop_basement.core.redaction import mask_json


@dataclass(frozen=True)
class OutboxMessage:
    """projection 변경과 **같은 transaction** 에 실리는 발행 메시지."""

    topic: str
    payload: dict[str, Any]
    dedupe_key: str


@dataclass(frozen=True)
class TransitionResult:
    case_id: UUID
    event_id: UUID
    previous_status: CaseStatus
    status: CaseStatus
    version: int
    published: list[str]  # 실제로 insert 된 outbox message_id (중복이면 비어 있다)


_SELECT_CASE = """
    SELECT status, version, state_json, intent, issue_code, sentiment, owner_team_id
    FROM customer_cases
    WHERE tenant_id = %(tenant_id)s AND case_id = %(case_id)s
"""

# v5 §6-1 의 문 그대로. version 조건이 optimistic concurrency 의 실체다.
_UPDATE_PROJECTION = """
    UPDATE customer_cases
    SET status = %(status)s, state_json = %(state_json)s,
        intent = %(intent)s, issue_code = %(issue_code)s, sentiment = %(sentiment)s,
        owner_team_id = %(owner_team_id)s,
        version = version + 1, updated_at = now()
    WHERE tenant_id = %(tenant_id)s AND case_id = %(case_id)s
      AND version = %(expected_version)s
    RETURNING version
"""

_INSERT_EVENT = """
    INSERT INTO case_events
        (tenant_id, case_id, aggregate_version, event_type, payload_json, actor_type, actor_id)
    VALUES
        (%(tenant_id)s, %(case_id)s, %(aggregate_version)s, %(event_type)s,
         %(payload_json)s, %(actor_type)s, %(actor_id)s)
    RETURNING event_id
"""

# UNIQUE(tenant_id, topic, dedupe_key) 가 중복 발행을 막는다 (v5 §8, DoD 12).
# ★버그사냥 2026-08-17 (라운드 01, 처리는 라운드 08) — 예전엔 tenant_id 가
#   빠져 있어 서로 다른 tenant 가 같은 (topic, dedupe_key) 를 쓰면 뒤의 것이
#   조용히 버려질 수 있었다. migrations/005 로 제약을 넓혔다.
_INSERT_OUTBOX = """
    INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json)
    VALUES (%(tenant_id)s, %(topic)s, %(dedupe_key)s, %(payload_json)s)
    ON CONFLICT (tenant_id, topic, dedupe_key) DO NOTHING
    RETURNING message_id
"""

_SELECT_EVENTS = """
    SELECT event_type, payload_json
    FROM case_events
    WHERE tenant_id = %(tenant_id)s AND case_id = %(case_id)s
    ORDER BY aggregate_version
"""


def _load_projection(conn: Connection, tenant_id: str, case_id: UUID) -> CaseProjection:
    with conn.cursor() as cur:
        cur.execute(_SELECT_CASE, {"tenant_id": tenant_id, "case_id": str(case_id)})
        row = cur.fetchone()
    if row is None:
        # ★tenant 가 다른 Case 도 여기로 온다. 존재 사실을 알리지 않는다(docs/handoff/03 §2).
        raise StateConflict(f"Case 를 찾을 수 없다: tenant={tenant_id} case={case_id}")
    status, version, state_json, intent, issue_code, sentiment, owner_team_id = row
    return CaseProjection(
        status=CaseStatus(status),
        version=version,
        state_json=state_json or {},
        intent=intent,
        issue_code=issue_code,
        sentiment=sentiment,
        owner_team_id=owner_team_id,
    )


def transition_case(
    conn: Connection,
    *,
    tenant_id: str,
    case_id: UUID,
    expected_version: int,
    event_type: EventType,
    payload: dict[str, Any],
    actor_type: str,
    actor_id: str | None = None,
    outbox: list[OutboxMessage] | None = None,
) -> TransitionResult:
    """Case 를 한 단계 전이시킨다.

    Args:
        conn: **transaction 이 열려 있는** psycopg 연결. 이 함수는 commit 하지 않는다 —
            호출자가 `with conn.transaction():` 으로 경계를 잡는다.
        expected_version: 호출자가 읽은 시점의 version. 그 사이 누가 바꿨으면 `StateConflict`.
        outbox: projection 변경과 원자적으로 발행할 메시지들.

    Raises:
        StateConflict: version 이 어긋났거나 Case 가 없다.
        InvalidTransition: 상태표에 없는 전이거나 payload 필수 키가 없다.
    """
    current = _load_projection(conn, tenant_id, case_id)

    if current.version != expected_version:
        raise StateConflict(
            f"version 충돌: expected={expected_version} actual={current.version} "
            f"(case={case_id}). 최신 Case 를 다시 읽어 재계산한다."
        )

    # 순수 리듀서가 전이 허용 여부와 payload schema 를 판정한다.
    # ★replay 도 같은 함수를 쓴다 — 그래서 재생 결과가 반드시 일치한다.
    safe_payload = mask_json(payload)
    updated = apply_event(current, event_type, safe_payload)

    with conn.cursor() as cur:
        cur.execute(
            _UPDATE_PROJECTION,
            {
                "status": updated.status.value,
                "state_json": Json(updated.state_json),
                "intent": updated.intent,
                "issue_code": updated.issue_code,
                "sentiment": updated.sentiment,
                "owner_team_id": updated.owner_team_id,
                "tenant_id": tenant_id,
                "case_id": str(case_id),
                "expected_version": expected_version,
            },
        )
        row = cur.fetchone()
        if row is None:
            # 읽은 뒤 UPDATE 사이에 누가 끼어들었다. 이것이 진짜 경합이다.
            raise StateConflict(
                f"동시 전이로 version 이 밀렸다: expected={expected_version} (case={case_id})"
            )
        new_version = row[0]

        cur.execute(
            _INSERT_EVENT,
            {
                "tenant_id": tenant_id,
                "case_id": str(case_id),
                "aggregate_version": new_version,
                "event_type": event_type.value,
                "payload_json": Json(safe_payload),
                "actor_type": actor_type,
                "actor_id": actor_id,
            },
        )
        event_id = cur.fetchone()[0]

        published: list[str] = []
        for message in outbox or []:
            cur.execute(
                _INSERT_OUTBOX,
                {
                    "tenant_id": tenant_id,
                    "topic": message.topic,
                    "dedupe_key": message.dedupe_key,
                    "payload_json": Json(message.payload),
                },
            )
            inserted = cur.fetchone()
            if inserted is not None:  # None = 같은 dedupe_key 가 이미 있다 (중복 발행 차단)
                published.append(str(inserted[0]))

    return TransitionResult(
        case_id=case_id,
        event_id=event_id,
        previous_status=current.status,
        status=updated.status,
        version=new_version,
        published=published,
    )


def replay_case(conn: Connection, *, tenant_id: str, case_id: UUID) -> CaseProjection:
    """`case_events` 를 순서대로 재생해 projection 을 다시 만든다 (v5 §6-2, DoD 3).

    저장된 projection 을 읽지 않는다 — 이벤트만으로 복원되는지 확인하는 것이 목적이다.
    """
    with conn.cursor() as cur:
        cur.execute(_SELECT_EVENTS, {"tenant_id": tenant_id, "case_id": str(case_id)})
        rows = cur.fetchall()
    events = [
        (EventType(event_type), payload if isinstance(payload, dict) else json.loads(payload))
        for event_type, payload in rows
    ]
    return fold_events(events)
