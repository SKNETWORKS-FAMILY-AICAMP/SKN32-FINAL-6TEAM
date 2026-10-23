# -*- coding: utf-8 -*-
"""숙소 일정의 **다른 숙소 후보를 숙소 팀이 골라 준다** — 숙소 팀이 꽂는 자리. `[2026-10-16 사용자 결정]` 후보 공급은 팀이, 일정 조립은 우리가

    부품      "명동 1박 숙소 자리에 맞는 다른 숙소"                       →  여기
    숙소 팀   "숙소 비교(마이리얼트립 · 구글 호텔)로 찾아 가격대 · 거리 순"  →  조립 때 `register()`

★미등록이거나 팀이 답하지 못하면 `None`(지역 · 날짜 · 인원 모름 · 바깥 소스 없음 · 오류 · 지도에 올릴 좌표가 있는 후보가 없음).
  부르는 쪽(확인 화면 `candidates.alternatives`)은 그때만 자체 고르기(관광공사 숙박 목록)로 간다.
★바깥(숙소 비교)을 부르므로 하루 한도를 쓴다 — 조립이 낮은 우선순위 몫(`low_priority_share`)으로 만든 소스만 넘긴다.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from app.core.service_bindings import collect_registration, read_binding

_rank: Callable[..., dict[str, Any] | None] | None = None


def register(*, rank: Callable[..., dict[str, Any] | None]) -> None:
    """조립 때 한 번."""
    if collect_registration("lodging_alternatives", locals()):
        return
    global _rank
    _rank = rank


def clear() -> None:
    global _rank
    _rank = None


def is_registered() -> bool:
    return read_binding("lodging_alternatives", "rank", globals()["_rank"]) is not None


def ranked(*, keyword: str | None, check_in: str | None, check_out: str | None, adults: int | None,
           anchor: tuple[float, float] | None = None, exclude_names: Iterable[str] = (),
           domestic: bool | None = True) -> dict[str, Any] | None:
    """숙소 후보 — `{"alternatives": [{name, latitude, longitude, source, price_per_night, rating, link}]}`.
    ★미등록 · 값 모름 · 답하지 못함이면 `None`(부르는 쪽이 자체 길로 간다). 인원을 모르면 지어내지 않는다."""
    selected = read_binding("lodging_alternatives", "rank", globals()["_rank"])
    if selected is None or not keyword or not check_in or not check_out or not isinstance(adults, int) or adults < 1:
        return None
    return selected(keyword=keyword, check_in=check_in, check_out=check_out, adults=adults, anchor=anchor,
                    exclude_names=tuple(exclude_names), domestic=domestic)
