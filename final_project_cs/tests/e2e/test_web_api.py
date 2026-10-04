# -*- coding: utf-8 -*-
"""웹(고객 브라우저) 경로 — 사용자 식별 키 `X-User-Key`. `[2026-09-24]` D-020 · 마이그레이션 025

★사용자 결정 — 로그인 없이 키를 발급해 브라우저 저장소에 두고, 사용자에게도 한 번 보여 줘 보관하게 한다.
★지켜야 할 것: 키는 **그 사용자 본인의 여행**만 연다 · 원문은 저장하지 않는다 · 다시 발급하면 옛 키 무효.

재현:

    python -m pytest tests/e2e/test_web_api.py -v
"""
from __future__ import annotations

from pathlib import Path

import copy

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.survey import SURVEY_VERSION

from .test_trip_api import DAY, SCENARIO, _body, api  # noqa: F401 — 픽스처를 그대로 쓴다


@pytest.fixture(autouse=True)
def _fresh_limit_cache():
    """제한값은 프로세스가 잠깐 캐시한다(`web_guard.values`) — 시험끼리 섞이지 않게 비운다.
    ★사용량은 DB(`web_usage`)에서 **테넌트별로** 센다 — 시험마다 새 테넌트라 쌓이지 않는다."""
    from app.modules.travel_ops import web_guard

    web_guard.clear_cache()
    yield
    web_guard.clear_cache()


def _override(api, name, value):
    """운영자가 바꾼 값처럼 넣는다(`runtime_limits`) — 운영 API 를 거치지 않는 짧은 길."""
    from psycopg.types.json import Json

    from app.modules.travel_ops import web_guard

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,%s,%s,'test') "
                    "ON CONFLICT (tenant_id, name) DO UPDATE SET value=EXCLUDED.value", (api["tenant"], name, Json(value)))
    web_guard.clear_cache()


def _session(api) -> dict:
    response = api["client"].post("/v1/web/session")
    assert response.status_code == 201, response.text
    return response.json()


def _h(key: str) -> dict:
    return {"X-User-Key": key}


def _member(api, user_key: str) -> None:
    """이 키의 사용자에게 소셜 계정을 붙인다 — **회원**이다. 게스트(로그인 안 한 웹 사용자)는 여행 1개 · 감시 불가라서(D-CS-011), 여러 여행을 만들거나 감시를 받는 시험은 회원으로 한다."""
    from uuid import uuid4

    from app.modules.travel_ops.web_session import resolve

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        customer = resolve(conn, tenant_id=api["tenant"], raw=user_key)
        cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,'google',%s,%s)",
                    (api["tenant"], "h-" + uuid4().hex, customer))


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


def test_a_no_change_result_carries_the_same_answer_as_the_conversation_path(api):
    """★`[2026-09-27]` 웹 채팅이 상태값(`no_meal`)만 받아 원래 이름을 그대로 보였다(실제 화면). 대화 경로와 같은
    문장표(`itinerary_team.ANSWERS`)의 답을 싣는다 — 웹이 문장을 지어내지 않게. 항목에는 지도 핀 좌표가 붙는다."""
    from app.modules.travel_ops.itinerary_team import ANSWERS

    me = _session(api)
    trip = api["client"].post("/v1/web/trips", json=_web_body(api), headers=_h(me["user_key"])).json()
    said = api["client"].post(f"/v1/web/trips/{trip['trip_id']}/messages", headers=_h(me["user_key"]),
                              json={"request_id": "late-closed", "message": "식당이 휴무예요",
                                    "at": "2030-01-01T12:00:00+09:00"}).json()
    assert said["status"] == "no_meal" and said["answer"] == ANSWERS["no_meal"]
    placed = [item for item in trip["items"] if item["place"]]
    assert placed and all(isinstance(item["lat"], float) and isinstance(item["lon"], float) for item in placed)
    # ★`[2026-09-28]` 전에는 「전부 False」를 봤다 — 시나리오의 「성수 점심 식사(예약)」(`detail.reserved`)도 False 라서
    #   예약 항목에 예약 표시가 안 나오던 결함을 시험이 정상으로 굳혀 두었다. 예약 항목만 True 다
    assert {item["title"] for item in trip["items"] if item["booked"]} == {"성수 점심 식사(예약)"}


@pytest.fixture()
def dev_mode(monkeypatch):
    """★`[2026-09-29 사용자 지시]` 근거(`basis`)·해석 결과(`decision`)는 개발 모드(`web.dev_mode = on`)일 때만 웹에 실린다 —
    그 칸을 읽는 시험은 개발 모드를 켜고 본다."""
    from app.modules.travel_ops import web_guard

    real = web_guard.values
    monkeypatch.setattr(web_guard, "values", lambda tenant: {**real(tenant), "web.dev_mode": "on"})


# ── 「먼저 물어봐줘」를 웹에서 고른다 ──────────────────────────────
def test_the_web_sees_the_question_chooses_and_a_late_click_gets_409(api):
    me = _session(api)
    _member(api, me["user_key"])                                  # 감시를 받는 사용자 — 게스트의 여행은 감시 대상이 아니다
    body = _web_body(api, survey={"version": SURVEY_VERSION, "on_disruption": "ask_first"})
    trip_id = api["client"].post("/v1/web/trips", json=body, headers=_h(me["user_key"])).json()["trip_id"]
    api["tick"]("09:00")                                          # 바꾸지 않고 묻는다

    # ★`[2026-09-29]` 활동 날씨 대체는 먼저 「바꿀까요?」(안 없음) — 웹이 「바꿔 줘」(key "change")를 보내면 그때 계산한다
    [asked] = api["client"].get(f"/v1/web/trips/{trip_id}/proposals",
                                headers=_h(me["user_key"])).json()["proposals"]
    assert asked["reason"] == "indoor_unknown" and asked["options"] == []
    said = api["client"].post(f"/v1/web/trips/{trip_id}/proposals/{asked['proposal_id']}/choose",
                              json={"key": "change"}, headers=_h(me["user_key"]))
    assert said.status_code == 200 and said.json()["status"] == "options", said.text
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
    _override(api, "web.session.per_ip_hour", 2)
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


# ── 채팅은 늘 답한다 (2026-09-28, ui 세션 인계 · 사용자 지시) ───────────────────
class _Chunk:
    def __init__(self, content, source_id, score):
        self.content, self.source_id, self.score = content, source_id, score


class _Talk:
    """추출기 흉내 — 문장에 맞는 신고 종류를 낸다."""

    def json(self, system, message):
        if "늦을" in message:
            return {"type": "delay", "minutes": 30, "products": []}
        if "바꿔" in message:
            return {"type": "change", "minutes": None, "products": []}
        if "?" in message or "요?" in message:
            return {"type": "question"}
        return {"type": "other"}


def _chat_client(api, search=None, place=None, classifier_down=False):
    from fastapi.testclient import TestClient

    from app.modules.travel_ops.trip_api import build_trip_router
    from app.presentation.api.app import create_app

    def classify(message):
        if classifier_down:
            raise TimeoutError("model is waking up")          # 원격 모델이 잠들어 첫 호출이 시간 초과
        if "늦을" in message:
            return {"intent": "incident_report", "issue_code": "dining_hours", "sentiment": "negative"}
        return {"intent": "confirm_request", "issue_code": "other", "sentiment": "neutral"}

    return TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(classifier_factory=lambda: classify, chat_factory=_Talk,
                                          policy_search_factory=(lambda: search) if search else None,
                                          place_factory=(lambda: place) if place else None)]))


def _say(client, key, trip_id, text, request_id):
    response = client.post(f"/v1/web/trips/{trip_id}/messages", headers=_h(key),
                           json={"request_id": request_id, "message": text, "at": "2030-01-01T09:00:00+09:00"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("answer"), body                       # ★어떤 결과든 답 문장이 있다
    assert "담당자에게 넘겼어요" not in body["answer"]      # ★무엇을 확인하는지 말한다
    return body


def test_a_policy_question_is_answered_with_the_customer_line_of_that_rule_not_the_staff_text(api):
    """★`[2026-09-28 사용자 결정]` 규정 문서는 직원에게 쓴 글이다 — 조각 원문이 아니라 그 절의 **고객용 문장**을 싣는다
    (ui 세션 실서버 시험: 「여기에 위약금 문장을 붙이면 없는 비용을 만들어 말하는 것」이 고객 답에 나갔다)."""
    from app.modules.travel_ops.itinerary_team import customer_lines

    found = []

    def search(**kwargs):
        found.append(kwargs)
        return [_Chunk("직원용 원문 — 여기에 위약금 문장을 붙이면 없는 비용을 만든다.", "t_doc_02#c5", 0.71),
                _Chunk("관련 없는 조각", "t_doc_09#c1", 0.31)]

    me = _session(api)
    client = _chat_client(api, search)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-1"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "취소하면 위약금 있어요?", "ask-1")
    assert body["status"] == "answered" and body["case_status"] == "resolved"
    assert customer_lines()["t_doc_02#c5"] in body["answer"]
    # ★`[2026-09-29 사용자 지시]` 근거 id 는 고객 문장에 없다 — 개발 모드(`web.dev_mode`)일 때만 `basis` 칸으로, 기록에는 늘
    assert "t_doc_" not in body["answer"] and "근거" not in body["answer"]
    assert "basis" not in body and "basis_sources" not in body and "decision" not in body        # 개발 모드가 아니다
    assert "직원용 원문" not in body["answer"] and "관련 없는 조각" not in body["answer"]
    assert found and found[0]["allowed_scopes"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT state_json->'basis'->'sources' FROM customer_cases WHERE case_id=%s", (body["case_id"],))
        assert cur.fetchone()[0] == ["t_doc_02#c5"]


def test_the_basis_is_shown_only_in_dev_mode(api, monkeypatch):
    from app.modules.travel_ops import web_guard

    def search(**kwargs):
        return [_Chunk("직원용 원문", "t_doc_02#c5", 0.71)]

    real = web_guard.values
    monkeypatch.setattr(web_guard, "values", lambda tenant: {**real(tenant), "web.dev_mode": "on"})
    me = _session(api)
    client = _chat_client(api, search)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-dev"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "취소하면 위약금 있어요?", "ask-dev")
    assert body["basis_sources"] == [{"source": "t_doc_02#c5"}] and "t_doc_" not in body["answer"]


def test_a_rule_section_with_no_customer_line_is_not_shown_and_counts_as_not_found(api):
    """내부 절차 절(고객용 문장 없음)만 걸리면 규정을 못 찾은 것이다 — 원문을 대신 싣지 않는다."""
    from knowledge.ingest import load_corpus

    from app.modules.travel_ops.itinerary_team import customer_lines

    manifest = Path(__file__).resolve().parents[2] / "knowledge" / "travel" / "manifest.json"
    internal = next(f"{d.frontmatter['document_id']}#c{s.number}" for d in load_corpus(manifest)
                    for s in d.sections if f"{d.frontmatter['document_id']}#c{s.number}" not in customer_lines())
    me = _session(api)
    client = _chat_client(api, lambda **_k: [_Chunk("내부 절차 원문", internal, 0.90)])
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-6"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "반려견도 데려가도 돼요?", "ask-6")
    assert body["status"] == "answered" and "찾지 못해서" in body["answer"] and "내부 절차 원문" not in body["answer"]


def test_a_question_with_no_matching_policy_says_so_instead_of_guessing(api):
    me = _session(api)
    client = _chat_client(api, lambda **_k: [_Chunk("엉뚱한 조각", "t_doc_05#c2", 0.40)])
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-2"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "반려견도 데려가도 돼요?", "ask-2")
    # ★`[2026-09-28 사용자 결정]` 사람 대기로 남기지 않는다(사람이 보는 것은 버그·오류 리포트뿐) — 못 찾았다고 말하고
    #   이 여행의 사실과 할 수 있는 일로 답한다(ui 세션 실서버 시험: 「비트코인 시세」가 사람 대기로 끝났다)
    assert body["status"] == "answered" and body["case_status"] == "resolved", body
    assert "찾지 못해서" in body["answer"] and "엉뚱한" not in body["answer"]
    assert "이 여행은" in body["answer"] and "늦어요" in body["answer"] and "사람이 확인" not in body["answer"]


def test_a_question_about_a_stop_is_answered_from_the_itinerary_even_without_rules(api):
    me = _session(api)
    client = _chat_client(api)                            # 규정 검색 없음
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-3"), headers=_h(me["user_key"])).json()
    stop = next(i for i in trip["items"] if i["kind"] != "mobility")
    body = _say(client, me["user_key"], trip["trip_id"], f"{stop['title']} 몇 시에 가요?", "ask-3")
    assert body["status"] == "answered" and stop["title"] in body["answer"] and stop["starts_at"][11:16] in body["answer"]


def test_small_talk_gets_what_we_can_do_and_the_trip_facts(api):
    me = _session(api)
    client = _chat_client(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-4"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "안녕하세요", "hi-1")
    assert body["status"] == "answered" and body["case_status"] == "resolved"
    assert "이 여행은" in body["answer"] and "늦어요" in body["answer"]


def test_a_change_request_still_answers_with_what_happened(api):
    me = _session(api)
    client = _chat_client(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-5"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "식당에 30분 늦을 것 같아요", "late-1")
    # ★「답이 있다」만 보지 않는다 — 그 처리 결과의 문장이어야 한다(`trip_replies.outcome_reply`)
    from app.modules.travel_ops.trip_replies import outcome_reply

    assert body["report"]["type"] == "delay" and body["report"]["minutes"] == 30
    assert body["answer"] == outcome_reply(body["status"], body["outcome"], "식당에 30분 늦을 것 같아요"), body
    assert "자동으로 처리하지 못한" not in body["answer"], body          # 아는 결과다 — 되묻는 문장이 아니다
    again = _say(client, me["user_key"], trip["trip_id"], "식당에 30분 늦을 것 같아요", "late-1")
    assert again["status"] == "duplicate" and again["answer"] == "같은 요청을 이미 받았어요.\n" + body["answer"]
    # 원문에 없는 값(분 수)은 받지 않는다 — 그래도 못 알아들었다는 **답**이 나간다
    vague = _say(client, me["user_key"], trip["trip_id"], "식당에 늦을 것 같아요", "late-2")
    assert vague["status"] == "escalated" and "알아듣지 못해" in vague["answer"]


# ── 이 여행의 사실을 묻는 말 — 화면의 빠른 질문 문장 그대로 (2026-09-28, ui 세션 인계) ─────────────
#: ★「답이 나왔다」가 아니라 **답에 기대한 사실이 들어 있다**를 본다. 전에는 이 문장들이 규정 검색으로 가서
#:   「규정에서 찾지 못했어요」+ 제목·시각 한 줄만 나갔다(실제 화면, 상위 점수 0.42~0.52 < 문턱 0.55).
QUICK = {
    "day": (f"{DAY} 하루 일정을 요약해 주세요.",
            ["9월 23일", "7곳", "호텔 조식", "잠실 스카이타워 전망 관람", "성수 점심 식사(예약)", "경복궁 한복 탐방",
             "롯데마트 서울역점 식료품 쇼핑", "10:50 출발 · 2호선 잠실→성수 직통 · 약 13분"]),
    "detail": (f"{DAY} 10:00 잠실 스카이타워 전망 관람 일정의 상세를 알려 주세요.",
               ["잠실 스카이타워 전망 관람", "10:00~10:45", "송파구", "09:30~22:00", "31,000원",
                "예약 기록 없음", "다음 일정", "성수동 팝업스토어·향수 쇼룸", "10:50 출발"]),
    "next": (f"{DAY} 13:00 성수 점심 식사(예약) 다음 일정을 알려 주세요.",
             ["경복궁 한복 탐방", "15:30", "15:00 출발", "2호선·3호선 환승", "약 30분"]),
    "booking": (f"{DAY} 예약 표시를 알려 주세요.",
                ["9월 23일(수) 예약 표시", "성수 점심 식사(예약) — 예약 있음", "호텔 조식 — 예약 기록 없음"]),
}


@pytest.mark.parametrize("kind", sorted(QUICK))
def test_the_screens_quick_questions_are_answered_from_the_trip_itself(dev_mode, api, kind):
    searched = []
    client = _chat_client(api, search=lambda **k: searched.append(k) or [])
    me = _session(api)
    trip_id = client.post("/v1/web/trips", json=_web_body(api), headers=_h(me["user_key"])).json()["trip_id"]
    text, expected = QUICK[kind]
    said = _say(client, me["user_key"], trip_id, text, f"quick-{kind}")
    assert said["status"] == "answered" and said["reason"] == "trip_fact_answered", said
    assert said["report"] == {"type": "question", "fact": kind}
    missing = [fact for fact in expected if fact not in said["answer"]]
    assert not missing, (missing, said["answer"])
    assert "찾지 못했어요" not in said["answer"] and "규정" not in said["answer"]
    assert said["basis"]["writer"] == "template" and searched == []          # 규정 검색을 부르지 않는다
    assert api["client"].get(f"/v1/web/trips/{trip_id}", headers=_h(me["user_key"])).json()["version"] == 1


CUSTOMER_FACTS = [
    ("경복궁 영업시간 알려 주세요", "hours", ["경복궁", "09:00~18:00", "저장된 값"]),
    ("성수 점심 예약돼 있어요?", "booking", ["성수 점심 식사(예약)", "예약 있음"]),
    ("경복궁 어떻게 가요?", "move", ["오는 길", "15:00 출발", "2호선·3호선 환승", "약 30분",
                                   "다음 일정(저녁 식사 18:00)으로", "17:15 출발"]),
    ("경복궁 몇 시에 가요?", "detail", ["경복궁 한복 탐방", "15:30~17:00", "종로구", "3,000원"]),
    ("저녁 식당 주소 알려 주세요", "address", ["서울역 저녁 식당(시나리오)", "주소는 모르겠어요",
                                            "관광공사 조회가 연결돼 있지 않음", "중구"]),
]


@pytest.mark.parametrize("text,kind,expected", CUSTOMER_FACTS)
def test_what_a_customer_asks_about_a_stop_is_answered_with_that_stops_facts(api, text, kind, expected):
    client = _chat_client(api)
    me = _session(api)
    trip_id = client.post("/v1/web/trips", json=_web_body(api), headers=_h(me["user_key"])).json()["trip_id"]
    said = _say(client, me["user_key"], trip_id, text, f"ask-{kind}")
    assert said["reason"] == "trip_fact_answered" and said["report"]["fact"] == kind, said
    missing = [fact for fact in expected if fact not in said["answer"]]
    assert not missing, (missing, said["answer"])


class _TourStub:
    """관광공사 상세 조회 흉내 — 원문을 그대로 준다. 몇 번 불렸는지 센다."""

    def __init__(self):
        self.calls = 0

    def by_content_id(self, content_id, content_type_id):
        self.calls += 1
        return {"content_id": content_id, "address": "서울특별시 송파구 올림픽로 300"}

    def operating(self, content_id, content_type_id):
        self.calls += 1
        return {"usetime_text": "10:30~22:00<br>(입장마감 21:00)", "restdate_text": "연중무휴", "info_phone": None}


def test_address_and_opening_hours_come_from_the_tourism_record_as_written(dev_mode, api):
    """★주소·운영시간은 저장하지 않는다(약관) — 물으면 관광공사 상세를 그때 읽어 **원문 그대로** 싣는다."""
    from app.modules.travel_ops import trip_facts

    trip_facts._CACHE.clear()
    tour = _TourStub()
    client = _chat_client(api, place=tour)
    me = _session(api)
    body = _web_body(api)
    for place in body["places"]:
        if place["key"] == "seoul_sky":
            place["attributes"] = {**place["attributes"], "source_content_id": "990001",
                                   "source_content_type_id": "12"}
    trip_id = client.post("/v1/web/trips", json=body, headers=_h(me["user_key"])).json()["trip_id"]
    said = _say(client, me["user_key"], trip_id, "잠실 스카이타워 주소 알려 주세요", "addr")
    assert "서울특별시 송파구 올림픽로 300" in said["answer"] and "관광공사" in said["answer"], said["answer"]
    hours = _say(client, me["user_key"], trip_id, "잠실 스카이타워 운영시간 알려 주세요", "hours")
    assert "10:30~22:00 / (입장마감 21:00)" in hours["answer"] and "연중무휴" in hours["answer"], hours["answer"]
    assert "09:30~22:00" in hours["answer"]                  # 저장된 값도 같이 — 어느 것이 어디서 왔는지 적힌다
    assert tour.calls == 2                                   # 두 번째 질문은 조회를 다시 하지 않는다(캐시)
    assert hours["basis"]["lookups"]["source"] == "관광공사"


def test_a_change_sentence_is_not_taken_as_a_fact_question(api):
    from app.modules.travel_ops.trip_facts import fact_question

    for text in ("경복궁 다음 일정을 바꿔 주세요", "저녁 식당이 문을 닫았어요", "30분 늦을 것 같아요",
                 "2번 일정으로 되돌려 주세요", "취소하면 위약금 있어요?", "예약 취소하면 환불돼요?"):
        assert fact_question(text) is None, text


def test_the_web_trip_marks_a_reserved_stop_as_booked(api):
    me = _session(api)
    trip_id = api["client"].post("/v1/web/trips", json=_web_body(api), headers=_h(me["user_key"])).json()["trip_id"]
    items = api["client"].get(f"/v1/web/trips/{trip_id}", headers=_h(me["user_key"])).json()["items"]
    booked = {i["title"]: i["booked"] for i in items if i["kind"] != "mobility"}
    assert booked["성수 점심 식사(예약)"] is True and booked["호텔 조식"] is False


class _NamedTour(_TourStub):
    """식별자 없는 장소를 이름으로 찾는 흉내 — 좌표는 시나리오 장소와 같은 자리(또는 멀리)."""

    def __init__(self, far=False):
        super().__init__()
        self.far = far

    def find(self, name, allowed_types=None, area_code=None):
        place = next(p for p in SCENARIO["places"] if p["name"] == name)
        return {"content_id": "126508", "content_type_id": "12", "matched_title": name,
                "latitude": place["lat"] + (0.05 if self.far else 0.0), "longitude": place["lon"]}


def test_a_stop_without_a_tourism_id_is_found_by_name_and_place_before_answering(api):
    """★`[2026-09-28]` 고객 글의 이름으로 붙은 장소(공용 장소 행)는 관광공사 식별자가 없어 주소·운영시간이 늘 「모름」이었다
    (ui 세션 실서버 시험 — 「경복궁」). 같은 이름·종류로 찾고 **좌표가 500m 안일 때만** 같은 곳으로 본다."""
    from app.modules.travel_ops import trip_facts

    for far, expected in ((False, "서울특별시 송파구 올림픽로 300"), (True, "떨어져 있어 같은 곳으로 보지 않았다")):
        trip_facts._CACHE.clear()
        client = _chat_client(api, place=_NamedTour(far=far))
        me = _session(api)
        trip_id = client.post("/v1/web/trips", json=_web_body(api, request_id=f"named-{far}"),
                              headers=_h(me["user_key"])).json()["trip_id"]
        said = _say(client, me["user_key"], trip_id, "경복궁 주소 알려 주세요", f"addr-{far}")
        assert expected in said["answer"], said["answer"]


def test_the_issue_limit_can_be_switched_off_for_development_only(api, monkeypatch):
    """★`[2026-09-28]` 화면 시험이 한 주소에서 새 사용자를 계속 만들다 429 에 걸렸다(ui 세션). 개발용 스위치 — 기본은 꺼짐."""
    import app.core.settings as settings_module

    _override(api, "web.session.per_ip_hour", 1)
    assert api["client"].post("/v1/web/session").status_code == 201
    assert api["client"].post("/v1/web/session").status_code == 429              # 한도만큼 받았다
    unlimited = settings_module.get_settings().model_copy(update={"web_session_issue_unlimited": True})
    monkeypatch.setattr(settings_module, "get_settings", lambda: unlimited)
    assert api["client"].post("/v1/web/session").status_code == 201
    assert settings_module.Settings.model_fields["web_session_issue_unlimited"].default is False


def test_asking_for_another_place_finds_one_on_the_spot(api):
    """★`[2026-09-29 사용자 지적]` 「다른 데로 바꿔 줘」에 들고 있던 대안이 없으면 **그 자리에서 찾는다** — 전에는 감시가 한 번
    고친 항목만 봐서 막 만든 일정은 늘 「바꿀 수 있는 다른 안이 없어요」였다(ui 세션 전달). 나머지 후보는 「다른 안」으로 남는다."""
    me = _session(api)
    client = _chat_client(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-7"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "점심 식당 다른 데로 바꿔 줘", "swap-1")
    assert body["status"] == "adjusted" and body["case_status"] == "resolved", body
    assert "성수 점심 식당 대신" in body["answer"] and "다른 안:" in body["answer"], body["answer"]
    lunch = _lunch(client, me, trip)
    assert lunch["title"] != "성수 점심 식당 식사" and lunch["title"].endswith("식사")
    # 다시 달라고 하면 이번에는 들고 있던 「다른 안」으로(원래 곳도 다른 안에 남아 있다)
    again = _say(client, me["user_key"], trip["trip_id"], "점심 식당 다른 데로 바꿔 줘", "swap-2")
    assert again["status"] == "adjusted", again
    assert _lunch(client, me, trip)["title"] not in (lunch["title"],)


def test_the_selected_item_on_screen_is_the_one_that_changes(api):
    """화면에서 고른 일정(`item_id`)이 문장보다 앞선다 — 「다른 데로 바꿔 줘」만 보내도 그 항목이 바뀐다."""
    me = _session(api)
    client = _chat_client(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-8"), headers=_h(me["user_key"])).json()
    lunch = _lunch(client, me, trip)
    response = client.post(f"/v1/web/trips/{trip['trip_id']}/messages", headers=_h(me["user_key"]),
                           json={"request_id": "sel-1", "message": "다른 데로 바꿔 줘", "item_id": lunch["item_id"],
                                 "at": "2030-01-01T09:00:00+09:00"})
    body = response.json()
    assert body["status"] == "adjusted" and "성수 점심 식당 대신" in body["answer"], body


def test_a_sentence_that_names_the_meal_wins_over_the_selected_item(api):
    """`[2026-09-29 ui 세션 지적]` 활동을 눌러 둔 채 「점심 식당 바꿔 줘」라고 쓰면 **점심**이 바뀐다 — 문장이 대상을
    분명히 말하면 문장이 이기고, 말하지 않을 때만 화면에서 고른 일정을 쓴다."""
    me = _session(api)
    client = _chat_client(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-9"), headers=_h(me["user_key"])).json()
    view = client.get(f"/v1/web/trips/{trip['trip_id']}", headers=_h(me["user_key"])).json()
    activity = next(i for i in view["items"] if i["kind"] == "activity")
    response = client.post(f"/v1/web/trips/{trip['trip_id']}/messages", headers=_h(me["user_key"]),
                           json={"request_id": "sel-2", "message": "점심 식당 바꿔 줘", "item_id": activity["item_id"],
                                 "at": "2030-01-01T09:00:00+09:00"})
    body = response.json()
    assert body["status"] == "adjusted" and "성수 점심 식당 대신" in body["answer"], body


def _lunch(client, me, trip) -> dict:
    view = client.get(f"/v1/web/trips/{trip['trip_id']}", headers=_h(me["user_key"])).json()
    return next(i for i in view["items"] if i["kind"] == "dining" and 11 <= int(i["starts_at"][11:13]) < 15)


def test_a_fact_question_is_answered_even_when_the_classifier_times_out(api):
    """★`[2026-09-29]` 원격 모델이 잠들어 분류가 시간 초과로 실패하면 화면의 「하루 요약」까지 「분류하지 못했어요」로
    끝났다(ui 세션 실서버 시험). 사실 질문은 모델 없이 기록으로 답한다 — 분류 실패는 **그대로 기록**한다(Case escalated)."""
    me = _session(api)
    client = _chat_client(api, classifier_down=True)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="down-1"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "하루 일정 요약해 주세요", "down-sum")
    assert body["status"] == "answered" and body["reason"] == "trip_fact_answered", body
    # ★`[2026-09-29]` 웹은 분류를 기다리지 않고 답한다(모델이 식어 있으면 34초 걸렸다) — 분류는 응답 뒤에서 돈다
    assert body["classification_pending"] is True
    assert "일정은" in body["answer"] and "분류하지 못해" not in body["answer"]
    with get_connection() as conn, conn.cursor() as cur:                                   # 응답 뒤 분류가 돌았다
        cur.execute("SELECT status FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (api["tenant"], body["case_id"]))
        assert cur.fetchone()[0] == "escalated"                                             # 모델 장애는 기록에 남는다
    again = _say(client, me["user_key"], trip["trip_id"], "하루 일정 요약해 주세요", "down-sum")
    assert again["status"] == "duplicate" and body["answer"] in again["answer"]           # 답이 기록에 남았다
    other = _say(client, me["user_key"], trip["trip_id"], "파이썬 코드 짜줘", "down-other")
    assert other["status"] == "escalated" and "분류하지 못해" in other["answer"]          # 사실 질문이 아니면 전과 같다


def test_a_fact_question_answers_before_classification_and_the_case_still_completes(api):
    """★`[2026-09-29]` 분류가 되면 응답 뒤에서 담당·완료까지 기록된다(웹 · 모델 정상)."""
    me = _session(api)
    client = _chat_client(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="defer-1"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "하루 일정 요약해 주세요", "defer-sum")
    assert body["status"] == "answered" and body["classification_pending"] is True
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, state_json->>'answer' FROM customer_cases WHERE tenant_id=%s AND case_id=%s",
                    (api["tenant"], body["case_id"]))
        status, stored = cur.fetchone()
    assert status == "resolved" and stored == body["answer"]



def test_the_google_map_is_loaded_only_while_the_budget_allows(api, monkeypatch):
    """`[2026-09-29 사용자 지시]` 구글 지도도 무료 한도 안에서만 — 화면이 부르기 전에 묻고, 한도가 차면 무료 지도로.
    ★실제 사용량 줄을 건드리지 않게 2099년 날짜로 세고 끝나면 지운다."""
    from datetime import UTC, datetime

    from app.infrastructure.travel.call_budget import CallBudget
    from app.modules.travel_ops import trip_api

    far = lambda: datetime(2099, 1, 2, tzinfo=UTC)
    monkeypatch.setattr(trip_api, "map_budget", lambda: CallBudget(
        connection_factory=get_connection, caps={trip_api.MAP_METER: {"month": 5, "day": 2}}, clock=far))
    from app.modules.travel_ops import web_guard

    me = _session(api)
    try:
        assert api["client"].post("/v1/web/map-load").status_code == 401                      # 키 없이는 안 된다
        # ★`[2026-09-29 사용자 결정]` 기본은 무료 지도 — 구글 한도를 세지 않는다
        first = api["client"].post("/v1/web/map-load", headers=_h(me["user_key"])).json()
        assert (first["provider"], first["allowed"], first["reason"]) == ("osm", False, "setting")
        monkeypatch.setattr(web_guard, "values", lambda tenant: {"web.map_provider": "google"})
        answers = [api["client"].post("/v1/web/map-load", headers=_h(me["user_key"])).json() for _ in range(3)]
        assert [a["allowed"] for a in answers] == [True, True, False]                         # 하루 2건
        assert answers[-1]["reason"] == "cap" and answers[-1]["fallback"] == "free_map"
        assert answers[-1]["used"] == {"month": 2, "day": 2}                                  # 무료 지도일 때는 안 셌다
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM external_call_budget WHERE meter=%s AND period LIKE %s", (trip_api.MAP_METER, "%2099%"))
