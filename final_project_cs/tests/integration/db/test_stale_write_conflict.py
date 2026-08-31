"""낙관적 동시성 — 지난 상태로 덮어쓰기 방지. 2026-08-31 추가.

`transition_case` 의 버전 대조를 `!=` 에서 `<` 로 바꾼 변경이 실행마다 결과가
갈렸다(세 번 중 두 번 통과). 그래서 이 규칙을 재현 가능한 형태로 다시 센다.

막으려는 것은 하나다. **내가 읽은 뒤 남이 먼저 바꿨는데 그걸 모르고 덮어쓰는 것.**
그때 현재 version 은 내가 읽은 것보다 **크다**. `<` 비교는 이 경우를 놓친다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.contracts import StateConflict
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db.repository import create_case, get_case

from tests.integration.controller.test_controller_integration import db  # noqa: F401


def _fresh_case(conn, tenant: str):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
            (tenant, uuid4().hex),
        )
        customer = cur.fetchone()[0]
    case_id = create_case(conn, tenant_id=tenant, customer_id=customer, subject="stale write")
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                        event_type=EventType.CREATED,
                        payload={"channel": "test", "message": "x"}, actor_type="test")
    conn.commit()
    return case_id


def test_writing_with_a_version_older_than_current_is_rejected(db):  # noqa: F811
    """읽은 시점보다 현재 version 이 **크면** 충돌이다."""
    conn, tenant = db
    case_id = _fresh_case(conn, tenant)
    current = get_case(conn, tenant_id=tenant, case_id=case_id)["version"]
    assert current == 1

    with pytest.raises(StateConflict):
        with conn.transaction():
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                            event_type=EventType.CLASSIFIED,
                            payload={"intent": "x", "issue_code": "x", "sentiment": "neutral"},
                            actor_type="test")


def test_a_rejected_stale_write_does_not_change_the_case(db):  # noqa: F811
    """거부됐으면 상태가 그대로여야 한다. 이게 덮어쓰기 방지의 실체다."""
    conn, tenant = db
    case_id = _fresh_case(conn, tenant)
    before = get_case(conn, tenant_id=tenant, case_id=case_id)

    with pytest.raises(StateConflict):
        with conn.transaction():
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                            event_type=EventType.CLASSIFIED,
                            payload={"intent": "x", "issue_code": "x", "sentiment": "neutral"},
                            actor_type="test")
    conn.rollback()
    after = get_case(conn, tenant_id=tenant, case_id=case_id)
    assert after["version"] == before["version"]
    assert after["status"] == before["status"]


def test_writing_with_a_version_ahead_of_current_is_rejected(db):  # noqa: F811
    """있지도 않은 미래 version 으로 쓰는 것도 충돌이다. 대조는 양방향이다."""
    conn, tenant = db
    case_id = _fresh_case(conn, tenant)
    with pytest.raises(StateConflict):
        with conn.transaction():
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=99,
                            event_type=EventType.CLASSIFIED,
                            payload={"intent": "x", "issue_code": "x", "sentiment": "neutral"},
                            actor_type="test")
