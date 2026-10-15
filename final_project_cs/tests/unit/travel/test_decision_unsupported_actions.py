"""시간 옮기기 · 일정 넣기 · 빼기 · 이름 말한 곳으로 바꾸기 · 순서 · 고정은 **실행할 할 일로 넘긴다** — 「아직 채팅에서 못 해요」로 막지 않는다.

`[2026-10-15 사용자 지시]` 10-14 에는 이 셋을 「정직한 안내」로 막았다(그 전엔 엉뚱한 「다른 곳으로 바꿔 줘」 되묻기로 끼웠다 —
x600 서버 웹 채팅 시험 2026-10-13: 시간 변경 58건 실행 0 · 엉뚱한 되묻기 29건, 추가·삭제 26건 정상 0). 막은 뒤에도 실서버 재시험(10-14)에서
옮기기 51건 중 40 · 넣기 8/8 · 빼기 10/11 이 「못 해요」로 끝났다. 이제 웹 「일정 수정」과 같은 길(`chat_edit`)로 실행한다 — 실행은
`tests/e2e/test_chat_edit_web.py` 가 본다. 여기는 해석이 그 할 일을 **버리지 않고 넘기는지**만 본다.
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du

KST = ZoneInfo("Asia/Seoul")
ITEM = SimpleNamespace(item_id=uuid4(), kind="dining", title="명동교자", place={"name": "성수망치버거"}, seq=1,
                       starts_at=datetime(2026, 10, 14, 12, 30, tzinfo=KST), ends_at=None)
STOPS = [du.Stop("i1", ITEM)]


def _decide(answer, message="문장"):
    class Chat:
        def structured(self, system, user, schema, *, num_predict=160):
            self.schema = schema
            return {"target_item": "none", "target_change": "none", "fact": "none", "minutes": 0, "choices": [],
                    "reads": [], "social": "", "general_requests": [], **answer}
    chat = Chat()
    decision = du.decide(chat, stops=STOPS, changes=[], history=[], selected_item_id=None, message=message)
    return decision, chat.schema


@pytest.mark.parametrize("action", ["change_time", "remove_item", "lock_item", "unlock_item"])
def test_edit_requests_are_passed_on_to_be_executed_not_refused(action):
    decision, _ = _decide({"action": action, "target_item": "i1"})
    assert decision.action == action and decision.item is ITEM
    assert "unsupported" not in decision.raw and "아직 채팅에서" not in decision.social
    assert du.stands_alone(decision)                     # 대기 중인 되묻기가 있어도 새 요청으로 처리한다


def test_add_needs_the_place_name_and_keeps_it():
    decision, _ = _decide({"action": "add_item", "destination_text": "통인시장"})
    assert decision.action == "add_item" and du.stands_alone(decision)
    nameless, _ = _decide({"action": "add_item"})
    assert nameless.action == "add_item" and not du.stands_alone(nameless)   # 어디를 넣을지 모른다 — 실행기가 되묻는다


def test_a_named_place_change_goes_to_the_named_replacement_not_to_a_candidate_list():
    """「경복궁 대신 창덕궁 가자」 — 전에는 다른 안만 보이고 「바로 바꾸는 기능은 아직 없어요」라고 답했다(10-14 실서버)."""
    decision, _ = _decide({"action": "apply_change", "target_item": "i1", "destination_text": "창덕궁"})
    assert decision.action == "replace_named" and decision.item is ITEM
    assert decision.raw["named_destination"] == {"text": "창덕궁", "from_action": "apply_change"}


def test_a_conditional_change_is_still_not_applied_now():
    decision, _ = _decide({"action": "apply_change", "target_item": "i1", "destination_text": "실내",
                           "condition_text": "내일 비 오면"})
    assert decision.action == "propose_alternatives"     # 조건부는 지금 바꾸지 않는다(다른 안만)


def test_edit_actions_are_offered_to_the_model_but_server_only_ones_are_not():
    _, schema = _decide({"action": "other"})
    offered = set(schema["properties"]["action"]["enum"])
    assert {"change_time", "add_item", "remove_item", "swap_order", "lock_item", "unlock_item"} <= offered
    assert "replace_named" not in offered and not du.UNSUPPORTED
    decision, _ = _decide({"action": "clarify", "choices": [{"action": "change_time", "target_item": "i1",
                                                            "target_change": "none", "fact": "none"}]})
    assert [c["action"] for c in decision.choices] == ["change_time"]


def test_the_shift_size_comes_from_the_sentence_and_the_direction_from_the_model():
    later, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": 30}, message="명동교자 30분 늦춰줘")
    earlier, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": -60}, message="명동교자 1시간 당겨줘")
    made_up, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": 45}, message="명동교자 좀 늦춰줘")
    assert (later.minutes, earlier.minutes, made_up.minutes) == (30, -60, None)
    assert [du.spoken_minutes(m) for m in ("한 시간 반 미뤄", "두 시간", "반 시간만", "오후 3시로")] == [90, 120, 30, None]


def test_clarify_choices_name_the_itinerary_title_not_the_linked_place():
    message = du.choice_message({"action": "apply_change", "item": ITEM, "change": None, "fact": "none"},
                                datetime(2026, 10, 13, 9, 0, tzinfo=KST))
    assert message == "2일차 12:30 명동교자 다른 곳으로 바꿔 줘"


def test_fields_unused_by_the_chosen_action_are_ignored_not_fatal():
    """할 일은 맞게 골랐는데 읽기 칸이 군더더기로 채워져도 해석을 버리지 않는다(x600 해석 실패 13건 중 9건)."""
    decision, _ = _decide({"action": "change_time", "target_item": "i1",
                           "reads": [{"fact": "price", "target_item": "i1", "origin_item": "i1", "origin_text": "",
                                      "transport_mode": "any", "reference": "none", "query": None, "text": "", "advice": ""}],
                           "query": {"day": "d1", "period": "all", "kind": "all", "position": "all"}, "fact": "schedule"})
    assert decision.action == "change_time" and decision.reads == [] and decision.query is None
    assert decision.raw["ignored_for_action"] == {"reads": 1, "fact": "schedule",
                                                  "query": {"day": "d1", "period": "all", "kind": "all", "position": "all"}}


def test_a_scope_with_no_target_is_kept_for_shifting_several_stops():
    decision, _ = _decide({"action": "change_time", "minutes": 60,
                           "query": {"day": "d1", "period": "afternoon", "kind": "all", "position": "all"}},
                          message="오후 일정 전부 한 시간씩 밀어줘")
    assert decision.action == "change_time" and decision.query == {"day": "d1", "period": "afternoon", "kind": "all", "position": "all"}
    assert decision.minutes == 60 and du.stands_alone(decision)


def test_an_item_fact_with_a_stray_list_scope_keeps_the_fact():
    decision, _ = _decide({"action": "answer_fact", "target_item": "i1", "fact": "time",
                           "query": {"day": "d1", "period": "all", "kind": "all", "position": "all"}})
    assert decision.action == "answer_fact" and decision.fact == "time" and decision.query is None
    assert "query" in decision.raw["ignored_for_action"]


def test_a_general_request_with_an_empty_answer_is_dropped_not_fatal():
    decision, _ = _decide({"action": "add_item", "destination_text": "카페",
                           "general_requests": [{"question": "카페 하나 추가해줘", "answer": ""}]})
    assert decision.action == "add_item" and decision.raw["ignored_for_action"]["general_requests"] == 1


def test_a_conditional_edit_is_not_applied_now_and_says_how_to_do_it_now():
    """`[2026-10-15 Codex 검토]` 「비 오면 북촌 30분 늦춰」 — 조건을 확인할 수 없으니 지금 바꾸지 않는다."""
    decision, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": 30, "condition_text": "비 오면"},
                          message="비 오면 명동교자 30분 늦춰줘")
    assert decision.action == "other" and decision.raw["condition_guard"]["blocked_action"] == "change_time"
    assert "조건 없이 다시 말씀해 주세요" in decision.social and du.stands_alone(decision)


def test_the_direction_comes_from_the_sentence_first_and_unknown_direction_is_not_guessed():
    """`[2026-10-15 Codex 검토]` 모델이 0 을 내도 「앞당겨」면 당기고, 방향 말도 부호도 없으면 옮기지 않는다(실행기가 되묻는다)."""
    earlier, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": 0}, message="명동교자 30분 앞당겨줘")
    flipped, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": 30}, message="명동교자 30분 일찍 가자")
    unknown, _ = _decide({"action": "change_time", "target_item": "i1", "minutes": 0}, message="명동교자 30분 옮겨줘")
    assert (earlier.minutes, flipped.minutes, unknown.minutes) == (-30, -30, None)
    assert [du.spoken_direction(m) for m in ("늦춰줘", "당겨줘", "옮겨줘", "늦게 일찍")] == [1, -1, None, None]
