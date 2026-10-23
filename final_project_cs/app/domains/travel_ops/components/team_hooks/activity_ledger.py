# -*- coding: utf-8 -*-
"""활동 장소가 **그때 열었나 · 재난문자가 그 활동을 막나** — 활동 팀이 꽂는 자리. `[2026-10-13]` 활동 코어 전달 사항 3번

요식 팀의 `dining_ledger` 와 같은 모양이다. 판정 규칙의 정본은 활동 팀이고(`instances/activity/verdicts.py`),
코어는 사실(방문 시각 · 재난문자 · 장소)을 넘기고 답을 받는다.

    부품      "이 시각에 이 관광지 여나? 이 재난문자가 이 활동을 막나?"  →  여기
    활동 팀   "원장 · 판정이 정본이다"                                   →  조립 때 `register()`

★미등록이면 판정은 `None`(모름)이다. 「열었다」 · 「영향 없음」으로 바꾸지 않는다 — 부르는 쪽은 그때 지금까지의 길
  (장소 행 · 관광공사 운영시간 표 · 공유 점검)을 그대로 간다.
★바깥을 부르지 않는다. 활동 팀 함수는 DB(활동 원장)만 읽고, 공휴일은 부르는 쪽이 넘길 때만 본다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.core.service_bindings import collect_registration, read_binding

_state: Callable[..., dict[str, Any] | None] | None = None
_state_by_content: Callable[..., dict[str, Any] | None] | None = None
_indoor: Callable[..., dict[str, Any] | None] | None = None
_disaster: Callable[..., dict[str, Any]] | None = None
_closure: Callable[..., Any] | None = None


def register(*, state: Callable[..., dict[str, Any] | None],
             indoor: Callable[..., dict[str, Any] | None],
             disaster: Callable[..., dict[str, Any]],
             state_by_content: Callable[..., dict[str, Any] | None] | None = None,
             closure: Callable[..., Any] | None = None) -> None:
    """조립 때 한 번. 셋은 꼭 줘야 한다 — 빠뜨리면 여기서 `TypeError` 로 바로 드러난다.

    `state_by_content` 는 아직 장소 행이 없는 확인 화면 단계(관광공사 번호만 아는 곳)의 판정이다. 없으면 그 단계는 모름이다.
    `closure` 는 휴무 원문 한 조각이 그날 휴무인가(`closure_rules.read_closure` 모양) — 원장에 없는 곳의 조건 문장을 읽는다. 없으면 모름이다."""
    if collect_registration("activity_ledger", locals()):
        return
    global _state, _state_by_content, _indoor, _disaster, _closure
    _state, _state_by_content, _indoor, _disaster, _closure = state, state_by_content, indoor, disaster, closure


def clear() -> None:
    global _state, _state_by_content, _indoor, _disaster, _closure
    _state = _state_by_content = _indoor = _disaster = _closure = None


def is_registered() -> bool:
    return read_binding("activity_ledger", "state", globals()["_state"]) is not None


def state(conn, tenant_id: str, place_id: str | None, at: datetime | None, until: datetime | None = None, *,
          holiday: Callable[..., Any] | None = None) -> dict[str, Any] | None:
    """한 곳 · 한 구간의 휴무 · 운영시간 판정(`closed` · `within_hours` · `cut_short` · `closes_at` · `usable_minutes` ·
    `closure_reason` · `quote` · `needs_caveat` …). ★미등록 · 원장에 없는 곳이면 `None`(모름)."""
    selected = read_binding("activity_ledger", "state", globals()["_state"])
    if selected is None:
        return None
    return selected(conn, tenant_id, place_id, at, until, holiday=holiday)


def state_by_content(conn, content_id: str | None, at: datetime | None, until: datetime | None = None, *,
                     holiday: Callable[..., Any] | None = None) -> dict[str, Any] | None:
    """관광공사 번호로 같은 판정 — 장소 행을 만들기 전(확인 화면). ★미등록이면 `None`(모름)."""
    selected = read_binding("activity_ledger", "state_by_content", globals()["_state_by_content"])
    if selected is None or not content_id:
        return None
    return selected(conn, content_id, at, until, holiday=holiday)


def closure(text: str | None, at: datetime | None, *, holiday: Callable[..., Any] | None = None) -> dict[str, Any] | None:
    """휴무 원문 한 조각(관광공사 운영시간을 읽을 때 따로 남긴 조건 문장)이 그 시각에 휴무인가. `[2026-10-20]`

    반환 `{"closed": True|False|None, "reason", "quote"}` — `closed` 는 휴무 · 그날엔 해당 없음 · 모름.
    `holiday` 는 날짜 → `{"is_holiday", "holiday_name"}` · None(모름) — 부르는 쪽이 DB 달력에서 넘긴다.
    ★미등록 · 시각을 모름이면 `None`(모름). 판정 규칙은 활동 팀 것이다 — 코어는 원문 · 달력만 넘긴다."""
    selected = read_binding("activity_ledger", "closure", globals()["_closure"])
    if selected is None or not text or not isinstance(at, datetime):
        return None
    read = selected(text, at, holiday)
    return {"closed": getattr(read, "value", None), "reason": getattr(read, "reason", None),
            "quote": getattr(read, "quote", None)}


def indoor(conn, tenant_id: str, place_id: str | None) -> dict[str, Any] | None:
    """저장된 실내외 값(`{"outdoor", "decided_by", "notice", "content_id"}`). ★미등록 · 모르면 `None`."""
    selected = read_binding("activity_ledger", "indoor", globals()["_indoor"])
    if selected is None:
        return None
    return selected(conn, tenant_id, place_id)


def disaster(messages: list[dict[str, Any]], *, outdoor: bool | None, at: datetime | None = None,
             place_name: str | None = None) -> dict[str, Any] | None:
    """재난문자 → 이 활동을 막나(`{"blocks", "ask_outdoor", "blocking", "ask", "unclassified", "no_effect"}`).
    `messages` 는 그 장소 구 · 시각으로 이미 걸러진 문자다. ★미등록이면 `None`(모름 — 공유 점검 결과를 그대로 쓴다)."""
    selected = read_binding("activity_ledger", "disaster", globals()["_disaster"])
    if selected is None:
        return None
    return selected(messages, outdoor=outdoor, at=at, place_name=place_name)
