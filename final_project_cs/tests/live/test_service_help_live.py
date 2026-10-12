"""설정된 실제 해석 모델의 기능 안내·여행 조회·변경 구분 표본 시험."""
from pathlib import Path

import pytest

from app.core.settings import get_settings
from app.domains.travel_ops.components.conversation.decision_unit import decide, stops_of
from app.infrastructure.ollama_chat import from_settings
from eval.decision_unit.replay import load_trips

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def model():
    chat = from_settings(get_settings())
    if chat is None:
        pytest.skip("실제 해석 모델 연결 설정을 확인하지 못했습니다")
    return chat


@pytest.mark.parametrize("message,action", [
    ("너가 할 수 있는 게 뭐야?", "answer_service"),
    ("어떤 기능을 쓸 수 있어?", "answer_service"),
    ("사용법 알려줘", "answer_service"),
    ("너는 누구야?", "answer_service"),
    ("예약도 대신 해 줘?", "answer_service"),
    ("경복궁이 뭐야?", "answer_fact"),
    ("점심 식당 다른 곳으로 바꿔 줘", "apply_change"),
    ("취소하면 위약금 있어요?", "ask_policy"),
    ("안녕하세요", "other"),
])
def test_real_model_separates_service_help_from_trip_actions(model, message, action):
    trips = load_trips(Path(__file__).resolve().parents[2] / "eval/decision_unit/trips.json")
    items, changes = trips["long7"]
    failure = None
    try:
        decision = decide(model, stops=stops_of(items), changes=changes, history=[],
                          selected_item_id=None, message=message)
    except Exception as exc:
        # 모델 연결 오류의 실제 접속 주소·공급자 응답 원문은 시험 보고에 싣지 않는다.
        failure = type(exc).__name__
    if failure:
        pytest.fail(f"실제 모델 호출·검증 실패: {failure}", pytrace=False)
    assert decision.action == action, (message, decision.action)
    if action == "answer_service":
        assert decision.item is None and decision.change is None and not decision.choices
