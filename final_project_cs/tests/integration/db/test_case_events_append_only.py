# -*- coding: utf-8 -*-
"""`case_events` 는 **DB 가** 추가만 하게 막는다 — 마이그레이션 904. `[2026-10-15]`

Case 의 사건 기록은 상태를 다시 만들 수 있는 유일한 근거(재생)이자 감사 기록이다. 「추가만 한다」는 코어 규칙이 지금까지 코드에만 있어서
아무 코드나 시험이 UPDATE · DELETE · TRUNCATE 를 해도 DB 가 말리지 못했다. 이 시험이 다음을 지킨다.

 ①INSERT 는 된다(정상 흐름)  ②UPDATE 는 늘 거절  ③스위치 없이 DELETE 는 거절  ④`SET LOCAL app.case_events_purge = 'on'` 이면 DELETE 가능
 ⑤TRUNCATE 는 스위치 없이 거절(스위치가 있으면 되지만 여기서는 롤백한다)  ⑥실제 `transition_case()` 로 상태를 바꾸면 사건이 쌓인다
 ⑦`cleanup_tenant()` 는 스위치를 스스로 켜고 테넌트를 지운다  ⑧스위치는 그 트랜잭션에서만 산다(다음 트랜잭션은 다시 거절)

거절된 시도가 이미 있는 행을 건드리지 않았는지도 매번 센다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.case_lifecycle.events import EventType
from app.core.contracts import CaseStatus
from app.core.transition import transition_case
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.infrastructure.db.repository import create_case, get_case_events
from app.infrastructure.db.session import get_connection
from tests.helpers.case_events_purge import allow_case_events_purge

REFUSED = "case_events 는 추가만 한다"


@pytest.fixture()
def world():
    """테넌트 하나 + 고객 하나 + Case 하나(사건 `created` 한 줄). 끝나면 정리 스위치를 켜고 치운다."""
    tenant = "test_cev_" + uuid4().hex[:12]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "case events append only"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (tenant, uuid4().hex))
        customer = cur.fetchone()[0]
    with get_connection() as conn:
        case_id = create_case(conn, tenant_id=tenant, customer_id=customer, subject="append only")
        with conn.transaction():
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0, event_type=EventType.CREATED,
                            payload={"channel": "test", "message": "hello"}, actor_type="test")
    yield {"tenant": tenant, "customer": customer, "case_id": case_id}
    cleanup_tenant(tenant)


def _events(tenant, case_id=None):
    with get_connection() as conn, conn.cursor() as cur:
        if case_id is None:
            cur.execute("SELECT aggregate_version, event_type FROM case_events WHERE tenant_id=%s ORDER BY aggregate_version", (tenant,))
        else:
            cur.execute("SELECT aggregate_version, event_type FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version",
                        (tenant, case_id))
        return cur.fetchall()


def _insert_event(cur, world, version):
    cur.execute("INSERT INTO case_events (tenant_id,case_id,aggregate_version,event_type,payload_json,actor_type,actor_id) "
                "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (world["tenant"], world["case_id"], version, "note", "{}", "test", "t"))


def test_insert_is_allowed(world):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        _insert_event(cur, world, 2)
    assert [v for v, _ in _events(world["tenant"])] == [1, 2]


def test_update_is_always_refused(world):
    with pytest.raises(Exception, match=REFUSED):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE case_events SET payload_json='{\"x\":1}'::jsonb WHERE tenant_id=%s", (world["tenant"],))
    # 스위치를 켜도 UPDATE 는 거절이다(스위치는 정리용 DELETE · TRUNCATE 만 연다)
    with pytest.raises(Exception, match=REFUSED):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            allow_case_events_purge(cur)
            cur.execute("UPDATE case_events SET event_type='tampered' WHERE tenant_id=%s", (world["tenant"],))
    assert _events(world["tenant"]) == [(1, "created")]


def test_delete_without_the_switch_is_refused(world):
    with pytest.raises(Exception, match=REFUSED):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (world["tenant"],))
    assert _events(world["tenant"]) == [(1, "created")]


def test_delete_with_the_switch_is_allowed(world):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        allow_case_events_purge(cur)
        cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (world["tenant"],))
        assert cur.rowcount == 1
    assert _events(world["tenant"]) == []


def test_the_switch_lives_only_in_its_own_transaction(world):
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            allow_case_events_purge(cur)                                      # 이 트랜잭션에서만 산다
        with pytest.raises(Exception, match=REFUSED):
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (world["tenant"],))
    assert _events(world["tenant"]) == [(1, "created")]


def test_truncate_without_the_switch_is_refused(world):
    with pytest.raises(Exception, match=REFUSED):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")                      # 다른 접속이 표를 잡고 있어도 시험이 매달리지 않게
            cur.execute("TRUNCATE case_events")
    assert _events(world["tenant"]) == [(1, "created")]


def test_truncate_with_the_switch_passes_the_guard_but_we_roll_it_back(world):
    """스위치가 있으면 TRUNCATE 도 트리거를 지난다 — 공용 시험 DB 를 비우면 안 되니 **반드시 롤백**한다."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            allow_case_events_purge(cur)
            cur.execute("TRUNCATE case_events")
            cur.execute("SELECT count(*) FROM case_events")
            assert cur.fetchone()[0] == 0
        conn.rollback()
    assert _events(world["tenant"]) == [(1, "created")]


def test_real_transitions_still_append_events(world):
    """실제 상태 전이(`transition_case`)는 DB 잠금 아래에서도 그대로 사건을 쌓는다."""
    with get_connection() as conn:
        with conn.transaction():
            transition_case(conn, tenant_id=world["tenant"], case_id=world["case_id"], expected_version=1,
                            event_type=EventType.CLASSIFIED,
                            payload={"intent": "incident_report", "issue_code": "activity_cancel_or_change", "sentiment": "neutral"},
                            actor_type="test")
        events = get_case_events(conn, tenant_id=world["tenant"], case_id=world["case_id"])
        with conn.cursor() as cur:
            cur.execute("SELECT version,status FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (world["tenant"], world["case_id"]))
            assert cur.fetchone() == (2, CaseStatus.ROUTING)
    assert [(e["aggregate_version"], e["event_type"]) for e in events] == [(1, "created"), (2, "classified")]


def test_cleanup_tenant_still_removes_the_tenant_and_its_events(world):
    tenant = world["tenant"]
    assert _events(tenant) == [(1, "created")]
    cleanup_tenant(tenant)
    assert _events(tenant) == []
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tenants WHERE tenant_id=%s", (tenant,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (tenant,))
        assert cur.fetchone()[0] == 0


def test_existing_rows_are_not_checked_when_the_trigger_is_installed(world):
    """소급 영향 없음 — 트리거를 지우고 다시 만들어도(= 마이그레이션 재적용) 이미 있는 행은 그대로이고 오류가 없다."""
    from app.infrastructure.db.migrate import MIGRATION_DIR
    sql = (MIGRATION_DIR / "904_case_events_append_only.sql").read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(sql)
            conn.execute(sql)                                                 # 두 번 적용해도 같다(멱등)
    assert _events(world["tenant"]) == [(1, "created")]
    with pytest.raises(Exception, match=REFUSED):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (world["tenant"],))
