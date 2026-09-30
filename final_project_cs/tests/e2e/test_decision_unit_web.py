# -*- coding: utf-8 -*-
"""결정 단위 — 웹 채팅이 **여행 상태를 보며** 한 번에 해석하고, 서버가 확인해 실행한다. `[2026-09-29 사용자 지시 · Codex 합의]`

★여기서 해석 모델은 **자동 시험용 고정 규칙**이다(실제 모델 아님) — 받은 입력(일정 목록 · 변경 이력 · 앞 대화)에서 id 를 찾아 고른다.
  그래서 이 시험은 ①서버가 모델에 무엇을 넘기는지(대화 기록 · 변경 id) ②모델이 고른 id 를 서버가 어떻게 확인 · 실행하는지를 본다.
  실제 모델의 정확도는 재생 시험(`tests/live/test_decision_unit_live.py`)이 잰다.
"""
from __future__ import annotations

import re

import pytest

from app.infrastructure.db.session import get_connection

from .test_web_api import _fresh_limit_cache, _h, _session, _web_body, api  # noqa: F401 — 시험 준비물


class _Decider:
    """해석 모델 흉내 — 문장 → (할 일, 대상 이름 조각, 사실 종류). 대상 id 는 **받은 일정 목록**에서 찾는다."""

    def __init__(self):
        self.prompts: list[str] = []

    @staticmethod
    def _alias(user: str, name: str) -> str:
        for line in user.split("\n"):
            if re.match(r"i\d+ \|", line) and name in line:
                return line.split(" |")[0]
        return "none"

    def structured(self, system, user, schema, *, num_predict=160):
        self.prompts.append(user)
        message = user.rsplit("고객 문장:", 1)[1].strip()
        none = {"target_change": "none", "fact": "none", "minutes": 0, "question": ""}
        if "고장" in message:
            raise RuntimeError("model is down")
        if "알려줘" in message and "성수 점심" in message:
            return {**none, "action": "answer_fact", "target_item": self._alias(user, "성수 점심"), "fact": "detail"}
        if "예약 표시" in message:
            lunch, dinner = self._alias(user, "성수 점심"), self._alias(user, "· 저녁")
            return {**none, "action": "clarify", "target_item": "none",
                    "choices": [{"action": "answer_fact", "target_item": lunch, "target_change": "none", "fact": "booking"},
                                {"action": "answer_fact", "target_item": dinner, "target_change": "none", "fact": "booking"}]}
        if "그 식당 어딨어" in message:
            return {**none, "action": "answer_fact", "target_item": self._alias(user, "성수 점심"), "fact": "address"}
        if "그 식당 전화번호" in message:
            talk = user.split("직전 대화:", 1)[1].split("화면에서 고른 일정:", 1)[0]
            target = self._alias(user, "성수 점심") if "성수 점심" in talk else "none"
            return {**none, "action": "answer_fact", "target_item": target, "fact": "phone"}
        if "점심 다른 데로 바꿔" in message:
            return {**none, "action": "apply_change", "target_item": self._alias(user, "성수 점심")}
        if "저녁 다른 데로 바꿔" in message:
            return {**none, "action": "apply_change", "target_item": self._alias(user, "· 저녁")}
        if "원래대로" in message:
            changes = re.findall(r"^(c\d+) \|", user, re.M)
            return {**none, "action": "rollback", "target_item": "none", "target_change": changes[-1] if changes else "none"}
        if "바꿔" == message:
            return {**none, "action": "clarify", "target_item": "none", "question": "어떤 일정을 바꿔 드릴까요?"}
        if "없는 번호" in message:
            return {**none, "action": "apply_change", "target_item": "i99"}
        return {**none, "action": "other", "target_item": "none"}


@pytest.fixture()
def decided(api, monkeypatch):
    from fastapi.testclient import TestClient

    from app.modules.travel_ops import trip_messages
    from app.modules.travel_ops.trip_api import build_trip_router
    from app.presentation.api.app import create_app

    from app.modules.travel_ops import web_guard

    decider = _Decider()
    monkeypatch.setattr(trip_messages, "_decision_mode", lambda chat, tenant=None: "on")
    real = web_guard.values          # ★해석 결과(`decision`)는 개발 모드일 때만 웹에 실린다 — 이 시험은 그 칸을 본다
    monkeypatch.setattr(web_guard, "values", lambda tenant: {**real(tenant), "web.dev_mode": "on"})
    client = TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(classifier_factory=lambda: (lambda m: {"intent": "other",
                                                                                 "issue_code": "other",
                                                                                 "sentiment": "neutral"}),
                                          chat_factory=lambda: decider)]))
    me = _session(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="du-1"), headers=_h(me["user_key"])).json()
    yield {"client": client, "key": me["user_key"], "trip": trip, "decider": decider}


def _say(decided, text, request_id, **extra):
    response = decided["client"].post(f"/v1/web/trips/{decided['trip']['trip_id']}/messages",
                                      headers=_h(decided["key"]),
                                      json={"request_id": request_id, "message": text,
                                            "at": "2030-01-01T09:00:00+09:00", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_a_place_question_is_answered_from_the_item_the_model_picked(decided):
    body = _say(decided, "성수 점심 식당 알려줘", "du-a")
    assert body["status"] == "answered" and body["decision"]["action"] == "answer_fact", body
    assert "성수 점심" in body["answer"] and "규정" not in body["answer"]
    assert body["classification"] == {"intent": "confirm_request", "issue_code": "dining_other"}


def test_the_previous_turn_is_given_to_the_model_so_that_that_restaurant_resolves(decided):
    _say(decided, "성수 점심 식당 알려줘", "du-b1")
    body = _say(decided, "그 식당 전화번호 알려줘", "du-b2")
    assert "고객: 성수 점심 식당 알려줘" in decided["decider"].prompts[-1]          # 서버가 앞 대화를 넘겼다
    assert body["decision"]["fact"] == "phone" and "성수 점심" in body["answer"], body
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat",
                                  headers=_h(decided["key"])).json()["turns"]
    assert [t["role"] for t in turns] == ["customer", "assistant", "customer", "assistant"]


def test_change_then_undo_without_a_number_goes_back_by_the_change_id(decided):
    changed = _say(decided, "점심 다른 데로 바꿔", "du-c1")
    assert changed["status"] == "adjusted", changed
    undone = _say(decided, "원래대로 돌려 줘", "du-c2")
    assert undone["status"] == "rolled_back" and re.match(r"c\d+", undone["decision"]["change"]), undone
    assert "되돌렸어요" in undone["answer"] and "버전" not in undone["answer"]


def test_an_unclear_request_is_asked_back_and_nothing_changes(decided):
    body = _say(decided, "바꿔", "du-d")
    # ★모델이 후보를 안 내도 서버가 고를 수 있는 일정을 버튼으로 싣는다(「다음 중 하나인가요?」)
    assert body["status"] == "clarify" and body["choices"] and "다음 중 하나인가요" in body["answer"], body
    view = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()
    assert view["version"] == 1


def test_a_model_failure_or_an_id_outside_the_list_changes_nothing_and_does_not_fall_back_to_rules(decided):
    down = _say(decided, "고장 났을 때 점심 바꿔", "du-e1")
    assert down["status"] == "escalated" and down["reason"] == "decision_failed", down
    assert "일정은 바꾸지 않았어요" in down["answer"]
    outside = _say(decided, "없는 번호 바꿔", "du-e2")
    assert outside["status"] == "escalated" and "목록 밖" in outside["failure"], outside
    view = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()
    assert view["version"] == 1
    with get_connection() as conn, conn.cursor() as cur:        # 실패도 기록에 남는다(오류 리포트)
        cur.execute("SELECT state_json->'decision' FROM customer_cases WHERE case_id=%s", (down["case_id"],))
        assert "failed" in cur.fetchone()[0]


def test_the_configured_mode_is_really_on_and_a_bare_yaml_on_is_not_read_as_off():
    """`[2026-09-29]` 설정의 `mode: on` 이 YAML 에서 참(True)으로 읽혀 결정 단위가 꺼진 채로 돌았다(실서버)."""
    from app.core.settings import get_guardrails
    from app.modules.travel_ops import trip_messages, web_guard

    assert get_guardrails().get("travel.decision_unit.mode") == "on"
    assert web_guard._mode_text(True) == "on" and web_guard._mode_text("shadow") == "shadow"

    class Structured:
        def structured(self, *a, **k):
            return {}

    assert trip_messages._decision_mode(Structured()) == "on"


def test_undoing_an_older_change_asks_once_and_a_yes_then_undoes_it(decided):
    """뒤에 다른 변경이 있는 옛 변경을 되돌리라면 한 번 묻고(버전 번호 없이), 「네」면 되돌린다 — 다시 묻지 않는다."""
    _say(decided, "점심 다른 데로 바꿔", "du-f1")                       # c2 — 점심
    _say(decided, "저녁 다른 데로 바꿔", "du-f2")                       # c3 — 저녁(점심 변경은 그대로 살아 있다)
    decider = decided["decider"]
    first_change = lambda user: re.findall(r"^(c\d+) \|", user, re.M)[0]  # noqa: E731

    original = decider.structured

    def older(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        return {"action": "rollback", "target_item": "none", "target_change": first_change(user), "fact": "none",
                "minutes": 0, "choices": []}

    decider.structured = older
    asked = _say(decided, "처음 바꾼 거 되돌려", "du-f3")
    assert asked["status"] == "ask_rollback" and "그래도 되돌릴까요" in asked["answer"] and "번 일정" not in asked["answer"]
    yes = _say(decided, "네, 되돌려 줘", "du-f4")
    decider.structured = original
    assert yes["status"] == "rolled_back", yes


def test_looking_for_options_never_offers_the_original_place(decided):
    """`[2026-09-29 ui 세션 지적]` 「알아봐 줘」 후보에 원래 곳(「3) 금용문」)이 섞였다 — 되돌리기용 기록이 고를 안으로 새었다."""
    decider = decided["decider"]
    original = decider.structured

    def propose(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        return {"action": "propose_alternatives", "target_item": decider._alias(user, "성수 점심"),
                "target_change": "none", "fact": "none", "minutes": 0, "choices": []}

    decider.structured = propose
    body = _say(decided, "점심 다른 데 알아봐 줘", "du-g1")
    decider.structured = original
    assert body["status"] == "asked", body
    names = [o["name"] for o in body["outcome"]["options"]]
    assert names and "성수 점심 식당" not in names and "성수 점심 식당" not in body["answer"].split("—", 1)[1]
    assert [o["rank"] for o in body["outcome"]["options"]] == list(range(1, len(names) + 1))


def test_undoing_a_change_that_is_already_undone_asks_instead(decided):
    """`[2026-09-29 ui 세션 지적]` 이미 되돌린 변경을 또 되돌리자고 했다(「바꿔」에) — 되돌리지 않고 「다음 중 하나인가요?」."""
    _say(decided, "점심 다른 데로 바꿔", "du-h1")                        # c2
    _say(decided, "원래대로 돌려 줘", "du-h2")                            # c3 — c2 를 되돌림
    decider = decided["decider"]
    original = decider.structured

    def stale(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        first = re.findall(r"^(c\d+) \|", user, re.M)[0]
        return {"action": "rollback", "target_item": "none", "target_change": first, "fact": "none", "minutes": 0,
                "choices": [{"action": "apply_change", "target_item": decider._alias(user, "성수 점심"),
                             "target_change": "none", "fact": "none"}]}

    decider.structured = stale
    body = _say(decided, "바꿔 줘", "du-h3")
    decider.structured = original
    assert "지금 일정에 없음" in decider.prompts[-1]                        # 모델에게도 알려 준다
    assert body["status"] == "clarify" and "다음 중 하나인가요" in body["answer"], body
    assert body["choices"] and "다른 곳으로 바꿔 줘" in body["choices"][0]["message"]
    view = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()
    assert view["version"] == 3                                              # 아무것도 안 바뀌었다


def test_when_the_model_gives_no_choices_the_server_still_offers_some(decided):
    """`[2026-09-29 ui 세션 지적]` 되물을 때 후보가 비면 웹에 버튼이 없다 — 서버가 바꿀 수 있는 가까운 일정 셋을 버튼으로 싣는다."""
    decider = decided["decider"]
    original = decider.structured

    def unclear(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        return {"action": "clarify", "target_item": "none", "target_change": "none", "fact": "none", "minutes": 0,
                "choices": []}

    decider.structured = unclear
    body = _say(decided, "음", "du-i1")
    decider.structured = original
    assert body["status"] == "clarify" and 1 <= len(body["choices"]) <= 3, body
    assert all(c["message"].endswith("다른 곳으로 바꿔 줘") for c in body["choices"])
    assert "다음 중 하나인가요" in body["answer"]


def test_where_is_it_gets_one_line_and_a_map_link_not_the_whole_description(decided):
    """☆`[2026-09-29 ui 세션 — 사용자 실사용 결함]` 「그건 어딧는거야」에 장소·주소·운영시간·예약·오는 길까지 열 줄이 나갔다.
    위치를 물으면 주소(또는 모름)와 **지도 앱 링크**만."""
    body = _say(decided, "그 식당 어딨어", "du-where")
    assert body["decision"]["fact"] == "address", body
    assert "https://www.google.com/maps/search/" in body["answer"], body["answer"]
    assert "예약" not in body["answer"].split("혹시")[0] and "다음 일정" not in body["answer"]
    assert "more" not in body
    # ★`[2026-09-29 사용자 지시]` 답하면서 「혹시 이런 뜻이었나요?」 — 가까운 질문을 버튼으로
    assert body["choices_title"] == "혹시 이런 뜻이었나요?" and 1 <= len(body["choices"]) <= 3, body
    assert any("가는 길" in c["message"] for c in body["choices"])
    # ★`[2026-09-29 ui 세션 요청]` 웹 답 문장에는 목록이 없다(버튼으로 그린다) — 대화 기록(글만)에는 목록이 남는다
    assert "혹시 이런 뜻이었나요?" not in body["answer"]
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat", headers=_h(decided["key"])).json()
    assert "혹시 이런 뜻이었나요?" in turns["turns"][-1]["text"], turns


def test_when_every_reading_is_a_question_it_answers_first_and_offers_the_rest(decided):
    """☆`[2026-09-29 사용자 지시]` 「예약 표시 알려 줘」를 두 일정 중 어느 것이냐고 되물었다 — 사실 질문은 잘못 짚어도 잃는 것이
    없으니 첫 해석으로 **먼저 답하고** 나머지를 「혹시 이런 뜻이었나요?」로. 바꾸기는 지금처럼 묻는다."""
    body = _say(decided, "예약 표시 알려 줘", "du-book")
    assert body["status"] == "answered" and body["decision"]["action"] == "answer_fact", body
    assert body["decision"]["fact"] == "booking" and "성수 점심" in body["decision"]["item"]
    assert any("저녁" in c["message"] or "예약" in c["message"] for c in body["choices"]), body
    unclear = _say(decided, "바꿔", "du-book-2")
    assert unclear["status"] == "clarify"                                   # 바꾸기는 여전히 되묻는다


def test_a_general_question_answers_the_core_first_and_keeps_the_rest_for_more(decided):
    """☆`[2026-09-29 ui 세션 요청]` 전반을 물어도 핵심(무엇 · 어디 · 그날 영업 · 다음 일정)만 먼저 — 나머지는 「더 보기」(`more`)."""
    body = _say(decided, "성수 점심 식당 알려줘", "du-core")
    assert "· 어디:" in body["answer"] and "· 다음 일정:" in body["answer"], body["answer"]
    assert "· 예약:" not in body["answer"] and "더 보기" not in body["answer"]
    assert "· 예약:" in body["more"], body
