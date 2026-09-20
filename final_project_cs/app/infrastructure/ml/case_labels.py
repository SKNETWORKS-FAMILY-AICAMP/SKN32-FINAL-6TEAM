# -*- coding: utf-8 -*-
"""학습한 모델로 Case 라벨을 내는 **제공자** — 로컬 우선, 모르면 LLM 에 넘긴다(캐스케이드).

    provider = LocalCaseLabels(intent_dir=..., issue_dir=..., sentiment_dir=..., fallback=llm)
    feedback.classify(text, llm=provider)          # 제품 분류 함수에 그대로 꽂힌다

★**모양은 LLM 제공자와 같다** — 글 하나를 받아 `sentiment·intent·issue_code·severity`
  네 칸짜리 dict 를 낸다. 어휘 검사는 `feedback.classify` 가 그대로 한다.

★**모르면 지어내지 않는다.** `intent`·`issue_code` 확신도가 임계값 아래면 **로컬 답을
  버리고** 뒷받침 LLM 에 통째로 넘긴다. 뒷받침이 없으면 실패로 알린다 → Case 는
  `escalated`(코어 1 규칙). 넘겼다는 사실은 `label_source` 로 남긴다.

★**`severity` 는 모델이 없다.** 학습 데이터에 심각도 라벨이 없었다. 규칙으로 채우면
  새 업무 규칙을 만드는 일이라 여기서 정하지 않는다 — 뒷받침 LLM 이 있으면 그 값을
  쓰고, 없으면 실패로 알린다. `[결정 필요]` 심각도를 규칙으로 채울지 팀이 정한다.

★**감정은 물러섬을 그대로 쓴다.** 확신이 낮은 감정은 중립이다(`sentiment.py`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.infrastructure.ml.labels import LocalLabelModel
from app.infrastructure.ml.sentiment import LocalSentiment

DEFAULT_LABEL_THRESHOLD = 0.7


class LocalLabelsUnsure(RuntimeError):
    """로컬 모델이 확신하지 못했고, 넘길 곳도 없다."""


class LocalCaseLabels:
    def __init__(self, *, intent_dir: str | Path, issue_dir: str | Path, sentiment_dir: str | Path,
                 fallback: Callable[[str], dict[str, Any]] | None = None,
                 threshold: float = DEFAULT_LABEL_THRESHOLD,
                 sentiment_threshold: float = 0.9) -> None:
        self.intent = LocalLabelModel(intent_dir)
        self.issue = LocalLabelModel(issue_dir)
        self.sentiment = LocalSentiment(sentiment_dir, threshold=sentiment_threshold)
        self.fallback = fallback
        self.threshold = threshold
        self.stats = {"local": 0, "fallback_unsure": 0, "failed_unsure": 0}

    def __call__(self, text: str) -> dict[str, Any]:
        intent, intent_conf = self.intent.predict(text)
        issue, issue_conf = self.issue.predict(text)
        unsure = min(intent_conf, issue_conf) < self.threshold
        if unsure:
            if self.fallback is None:
                self.stats["failed_unsure"] += 1
                raise LocalLabelsUnsure(
                    f"로컬 확신 부족(intent {intent_conf:.2f}, issue_code {issue_conf:.2f}) · 뒷받침 없음")
            self.stats["fallback_unsure"] += 1
            answer = dict(self.fallback(text))
            answer["label_source"] = "fallback:unsure"
            return answer

        if self.fallback is None:
            # ★심각도 모델이 없다 — 지어내지 않는다.
            self.stats["failed_unsure"] += 1
            raise LocalLabelsUnsure("severity 를 낼 모델도 뒷받침도 없다")
        severity = (self.fallback(text) or {}).get("severity")
        sentiment = self.sentiment(text)
        self.stats["local"] += 1
        return {
            "sentiment": sentiment["sentiment"], "intent": intent, "issue_code": issue,
            "severity": severity,
            "label_source": "local", "confidence": {"intent": round(intent_conf, 4),
                                                    "issue_code": round(issue_conf, 4),
                                                    "sentiment": sentiment["confidence"]},
            "models": {"intent": self.intent.name, "issue_code": self.issue.name,
                       "sentiment": sentiment["model"]},
        }


__all__ = ["DEFAULT_LABEL_THRESHOLD", "LocalCaseLabels", "LocalLabelsUnsure"]
