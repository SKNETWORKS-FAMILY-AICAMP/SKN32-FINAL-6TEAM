# -*- coding: utf-8 -*-
"""우리가 학습한 감정 모델을 제품이 부르는 자리 — 계약과 물러섬.

★모델 산출물은 저장소 밖에 있다(용량). 없는 기계에서는 **건너뛴다** — 다만
  「모델이 없으면 조용히 기본값을 낸다」가 아니라 **예외로 알린다**는 것은
  모델 없이도 시험한다. 그게 이 어댑터의 핵심 약속이다.
"""
from __future__ import annotations

import pytest

from app.infrastructure.ml.sentiment import (SENTIMENTS, LocalSentiment,
                                             SentimentUnavailable)
from app.modules.travel_ops.feedback import SENTIMENTS as PRODUCT_SENTIMENTS


def _baseline() -> LocalSentiment:
    model = LocalSentiment()
    if not (model.path / "model.joblib").exists():
        pytest.skip(f"학습 산출물이 없다: {model.path} — `python -m ml.train_baseline` 로 만든다")
    return model


def test_labels_match_the_product_vocabulary():
    """★어댑터가 내는 라벨이 제품 어휘 밖이면 분류가 통째로 실패한다."""
    assert set(SENTIMENTS) == set(PRODUCT_SENTIMENTS)


def test_missing_model_is_announced_not_defaulted(tmp_path):
    """★모델이 없으면 **켜지지 않는다.** 조용히 중립을 내면 신호 없는 축소다."""
    model = LocalSentiment(tmp_path / "없는폴더")
    with pytest.raises(SentimentUnavailable):
        model("배송이 빨라서 좋았어요")


def test_clear_sentences_are_classified():
    model = _baseline()
    positive = model("정말 만족스럽고 좋아요 다음에 또 쓸게요")
    negative = model("최악이에요 다시는 안 씁니다 환불해 주세요")
    assert positive["sentiment"] == "positive", positive
    assert negative["sentiment"] == "negative", negative
    assert positive["abstained"] is False and negative["abstained"] is False


def test_low_confidence_falls_back_to_neutral():
    """★학습 라벨에 중립이 없다 — 중립은 **물러선 결과**로만 나온다."""
    model = LocalSentiment(threshold=0.999)   # 사실상 모든 문장이 확신 미달이 된다
    if not (model.path / "model.joblib").exists():
        pytest.skip("학습 산출물이 없다")
    answer = model("내일 일정 그대로 가면 되나요")
    assert answer["sentiment"] == "neutral"
    assert answer["abstained"] is True
    assert 0.0 <= answer["confidence"] <= 1.0


def test_contract_keys_are_stable():
    model = _baseline()
    answer = model("바꿔주신 식당 좋았어요")
    assert set(answer) == {"sentiment", "confidence", "abstained", "model"}
    assert answer["sentiment"] in SENTIMENTS


def test_trained_transformer_loads_through_the_same_adapter():
    """★GPU 에서 학습한 A.X 인코더를 **제품 어댑터 그대로** 부른다 — 부르는 쪽은 종류를 모른다."""
    from app.infrastructure.ml.sentiment import _artifact_root

    model_dir = _artifact_root() / "sentiment_ko" / "skt__A.X-Encoder-base"
    if not (model_dir / "config.json").exists():
        pytest.skip(f"학습 산출물이 없다: {model_dir}")
    model = LocalSentiment(model_dir, threshold=0.9)
    assert model.kind == "transformer"
    positive = model("바꿔주신 식당 정말 좋았어요 감사합니다")
    negative = model("추천해준 식당 갔더니 문 닫혀 있었어요 어이가 없네요")
    assert positive["sentiment"] == "positive", positive
    assert negative["sentiment"] == "negative", negative
    assert set(positive) == {"sentiment", "confidence", "abstained", "model"}
