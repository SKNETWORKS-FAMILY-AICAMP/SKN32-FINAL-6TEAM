# -*- coding: utf-8 -*-
"""여행 삭제 · 게스트 제한 · 게스트 정리. `[2026-10-04 사용자 결정 — D-CS-011]`

계약: `wiki/external/rest-endpoints.md` 「여행 삭제」 · 「게스트」 · 요청서 `wiki/records/plans/2026-10-03_1920_웹_실서버_전환_백엔드_요청.md` 「구현 지침」
구현: `trip_delete.py` · `guest_policy.py` · `guest_cleanup.py` · `itinerary.py`(감시 대상에서 게스트 제외)

★지키려는 것
 ①삭제는 즉시 · 완전 — 목록 · 조회에서 사라지고, 외래키 없는 표(대화 · 영업 확인 · 요식 알림 · 접수 · 전용 장소 · 바깥함 알림)도 같이 지워진다. 남의 것은 안 건드린다
 ②남의 여행 · 없는 여행 · 이미 지운 여행은 **같은 404**. 열린 Case 는 전이표가 허용하는 정상 전이로 닫히고(`case_events` 는 안 지운다), 해결된 Case 는 그대로
 ③여행 번호를 들고 있는 표 목록이 **빠짐없다**(새 표가 생기면 이 시험이 걸린다)
 ④게스트는 여행 1개(동시 생성까지) · 시작 365일 · 길이 7일, 회원과 에이전트 API 고객은 제한이 없다. 게스트의 여행은 감시 · 안내 대상이 아니다
 ⑤게스트 정리는 마지막 사용 뒤 보존 시간이 지난 게스트만, 일정이 남았으면 종료 + 유예(상한 마지막 사용 + 180일)까지 둔다. 회원 · 에이전트 고객은 안 건드린다. 기록이 가리키면 사용자 행만 남긴다

재현:

    python -m pytest tests/e2e/test_guest_and_trip_delete.py -v
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.modules.web_account.guest_cleanup import cleanup_guests
from app.domains.travel_ops.components.itinerary.itinerary import TripStore

from .test_trip_api import _body, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401


def _make_trip(env, client=None, request_id=None, **override) -> tuple[int, dict]:
    """쿠키 세션으로 여행을 만든다 — (상태 코드, 몸통). 사용자 번호는 서버가 정한다."""
    client = client or env["client"]
    csrf = client.get("/v1/web/auth/me").json()["csrf_token"]
    body = {k: v for k, v in _body(uuid4(), request_id or f"r-{uuid4().hex[:8]}", **override).items() if k != "customer_id"}
    response = client.post("/v1/web/trips", json=body, headers={"Origin": WEB, "X-CSRF-Token": csrf})
    return response.status_code, response.json()


def _customer_of(env, client=None) -> UUID:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM web_sessions WHERE tenant_id=%s AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1", (env["tenant"],))
        return cur.fetchone()[0]


def _delete(env, trip_id, client=None):
    client = client or env["client"]
    csrf = client.get("/v1/web/auth/me").json()["csrf_token"]
    return client.post(f"/v1/web/trips/{trip_id}/delete", headers={"Origin": WEB, "X-CSRF-Token": csrf})


def _count(sql: str, *params) -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return int(cur.fetchone()[0])


def _link(env, customer: UUID) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,'google',%s,%s)",
                    (env["tenant"], "h-" + uuid4().hex, customer))


# ── ① ② 삭제 ─────────────────────────────────────────────────────
def test_delete_removes_the_trip_and_everything_tied_to_it_but_nothing_else(cookies):
    _guest(cookies)
    status, trip = _make_trip(cookies)
    assert status == 201
    trip_id, tenant, customer = UUID(trip["trip_id"]), cookies["tenant"], _customer_of(cookies)
    # 다른 여행 하나(같은 사용자 · 회원으로 바꿔 둔다 — 게스트는 1개뿐)
    _link(cookies, customer)
    other_status, other = _make_trip(cookies)
    assert other_status == 201
    other_id = UUID(other["trip_id"])
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO dining.dn_place (name_ko, area, record_status) VALUES ('삭제시험', '종로구', 'active') RETURNING place_uid")
        dining_place = cur.fetchone()[0]                      # 요식 알림이 가리키는 장소(시험이 끝나면 지운다)
        for target in (trip_id, other_id):
            cur.execute("INSERT INTO trip_chat_turns (tenant_id, trip_id, role, text) VALUES (%s,%s,'customer','안녕')", (tenant, target))
            cur.execute("INSERT INTO place_open_checks (tenant_id, trip_id, item_id, day, place_id, verdict, source) "
                        "VALUES (%s,%s,%s,current_date,%s,'open','test')", (tenant, target, uuid4(), uuid4()))
            cur.execute("INSERT INTO dining.dn_notice (place_uid, target_at, kind, body, based_on, tenant_id, trip_id) "
                        "VALUES (%s, now(), 'closed', 'b', 'x', %s, %s)", (dining_place, tenant, target))
            cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, status, trip_id) VALUES (%s,%s,'confirmed',%s)", (tenant, customer, target))
            cur.execute("INSERT INTO places (place_id, tenant_id, name, kind, latitude, longitude, trip_scope) "
                        "VALUES (%s,%s,'전용','activity',37.5,127.0,%s)", (uuid4(), tenant, target))
    assert _count("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice' AND dedupe_key LIKE %s", tenant, f"{trip_id}:%") > 0

    response = _delete(cookies, trip_id)
    assert response.status_code == 200 and response.json() == {"trip_id": str(trip_id), "status": "deleted"}
    mine = (tenant, trip_id)
    for sql in ("SELECT count(*) FROM trips WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM itinerary_items WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM trip_chat_turns WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM place_open_checks WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM dining.dn_notice WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM trip_intakes WHERE tenant_id=%s AND trip_id=%s",
                "SELECT count(*) FROM places WHERE tenant_id=%s AND trip_scope=%s"):
        assert _count(sql, *mine) == 0, sql
    assert _count("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice' AND dedupe_key LIKE %s", tenant, f"{trip_id}:%") == 0
    # 다른 여행은 그대로
    assert _count("SELECT count(*) FROM trips WHERE tenant_id=%s AND trip_id=%s", tenant, other_id) == 1
    assert _count("SELECT count(*) FROM trip_chat_turns WHERE tenant_id=%s AND trip_id=%s", tenant, other_id) == 1
    assert _count("SELECT count(*) FROM places WHERE tenant_id=%s AND trip_scope=%s", tenant, other_id) == 1
    assert cookies["client"].get("/v1/web/trips").json()["trips"][0]["trip_id"] == str(other_id)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:                # 시험이 만든 요식 줄을 치운다(공용 표)
        cur.execute("DELETE FROM dining.dn_notice WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM dining.dn_place WHERE place_uid=%s", (dining_place,))


def test_someone_elses_missing_and_already_deleted_trips_are_the_same_404(cookies):
    _guest(cookies)
    _, trip = _make_trip(cookies)
    trip_id = trip["trip_id"]
    stranger = TestClient(cookies["client"].app, follow_redirects=False)
    stranger.post("/v1/web/auth/session", headers={"X-Forwarded-For": cookies["ip"]})
    foreign = _delete(cookies, trip_id, client=stranger)
    missing = _delete(cookies, uuid4())
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"error": {"code": "not_found", "message": "resource not found"}}
    assert _count("SELECT count(*) FROM trips WHERE tenant_id=%s AND trip_id=%s", cookies["tenant"], UUID(trip_id)) == 1   # 남의 요청은 안 지웠다
    assert _delete(cookies, trip_id).status_code == 200
    again = _delete(cookies, trip_id)
    assert again.status_code == 404 and again.json() == missing.json()                                                # 두 번째 호출


def test_open_cases_about_the_trip_are_closed_by_normal_transitions_and_resolved_ones_stay(cookies):
    _guest(cookies)
    _, trip = _make_trip(cookies)
    trip_id, tenant, customer = UUID(trip["trip_id"]), cookies["tenant"], _customer_of(cookies)
    subject = '{"subject_ref": {"kind": "trip", "id": "%s"}}' % trip_id
    cases = {status: uuid4() for status in ("running", "waiting_input", "escalated", "resolved", "cancelled")}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for status, case_id in cases.items():
            cur.execute("INSERT INTO customer_cases (case_id, tenant_id, customer_id, status, subject, state_json, version) "
                        "VALUES (%s,%s,%s,%s::case_status,'t',%s::jsonb,3)", (case_id, tenant, customer, status, subject))
    assert _delete(cookies, trip_id).status_code == 200
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id, status::text, version FROM customer_cases WHERE tenant_id=%s", (tenant,))
        after = {row[0]: row[1:] for row in cur.fetchall()}
        cur.execute("SELECT event_type, actor_id FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version", (tenant, cases["running"]))
        events = cur.fetchall()
    assert after[cases["running"]] == ("cancelled", 5)            # running → guardrail_escalated → escalated → cancelled (3걸음)
    assert after[cases["waiting_input"]] == ("cancelled", 5)      # wait_expired → escalated → cancelled
    assert after[cases["escalated"]] == ("cancelled", 4)          # cancelled_by_user 한 걸음
    assert after[cases["resolved"]] == ("resolved", 3)            # 해결된 Case 는 기록이라 그대로
    assert after[cases["cancelled"]] == ("cancelled", 3)
    assert [event for event, _ in events] == ["guardrail_escalated", "cancelled_by_user"]         # 전이표가 허용하는 정상 전이만 — 두 걸음
    assert all(actor == "trip_delete" for _, actor in events)


def test_every_table_that_carries_a_trip_number_is_accounted_for():
    """새 표가 `trip_id`(또는 `trip_scope`)를 들고 생기면 여기서 걸린다 — 삭제 목록에 넣거나, 외래키 CASCADE 로 두거나, 이유와 함께 이 목록에 더한다."""
    handled = {
        "trips", "itinerary_versions", "itinerary_items", "pending_changes",           # trips 를 지우면 CASCADE
        "trip_guardian_changes",                                                       # 항로 지킴이 켜고 끈 기록(050) — trips 를 지우면 CASCADE
        "trip_safety_pauses",                                                          # 재난 시 일정 정지(052) — trips 를 지우면 CASCADE
        "trip_chat_turns", "place_open_checks", "dining.dn_notice",                    # trip_delete._PURGE
        "trip_intakes",                                                                # trip_delete 가 이름을 대어 지운다
        "places",                                                                      # trip_scope — trip_delete 가 지운다
    }
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT table_schema, table_name FROM information_schema.columns WHERE column_name IN ('trip_id','trip_scope') "
                    "AND table_schema NOT IN ('pg_catalog','information_schema')")
        found = {(f"{s}.{t}" if s != "public" else t) for s, t in cur.fetchall()}
        cur.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='v'")
        views = {r[0] for r in cur.fetchall()}
    unknown = found - handled - views
    assert not unknown, f"여행 번호를 들고 있는데 삭제 목록에 없는 표: {sorted(unknown)}"


# ── 계획서 내려받기 ───────────────────────────────────────────────
def test_the_plan_link_can_be_downloaded_as_a_file_without_logging_in(cookies):
    """게스트 데이터는 보존 시간 뒤 지워진다 — 계획서 링크에 `download=1` 을 붙이면 같은 페이지를 **파일로** 받는다(로그인 없음 · 링크가 곧 자격)."""
    from app.domains.travel_ops.components.itinerary.plan_link import plan_token

    _guest(cookies)
    status, trip = _make_trip(cookies)
    assert status == 201
    trip_id, token = trip["trip_id"], plan_token(cookies["tenant"], UUID(trip["trip_id"]))
    anon = TestClient(cookies["client"].app)
    shown = anon.get(f"/plan/{trip_id}", params={"t": token})
    assert shown.status_code == 200 and "content-disposition" not in shown.headers          # 그냥 열면 보기만
    got = anon.get(f"/plan/{trip_id}", params={"t": token, "download": "1"})
    assert got.status_code == 200 and got.text == shown.text                                # 같은 내용
    disposition = got.headers["content-disposition"]
    assert disposition.startswith("attachment;") and "filename*=UTF-8''triPilot-" in disposition and disposition.endswith(".html")
    assert "/" not in disposition.split("filename*=UTF-8''")[1]                              # 제목의 경로 글자는 이름에 안 들어간다
    assert "<script src" not in got.text and "<link " not in got.text                      # 외부 파일 없이 혼자 열린다
    assert anon.get(f"/plan/{trip_id}", params={"t": "wrong", "download": "1"}).status_code == 404   # 틀린 토큰은 있는지도 말하지 않는다


# ── ④ 게스트 제한 ─────────────────────────────────────────────────
def test_a_guest_gets_one_trip_and_is_asked_to_log_in_for_a_second(cookies):
    _guest(cookies)
    assert _make_trip(cookies)[0] == 201
    status, body = _make_trip(cookies)
    assert status == 403
    assert body["error"]["code"] == "guest_trip_limit" and body["error"]["login_required"] is True and body["error"]["cap"] == 1
    _link(cookies, _customer_of(cookies))                                    # 소셜 계정이 붙으면 같은 사용자가 회원이다
    assert _make_trip(cookies)[0] == 201


def test_two_simultaneous_creations_make_only_one_trip_for_a_guest(cookies):
    _guest(cookies)
    results: list[int] = []

    def go(n: int):
        results.append(_make_trip(cookies, client=cookies["client"], request_id=f"race-{n}")[0])

    threads = [threading.Thread(target=go, args=(n,)) for n in range(3)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201, 403, 403], results
    assert _count("SELECT count(*) FROM trips WHERE tenant_id=%s", cookies["tenant"]) == 1


def test_guest_trip_dates_are_bounded(cookies):
    """시작이 너무 먼 여행 · 너무 긴 여행 — 규칙 함수를 직접 부른다(API 는 일정 판정이 먼저라 이 규칙까지 못 오는 몸통이 있다)."""
    from app.domains.travel_ops.modules.web_account import guest_policy

    _guest(cookies)
    customer = _customer_of(cookies)
    now = datetime.now().astimezone()
    with get_connection() as conn, conn.transaction():
        guest_policy.check_new_trip(conn, tenant_id=cookies["tenant"], customer_id=customer,
                                    starts=[now + timedelta(days=364)], ends=[now + timedelta(days=370)])      # 안쪽 — 통과
        for starts, ends, code in (([now + timedelta(days=366)], [now + timedelta(days=367)], "guest_trip_too_far"),
                                   ([now + timedelta(days=1)], [now + timedelta(days=9)], "guest_trip_too_long")):
            try:
                guest_policy.check_new_trip(conn, tenant_id=cookies["tenant"], customer_id=customer, starts=starts, ends=ends)
            except guest_policy.GuestLimit as refused:
                assert refused.detail["error"]["code"] == code and refused.detail["error"]["login_required"] is True
            else:
                raise AssertionError(f"{code} 로 막혀야 한다")


def test_agent_api_customers_have_no_guest_limit(api):
    for n in range(3):
        assert api["client"].post("/v1/trips", json=_body(api["customer"], f"agent-{n}"), headers=api["auth"]("trip:write")).status_code == 201


def test_a_guests_trip_is_not_watched_but_a_members_is(cookies):
    _guest(cookies)
    assert _make_trip(cookies)[0] == 201
    store = TripStore(cookies["tenant"])
    with get_connection() as conn:
        everything = datetime.now().astimezone() - timedelta(days=4000), datetime.now().astimezone() + timedelta(days=4000)
        assert store.active_trip_ids(conn) == [] and store.due(conn, start=everything[0], end=everything[1]) == []
    _link(cookies, _customer_of(cookies))
    with get_connection() as conn:
        assert len(store.active_trip_ids(conn)) == 1 and store.due(conn, start=everything[0], end=everything[1])


# ── ⑤ 게스트 정리 ────────────────────────────────────────────────
def _age(env, customer: UUID, days: float) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_sessions SET last_used_at = now() - make_interval(hours => %s), created_at = now() - make_interval(hours => %s) "
                    "WHERE tenant_id=%s AND customer_id=%s", (int(days * 24), int(days * 24), env["tenant"], customer))
        cur.execute("UPDATE customers SET created_at = now() - make_interval(hours => %s) WHERE tenant_id=%s AND customer_id=%s",
                    (int(days * 24), env["tenant"], customer))


def _new_guest_with_trip(env, *, days_idle: float, trip: bool = True) -> UUID:
    browser = TestClient(env["client"].app, follow_redirects=False)
    browser.post("/v1/web/auth/session", headers={"X-Forwarded-For": env["ip"]})
    env2 = {**env, "client": browser}
    customer = _customer_of(env2)
    if trip:
        assert _make_trip(env2)[0] == 201
    _age(env, customer, days_idle)
    return customer


def _exists(env, customer: UUID) -> bool:
    return _count("SELECT count(*) FROM customers WHERE tenant_id=%s AND customer_id=%s", env["tenant"], customer) == 1


def _set_trip_end(env, customer: UUID, *, days_from_now: float) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE itinerary_items i SET starts_at = now() + make_interval(hours => %s) - interval '1 hour', "
                    "ends_at = now() + make_interval(hours => %s) FROM trips t WHERE t.trip_id=i.trip_id AND t.latest_version=i.version "
                    "AND t.tenant_id=%s AND t.customer_id=%s", (int(days_from_now * 24), int(days_from_now * 24), env["tenant"], customer))


def test_only_expired_guests_are_deleted_with_their_trips(cookies):
    old = _new_guest_with_trip(cookies, days_idle=8)                       # 기본 보존 7일을 넘겼다 — 일정은 이미 지난 날짜
    fresh = _new_guest_with_trip(cookies, days_idle=2)
    member = _new_guest_with_trip(cookies, days_idle=30)
    _link(cookies, member)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:   # 에이전트 API 로 만든 고객 — `web:` 이 아니다
        cur.execute("UPDATE customers SET created_at = now() - interval '400 days' WHERE tenant_id=%s AND external_id='taiwan-friends'", (cookies["tenant"],))
    with get_connection() as conn:
        result = cleanup_guests(conn, cookies["tenant"])
    assert result == {"candidates": 1, "held_for_trips": 0, "customers_deleted": 1, "customers_kept": 0, "trips_deleted": 1}, result
    assert not _exists(cookies, old) and _exists(cookies, fresh) and _exists(cookies, member)
    assert _count("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s", cookies["tenant"], old) == 0
    assert _count("SELECT count(*) FROM customers WHERE tenant_id=%s AND external_id='taiwan-friends'", cookies["tenant"]) == 1
    assert _count("SELECT count(*) FROM web_sessions WHERE tenant_id=%s AND customer_id=%s", cookies["tenant"], old) == 0


def test_a_guest_with_a_trip_still_to_come_is_held_until_the_trip_ends_plus_grace(cookies):
    guest = _new_guest_with_trip(cookies, days_idle=10)
    _set_trip_end(cookies, guest, days_from_now=20)                         # 20일 뒤 끝난다
    with get_connection() as conn:
        held = cleanup_guests(conn, cookies["tenant"])
    assert held["held_for_trips"] == 1 and held["customers_deleted"] == 0 and _exists(cookies, guest)
    _set_trip_end(cookies, guest, days_from_now=-4)                         # 종료 뒤 4일 — 유예 3일이 지났다
    with get_connection() as conn:
        done = cleanup_guests(conn, cookies["tenant"])
    assert done["customers_deleted"] == 1 and not _exists(cookies, guest)


def test_the_keep_cap_is_measured_from_the_last_use_not_from_now(cookies):
    """일정이 아주 먼 미래여도 마지막 사용 + 180일(+유예 3일)이 지나면 지운다 — 날짜를 빌미로 영구히 남지 않는다."""
    guest = _new_guest_with_trip(cookies, days_idle=185)
    _set_trip_end(cookies, guest, days_from_now=400)
    with get_connection() as conn:
        result = cleanup_guests(conn, cookies["tenant"])
    assert result["customers_deleted"] == 1 and not _exists(cookies, guest)
    recent = _new_guest_with_trip(cookies, days_idle=100)
    _set_trip_end(cookies, recent, days_from_now=400)
    with get_connection() as conn:
        assert cleanup_guests(conn, cookies["tenant"])["held_for_trips"] == 1
    assert _exists(cookies, recent)


def test_a_guest_a_record_points_at_keeps_only_the_empty_user_row(cookies):
    guest = _new_guest_with_trip(cookies, days_idle=9)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:   # 해결된 Case — 기록이라 지우지 않는다
        cur.execute("INSERT INTO customer_cases (tenant_id, customer_id, status, subject, state_json, version) "
                    "VALUES (%s,%s,'resolved','t','{}'::jsonb,1)", (cookies["tenant"], guest))
    with get_connection() as conn:
        result = cleanup_guests(conn, cookies["tenant"])
    assert result["customers_kept"] == 1 and result["customers_deleted"] == 0 and result["trips_deleted"] == 1, result
    assert _exists(cookies, guest)                                           # 이메일도 이름도 없는 무작위 번호 한 줄
    assert _count("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s", cookies["tenant"], guest) == 0
    assert _count("SELECT count(*) FROM web_sessions WHERE tenant_id=%s AND customer_id=%s", cookies["tenant"], guest) == 0
    assert _count("SELECT count(*) FROM customer_cases WHERE tenant_id=%s AND customer_id=%s", cookies["tenant"], guest) == 1


def test_guest_cleanup_does_nothing_when_switched_off_and_follows_the_operator_hours(cookies):
    guest = _new_guest_with_trip(cookies, days_idle=2, trip=False)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,'web.guest_cleanup_enabled','false'::jsonb,'test')",
                    (cookies["tenant"],))
    web_guard.clear_cache()
    with get_connection() as conn:
        assert cleanup_guests(conn, cookies["tenant"]) == {"skipped": "disabled"}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:   # 켜고 보존을 24시간으로 줄이면 2일 된 게스트가 후보가 된다
        cur.execute("UPDATE runtime_limits SET value='true'::jsonb WHERE tenant_id=%s AND name='web.guest_cleanup_enabled'", (cookies["tenant"],))
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,'web.guest_idle_hours',to_jsonb(24),'test')",
                    (cookies["tenant"],))
    web_guard.clear_cache()
    with get_connection() as conn:
        assert cleanup_guests(conn, cookies["tenant"])["customers_deleted"] == 1
    assert not _exists(cookies, guest)


def test_the_sweeper_job_runs_the_guest_cleanup(cookies):
    from scripts.run_sweepers import _run_web_guard

    result = _run_web_guard(cookies["tenant"])
    assert "guests" in result and "idle_keys" not in result
