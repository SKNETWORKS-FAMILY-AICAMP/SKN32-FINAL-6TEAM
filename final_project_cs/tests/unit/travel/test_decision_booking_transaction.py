"""업체 예약 취소·변경 · 환불 · 결제 실행 요청은 **지원하지 않는 요청**이라고 답한다 — 공개 상태 · 계약은 그대로다.

`[2026-10-26 사용자 지시]` 「내 예약을 취소하고 카드로 환불해줘」를 모델이 규정 질문(`ask_policy`)으로 읽어
「규정 자료에서 맞는 내용을 찾지 못했다」로 끝났다(U01). 계약(공개 status · reason 값)은 바꾸지 않고, 우리 백엔드 답 문장만
「지원하지 않는 요청」 안내로 한다. 판별은 고객 문장 낱말이 아니라 **모델이 고른 할 일**(`booking_transaction`)이다 —
기존 미지원 갈래(`UNSUPPORTED`, 여행 설정 `edit_trip` 과 같은 길)로 닫는다: 할 일은 `other`, 공개 상태는 `answered`, 실행 0.
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.conversation import decision_unit as du

KST = ZoneInfo("Asia/Seoul")
ITEM = SimpleNamespace(item_id=uuid4(), kind="dining", title="명동교자", place={"name": "명동교자"}, seq=1,
                       starts_at=datetime(2030, 1, 2, 12, 0, tzinfo=KST), ends_at=None)
STOPS = [du.Stop("i1", ITEM)]
MESSAGE = "내 예약을 취소하고 카드로 환불해줘"
NOTICE = ("업체 예약 취소·변경이나 환불·결제는 지원하지 않는 요청이라 처리하지 않았어요. "
          "예약한 업체에 직접 문의해 주세요. 일정은 바꾸지 않았어요.")


def _decide(answer, message=MESSAGE):
    class Chat:
        def structured(self, system, user, schema, *, num_predict=160):
            self.system, self.schema = system, schema
            return {"target_item": "none", "target_change": "none", "fact": "none", "minutes": 0, "choices": [],
                    "reads": [], "social": "", "general_requests": [], **answer}
    chat = Chat()
    decision = du.decide(chat, stops=STOPS, changes=[], history=[], selected_item_id=None, message=message)
    return decision, chat


def _offered(schema, path):
    branches = schema.get("anyOf", [schema])
    found = set()
    for branch in branches:
        node = branch
        for key in path:
            node = node[key]
        found |= set(node)
    return found


def test_vendor_booking_transaction_is_closed_by_the_existing_unsupported_path():
    decision, _ = _decide({"action": "booking_transaction"})
    assert decision.action == "other"                         # 실행할 할 일로 넘기지 않는다(공개 처리는 기존 other → answered)
    assert decision.raw["unsupported"] == "booking_transaction"
    assert decision.social == NOTICE == du.UNSUPPORTED["booking_transaction"]
    assert decision.item is None and decision.change is None and decision.choices == []
    assert du.stands_alone(decision)                          # 대기 되묻기가 있어도 이 안내가 답이다


def test_a_stray_target_does_not_turn_the_request_into_an_itinerary_action():
    decision, _ = _decide({"action": "booking_transaction", "target_item": "i1", "fact": "booking"})
    assert decision.action == "other" and decision.raw["unsupported"] == "booking_transaction"
    assert decision.social == NOTICE


def test_the_model_can_choose_it_but_it_is_never_offered_as_a_clarify_choice():
    _, chat = _decide({"action": "booking_transaction"})
    assert "booking_transaction" in _offered(chat.schema, ("properties", "action", "enum"))
    assert "booking_transaction" not in _offered(
        chat.schema, ("properties", "choices", "items", "properties", "action", "enum"))
    assert "booking_transaction" not in du.EDIT_ACTIONS and "booking_transaction" not in du.SERVER_ACTIONS


def test_a_clarify_candidate_for_it_is_dropped_not_executed():
    decision, _ = _decide({"action": "clarify", "choices": [
        {"action": "booking_transaction", "target_item": "none", "target_change": "none", "fact": "none"},
        {"action": "ask_policy", "target_item": "none", "target_change": "none", "fact": "booking"}]})
    assert [c["action"] for c in decision.choices] == ["ask_policy"]


def test_the_decision_is_the_models_action_not_a_keyword_match_on_the_sentence():
    """같은 문장이어도 모델이 규정 질문으로 고르면 서버가 낱말로 덮어쓰지 않는다(판별은 고른 할 일뿐)."""
    policy, _ = _decide({"action": "ask_policy", "fact": "booking"})
    assert policy.action == "ask_policy" and "unsupported" not in policy.raw and policy.social == ""
    question, _ = _decide({"action": "ask_policy"}, message="이 예약 취소 위약금은 얼마야?")
    assert question.action == "ask_policy" and "unsupported" not in question.raw


def test_the_instruction_defines_it_against_policy_service_and_remove():
    _, chat = _decide({"action": "booking_transaction"})
    line = next(row for row in chat.system.splitlines() if row.startswith("- booking_transaction:"))
    for neighbour in ("ask_policy", "answer_service", "remove_item"):
        assert neighbour in line


def test_the_existing_trip_settings_notice_is_unchanged():
    assert set(du.UNSUPPORTED) == {"edit_trip", "booking_transaction"}
    decision, _ = _decide({"action": "edit_trip"}, message="인원 4명으로 바꿔줘")
    assert decision.raw["unsupported"] == "edit_trip"
    assert decision.social == "여행 인원·이름·기간 같은 여행 설정을 바꾸는 일은 아직 채팅에서 하지 못해 일정은 바꾸지 않았어요."
