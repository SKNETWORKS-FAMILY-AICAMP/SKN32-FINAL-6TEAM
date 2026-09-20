# -*- coding: utf-8 -*-
"""감정 분류 모델 — 전처리 · 학습 · 평가.

★이 패키지는 **모델을 만드는 쪽**이다. 만든 모델을 제품이 쓰는 자리는
  `app/infrastructure/ml/` 다. 둘을 갈라 두는 이유는 학습 의존성
  (scikit-learn·transformers)이 **운영 기동 경로에 들어오면 안 되기** 때문이다.

★산출물(분할 데이터·모델 가중치)은 저장소 밖에 쓴다 — 용량이 크고 재생성된다.
  기본 위치는 `<저장소>/../datasets/ml/` 이고 `ACOP_ML_DIR` 로 바꾼다.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def artifact_dir(*parts: str) -> Path:
    """산출물 폴더. 없으면 만든다."""
    base = Path(os.environ.get("ACOP_ML_DIR") or (REPO_ROOT.parent / "datasets" / "ml"))
    path = base.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["REPO_ROOT", "artifact_dir"]
