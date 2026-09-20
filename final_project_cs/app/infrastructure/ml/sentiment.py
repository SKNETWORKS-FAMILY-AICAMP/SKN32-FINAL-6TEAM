# -*- coding: utf-8 -*-
"""감정 분류 — 우리가 학습한 모델을 부르는 어댑터.

★**왜 필요한가.** 지금 감정은 LLM 이 낸다(`travel_ops/feedback.py`). 그 한 축을
  우리 모델이 맡으면 호출이 줄고, 망이 끊겨도 답이 나온다. **대신 정확도를
  숫자로 알고 써야 한다** — 지표는 산출물 폴더의 `metrics.json` 이 갖는다.

★**학습 라벨은 둘(긍정·부정)이고 제품 라벨은 셋이다**(중립 포함). 학습 말뭉치에
  중립이 **아예 없다** — 원 말뭉치에 별점 3점이 없다. 그래서 중립을 지어내지
  않는다. **확신이 낮으면 중립으로 물러선다**(`threshold`). 물러섰다는 사실을
  `abstained` 로 같이 돌려준다 — 조용히 중립이라고 답하면 「모름」과 「중립」이
  구분되지 않는다(`CLAUDE.md` §1).

★**모델이 없으면 켜지지 않는다.** 산출물이 없는 기계에서 조용히 기본값을 내면
  그게 바로 신호 없는 축소다. `SentimentUnavailable` 로 알린다.

★모델 적재·확률 계산은 `labels.LocalLabelModel` 하나가 한다(2026-09-17 통일) —
  감정·intent·issue_code 가 같은 방식으로 불린다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.infrastructure.ml.labels import LabelModelUnavailable, LocalLabelModel, artifact_root

#: 제품이 쓰는 감정 라벨(`travel_ops/feedback.py::SENTIMENTS` 와 같아야 한다).
SENTIMENTS = ("positive", "neutral", "negative")

#: ★기본 임계값 0.8 — 기준선 시험 조각에서 커버리지 84%·그때 정확도 0.96 이었다
#:  (`sentiment_ko/baseline/metrics.json`, 2026-09-16 실측). A.X 인코더는 여행 조각
#:  41건에서 0.9 가 가장 나았다(`skt__A.X-Encoder-base/cpu_eval.json`) — 41건이라
#:  기본값을 옮길 근거로는 부족해 그대로 둔다. 부르는 쪽이 정한다.
DEFAULT_THRESHOLD = 0.8


class SentimentUnavailable(LabelModelUnavailable):
    """학습한 감정 모델을 찾지 못했다. ★조용히 넘기지 않는다."""


def _artifact_root() -> Path:          # 옛 이름 — 시험이 쓴다
    return artifact_root()


class LocalSentiment:
    """학습한 감정 모델 하나를 들고 문장마다 라벨을 낸다."""

    def __init__(self, model_dir: str | Path | None = None, *,
                 threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold
        self._inner = LocalLabelModel(model_dir or artifact_root() / "sentiment_ko" / "baseline")

    # ── 평가 스크립트가 들여다보는 이름들 ───────────────────────
    @property
    def path(self) -> Path:
        return self._inner.path

    @property
    def kind(self) -> str:
        return self._inner.kind

    @property
    def _model(self) -> Any:
        return self._inner._model

    @property
    def _tokenizer(self) -> Any:
        return self._inner._tokenizer

    def _probabilities(self, text: str) -> dict[str, float]:
        try:
            return self._inner.probabilities(text)
        except LabelModelUnavailable as exc:
            raise SentimentUnavailable(str(exc)) from exc

    def __call__(self, text: str) -> dict[str, Any]:
        """`{"sentiment", "confidence", "abstained", "model"}` 를 돌려준다."""
        probabilities = self._probabilities(text)
        best = max(probabilities, key=probabilities.get)
        confidence = probabilities[best]
        abstained = confidence < self.threshold
        return {
            "sentiment": "neutral" if abstained else best,
            "confidence": round(confidence, 4),
            "abstained": abstained,
            "model": self._inner.name,
        }


__all__ = ["DEFAULT_THRESHOLD", "SENTIMENTS", "LocalSentiment", "SentimentUnavailable"]
