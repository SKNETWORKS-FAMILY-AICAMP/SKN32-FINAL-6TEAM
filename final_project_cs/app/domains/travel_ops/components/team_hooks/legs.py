# -*- coding: utf-8 -*-
"""두 지점 사이를 **어떻게 · 얼마나** 가나 — 이동 팀이 꽂는 자리. `[2026-10-06]` D-CS-013

전에는 계획 · 대화 · 접수 · 일정 변경 부품이 `instances.mobility.wiring` 과 이동 팀의
가드레일 파일을 직접 import 했다(7곳). 이동 팀을 빼면 그 부품들이 다 깨지는 모양이었다.

    부품   "여기서 저기까지 몇 시에 나서야 하나?"  →  여기(`leg_planner`)
    이동 팀 "내가 시간표로 계산해 준다"            →  조립 때 `register()`

★미등록이면 `leg_planner` 는 `None` 이다 — 부르는 쪽은 이미 그 길을 안다(직선 거리 어림값).
  이동 계산기가 꺼져 있을 때와 **똑같은 상태**이고, 새 기본값을 만들지 않는다.
"""
from __future__ import annotations

from typing import Any, Callable

_leg_planner: Callable[..., Any] | None = None
_disruptions_from_events: Callable[[dict[str, Any]], tuple[list[dict[str, Any]], list[str]]] | None = None
_walk_limit_m: Callable[[], float | None] | None = None
_basis: Callable[[], dict[str, Any]] | None = None


def register(*, leg_planner: Callable[..., Any],
             disruptions_from_events: Callable[[dict[str, Any]], tuple[list[dict[str, Any]], list[str]]],
             walk_limit_m: Callable[[], float | None],
             basis: Callable[[], dict[str, Any]] | None = None) -> None:
    """조립 때 한 번. 앞 셋을 다 줘야 한다 — 빠뜨리면 여기서 `TypeError` 로 바로 드러난다. `basis` 는 선택(`[2026-10-06]` 판정 근거를 밝히는 읽기 입구용)."""
    global _leg_planner, _disruptions_from_events, _walk_limit_m, _basis
    _leg_planner, _disruptions_from_events, _walk_limit_m, _basis = leg_planner, disruptions_from_events, walk_limit_m, basis


def clear() -> None:
    global _leg_planner, _disruptions_from_events, _walk_limit_m, _basis
    _leg_planner = _disruptions_from_events = _walk_limit_m = _basis = None


def is_registered() -> bool:
    return _leg_planner is not None


def leg_planner(party_size: int | None, constraints: dict[str, Any] | None, *, disruptions=None, modes=None):
    """구간 계산기를 만든다 → `leg(a, b, 도착목표, 그전엔안됨)` → (결과, None) 또는 (None, 이유).
    ★이동 팀이 없거나 계산기가 꺼져 있으면 `None` — 부르는 쪽이 어림값으로 간다.
    `modes`(`["subway"]` 처럼 이 수단만으로) 는 주었을 때만 이동 팀에 넘긴다 — 안 받는 옛 등록 함수도 그대로 돈다."""
    if _leg_planner is None:
        return None
    if modes:
        return _leg_planner(party_size, constraints, disruptions=disruptions, modes=modes)
    return _leg_planner(party_size, constraints, disruptions=disruptions)


def disruptions_from_events(events: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """우리 경로 사건 → 계산기가 아는 사고 조건. (옮긴 것, 못 옮긴 대상).
    ★미등록이면 `([], [])` — 「사고 정보가 없다」와 같다. 못 옮긴 것을 숨기는 게 아니다(옮길 것 자체가 없다)."""
    if _disruptions_from_events is None:
        return [], []
    return _disruptions_from_events(events)


def basis() -> dict[str, Any] | None:
    """판정기가 **어떤 상태이고 어느 시간표 · 규칙 판으로** 판정하나 — `{mode, timetable_built_at, rules_version, timetable_stale}`. ★미등록이면 `None`(모른다 — 「꺼짐」이라고 말하지 않는다)."""
    if _basis is None:
        return None
    return _basis()


def walk_limit_m() -> float | None:
    """「걸어갈 수 있다」고 보는 거리 상한(m). ★미등록이면 `None` — 부르는 쪽은 상한을 못 읽었을 때처럼
    보수적으로 간다(늘 새 경로를 만든다). 숫자를 지어내지 않는다."""
    if _walk_limit_m is None:
        return None
    return _walk_limit_m()
