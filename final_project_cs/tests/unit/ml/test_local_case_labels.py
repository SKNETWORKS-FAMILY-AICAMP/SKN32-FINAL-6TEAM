# -*- coding: utf-8 -*-
"""로컬 우선 · 모르면 LLM — 캐스케이드 제공자가 제품 분류 함수에 그대로 꽂히는가.

★모델 산출물 없이 시험한다 — 모델 자리를 가짜 확률로 바꿔 끼운다. 여기서 보는 것은
  **물러섬 규칙과 계약**이지 모델 정확도가 아니다(정확도는 `metrics.json`).
"""
from __future__ import annotations

import pytest

from app.infrastructure.ml import case_labels
from app.infrastructure.ml.case_labels import LocalCaseLabels, LocalLabelsUnsure
from app.modules.travel_ops import feedback


class _FakeModel:
    def __init__(self, label, confidence):
        self.label, self.confidence, self.name = label, confidence, "fake:model"

    def predict(self, text):
        return self.label, self.confidence


class _FakeSentiment:
    def __call__(self, text):
        return {"sentiment": "negative", "confidence": 0.97, "abstained": False, "model": "fake:sentiment"}


def _provider(intent_conf, issue_conf, fallback):
    provider = LocalCaseLabels.__new__(LocalCaseLabels)
    provider.intent = _FakeModel("incident_report", intent_conf)
    provider.issue = _FakeModel("dining_hours", issue_conf)
    provider.sentiment = _FakeSentiment()
    provider.fallback = fallback
    provider.threshold = case_labels.DEFAULT_LABEL_THRESHOLD
    provider.stats = {"local": 0, "fallback_unsure": 0, "failed_unsure": 0}
    return provider


def _llm(calls):
    def llm(text):
        calls.append(text)
        return {"sentiment": "neutral", "intent": "confirm_request", "issue_code": "other", "severity": "low"}
    return llm


def test_confident_local_labels_pass_the_product_classifier():
    calls: list[str] = []
    provider = _provider(0.95, 0.91, _llm(calls))
    result = feedback.classify("저녁 식당이 오늘 임시휴무래요", llm=provider)
    assert (result.intent, result.issue_code, result.sentiment) == ("incident_report", "dining_hours", "negative")
    assert result.severity == "low"            # ★심각도만 뒷받침에서 온다
    assert provider.stats["local"] == 1


def test_unsure_local_labels_are_discarded_not_guessed():
    calls: list[str] = []
    provider = _provider(0.95, 0.40, _llm(calls))
    result = feedback.classify("음", llm=provider)
    assert (result.intent, result.issue_code) == ("confirm_request", "other")   # 통째로 LLM 답
    assert provider.stats["fallback_unsure"] == 1


def test_without_fallback_unsure_fails_loudly():
    provider = _provider(0.30, 0.95, None)
    with pytest.raises(feedback.ClassificationFailed):
        feedback.classify("음", llm=provider)
    assert provider.stats["failed_unsure"] == 1


def test_without_fallback_severity_is_not_invented():
    provider = _provider(0.99, 0.99, None)
    with pytest.raises(LocalLabelsUnsure):
        provider("저녁 식당이 오늘 임시휴무래요")
