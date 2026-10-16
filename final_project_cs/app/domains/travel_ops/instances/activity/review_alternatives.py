# -*- coding: utf-8 -*-
"""확인 화면의 「다른 곳」 후보 — 활동 팀의 대체안 엔진(`alternatives.rank_alternatives`)을 **등록 전 단계**에서도 부르는 어댑터. `[2026-10-15]`

원래 장소는 관광공사 번호로 활동 원장(`activity.ac_place`)에서 읽고(`db_search.find_place_candidates`), 닫은 곳(휴무 요일 · 운영시간 밖) · 이미 일정에 있는 곳을 먼저 빼고
비슷한 정도 · 거리로 줄 세운 결과를 돌려준다. 원장에 원래 장소가 없거나 좌표가 없으면 `None`(모름) — 부르는 쪽이 자체 길로 간다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .alternatives import _LEVEL_TEXT, rank_alternatives
from .db_search import find_place_candidates

#: 팀 엔진의 분류 가까움 문구 → 확인 화면의 맞은 단계(3 소분류 · 2 중분류 · 1 대분류). 「분류는 다름」은 단계 없음
_TIER = {_LEVEL_TEXT[0]: 3, _LEVEL_TEXT[1]: 2, _LEVEL_TEXT[2]: 1}


class _Keep:
    """이미 열린 연결을 `with` 로 쓰되 닫지 않는다."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def __enter__(self) -> Any:
        return self._conn

    def __exit__(self, *exc: Any) -> bool:
        return False


def rank(conn: Any, tenant_id: str, content_id: str, at: datetime, *, exclude_content_ids: tuple[str, ...] = (),
         preference: str | None = None) -> dict[str, Any] | None:
    pool = find_place_candidates(lambda: _Keep(conn), tenant_id, content_id)
    if pool is None:
        return None
    ranked = rank_alternatives(pool["origin"], pool["candidates"], at, preference=preference, exclude_ids=exclude_content_ids)
    if ranked["reason"] == "origin_no_coordinates":
        return None
    by_id = {str(c.get("contentid")): c for c in pool["candidates"]}
    out: list[dict[str, Any]] = []
    for shown, group in ((True, ranked["alternatives"]), (False, ranked["more_alternatives"])):
        for alt in group:
            row = by_id.get(str(alt["contentid"]))
            if row is None or row.get("mapx") is None or row.get("mapy") is None:
                continue
            tier = next((value for text, value in _TIER.items() if text in str(alt.get("reason") or "")), None)
            out.append({**alt, "tier": tier, "latitude": float(row["mapy"]), "longitude": float(row["mapx"]),
                        "content_type_id": row.get("contenttypeid"), "address": row.get("addr1"), "shown": shown})
    return {"alternatives": out, "matched_fields": ranked["matched_fields"], "dropped_fields": ranked["dropped_fields"],
            "radius_km": ranked["radius_km"], "origin_title": (pool["origin"] or {}).get("title")}
