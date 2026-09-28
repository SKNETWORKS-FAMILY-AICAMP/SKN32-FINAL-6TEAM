# -*- coding: utf-8 -*-
"""교사 라벨링 스크립트의 어휘가 제품 어휘와 같은가.

★라벨링 스크립트는 GPU 기계에서 저장소 없이 돌아서 어휘를 **복사해 들고 간다.**
  제품 어휘가 바뀌었는데 복사본이 안 바뀌면, 학습한 모델이 제품이 모르는 라벨을
  내거나 제품 라벨을 영원히 못 낸다 — 커머스 시절 `INTENTS` 가 옛 어휘로 남아
  운영 분류가 전량 실패한 사고와 같은 모양이다(2026-08-17).
"""
from app.modules.travel_ops.feedback import INTENTS, ISSUE_CODES
from ml import label_with_gemma


def test_teacher_intents_match_product():
    assert set(label_with_gemma.INTENTS) == set(INTENTS)


def test_teacher_issue_codes_match_product():
    assert set(label_with_gemma.ISSUE_CODES) == set(ISSUE_CODES)


def test_every_issue_code_is_explained_to_the_teacher():
    """뜻풀이가 빠진 코드는 교사가 거의 안 고른다 — 분포가 조용히 기운다."""
    for code in ISSUE_CODES:
        assert code in label_with_gemma.GUIDE, code
    for intent in INTENTS:
        assert intent in label_with_gemma.GUIDE, intent
