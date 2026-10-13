"""알아듣지만 아직 채팅으로 실행하지 않는 요청(시간 옮기기 · 일정 넣기 · 빼기)은 늘 같은 정직한 안내로 답한다.

전에는 할 일 목록에 이 셋이 없어 모델이 가장 가까운 「다른 곳으로 바꿔 줘」 되묻기로 끼웠다
(x600 서버 웹 채팅 시험 2026-10-13: 시간 변경 58건 실행 0 · 엉뚱한 되묻기 29건, 추가·삭제 26건 정상 0).
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


def _decide(answer):
    class Chat:
        def structured(self, system, user, schema, *, num_predict=160):
            self.schema = schema
            return {"target_item": "none", "target_change": "none", "fact": "none", "minutes": 0, "choices": [],
                    "reads": [], "social": "", "general_requests": [], **answer}
    chat = Chat()
    decision = du.decide(chat, stops=STOPS, changes=[], history=[], selected_item_id=None, message="문장")
    return decision, chat.schema


@pytest.mark.parametrize("action", ["change_time", "add_item", "remove_item"])
def test_unsupported_requests_get_the_same_honest_reply_and_change_nothing(action):
    decision, _ = _decide({"action": action, "target_item": "i1"})
    assert decision.action == "other" and decision.raw["unsupported"] == action
    assert decision.social == du.UNSUPPORTED[action] and "일정은 바꾸지 않았어요" in decision.social
    assert du.stands_alone(decision)                     # 대기 중인 되묻기가 있어도 새 요청으로 처리한다


def test_unsupported_requests_are_not_offered_as_clarify_choices():
    _, schema = _decide({"action": "other"})
    offered = schema["properties"]["choices"]["items"]["properties"]["action"]["enum"]
    assert not set(du.UNSUPPORTED) & set(offered)
    assert set(du.UNSUPPORTED) <= set(schema["properties"]["action"]["enum"])
    decision, _ = _decide({"action": "clarify", "choices": [{"action": "change_time", "target_item": "i1",
                                                            "target_change": "none", "fact": "none"}]})
    assert decision.choices == []                       # 실행할 수 없는 후보는 버린다


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
    assert decision.raw["unsupported"] == "change_time" and decision.reads == []
    assert decision.raw["ignored_for_action"] == {"reads": 1, "query": {"day": "d1", "period": "all", "kind": "all", "position": "all"},
                                                  "fact": "schedule"}


def test_an_item_fact_with_a_stray_list_scope_keeps_the_fact():
    decision, _ = _decide({"action": "answer_fact", "target_item": "i1", "fact": "time",
                           "query": {"day": "d1", "period": "all", "kind": "all", "position": "all"}})
    assert decision.action == "answer_fact" and decision.fact == "time" and decision.query is None
    assert "query" in decision.raw["ignored_for_action"]


def test_a_general_request_with_an_empty_answer_is_dropped_not_fatal():
    decision, _ = _decide({"action": "add_item", "general_requests": [{"question": "카페 하나 추가해줘", "answer": ""}]})
    assert decision.raw["unsupported"] == "add_item" and decision.raw["ignored_for_action"]["general_requests"] == 1
