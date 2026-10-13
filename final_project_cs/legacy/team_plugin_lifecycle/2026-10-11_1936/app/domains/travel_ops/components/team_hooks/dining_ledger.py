# -*- coding: utf-8 -*-
"""식당이 **그때 열었나 · 근처에 무엇이 있나** — 요식 팀이 꽂는 자리. `[2026-10-06]` D-CS-013

전에는 대화 창구 · 접수 읽기 · 감시(새벽 점검 · 완화 후보)가 `instances.dining` 의 원장 모듈을
직접 import 했다(5곳). 요식 팀을 빼면 접수와 감시가 통째로 깨지는 모양이었다.

    부품    "이 시각에 이 집 여나? 근처에 다른 집은?"  →  여기
    요식 팀 "원장이 정본이다 — 내가 판정한다"          →  조립 때 `register()`

★미등록이면 판정은 `None`, 근처 들여놓기는 **받은 목록 그대로**다. 시나리오 모드가 원장을 끌 때
  (`dining_ledger=False`) 부품이 이미 가는 길과 **똑같다** — 「모른다」를 「열었다」로 바꾸지 않는다.
  영업 여부를 모르면서 열었다고 답하는 것이 이 자리에서 가장 나쁜 일이다.
"""
from __future__ import annotations

from typing import Any, Callable

_add_nearby: Callable[..., list[dict[str, Any]]] | None = None
_states: Callable[..., dict[str, dict[str, Any] | None]] | None = None
_state: Callable[..., dict[str, Any] | None] | None = None
_find_by_name: Callable[[Any, str | None], dict[str, Any] | None] | None = None


def register(*, add_nearby: Callable[..., list[dict[str, Any]]],
             states: Callable[..., dict[str, dict[str, Any] | None]],
             state: Callable[..., dict[str, Any] | None],
             find_by_name: Callable[[Any, str | None], dict[str, Any] | None]) -> None:
    """조립 때 한 번. 넷을 다 줘야 한다 — 빠뜨리면 여기서 `TypeError` 로 바로 드러난다."""
    global _add_nearby, _states, _state, _find_by_name
    _add_nearby, _states, _state, _find_by_name = add_nearby, states, state, find_by_name


def clear() -> None:
    global _add_nearby, _states, _state, _find_by_name
    _add_nearby = _states = _state = _find_by_name = None


def is_registered() -> bool:
    return _add_nearby is not None


def add_nearby(conn, store: Any, trip_id: Any, items: list[Any], places: list[dict[str, Any]],
               *, radius_m: int | None = None) -> list[dict[str, Any]]:
    """근처 원장 가게를 **그 여행 전용 장소**로 들여놓은 새 목록. ★미등록이면 받은 `places` 그대로 —
    들여놓기에 실패했을 때 요식 팀 자신이 하는 것과 같다."""
    if _add_nearby is None:
        return places
    if radius_m is None:
        return _add_nearby(conn, store, trip_id, items, places)
    return _add_nearby(conn, store, trip_id, items, places, radius_m=radius_m)


def states(conn, tenant_id: str, slots: list[dict[str, Any]], **kwargs) -> dict[str, dict[str, Any] | None] | None:
    """후보 여럿의 방문 구간 판정을 한 연결에서. ★미등록이면 `None` — 「판정 없이 간다」(원장을 끈 것과 같다)."""
    if _states is None:
        return None
    return _states(conn, tenant_id, slots, **kwargs)


def state_lookup(conn, tenant_id: str, **kwargs) -> Callable[[list[dict[str, Any]]], Any] | None:
    """부품들이 넘겨 쓰는 모양 — `slots` 하나만 받는 함수. ★미등록이면 `None`(판정기를 안 넘긴다)."""
    if _states is None:
        return None
    return lambda slots: _states(conn, tenant_id, slots, **kwargs)


def state(conn, tenant_id: str, place_id: str | None, at: Any = None, until: Any = None,
          **kwargs) -> dict[str, Any] | None:
    """한 곳 · 한 구간 판정. ★미등록이면 `None`(모름)."""
    if _state is None:
        return None
    return _state(conn, tenant_id, place_id, at, until, **kwargs)


def find_by_name(conn, name: str | None) -> dict[str, Any] | None:
    """이름으로 원장 가게 하나 — **하나로 정해질 때만**. ★미등록이면 `None`(못 찾음)."""
    if _find_by_name is None:
        return None
    return _find_by_name(conn, name)
