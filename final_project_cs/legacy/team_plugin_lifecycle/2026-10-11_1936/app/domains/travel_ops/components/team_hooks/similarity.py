# -*- coding: utf-8 -*-
"""활동이 **얼마나 비슷한가 · 무엇을 먼저 보나** — 활동 팀이 꽂는 자리. `[2026-10-06]` D-CS-013

전에는 감시와 「바꿔 줘」 처리가 `instances.activity.similarity` 를 직접 import 했다(2곳).

    부품    "경복궁 대신 내놓을 비슷한 곳 순서"  →  여기
    활동 팀 "분류 · 선호로 점수를 낸다"          →  조립 때 `register()`

★미등록이면 셋 다 「선호 없음 · 유사도 없음」이다. 부르는 쪽(`plan_activity_adjustment`)은
  `similarity=None` 을 이미 받는다 — 그때는 거리만 본다. 지어낸 점수를 쓰지 않는다.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

_score: Callable[..., int] | None = None
_preference_of: Callable[[Mapping[str, Any] | None], str | None] | None = None
_distance_first: Callable[[str | None], bool] | None = None


def register(*, score: Callable[..., int],
             preference_of: Callable[[Mapping[str, Any] | None], str | None],
             distance_first: Callable[[str | None], bool]) -> None:
    """조립 때 한 번. 셋을 다 줘야 한다."""
    global _score, _preference_of, _distance_first
    _score, _preference_of, _distance_first = score, preference_of, distance_first


def clear() -> None:
    global _score, _preference_of, _distance_first
    _score = _preference_of = _distance_first = None


def is_registered() -> bool:
    return _score is not None


def preference_of(constraints: Mapping[str, Any] | None) -> str | None:
    """여행 조건의 설문에서 읽은 선호. ★미등록이면 `None`(설문 없음과 같다)."""
    if _preference_of is None:
        return None
    return _preference_of(constraints)


def distance_first(preference: str | None) -> bool:
    """거리를 분류보다 앞세우나. ★미등록이면 `False` — 선호를 모를 때 활동 팀이 내는 답과 같다."""
    if _distance_first is None:
        return False
    return _distance_first(preference)


def scorer(preference: str | None) -> Callable[..., int] | None:
    """후보 점수 함수 — 부품이 넘겨 쓰는 모양(`similarity=`). ★미등록이면 `None`(유사도 없이 거리만)."""
    if _score is None:
        return None
    from functools import partial

    return partial(_score, preference=preference)
