# -*- coding: utf-8 -*-
"""활동 장소의 **다른 곳 후보를 팀이 골라 준다** — 활동 팀이 꽂는 자리. `[2026-10-15 사용자 결정]` 후보 공급은 팀이, 일정 조립(자동 추천)은 우리가

요식 팀의 `dining_ledger` · 활동 팀의 `activity_ledger` 와 같은 모양이다.

    부품      "경복궁 08:00 자리에 맞는 다른 곳 셋(+ 더보기)"  →  여기
    활동 팀   "닫은 곳을 먼저 빼고, 비슷한 정도 · 거리로 줄 세운다"  →  조립 때 `register()`

★미등록이거나 팀이 답하지 못하면 `None` 이다(원래 장소를 목록에서 못 찾음 · 좌표 없음 · 오류). 부르는 쪽(확인 화면 `candidates.alternatives`)은 그때만
  **지금까지의 자체 후보 고르기**로 간다 — 팀이 「후보 없음」이라고 **답한** 것(빈 목록)은 대비책으로 넘어가지 않는다.
★바깥을 부르지 않는다. 활동 팀 함수는 DB(관광공사 목록)만 읽는다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable

from app.core.service_bindings import collect_registration, read_binding

_rank: Callable[..., dict[str, Any] | None] | None = None


def register(*, rank: Callable[..., dict[str, Any] | None]) -> None:
    """조립 때 한 번."""
    if collect_registration("activity_alternatives", locals()):
        return
    global _rank
    _rank = rank


def clear() -> None:
    global _rank
    _rank = None


def is_registered() -> bool:
    return read_binding("activity_alternatives", "rank", globals()["_rank"]) is not None


def ranked(conn, tenant_id: str, content_id: str | None, at: datetime | None, *,
           exclude_content_ids: Iterable[str] = (), preference: str | None = None) -> dict[str, Any] | None:
    """원래 장소(관광공사 번호) 기준 다른 곳 — `{"alternatives": [{contentid, title, latitude, longitude, distance_km, availability, reason, shown}],
    "matched_fields", "dropped_fields", "radius_km"}`. ★미등록 · 답하지 못함이면 `None`(모름 — 부르는 쪽이 자체 길로 간다)."""
    selected = read_binding("activity_alternatives", "rank", globals()["_rank"])
    if selected is None or not content_id or at is None:
        return None
    return selected(conn, tenant_id, str(content_id), at, exclude_content_ids=tuple(exclude_content_ids), preference=preference)
