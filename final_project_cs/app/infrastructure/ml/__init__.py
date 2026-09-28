# -*- coding: utf-8 -*-
"""우리가 학습한 모델을 제품이 쓰는 자리.

★학습 쪽(`ml/`)과 갈라 둔다 — 학습 의존성(scikit-learn·transformers)이 운영
  기동 경로에 들어오면 안 된다. 여기서는 **불러 쓰기만** 하고, 그 import 도
  실제로 쓸 때까지 미룬다.
"""
from app.infrastructure.ml.sentiment import LocalSentiment, SentimentUnavailable

__all__ = ["LocalSentiment", "SentimentUnavailable"]
