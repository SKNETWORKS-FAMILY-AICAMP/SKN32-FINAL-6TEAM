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

from .test_trip_api import DAY, SCENARIO, _body, api  # noqa: F401 — 픽스처를 그대로 쓴다


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


# ── 채팅은 늘 답한다 (2026-09-28, ui 세션 인계 · 사용자 지시) ───────────────────
class _Chunk:
    def __init__(self, content, source_id, score):
        self.content, self.source_id, self.score = content, source_id, score


class _Talk:
    """추출기 흉내 — 문장에 맞는 신고 종류를 낸다."""

    def json(self, system, message):
        if "늦을" in message:
            return {"type": "delay", "minutes": 30, "products": []}
        if "?" in message or "요?" in message:
            return {"type": "question"}
        return {"type": "other"}


def _chat_client(api, search=None, place=None):
    from fastapi.testclient import TestClient

    from app.modules.travel_ops.trip_api import build_trip_router
    from app.presentation.api.app import create_app

    def classify(message):
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


def test_a_policy_question_is_answered_with_the_policy_excerpt_and_its_source(api):
    found = []

    def search(**kwargs):
        found.append(kwargs)
        return [_Chunk("예약 취소는 시작 24시간 전까지 수수료가 없다.", "t_doc_01#c3", 0.71),
                _Chunk("관련 없는 조각", "t_doc_09#c1", 0.31)]

    me = _session(api)
    client = _chat_client(api, search)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-1"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "취소하면 위약금 있어요?", "ask-1")
    assert body["status"] == "answered" and body["case_status"] == "resolved"
    assert "24시간 전까지" in body["answer"] and "근거 t_doc_01#c3" in body["answer"]
    assert "관련 없는 조각" not in body["answer"]          # ★문턱(0.55) 아래 조각은 싣지 않는다
    assert found and found[0]["allowed_scopes"]


def test_a_question_with_no_matching_policy_says_so_instead_of_guessing(api):
    me = _session(api)
    client = _chat_client(api, lambda **_k: [_Chunk("엉뚱한 조각", "t_doc_05#c2", 0.40)])
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="q-2"), headers=_h(me["user_key"])).json()
    body = _say(client, me["user_key"], trip["trip_id"], "반려견도 데려가도 돼요?", "ask-2")
    assert body["status"] == "escalated" and "찾지 못했어요" in body["answer"] and "엉뚱한" not in body["answer"]


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
def test_the_screens_quick_questions_are_answered_from_the_trip_itself(api, kind):
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
                                            "관광공사 식별자가 없는 장소", "중구"]),
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


def test_address_and_opening_hours_come_from_the_tourism_record_as_written(api):
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

