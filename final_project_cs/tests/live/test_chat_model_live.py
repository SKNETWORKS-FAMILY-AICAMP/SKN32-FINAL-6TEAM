# -*- coding: utf-8 -*-
"""**실제 모델**(모델 서버 의 gemma4 — 설정 `ACOP_OLLAMA_BASE_URL`)이 채팅 대표 문장을 제대로 읽는가. `[2026-09-29]`

★왜 따로 있나. 자동 시험(`tests/e2e/test_web_api.py` 등)은 모델 자리에 **자동 시험 안에서만 쓰는 정해진 답**을 끼운다 —
  「모델이 '늦음 30분'이라고 읽었을 때 서버가 맞게 처리하나」는 증명하지만 「진짜 모델이 그렇게 읽나」는 증명하지 못한다.
  그 뒤쪽을 여기서 본다. 실서버(8042)가 부르는 것과 **같은 함수**(`trip_intake.extract` · `feedback.classify`)를 같은 설정으로 부른다.
★그전에 있던 실제 모델 시험 둘은 낡았다 — 하나는 크레딧이 떨어진 OpenAI 를, 하나는 쇼핑몰 시절 문장을 쓴다(2026-09-29 확인).
★모델 서버 GPU 는 다른 작업과 나눠 쓴다 — 모델을 올리므로 **그 작업이 없을 때** 돌린다:

    python -m pytest tests/live/test_chat_model_live.py -m live -v
"""
from __future__ import annotations

import pytest

from app.core.settings import get_settings

pytestmark = pytest.mark.live

#: (문장, 기대하는 신고 종류, 추가로 맞아야 할 값). 종류가 둘 중 하나면 둘 다 받는다(해석이 갈리는 문장)
CASES = [
    ("식당에 30분 늦을 것 같아요", {"delay"}, {"minutes": 30}),
    ("팝업스토어 줄이 길어서 점심에 70분 늦을 것 같아요", {"delay"}, {"minutes": 70}),
    ("저녁 먹으려던 식당이 오늘 임시휴무래요", {"closed"}, {}),
    ("라면 선물세트가 품절이에요. 이 근처에 파는 다른 곳 없어?", {"stock_out"}, {}),
    ("2번 일정으로 되돌려 주세요", {"rollback"}, {"to_version": 2}),
    ("점심 식당 다른 데로 바꿔 줘", {"change"}, {}),
    ("취소하면 위약금 있어요?", {"question"}, {}),
    ("경복궁 몇 시에 가요?", {"question"}, {}),
    ("안녕하세요", {"other"}, {}),
    ("파이썬 코드 짜줘", {"other", "question"}, {}),
    ("오늘 비트코인 시세 알려줘", {"other", "question"}, {}),
]


@pytest.fixture(scope="module")
def chat():
    from app.infrastructure.ollama_chat import from_settings

    client = from_settings(get_settings())
    if client is None:
        pytest.skip("ACOP_OLLAMA_BASE_URL 이 비어 있다 — 실제 모델이 연결돼 있지 않다")
    return client


@pytest.mark.parametrize("message, kinds, values", CASES, ids=[c[0] for c in CASES])
def test_the_real_model_reads_a_customer_sentence(chat, message, kinds, values):
    from app.domains.travel_ops.components.conversation.trip_intake import extract

    report = extract(message, chat)
    assert report is not None, f"모델이 쓸 수 없는 답을 냈다: {message}"
    assert report["type"] in kinds, (message, report)
    for key, expected in values.items():
        assert report.get(key) == expected, (message, report)


@pytest.mark.parametrize("message", ["식당에 30분 늦을 것 같아요", "취소하면 위약금 있어요?", "안녕하세요"])
def test_the_real_classifier_gives_all_three_labels(chat, message):
    """모든 Case 가 거치는 분류(의도 · 이슈 코드 · 감정) — 빈 라벨이면 분류 실패로 사람 대기가 된다."""
    from app.domains.travel_ops.components.core_hooks.feedback import classify

    result = classify(message)
    assert result.intent and result.issue_code and result.sentiment, (message, result)
