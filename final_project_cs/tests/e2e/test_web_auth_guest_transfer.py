"""통합 소셜 인증: 실제 로컬 DB + mock 소셜 업체. 외부 인증 요청은 보내지 않는다."""
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from app.domains.travel_ops.modules.web_account import web_cookie
from app.domains.travel_ops.modules.web_account.web_session import new_customer
from app.infrastructure.db.session import get_connection
from .test_trip_api import api  # noqa: F401
from .test_web_cookie_session import cookies, _guest, WEB, NONCE  # noqa: F401


def flow(env, code, csrf=None, mode="login"):
    client = env["client"]
    headers = {"Origin": WEB, "X-CSRF-Token": csrf} if csrf else {}
    start = client.post("/v1/web/auth/google/start", headers=headers, json={"mode": mode, "client_nonce": NONCE})
    assert start.status_code == 200, start.text
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]
    callback = client.get("/v1/web/auth/google/callback", params={"state": state, "code": code})
    query = parse_qs(urlparse(callback.headers["location"]).query)
    return query


def exchange(env, ticket, nonce=NONCE):
    return env["client"].post("/v1/web/auth/exchange", json={"ticket": ticket, "client_nonce": nonce, "session": "cookie"})


def session_owner(env):
    with get_connection() as conn:
        return web_cookie.lookup(conn, tenant_id=env["tenant"], raw=env["client"].cookies.get(web_cookie.cookie_name())).customer_id


def seed_plan(env, customer):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        trip, intake = uuid4(), uuid4()
        cur.execute("INSERT INTO trips(trip_id,tenant_id,customer_id,title) VALUES (%s,%s,%s,'서울 여행')", (trip, env["tenant"], customer))
        cur.execute("INSERT INTO trip_intakes(intake_id,tenant_id,customer_id,stage) VALUES (%s,%s,%s,'received')", (intake, env["tenant"], customer))
        return trip, intake


def owner(env, table, column, ident):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT customer_id FROM {table} WHERE tenant_id=%s AND {column}=%s", (env["tenant"], ident))
        return cur.fetchone()[0]


def member(env, code):
    response = exchange(env, flow(env, code)["ticket"][0])
    assert response.status_code == 200, response.text
    customer = session_owner(env)
    env["client"].cookies.clear()
    return customer


def test_new_social_account_promotes_the_guest_and_keeps_intake_and_trip(cookies):
    session, _ = _guest(cookies)
    guest = session_owner(cookies)
    trip, intake = seed_plan(cookies, guest)
    result = exchange(cookies, flow(cookies, "sub-new", session["csrf_token"])["ticket"][0])
    assert result.status_code == 200 and result.json()["outcome"] == "created"
    assert session_owner(cookies) == guest
    assert owner(cookies, "trips", "trip_id", trip) == guest
    assert owner(cookies, "trip_intakes", "intake_id", intake) == guest
    assert result.json()["kind"] == "member"


def test_existing_member_receives_only_current_guest_plans_after_correct_nonce(cookies):
    target = member(cookies, "sub-existing")
    existing_trip, _ = seed_plan(cookies, target)
    session, old = _guest(cookies)
    guest = session_owner(cookies)
    trip, intake = seed_plan(cookies, guest)
    with get_connection() as conn, conn.transaction():
        other = new_customer(conn, tenant_id=cookies["tenant"])
    other_trip, _ = seed_plan(cookies, other)
    ticket = flow(cookies, "sub-existing", session["csrf_token"])["ticket"][0]
    assert owner(cookies, "trips", "trip_id", trip) == guest  # 콜백만으로 옮기지 않는다.
    assert exchange(cookies, ticket, "x" * 40).status_code == 410
    assert owner(cookies, "trip_intakes", "intake_id", intake) == guest
    result = exchange(cookies, ticket)
    assert result.status_code == 200, result.text
    assert session_owner(cookies) == target
    assert owner(cookies, "trips", "trip_id", trip) == target
    assert owner(cookies, "trip_intakes", "intake_id", intake) == target
    assert owner(cookies, "trips", "trip_id", existing_trip) == target
    assert owner(cookies, "trips", "trip_id", other_trip) == other
    with get_connection() as conn:
        assert web_cookie.lookup(conn, tenant_id=cookies["tenant"], raw=old) is None
    assert exchange(cookies, ticket).status_code == 410


def test_guest_legacy_link_to_existing_account_also_transfers(cookies):
    target = member(cookies, "sub-existing")
    session, _ = _guest(cookies)
    trip, _ = seed_plan(cookies, session_owner(cookies))
    query = flow(cookies, "sub-existing", session["csrf_token"], mode="link")
    assert "ticket" in query
    assert exchange(cookies, query["ticket"][0]).status_code == 200
    assert owner(cookies, "trips", "trip_id", trip) == target


def test_guest_login_start_requires_csrf_before_recording_source(cookies):
    _guest(cookies)
    denied = cookies["client"].post("/v1/web/auth/google/start", json={"mode": "login", "client_nonce": NONCE})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "csrf_failed"


def test_two_existing_members_are_not_merged(cookies):
    first = member(cookies, "sub-first")
    query = flow(cookies, "sub-second")
    response = exchange(cookies, query["ticket"][0])
    assert response.status_code == 200
    second = session_owner(cookies)
    trip, _ = seed_plan(cookies, second)
    csrf = response.json()["csrf_token"]
    assert flow(cookies, "sub-first", csrf, mode="link") == {"error": ["already_linked_elsewhere"]}
    assert owner(cookies, "trips", "trip_id", trip) == second and first != second


def test_member_switch_login_does_not_move_existing_member_trips(cookies):
    first = member(cookies, "sub-first")
    response = exchange(cookies, flow(cookies, "sub-second")["ticket"][0])
    second = session_owner(cookies)
    trip, _ = seed_plan(cookies, second)
    switch = exchange(cookies, flow(cookies, "sub-first", response.json()["csrf_token"])["ticket"][0])
    assert switch.status_code == 200 and session_owner(cookies) == first
    assert owner(cookies, "trips", "trip_id", trip) == second


def test_guest_promoted_during_pending_signin_is_not_merged_as_a_member(cookies):
    member(cookies, "sub-existing")
    session, _ = _guest(cookies)
    guest = session_owner(cookies)
    trip, _ = seed_plan(cookies, guest)
    pending = flow(cookies, "sub-existing", session["csrf_token"])["ticket"][0]
    promoted = exchange(cookies, flow(cookies, "sub-other-new", session["csrf_token"])["ticket"][0])
    assert promoted.status_code == 200
    refused = exchange(cookies, pending)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "guest_transfer_changed"
    assert owner(cookies, "trips", "trip_id", trip) == guest


def test_transferred_trip_with_open_case_keeps_web_proposal_access(cookies):
    from uuid import UUID
    from app.infrastructure.db import repository
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.planning.pending import Decision, PendingStore
    from .test_trip_api import _create

    target = member(cookies, "sub-existing")
    session, _ = _guest(cookies)
    guest = session_owner(cookies)
    trip_id = UUID(_create(cookies, customer_id=str(guest))["trip_id"])
    with get_connection() as conn, conn.transaction():
        trip, items = TripStore(cookies["tenant"]).latest(conn, trip_id)
        case_id = repository.create_case(conn, tenant_id=cookies["tenant"], customer_id=guest,
                                         subject="서울 일정 변경 검토", state_json={"trip_id": str(trip_id)})
        item = next(item for item in items if item.kind == "activity")
        proposal = PendingStore(cookies["tenant"]).open(
            conn, trip_id=trip_id, item=item, base_version=trip["version"],
            decision=Decision("ask", "ask_first", None, False), causes=[{"case_id": str(case_id)}], options=[])
    result = exchange(cookies, flow(cookies, "sub-existing", session["csrf_token"])["ticket"][0])
    assert result.status_code == 200
    assert owner(cookies, "trips", "trip_id", trip_id) == target
    # Case는 발생 당시 고객을 보존한다. 현재 여행 소유자가 제안 조회·선택 권한을 갖는다.
    assert owner(cookies, "customer_cases", "case_id", case_id) == guest
    listed = cookies["client"].get(f"/v1/web/trips/{trip_id}/proposals")
    assert listed.status_code == 200 and listed.json()["proposals"][0]["proposal_id"] == str(proposal)
    chosen = cookies["client"].post(f"/v1/web/trips/{trip_id}/proposals/{proposal}/choose",
        headers={"Origin": WEB, "X-CSRF-Token": result.json()["csrf_token"]}, json={"key": None})
    assert chosen.status_code == 200 and chosen.json()["status"] == "kept", chosen.text
    # 다른 게스트로는 같은 여행의 제안에 접근할 수 없다.
    cookies["client"].cookies.clear()
    _guest(cookies)
    assert cookies["client"].get(f"/v1/web/trips/{trip_id}/proposals").status_code == 404


def test_guest_cleanup_preserves_case_history_of_member_transferred_trip(cookies):
    from app.core.case_lifecycle.events import EventType
    from app.core.transition import transition_case
    from app.infrastructure.db import repository
    from app.domains.travel_ops.modules.web_account.guest_cleanup import cleanup_guests

    member(cookies, "sub-existing")
    session, _ = _guest(cookies)
    guest = session_owner(cookies)
    trip, _ = seed_plan(cookies, guest)
    cases = []
    with get_connection() as conn, conn.transaction():
        for state in ({"subject_ref": {"kind": "trip", "id": str(trip)}},
                      {"trip_message": {"trip_id": str(trip), "request_id": "retention-test"}},
                      {"trip_id": str(trip)}):
            case = repository.create_case(conn, tenant_id=cookies["tenant"], customer_id=guest,
                                          subject="서울 여행 검토", state_json=state)
            transition_case(conn, tenant_id=cookies["tenant"], case_id=case, expected_version=0,
                            event_type=EventType.CREATED, payload={"channel": "web", "message": "서울 여행 검토"},
                            actor_type="api", actor_id="test")
            cases.append(case)
    assert exchange(cookies, flow(cookies, "sub-existing", session["csrf_token"])["ticket"][0]).status_code == 200
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        unrelated = new_customer(conn, tenant_id=cookies["tenant"])
        cur.execute("UPDATE customers SET created_at=now()-interval '10 days' WHERE tenant_id=%s AND customer_id = ANY(%s)",
                    (cookies["tenant"], [guest, unrelated]))
        cur.execute("UPDATE web_sessions SET created_at=now()-interval '10 days', last_used_at=now()-interval '10 days' "
                    "WHERE tenant_id=%s AND customer_id=%s", (cookies["tenant"], guest))
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        result = cleanup_guests(conn, cookies["tenant"])
        assert result["customers_deleted"] == 1  # 관계 없는 만료 게스트는 정상 정리한다.
        for case in cases:
            assert repository.get_case(conn, tenant_id=cookies["tenant"], case_id=case) is not None
            cur.execute("SELECT count(*) FROM case_events WHERE tenant_id=%s AND case_id=%s", (cookies["tenant"], case))
            assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM customers WHERE tenant_id=%s AND customer_id=%s", (cookies["tenant"], guest))
        assert cur.fetchone()[0] == 1
        # 연결 여행이 사라지면 원래 보관기간에 따른 정리로 돌아간다.
        cur.execute("DELETE FROM trips WHERE tenant_id=%s AND trip_id=%s", (cookies["tenant"], trip))
        released = cleanup_guests(conn, cookies["tenant"])
        assert released["customers_deleted"] == 1
        assert all(repository.get_case(conn, tenant_id=cookies["tenant"], case_id=case) is None for case in cases)
