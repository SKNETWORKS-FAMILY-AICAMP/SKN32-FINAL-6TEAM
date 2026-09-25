# -*- coding: utf-8 -*-
"""웹(고객 브라우저) 경로 — 사용자 식별 키 `X-User-Key`. `[2026-09-24]` D-020 · 마이그레이션 025

★사용자 결정 — 로그인 없이 키를 발급해 브라우저 저장소에 두고, 사용자에게도 한 번 보여 줘 보관하게 한다.
★지켜야 할 것: 키는 **그 사용자 본인의 여행**만 연다 · 원문은 저장하지 않는다 · 다시 발급하면 옛 키 무효.

재현:

    python -m pytest tests/e2e/test_web_api.py -v
"""
from __future__ import annotations

import copy

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.survey import SURVEY_VERSION

from .test_trip_api import SCENARIO, _body, api  # noqa: F401 — 픽스처를 그대로 쓴다


@pytest.fixture(autouse=True)
def _fresh_issue_counter(monkeypatch):
    """발급 속도 제한은 프로세스 안에서 센다 — 시험끼리 수가 쌓여 뒤 시험이 429 를 맞지 않게 비운다."""
    from app.modules.travel_ops import web_session

    monkeypatch.setattr(web_session, "_issued", {})


def _session(api) -> dict:
    response = api["client"].post("/v1/web/session")
    assert response.status_code == 201, response.text
    return response.json()


def _h(key: str) -> dict:
    return {"X-User-Key": key}


def _web_body(api, request_id="web-1", **constraints):
    body = _body(api["customer"], request_id=request_id)
    body.pop("customer_id")
    if constraints:
        body["constraints"] = {**copy.deepcopy(body["constraints"]), **constraints}
    return body


# ── 키 ──────────────────────────────────────────────────────────
def test_a_first_visit_gets_a_key_shown_once_and_stored_only_as_a_hash(api):
    session = _session(api)
    assert session["user_key"].startswith("acop_u_") and "보관" in session["notice"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT key_hash FROM web_user_keys WHERE customer_id=%s", (session["customer_id"],))
        [(stored,)] = cur.fetchall()
    assert stored != session["user_key"] and session["user_key"] not in stored     # ★원문은 없다


def test_without_a_key_or_with_a_wrong_one_nothing_opens(api):
    assert api["client"].get("/v1/web/trips").status_code == 401
    assert api["client"].get("/v1/web/trips", headers=_h("acop_u_nope")).status_code == 401
    assert api["client"].get("/v1/web/trips", headers=_h("not-our-key")).status_code == 401


def test_the_server_scope_key_does_not_open_the_web_paths(api):
    """★서버용 scope 키(테넌트 전체)는 웹 경로에서 받지 않는다 — 둘을 섞지 않는다."""
    response = api["client"].get("/v1/web/trips", headers=api["auth"]("trip:read"))
    assert response.status_code == 401


def test_rotating_kills_the_old_key(api):
    session = _session(api)
    fresh = api["client"].post("/v1/web/session/rotate", headers=_h(session["user_key"])).json()
    assert fresh["customer_id"] == session["customer_id"] and fresh["user_key"] != session["user_key"]
    assert api["client"].get("/v1/web/trips", headers=_h(session["user_key"])).status_code == 401
    assert api["client"].get("/v1/web/trips", headers=_h(fresh["user_key"])).status_code == 200


# ── 내 여행만 ────────────────────────────────────────────────────
def test_a_user_registers_under_their_own_name_only(api):
    me = _session(api)
    created = api["client"].post("/v1/web/trips", json=_web_body(api), headers=_h(me["user_key"]))
    assert created.status_code == 201, created.text
    assert created.json()["customer_id"] == me["customer_id"]

    forged = _web_body(api, request_id="web-forged")
    forged["customer_id"] = str(api["customer"])                # 남의 이름으로
    refused = api["client"].post("/v1/web/trips", json=forged, headers=_h(me["user_key"]))
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "customer_id_not_allowed"


def test_someone_elses_trip_does_not_exist_for_you(api):
    """★남의 여행은 **없는 것**과 같다(404) — 있는지도 말하지 않는다."""
    me, other = _session(api), _session(api)
    trip_id = api["client"].post("/v1/web/trips", json=_web_body(api),
                                 headers=_h(me["user_key"])).json()["trip_id"]
    for path in (f"/v1/web/trips/{trip_id}", f"/v1/web/trips/{trip_id}/proposals",
                 f"/v1/web/trips/{trip_id}/notices"):
        assert api["client"].get(path, headers=_h(other["user_key"])).status_code == 404, path
    said = api["client"].post(f"/v1/web/trips/{trip_id}/messages", headers=_h(other["user_key"]),
                              json={"request_id": "x", "message": "식당이 휴무예요"})
    assert said.status_code == 404
    assert api["client"].get("/v1/web/trips", headers=_h(other["user_key"])).json() == {"trips": []}
    [mine] = api["client"].get("/v1/web/trips", headers=_h(me["user_key"])).json()["trips"]
    assert mine["trip_id"] == trip_id


# ── 「먼저 물어봐줘」를 웹에서 고른다 ──────────────────────────────
def test_the_web_sees_the_question_chooses_and_a_late_click_gets_409(api):
    me = _session(api)
    body = _web_body(api, survey={"version": SURVEY_VERSION, "on_disruption": "ask_first"})
    trip_id = api["client"].post("/v1/web/trips", json=body, headers=_h(me["user_key"])).json()["trip_id"]
    api["tick"]("09:00")                                          # 바꾸지 않고 묻는다

    [proposal] = api["client"].get(f"/v1/web/trips/{trip_id}/proposals",
                                   headers=_h(me["user_key"])).json()["proposals"]
    assert proposal["status"] == "open" and proposal["options"][0]["rank"] == 1
    notices = api["client"].get(f"/v1/web/trips/{trip_id}/notices", headers=_h(me["user_key"])).json()["notices"]
    assert any(n["type"] == "proposal_request" and n["proposal_id"] == proposal["proposal_id"] for n in notices)

    url = f"/v1/web/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose"
    chosen = api["client"].post(url, json={"key": proposal["options"][0]["key"]}, headers=_h(me["user_key"]))
    assert chosen.status_code == 200 and chosen.json()["version"] == 2
    late = api["client"].post(url, json={"key": proposal["options"][0]["key"]}, headers=_h(me["user_key"]))
    assert late.status_code == 409 and late.json()["error"]["code"] == "already_decided"

    notices = api["client"].get(f"/v1/web/trips/{trip_id}/notices", headers=_h(me["user_key"])).json()["notices"]
    assert notices[-1]["type"] == "change_notice"


def test_the_agent_api_can_see_and_answer_the_same_question(api):
    """에이전트(서버 키)도 같은 제안을 보고 고를 수 있다 — 같은 규칙을 탄다."""
    body = _body(api["customer"], request_id="agent-ask")
    body["constraints"] = {**body["constraints"], "survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}}
    trip_id = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write")).json()["trip_id"]
    api["tick"]("09:00")
    [proposal] = api["client"].get(f"/v1/trips/{trip_id}/proposals",
                                   headers=api["auth"]("trip:read")).json()["proposals"]
    kept = api["client"].post(f"/v1/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose",
                              json={"key": None}, headers=api["auth"]("trip:write"))
    assert kept.status_code == 200 and kept.json() == {"status": "kept"}


def test_only_the_web_origin_may_call_from_a_browser(api):
    ok = api["client"].options("/v1/web/session", headers={
        "Origin": "http://127.0.0.1:3100", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-User-Key"})
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:3100"
    other = api["client"].options("/v1/web/session", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert other.headers.get("access-control-allow-origin") is None


def test_one_address_cannot_mint_users_without_end(api, monkeypatch):
    """★키 없이 열린 발급 경로 — 한 주소에서 한 시간에 정한 수까지만. 넘으면 429 + Retry-After."""
    from app.modules.travel_ops import web_session

    monkeypatch.setattr(web_session, "_issue_limit", lambda: (2, 3600.0))
    assert [api["client"].post("/v1/web/session").status_code for _ in range(2)] == [201, 201]
    third = api["client"].post("/v1/web/session")
    assert third.status_code == 429 and third.json()["error"]["code"] == "too_many_sessions"
    assert 0 < int(third.headers["retry-after"]) <= 3600
    # 이미 가진 키로 하는 일은 막지 않는다 — 막는 것은 **새로 찍어 내기**뿐이다
    assert api["client"].get("/v1/web/trips", headers=_h(_first_key(api))).status_code == 200


def _first_key(api) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM web_user_keys WHERE tenant_id=%s LIMIT 1", (api["tenant"],))
        [customer] = cur.fetchone()
    from app.modules.travel_ops.web_session import rotate

    with get_connection() as conn, conn.transaction():
        return rotate(conn, tenant_id=api["tenant"], customer_id=customer)
