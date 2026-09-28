# -*- coding: utf-8 -*-
"""우리가 학습한 분류 모델 하나를 불러 `(라벨, 확신도)` 를 낸다 — 종류를 가리지 않는다.

★두 종류를 같은 모양으로 받는다 — 기준선(`model.joblib`, scikit-learn)과 파인튜닝한
  인코더(`config.json` 이 있는 폴더, transformers). **부르는 쪽은 둘을 구분하지 않는다.**

★**적재는 처음 부를 때까지 미룬다.** 학습 의존성이 운영 기동 경로에 들어오지 않게.

★**모델이 없으면 켜지지 않는다**(`LabelModelUnavailable`). 조용히 기본 라벨을 내면
  그게 바로 신호 없는 축소다(`CLAUDE.md` §1).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class LabelModelUnavailable(RuntimeError):
    """학습한 모델을 찾지 못했다. ★조용히 넘기지 않는다."""


def artifact_root() -> Path:
    """학습 산출물 폴더 — 저장소 밖(`<저장소>/../datasets/ml`), `ACOP_ML_DIR` 로 바꾼다."""
    base = os.environ.get("ACOP_ML_DIR")
    if base:
        return Path(base)
    return Path(__file__).resolve().parents[3].parent / "datasets" / "ml"


class LocalLabelModel:
    """폴더 하나 = 모델 하나. `probabilities(text)` 와 `predict(text)` 를 낸다."""

    def __init__(self, model_dir: str | Path, *, max_len: int = 96) -> None:
        self.path = Path(model_dir)
        self.kind = "transformer" if (self.path / "config.json").exists() else "sklearn"
        self.max_len = max_len
        self._model: Any = None
        self._tokenizer: Any = None

    @property
    def name(self) -> str:
        return f"{self.kind}:{self.path.name}"

    def _load(self) -> None:
        if self._model is not None:
            return
        if not self.path.exists():
            raise LabelModelUnavailable(f"학습한 모델이 없다: {self.path}")
        if self.kind == "sklearn":
            weights = self.path / "model.joblib"
            if not weights.exists():
                raise LabelModelUnavailable(f"모델 파일이 없다: {weights}")
            import joblib

            self._model = joblib.load(weights)
            return
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(str(self.path))
        self._model = AutoModelForSequenceClassification.from_pretrained(str(self.path))
        self._model.eval()

    def probabilities(self, text: str) -> dict[str, float]:
        self._load()
        if self.kind == "sklearn":
            scores = self._model.predict_proba([text])[0]
            return {str(label): float(score) for label, score in zip(self._model.classes_, scores)}
        import torch

        with torch.no_grad():
            encoded = self._tokenizer(text, truncation=True, max_length=self.max_len, return_tensors="pt")
            logits = self._model(**encoded).logits[0]
            scores = torch.softmax(logits, dim=-1).tolist()
        id2label = self._model.config.id2label
        return {str(id2label[index]): float(score) for index, score in enumerate(scores)}

    def predict(self, text: str) -> tuple[str, float]:
        probabilities = self.probabilities(text)
        best = max(probabilities, key=probabilities.get)
        return best, probabilities[best]


__all__ = ["LabelModelUnavailable", "LocalLabelModel", "artifact_root"]
