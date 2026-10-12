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

from app.core.service_bindings import collect_registration, read_binding

from typing import Any, Callable

_add_nearby: Callable[..., list[dict[str, Any]]] | None = None
_states: Callable[..., dict[str, dict[str, Any] | None]] | None = None
_state: Callable[..., dict[str, Any] | None] | None = None
_find_by_name: Callable[[Any, str | None], dict[str, Any] | None] | None = None
_catalog_state: Callable[..., dict[str, Any] | None] | None = None
_http_providers: dict[str, Callable[..., Any] | None] = {}


def register(*, add_nearby: Callable[..., list[dict[str, Any]]],
             states: Callable[..., dict[str, dict[str, Any] | None]],
             state: Callable[..., dict[str, Any] | None],
             find_by_name: Callable[[Any, str | None], dict[str, Any] | None],
             catalog_state: Callable[..., dict[str, Any] | None] | None = None,
             lookup_factory: Callable[..., Any] | None = None,
             slot_verdicts: Callable[..., Any] | None = None,
             planner_factory: Callable[..., Any] | None = None,
             link_core_place: Callable[..., Any] | None = None,
             closure_observation: Callable[..., Any] | None = None) -> None:
    """조립 때 한 번. 넷을 다 줘야 한다 — 빠뜨리면 여기서 `TypeError` 로 바로 드러난다."""
    if collect_registration("dining_ledger", locals()):
        return
    global _add_nearby, _states, _state, _find_by_name, _catalog_state
    _add_nearby, _states, _state, _find_by_name = add_nearby, states, state, find_by_name
    _catalog_state = catalog_state
    _http_providers.update(lookup_factory=lookup_factory, slot_verdicts=slot_verdicts,
                           planner_factory=planner_factory, link_core_place=link_core_place,
                           closure_observation=closure_observation)


def clear() -> None:
    global _add_nearby, _states, _state, _find_by_name, _catalog_state
    _add_nearby = _states = _state = _find_by_name = None
    _catalog_state = None
    _http_providers.clear()


def is_registered() -> bool:
    _selected_0 = read_binding("dining_ledger", "add_nearby", globals()["_add_nearby"])
    return _selected_0 is not None


def add_nearby(conn, store: Any, trip_id: Any, items: list[Any], places: list[dict[str, Any]],
               *, radius_m: int | None = None) -> list[dict[str, Any]]:
    """근처 원장 가게를 **그 여행 전용 장소**로 들여놓은 새 목록. ★미등록이면 받은 `places` 그대로 —
    들여놓기에 실패했을 때 요식 팀 자신이 하는 것과 같다."""
    _selected_0 = read_binding("dining_ledger", "add_nearby", globals()["_add_nearby"])
    if _selected_0 is None:
        return places
    if radius_m is None:
        return _selected_0(conn, store, trip_id, items, places)
    return _selected_0(conn, store, trip_id, items, places, radius_m=radius_m)


def states(conn, tenant_id: str, slots: list[dict[str, Any]], **kwargs) -> dict[str, dict[str, Any] | None] | None:
    """후보 여럿의 방문 구간 판정을 한 연결에서. ★미등록이면 `None` — 「판정 없이 간다」(원장을 끈 것과 같다)."""
    _selected_0 = read_binding("dining_ledger", "states", globals()["_states"], required_team="dining")
    if _selected_0 is None:
        return None
    return _selected_0(conn, tenant_id, slots, **kwargs)


def state_lookup(conn, tenant_id: str, **kwargs) -> Callable[[list[dict[str, Any]]], Any] | None:
    """부품들이 넘겨 쓰는 모양 — `slots` 하나만 받는 함수. ★미등록이면 `None`(판정기를 안 넘긴다)."""
    _selected_0 = read_binding("dining_ledger", "states", globals()["_states"], required_team="dining")
    if _selected_0 is None:
        return None
    return lambda slots: _selected_0(conn, tenant_id, slots, **kwargs)


def state(conn, tenant_id: str, place_id: str | None, at: Any = None, until: Any = None,
          **kwargs) -> dict[str, Any] | None:
    """한 곳 · 한 구간 판정. ★미등록이면 `None`(모름)."""
    _selected_0 = read_binding("dining_ledger", "state", globals()["_state"], required_team="dining")
    if _selected_0 is None:
        return None
    return _selected_0(conn, tenant_id, place_id, at, until, **kwargs)


def find_by_name(conn, name: str | None) -> dict[str, Any] | None:
    """이름으로 원장 가게 하나 — **하나로 정해질 때만**. ★미등록이면 `None`(못 찾음)."""
    _selected_0 = read_binding("dining_ledger", "find_by_name", globals()["_find_by_name"])
    if _selected_0 is None:
        return None
    return _selected_0(conn, name)


def catalog_state(conn, content_id, place, start, end, **kwargs):
    """Core place 행을 만들기 전의 식당 판정도 같은 Dining 관문을 거친다."""
    selected = read_binding("dining_ledger", "catalog_state", _catalog_state, required_team="dining")
    return selected(conn, content_id, place, start, end, **kwargs) if selected is not None else None


def require_state_provider(*, registered_place: bool) -> None:
    """식당 판정의 DB 조회 전에 담당과 고정된 계산 입구를 확인한다."""
    key = "state" if registered_place else "catalog_state"
    legacy = _state if registered_place else _catalog_state
    read_binding("dining_ledger", key, legacy, required_team="dining")


def _http_provider(key: str):
    from app.core.team_availability import TeamUnavailable

    selected = read_binding("dining_ledger", key, _http_providers.get(key), required_team="dining")
    if selected is None:
        raise TeamUnavailable("dining", "not_installed")
    return selected


def lookup_factory(*args, **kwargs):
    return _http_provider("lookup_factory")(*args, **kwargs)


def require_slot_verdicts() -> None:
    """DB 연결을 열기 전에 고정된 방문구간 판정 제공자를 확인한다."""
    _http_provider("slot_verdicts")


def slot_verdicts(*args, **kwargs):
    return _http_provider("slot_verdicts")(*args, **kwargs)


def planner_factory(*args, **kwargs):
    return _http_provider("planner_factory")(*args, **kwargs)


def link_core_place(*args, **kwargs):
    return _http_provider("link_core_place")(*args, **kwargs)


def require_planner_factory() -> None:
    _http_provider("planner_factory")


def require_link_core_place() -> None:
    _http_provider("link_core_place")


def closure_observation(*args, **kwargs):
    selected = read_binding('dining_ledger', 'closure_observation', _http_providers.get('closure_observation'),
                            required_team='dining')
    return selected(*args, **kwargs) if selected is not None else None
