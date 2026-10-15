"""잡담을 일반 질문 칸에 옮겨 적고 답만 비운 해석은 버리지 않는다 — 모델이 이미 `social` 로 답했기 때문이다.

`[2026-10-15]` 고정 1,448문장 회귀를 제품 경로(학습 E4B · 최신 코드)로 재생했더니 일정과 무관한 잡담 1,300문장 중 100건(7.7%)이
「일반 요청의 질문·답이 유효하지 않습니다」로 해석 전체가 버려졌다. 모두 `action=other` 에 `social` 은 채워져 있고 `general_requests` 에
고객 말을 그대로 옮긴 칸이 하나 있었으며 답은 빈 문자열이었다. `social` 도 비어 있으면(고객 말에 아무 답도 없음) 예전처럼 실패로 드러낸다.
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
MESSAGE = "요즘은 파충류도 반려동물로 많이 키우던데"


def _decide(answer):
    class Chat:
        def structured(self, system, user, schema, *, num_predict=160):
            return {"target_item": "none", "target_change": "none", "fact": "none", "minutes": 0, "choices": [],
                    "reads": [], "social": "", "general_requests": [], **answer}
    return du.decide(Chat(), stops=STOPS, changes=[], history=[], selected_item_id=None, message=MESSAGE)


@pytest.mark.parametrize("action", ["other", "answer_service"])
def test_empty_general_answer_is_dropped_when_social_already_replied(action):
    decision = _decide({"action": action, "social": "흥미로운 주제네요.",
                        "general_requests": [{"question": MESSAGE, "answer": ""}]})
    assert decision.action == action and decision.item is None
    assert decision.social == "흥미로운 주제네요."          # 빈 칸은 버리고 모델의 답만 나간다
    assert decision.raw["ignored_for_action"]["general_requests"] == 1


# ★`[2026-10-15 커밋 세션]` answer_service 는 「채팅 해석 재측정」(1a733c54)에서 빈 일반 답이어도 서버가 서비스 안내로 답하게 바뀌어
#   실패 쪽 기대에서 뺐다(원격 role-manager 판에 맞춤). other 만 여전히 실패로 드러낸다.
@pytest.mark.parametrize("action", ["other"])
def test_empty_general_answer_without_any_reply_still_fails_loudly(action):
    with pytest.raises(du.DecisionFailed):
        _decide({"action": action, "social": "", "general_requests": [{"question": MESSAGE, "answer": ""}]})


def test_a_filled_general_answer_is_kept_as_before():
    decision = _decide({"action": "other", "social": "",
                        "general_requests": [{"question": MESSAGE, "answer": "네, 인기가 늘었어요."}]})
    assert "네, 인기가 늘었어요." in decision.social
