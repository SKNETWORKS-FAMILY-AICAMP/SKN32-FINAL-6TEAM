# -*- coding: utf-8 -*-
"""일정 항목 **한 개를 다시 점검하는 계산** — 세 팀이 꽂는 자리. `[2026-10-06]` D-CS-013

같은 여행에 문제가 여럿 겹쳤을 때 묶음 처리(`watch/trip_watch_batch.py`)가 항목마다 그 종류의
팀 계산을 부른다. 전에는 세 팀의 `team.py` 를 직접 import 했다(3곳) — 게다가 순환 import 때문에
**함수 안에서 늦게** 불러야 했다. 자리로 바꾸면 그 순환이 사라진다.

    부품  "이 활동 항목, 다시 점검해서 안을 내 줘"  →  여기(`planner("activity")`)
    세 팀 "내 종류는 내가 계산한다"                 →  조립 때 `register()`

★미등록이면 `None` 이다 — 부품은 이미 「모르는 종류」를 `None` 으로 다루고 건너뛴다. 그 팀이
  조립에 없으면 그 종류의 문제는 처리되지 않는 것이 맞다. 다른 팀 계산으로 **대신하지 않는다.**
"""
from __future__ import annotations

from typing import Any, Callable

_planners: dict[str, Callable[..., Any]] = {}


def register(kind: str, planner: Callable[..., Any]) -> None:
    """조립 때 종류마다 한 번. 같은 종류를 다시 등록하면 **교체**한다(재조립 대비)."""
    _planners[kind] = planner


def clear() -> None:
    _planners.clear()


def registered() -> tuple[str, ...]:
    return tuple(sorted(_planners))


def planner(kind: str) -> Callable[..., Any] | None:
    """항목 종류 → 점검 계산 함수. ★없으면 `None`(그 팀이 조립에 없거나 모르는 종류)."""
    return _planners.get(kind)
