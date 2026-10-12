"""초기 동일 요청의 동시 접수도 업무 생성·적용은 한 번만 한다."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from uuid import uuid4
import pytest

from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _member, _web_body, _h  # noqa: F401
from .test_web_conversation_resume import _post


@pytest.mark.parametrize("mode", ["on", "off"])
def test_concurrent_initial_message_has_one_case_and_one_application(decided, monkeypatch, mode):
    from app.domains.travel_ops.components.conversation import trip_messages

    barrier = Barrier(2, timeout=30)
    monkeypatch.setattr(trip_messages, "_decision_mode", lambda *a, **k: mode)
    monkeypatch.setattr(trip_messages, "extract", lambda *a, **k: {"type": "change"})
    original = trip_messages._open_message_case

    def create(*args, **kwargs):
        barrier.wait()
        return original(*args, **kwargs)

    monkeypatch.setattr(trip_messages, "_open_message_case", create)
    request_id = f"concurrent-initial-request-{mode}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _post(decided, "점심 다른 데로 바꿔", request_id), range(2)))
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s", (request_id,))
        ids = cur.fetchall()
        assert len(ids) == 1, ([r.status_code for r in results], ids)
        cur.execute("SELECT count(*) FROM case_events WHERE case_id=%s AND event_type='created'", (ids[0][0],))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (f"{decided['trip']['trip_id']}:v2",))
        assert cur.fetchone()[0] == 1
    assert sorted(r.status_code for r in results) in ([200, 200], [200, 409])


def test_different_original_pii_with_same_redaction_is_a_conflicting_body(decided):
    first = _post(decided, "점심 다른 데로 바꿔 010-1234-5678", "original-body-hash")
    assert first.status_code == 200, first.text
    changed = _post(decided, "점심 다른 데로 바꿔 010-9999-5678", "original-body-hash")
    assert changed.status_code == 409, changed.text
    assert _post(decided, "점심 다른 데로 바꿔 010-1234-5678", "original-body-hash").json()["status"] == "duplicate"


def test_same_request_id_in_two_trips_is_not_a_creation_collision(decided, api):
    _member(api, decided["key"])
    created = decided["client"].post("/v1/web/trips", json=_web_body(api, request_id="second-trip-scope"),
                                      headers=_h(decided["key"]))
    assert created.status_code == 201, created.text
    other = {**decided, "trip": created.json()}
    one = _post(decided, "점심 다른 데로 바꿔", "shared-message-id")
    two = _post(other, "점심 다른 데로 바꿔", "shared-message-id")
    assert one.status_code == two.status_code == 200, (one.text, two.text)
    assert one.json()["case_id"] != two.json()["case_id"]
    assert one.json()["status"] == two.json()["status"] == "adjusted"


def test_create_only_key_is_isolated_by_tenant_in_actual_database(api):
    from app.application.case_intake import create_case_once
    from app.infrastructure.db import repository

    tenant = "initial_scope_" + uuid4().hex[:12]
    customer = uuid4()
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants(tenant_id,name) VALUES (%s,'synthetic creation scope')", (tenant,))
                cur.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES (%s,%s,'synthetic')",
                            (customer, tenant))
            base = dict(repository=repository, request_id="shared-message-id", message="서울 점심 변경",
                        channel="trip_message", actor_type="api", actor_id="synthetic",
                        idempotency_key="same-key-in-independent-tenants", state_json={"travel_test": True})
            one = create_case_once(conn, tenant_id=api["tenant"], customer_id=api["customer"], **base)
            two = create_case_once(conn, tenant_id=tenant, customer_id=customer, **base)
            again = create_case_once(conn, tenant_id=tenant, customer_id=customer, **base)
            assert one.created and two.created and not again.created
            assert one.case_id != two.case_id == again.case_id
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM case_events WHERE case_id=%s AND event_type='created'", (two.case_id,))
                assert cur.fetchone()[0] == 1
        finally:
            # 이 시험이 만든 합성 행만 트랜잭션 전체를 되돌린다.
            conn.rollback()


@pytest.mark.parametrize("winner_state", ["running", "resolved"])
def test_routing_retry_loser_returns_conflict_after_winner_has_completed(decided, monkeypatch, winner_state):
    import asyncio

    from app.core.team_availability import TeamUnavailable
    from app.domains.travel_ops.components.conversation import case_dispatch

    original_prepare = case_dispatch._prepare_candidates

    def blocked(*args, **kwargs):
        raise TeamUnavailable("mobility", "engine_unavailable")

    monkeypatch.setattr(case_dispatch, "_prepare_candidates", blocked)
    request_id = "concurrent-routing-retry"
    assert _post(decided, "점심 다른 데로 바꿔", request_id).status_code == 503
    original_execute = case_dispatch.execute
    both_preflighted = Barrier(2, timeout=30)
    winner_done = Event()
    release_winner = Event()
    lock = Lock()
    prepared = [0]

    def execute(*args, **kwargs):
        # 두 요청 모두 동일 routing 스냅샷의 사전 점검과 commit을 끝낸 뒤 실행한다.
        both_preflighted.wait()
        return original_execute(*args, **kwargs)

    def prepare(*args, **kwargs):
        with lock:
            prepared[0] += 1
            position = prepared[0]
        if position == 2:
            assert winner_done.wait(30), "synthetic winner did not finish"
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(case_dispatch, "execute", execute)
    monkeypatch.setattr(case_dispatch, "_prepare_candidates", prepare)
    if winner_state == "running":
        executor = decided["client"].app.state.runtime.published_snapshot().controller.team_executor
        original_team_execute = executor.execute

        async def team_execute(task):
            winner_done.set()
            assert await asyncio.to_thread(release_winner.wait, 30), "synthetic loser did not finish"
            return await original_team_execute(task)

        monkeypatch.setattr(executor, "execute", team_execute)

    def post(_):
        try:
            answer = _post(decided, "점심 다른 데로 바꿔", request_id)
        except BaseException:
            release_winner.set()
            raise
        if answer.status_code == 200:
            winner_done.set()
        elif answer.status_code == 409:
            release_winner.set()
        return answer

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(post, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id,state_json,status FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s",
                    (request_id,))
        cases = cur.fetchall()
        assert len(cases) == 1 and cases[0][2] == "resolved"
        assert len(cases[0][1]["applied_actions"]) == 1
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (f"{decided['trip']['trip_id']}:v2",))
        assert cur.fetchone()[0] == 1
