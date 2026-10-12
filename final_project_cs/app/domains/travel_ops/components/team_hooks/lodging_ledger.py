# -*- coding: utf-8 -*-
"""숙소 · 항공 원장 — 숙소 팀이 꽂는 자리. `[2026-10-12]` (`dining_ledger.py` 와 같은 모양, D-CS-013)

    부품    "이 항목에 무엇을 보여 줬나? 고른 숙소를 장소로 들여놓아 줘"  →  여기
    숙소 팀 "보여 준 후보 · 고른 숙소의 출처는 내 원장이 안다"          →  조립 때 `register()`

★미등록이면 지금 길 그대로다 — 기억은 안 하고(빈 목록 · 0), 들여놓기는 `None`(부르는 쪽은 `place_id` 를 비운 채로 간다).
  값을 지어내지 않는다. 부르는 곳(대화 부품 · 고르기 처리)은 아직 없다 — `wiki/records/reports/2026-10-12_숙소항공_원장_연결안내.md`.
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.service_bindings import collect_registration, read_binding

_remember: Callable[..., int] | None = None
_shown: Callable[..., list[str]] | None = None
_adopt: Callable[..., dict[str, Any] | None] | None = None
_item_key: Callable[[str, dict[str, Any]], str | None] | None = None


def register(*, remember: Callable[..., int], shown: Callable[..., list[str]],
             adopt: Callable[..., dict[str, Any] | None], item_key: Callable[[str, dict[str, Any]], str | None]) -> None:
    """조립 때 한 번. 넷을 다 줘야 한다 — 빠뜨리면 여기서 `TypeError` 로 바로 드러난다.
    `[2026-10-12]` develop 의 조립 방식(요청마다 묶음 표 · `collect_services`)에 맞춘다 — 요식 · 활동 자리와 같다."""
    if collect_registration("lodging_ledger", locals()):
        return
    global _remember, _shown, _adopt, _item_key
    _remember, _shown, _adopt, _item_key = remember, shown, adopt, item_key


def clear() -> None:
    global _remember, _shown, _adopt, _item_key
    _remember = _shown = _adopt = _item_key = None


def _bound(key: str, legacy: Any) -> Any:
    return read_binding("lodging_ledger", key, legacy)


def is_registered() -> bool:
    return _bound("adopt", globals()["_adopt"]) is not None


def item_key(kind: str, query: dict[str, Any]) -> str | None:
    """항목 이름(판이 바뀌어도 같다). ★미등록이면 None."""
    selected = _bound("item_key", globals()["_item_key"])
    return selected(kind, query) if selected is not None else None


def remember_shown(conn, tenant_id: str, trip_id: Any, key: str, options: list[dict[str, Any]], **kwargs) -> int:
    """보여 준 후보를 적는다. ★미등록이면 0(적지 않는다)."""
    selected = _bound("remember", globals()["_remember"])
    return selected(conn, tenant_id, trip_id, key, options, **kwargs) if selected is not None else 0


def shown_keys(conn, tenant_id: str, trip_id: Any, key: str) -> list[str]:
    """그 항목에 보여 준 후보 key. ★미등록이면 빈 목록(모름 — 부르는 쪽은 항목 상세의 `shown` 을 쓴다)."""
    selected = _bound("shown", globals()["_shown"])
    return selected(conn, tenant_id, trip_id, key) if selected is not None else []


def adopt_option(conn, store: Any, trip_id: Any, option: dict[str, Any]) -> dict[str, Any] | None:
    """고른 숙소 후보를 그 여행 전용 장소로. ★미등록이면 None(들여놓지 않는다)."""
    selected = _bound("adopt", globals()["_adopt"])
    return selected(conn, store, trip_id, option) if selected is not None else None
