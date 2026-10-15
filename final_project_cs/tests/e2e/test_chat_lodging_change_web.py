# -*- coding: utf-8 -*-
"""웹 채팅의 「숙소 다른 곳으로 바꿔 줘」가 **숙소 팀**에 닿는다. `[2026-10-15 숙박예약 동작 점검 LB-02]`

☆왜: 채팅은 요청이 가리킨 일정의 종류로 담당 팀을 정한다(`trip_messages._dispatch_decision`). 식당 · 활동 · 이동만 알고 있어서 숙소 항목을 가리킨 요청은
  담당이 없는 채로 **활동 팀**으로 넘어갔다 — 숙소 팀은 일정 항목이 아니라 문장으로만 켜지고, 일정에 든 숙소를 바꾸는 길(Case → `lodging.itinerary`)은
  웹 채팅에서 한 번도 열리지 않았다(10-13 반영 때 x600 서버에서 확인한 것은 Case 를 직접 열고 돌린 길이었다).
  같은 줄기가 둘 더 있었다: ①되묻기에서 고른 항목의 팀을 찾는 곳(`case_dispatch._resume_route`)이 숙소를 모른다 ②규칙 해석 경로의 대상 고르기(`_change_target`)가 식사 · 활동만 센다.

★지키려는 것
 ⑤웹 접수로 만든 여행은 인원이 비어 있다 — 숙소 팀이 사람에게 넘기지 않고 「몇 분이 함께 가시나요」를 묻고, 답한 인원으로 찾는다 `[2026-10-15 x600 서버 실서버 확인에서 찾음]`
 ①숙소 항목을 가리킨 「바꿔 줘」 · 「다른 곳」은 숙소 팀 일정 관리(`lodging.itinerary`)로 가고, 그 팀의 답이 고객에게 나간다 — 활동 팀이 받지 않는다
 ②식당 · 활동의 담당은 그대로다(식당을 가리키면 식당 팀)
 ③되묻기 번호 고르기에서 숙소를 고르면 숙소 팀으로 간다
 ④규칙 해석 경로도 「숙소 바꿔 줘」의 대상을 숙소 항목으로 잡는다

★여기서 해석 모델과 숙소 팀의 실제 검색(MCP)은 **자동 시험용 고정 대역**이다 — 이 시험은 채팅이 일을 누구에게 맡기는가(배선)를 본다. 후보 검색 · 고르기 자체는
  `tests/unit/travel/booking/test_lodging_team.py` · `tests/integration/travel/test_lodging_flight_options.py`.

재현:

    python -m pytest tests/e2e/test_chat_lodging_change_web.py -v
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.contracts import NextAction
from tests.helpers.plugin_bindings import publish_fixed_mobility

from .test_trip_api import DAY
from .test_web_api import _fresh_limit_cache, _h, _session, _web_body, api  # noqa: F401 — 시험 준비물

KST = timezone(timedelta(hours=9))
NEXT_DAY = (datetime.fromisoformat(DAY) + timedelta(days=1)).date().isoformat()


class _Decider:
    """해석 모델 흉내 — 「숙소 …」는 숙소 항목, 「점심 …」은 성수 점심을 고른다. 대상 id 는 받은 일정 목록에서 찾는다."""

    @staticmethod
    def _alias(user: str, name: str) -> str:
        for line in user.split("\n"):
            if re.match(r"i\d+ \|", line) and name in line:
                return line.split(" |")[0]
        return "none"

    def structured(self, system, user, schema, *, num_predict=160):
        message = user.rsplit("고객 문장:", 1)[1].strip()
        none = {"target_change": "none", "fact": "none", "minutes": 0, "question": ""}
        if "숙소 다른 곳" in message:
            return {**none, "action": "propose_alternatives", "target_item": self._alias(user, "롯데호텔 서울")}
        if "숙소 바꿔" in message:
            return {**none, "action": "apply_change", "target_item": self._alias(user, "롯데호텔 서울")}
        if "점심 다른 곳" in message:
            return {**none, "action": "propose_alternatives", "target_item": self._alias(user, "성수 점심")}
        if "무엇을" in message:
            hotel, lunch = self._alias(user, "롯데호텔 서울"), self._alias(user, "성수 점심")
            return {**none, "action": "clarify", "target_item": "none",
                    "choices": [{"action": "propose_alternatives", "target_item": hotel, "target_change": "none", "fact": "none"},
                                {"action": "propose_alternatives", "target_item": lunch, "target_change": "none", "fact": "none"}]}
        return {**none, "action": "other", "target_item": "none"}


@pytest.fixture()
def hotel_chat(api, monkeypatch):
    from fastapi.testclient import TestClient

    from app.domains.travel_ops.components.conversation import trip_messages
    from app.domains.travel_ops.entry.trip_api import build_trip_router
    from app.domains.travel_ops.instances.lodging import LodgingTeam
    from app.presentation.api.app import create_app

    calls: list[dict] = []

    def stand_in(self, task, ctx):
        """숙소 팀 자신의 「바꿔 줘」(`LodgingTeam._change`) — 어떤 항목으로 불렸는지만 적고 후보 대신 정해진 답을 낸다(실제 검색 없음)."""
        ref = ctx["ref"]
        calls.append({"team": self.manifest.team_id, "capability": task.capability, "part_id": ref.get("part_id"),
                      "action": ctx["request"].get("action")})
        evidence = self._evidence(task, source_id="read.itinerary", claim="현재 일정 버전", value={"stand_in": True})
        return self._result(task, outcome="completed", confidence=1.0, evidence=evidence, next_action=NextAction.RESPOND,
                            answer="롯데호텔 서울 대신 갈 수 있는 곳이에요 — 1) 해밀톤 호텔 2) 코리아나 호텔 · 고르시면 바꿀게요.",
                            decisions=[{"itinerary": "asked", "item": "롯데호텔 서울"}])

    monkeypatch.setattr(LodgingTeam, "_change", stand_in)
    monkeypatch.setattr(trip_messages, "_decision_mode", lambda chat, tenant=None: "on")
    client = TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(classifier_factory=lambda: (lambda m: {"intent": "other", "issue_code": "other",
                                                                                 "sentiment": "neutral"}),
                                          chat_factory=lambda: _Decider())]))
    publish_fixed_mobility(client.app, source="chat_lodging_test")
    me = _session(api)
    body = _web_body(api, request_id="lodg-" + uuid4().hex[:6])
    last = max(it["seq"] for it in body["items"])
    body["items"].append({"seq": last + 1, "kind": "lodging", "title": "롯데호텔 서울", "place": "hotel", "route": None,
                          "starts_at": f"{DAY}T21:00:00+09:00", "ends_at": f"{NEXT_DAY}T10:00:00+09:00", "detail": {}})
    trip = client.post("/v1/web/trips", json=body, headers=_h(me["user_key"]))
    assert trip.status_code in (200, 201), trip.text
    yield {"client": client, "key": me["user_key"], "trip": trip.json(), "calls": calls}


def _say(chat, text, request_id, **extra):
    response = chat["client"].post(f"/v1/web/trips/{chat['trip']['trip_id']}/messages", headers=_h(chat["key"]),
                                   json={"request_id": request_id, "message": text, "at": f"{DAY}T09:00:00+09:00", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_asking_for_another_lodging_goes_to_the_lodging_team_and_its_answer_reaches_the_customer(hotel_chat):
    body = _say(hotel_chat, "숙소 다른 곳으로 보여 줘", "lodg-a")
    assert hotel_chat["calls"], f"숙소 팀이 불리지 않았다: {body}"
    call = hotel_chat["calls"][0]
    assert call["team"] == "lodging" and call["capability"] == "lodging.itinerary" and call["action"] == "propose_alternatives", call
    assert "해밀톤 호텔" in body["answer"], body
    hotel = next(i for i in hotel_chat["trip"]["items"] if i["kind"] == "lodging")
    assert call["part_id"] == hotel["item_id"], (call, hotel)


def test_the_change_request_form_goes_to_the_lodging_team_too(hotel_chat):
    _say(hotel_chat, "숙소 바꿔 줘", "lodg-b")
    assert [c["team"] for c in hotel_chat["calls"]] == ["lodging"], hotel_chat["calls"]


def test_a_lunch_request_still_goes_to_a_dining_team_not_the_lodging_team(hotel_chat):
    _say(hotel_chat, "점심 다른 곳으로 보여 줘", "lodg-c")
    assert hotel_chat["calls"] == [], "식당 요청은 숙소 팀이 받지 않는다"


def test_picking_the_lodging_from_a_clarify_list_goes_to_the_lodging_team(hotel_chat):
    ask = _say(hotel_chat, "무엇을 바꿀까", "lodg-d1")
    assert ask["status"] == "clarify" and ask["choices"], ask
    number = next(n for n, c in enumerate(ask["choices"], start=1) if "롯데호텔" in (c.get("label") or c.get("message") or ""))
    picked = _say(hotel_chat, f"{number}번", "lodg-d2", case_id=ask["case_id"])
    assert "해밀톤 호텔" in picked["answer"], picked
    assert [c["team"] for c in hotel_chat["calls"]] == ["lodging"], hotel_chat["calls"]


@pytest.fixture()
def hotel_chat_unknown_party(api, monkeypatch):
    """인원이 빈 여행(웹 접수가 만든 여행과 같다) + 숙소 팀의 진짜 「바꿔 줘」 — 외부 검색(MCP)만 막고 어떤 조건으로 부르는지 적는다."""
    from fastapi.testclient import TestClient

    from app.domains.travel_ops.components.conversation import trip_messages
    from app.domains.travel_ops.entry.trip_api import build_trip_router
    from app.domains.travel_ops.instances.lodging import LodgingTeam
    from app.presentation.api.app import create_app

    searches: list[tuple[str, dict]] = []
    original = LodgingTeam._read

    def spy(self, task, tool, args, seen):
        if tool == "read.itinerary":
            return original(self, task, tool, args, seen)
        searches.append((tool, dict(args)))
        return None                                           # 검색 결과 없음 — 여기서는 어떤 조건으로 불렀는지만 본다

    monkeypatch.setattr(LodgingTeam, "_read", spy)
    monkeypatch.setattr(trip_messages, "_decision_mode", lambda chat, tenant=None: "on")
    client = TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(classifier_factory=lambda: (lambda m: {"intent": "other", "issue_code": "other",
                                                                                 "sentiment": "neutral"}),
                                          chat_factory=lambda: _Decider())]))
    publish_fixed_mobility(client.app, source="chat_lodging_party_test")
    me = _session(api)
    body = _web_body(api, request_id="lodgp-" + uuid4().hex[:6])
    body["party_size"] = None
    last = max(it["seq"] for it in body["items"])
    body["items"].append({"seq": last + 1, "kind": "lodging", "title": "롯데호텔 서울", "place": "hotel", "route": None,
                          "starts_at": f"{DAY}T21:00:00+09:00", "ends_at": f"{NEXT_DAY}T10:00:00+09:00", "detail": {}})
    trip = client.post("/v1/web/trips", json=body, headers=_h(me["user_key"]))
    assert trip.status_code in (200, 201), trip.text
    assert trip.json().get("party_size") is None
    yield {"client": client, "key": me["user_key"], "trip": trip.json(), "searches": searches}


def test_an_unknown_party_size_is_asked_not_escalated_and_the_answer_fills_the_search(hotel_chat_unknown_party):
    chat = hotel_chat_unknown_party
    ask = _say(chat, "숙소 다른 곳으로 보여 줘", "lodgp-a")
    assert ask["case_status"] == "waiting_input" and "몇 분" in ask["answer"], ask               # 사람에게 넘기지 않고 묻는다
    assert ask["required_input_schema"]["required"] == ["adults"], ask
    assert chat["searches"] == [], "인원을 모르는 채로 외부 검색을 부르지 않는다"
    _say(chat, "2명이요", "lodgp-b", case_id=ask["case_id"])
    asked = [args for _tool, args in chat["searches"] if "adults" in args]
    assert asked and all(args["adults"] == 2 for args in asked), chat["searches"]


def test_a_reply_that_is_not_a_party_size_does_not_search(hotel_chat_unknown_party):
    chat = hotel_chat_unknown_party
    ask = _say(chat, "숙소 다른 곳으로 보여 줘", "lodgp-c")
    assert ask["case_status"] == "waiting_input", ask
    _say(chat, "글쎄요", "lodgp-d", case_id=ask["case_id"])
    assert chat["searches"] == [], "인원으로 읽히지 않는 답으로 검색하지 않는다"


def test_the_party_size_typed_without_the_case_id_still_answers_the_question(hotel_chat_unknown_party):
    """웹은 답에 대기 건 번호를 항상 붙이지는 않는다 — 번호 없이 「2명이요」만 보내도 방금 그 질문의 답으로 이어진다."""
    chat = hotel_chat_unknown_party
    ask = _say(chat, "숙소 다른 곳으로 보여 줘", "lodgp-e")
    assert ask["case_status"] == "waiting_input", ask
    _say(chat, "2명이요", "lodgp-f")
    asked = [args for _tool, args in chat["searches"] if "adults" in args]
    assert asked and all(args["adults"] == 2 for args in asked), chat["searches"]


def _adults(chat):
    return [args["adults"] for _tool, args in chat["searches"] if "adults" in args]


def test_a_party_size_written_in_the_same_sentence_is_used_without_asking(hotel_chat_unknown_party):
    """`[2026-10-15 사용자 지시]` 인원을 이미 받았으면 그것으로 하고, 어디에도 없을 때만 묻는다 — 이번 문장에 적힌 인원."""
    chat = hotel_chat_unknown_party
    got = _say(chat, "2명 기준으로 숙소 다른 곳으로 보여 줘", "lodgp-g")
    assert got["case_status"] != "waiting_input" or "몇 분" not in got["answer"], got
    assert _adults(chat) and set(_adults(chat)) == {2}, chat["searches"]


def test_a_party_size_already_answered_in_this_trip_chat_is_not_asked_again(hotel_chat_unknown_party):
    chat = hotel_chat_unknown_party
    ask = _say(chat, "숙소 다른 곳으로 보여 줘", "lodgp-h")
    assert ask["case_status"] == "waiting_input" and "몇 분" in ask["answer"], ask
    _say(chat, "3명이요", "lodgp-i", case_id=ask["case_id"])
    before = len(_adults(chat))
    again = _say(chat, "숙소 다른 곳으로 보여 줘", "lodgp-j")
    assert "몇 분" not in again["answer"], again                       # 한 번 답한 인원은 다시 묻지 않는다
    assert len(_adults(chat)) > before and set(_adults(chat)) == {3}, chat["searches"]


def test_the_party_size_registered_with_the_trip_is_used_and_never_asked(hotel_chat_unknown_party, api):
    """계획을 쓰거나 만들 때 받은 인원(여행에 적힌 `party_size`)이 있으면 그것으로 찾는다."""
    chat = hotel_chat_unknown_party
    body = _web_body(api, request_id="lodgp-k-" + uuid4().hex[:6])
    body["party_size"] = 4
    last = max(it["seq"] for it in body["items"])
    body["items"].append({"seq": last + 1, "kind": "lodging", "title": "롯데호텔 서울", "place": "hotel", "route": None,
                          "starts_at": f"{DAY}T21:00:00+09:00", "ends_at": f"{NEXT_DAY}T10:00:00+09:00", "detail": {}})
    other = _session(api)                                          # 게스트는 여행을 1개까지만 — 다른 게스트로 만든다
    trip = chat["client"].post("/v1/web/trips", json=body, headers=_h(other["user_key"]))
    assert trip.status_code in (200, 201), trip.text
    known = {**chat, "trip": trip.json(), "key": other["user_key"]}
    got = _say(known, "숙소 다른 곳으로 보여 줘", "lodgp-l")
    assert "몇 분" not in got["answer"], got
    assert _adults(chat) and set(_adults(chat)) == {4}, chat["searches"]
