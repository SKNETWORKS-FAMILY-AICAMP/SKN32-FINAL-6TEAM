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


# ── 2026-09-01: SQL 쪽 조건을 결정적으로 재는 법 ─────────────────────
#
# 낙관적 동시성은 두 겹이다. 파이썬(transition_case)은 친절한 조기 실패이고,
# SQL 의 `AND version = %(expected_version)s` 는 원자적 compare-and-swap 이다.
# 조회와 UPDATE 사이에 다른 트랜잭션이 커밋할 수 있으므로 둘은 중복이 아니다.
#
# 기존 동시성 테스트는 두 조회가 **모두 끝났음을 보장하지 않는다.** 한쪽이 커밋한
# 뒤에 다른 쪽이 조회하면 파이썬 검사만으로 충돌해서, SQL 조건을 지운 변이를
# 구분하지 못한다(실측: 단독 5회 중 4회 통과).
#
# 그래서 두 스레드가 **같은 version 을 읽은 것이 확정된 뒤에** 진행하도록 barrier 로
# 맞춘다. 그러면 둘 다 파이썬 검사를 지나 UPDATE 로 가고, SQL 조건이 살아 있어야만
# 한쪽이 진다.


def test_two_writers_that_read_the_same_version_produce_exactly_one_conflict(
    db, monkeypatch  # noqa: F811
):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app.core import transition as transition_module
    from app.infrastructure.db.session import get_connection

    conn, tenant = db
    case_id = _fresh_case(conn, tenant)

    barrier = threading.Barrier(2, timeout=15)
    original = transition_module._load_projection

    def synchronized(connection, tenant_id, target_case_id):
        projection = original(connection, tenant_id, target_case_id)
        barrier.wait()  # 둘 다 같은 version 을 읽은 것이 여기서 확정된다
        return projection

    monkeypatch.setattr(transition_module, "_load_projection", synchronized)

    def attempt() -> str:
        with get_connection() as worker:
            try:
                with worker.transaction():
                    transition_case(
                        worker, tenant_id=tenant, case_id=case_id, expected_version=1,
                        event_type=EventType.CLASSIFIED,
                        payload={"intent": "x", "issue_code": "x", "sentiment": "neutral"},
                        actor_type="test")
                return "success"
            except StateConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: attempt(), range(2)))
    assert outcomes == ["conflict", "success"], (
        "같은 version 을 읽은 두 실행이 모두 성공했다 — SQL 의 version 조건이 없으면 "
        "나중 것이 먼저 것을 덮어쓴다"
    )
    assert get_case(conn, tenant_id=tenant, case_id=case_id)["version"] == 2
