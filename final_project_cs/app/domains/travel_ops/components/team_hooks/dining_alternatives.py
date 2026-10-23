# -*- coding: utf-8 -*-
"""식사 일정의 **다른 식당 후보를 요식 팀이 골라 준다** — 요식 팀이 꽂는 자리. `[2026-10-15 사용자 결정]` 후보 공급은 팀이, 일정 조립(자동 추천)은 우리가

    부품      "토속촌 12:00 자리에 맞는 다른 식당"           →  여기
    요식 팀   "그 시각 영업 · 식이 조건을 보고 축마다 한 곳" →  조립 때 `register()`

★미등록이거나 팀이 답하지 못하면 `None`(원래 식당이 원장에 없음 · 오류). 가게 이름 없는 식사는 `near`(한 지점 둘레). 부르는 쪽(확인 화면 `candidates.alternatives`)은 그때만 자체 고르기로 간다 —
  팀이 「없다」고 **답한** 빈 목록은 대비책으로 넘어가지 않는다. 바깥을 부르지 않는다(원장 DB 만 읽는다).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable

from app.core.service_bindings import collect_registration, read_binding

_rank: Callable[..., dict[str, Any] | None] | None = None
#: `[2026-10-18 사용자 지시]` 가게 이름 없는 식사(「점심」 · 「ㅇㅇ 근처 점심」) — 원래 식당 없이 한 지점 둘레에서 고르는 길
_near: Callable[..., dict[str, Any] | None] | None = None


def register(*, rank: Callable[..., dict[str, Any] | None], near: Callable[..., dict[str, Any] | None] | None = None) -> None:
    """조립 때 한 번. `near` 는 가게 이름 없는 식사의 길 — 등록하지 않은 팀이면 그 식사는 `None`(모름)이다."""
    if collect_registration("dining_alternatives", locals()):
        return
    global _rank, _near
    _rank, _near = rank, near


def clear() -> None:
    global _rank, _near
    _rank = _near = None


def is_registered() -> bool:
    return read_binding("dining_alternatives", "rank", globals()["_rank"]) is not None


def ranked(conn, tenant_id: str, place_uid: str | None, starts_at: datetime | None, ends_at: datetime | None = None, *,
           next_point: tuple[float, float] | None = None, conditions: Iterable[str] = ()) -> dict[str, Any] | None:
    """원래 식당(요식 원장 번호) 기준 다른 식당 — `{"alternatives": [{place_id, place_uid, name, latitude, longitude, address, axis, axis_label}]}`.
    ★미등록 · 답하지 못함이면 `None`(모름 — 부르는 쪽이 자체 길로 간다)."""
    selected = read_binding("dining_alternatives", "rank", globals()["_rank"])
    if selected is None or not place_uid or starts_at is None:
        return None
    return selected(conn, tenant_id, str(place_uid), starts_at, ends_at, next_point=next_point, conditions=tuple(conditions))


def near(conn, tenant_id: str, point: tuple[float, float] | None, starts_at: datetime | None, ends_at: datetime | None = None, *,
         next_point: tuple[float, float] | None = None, conditions: Iterable[str] = (), meal: bool = True,
         radius_m: int = 2000) -> dict[str, Any] | None:
    """가게 이름 없는 식사 — 한 지점(줄에 적은 지역 · 앞뒤 일정) 둘레의 원장 식당. 모양은 `ranked` 와 같다.
    `meal` = 끼니(점심 · 저녁 …)면 카페 · 디저트를 빼라는 뜻. ★미등록 · 답하지 못함 · 지점이나 시각을 모르면 `None`(모름)."""
    selected = read_binding("dining_alternatives", "near", globals()["_near"])
    if selected is None or point is None or starts_at is None:
        return None
    return selected(conn, tenant_id, (float(point[0]), float(point[1])), starts_at, ends_at, next_point=next_point,
                    conditions=tuple(conditions), meal=bool(meal), radius_m=int(radius_m))
