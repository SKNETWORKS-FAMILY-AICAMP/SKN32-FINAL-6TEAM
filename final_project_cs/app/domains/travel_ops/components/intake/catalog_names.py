# -*- coding: utf-8 -*-
"""관광공사 이름 조회의 **대체 길** — 우리가 저장해 둔 관광공사 장소 목록(`place_catalog`)에서 이름을 찾는다. `[2026-10-15 사용자 지시 — 코어]`

☆왜: 접수는 장소 이름을 관광공사 검색(`TourApiPlace.find`)으로 찾는데, 이름 비교가 **글자 그대로**(공백 · 괄호만 무시)라 「더 플라자 호텔」과 목록의 「더플라자호텔」,
  「엔서울타워」와 「N서울타워」 같은 표기 차이는 못 찾는다. 게다가 검색은 호출 예산이 바닥나면 아무것도 못 찾는다(x600 서버 실측 `budget_exhausted`). 숙소(분류 32)는 우리 장소 표(`places`)에도 없어서
  이름 있는 호텔이 접수에서 늘 `unresolved` 였고 고객이 후보에서 한 번 골라야 했다.
★이 길은 **정확히 하나**로 정해질 때만 돌려준다: 공백 · 괄호 · 가운뎃점 · 대소문자를 무시한 제목이 같은 곳이 하나. 둘 이상이면(같은 이름 여러 곳) 모름이다 — 지어내지 않는다.
  부분 일치는 받지 않는다(「경복궁」에 「경복궁 별빛야행」이 섞이지 않게). 원래 조회가 찾았으면 그것을 쓴다(이 길은 못 찾았을 때만).
"""
from __future__ import annotations

from typing import Any, Callable

from .hours import _tenants
from .places import normalize_full

#: 제목에서 괄호 병기를 떼고 공백 · 구분 기호를 없앤 비교 값(SQL) — `places.normalize_full` 과 같은 뜻
_SQL_KEY = (r"lower(regexp_replace(regexp_replace(title, '[\(\[（【].*?[\)\]）】]', '', 'g'), "
            r"'[\s·\-_/]+', '', 'g'))")


class CatalogNames:
    """`TourApiPlace.find` 와 같은 계약(`find` + `misses`)으로 우리 목록에서 이름을 찾는다."""

    def __init__(self, connect: Callable[[], Any], tenant_id: str) -> None:
        self._connect, self._tenant = connect, tenant_id
        self.misses: dict[str, int] = {}

    def find(self, place_name: str, *, area_code: str | None = None, **_: Any) -> dict[str, Any] | None:
        key = normalize_full(place_name)
        if len(key) < 2:
            return None
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT content_id, content_type_id, title, address, latitude, longitude FROM place_catalog "
                "WHERE tenant_id = ANY(%s) AND source='tour_api' AND latitude IS NOT NULL AND address LIKE '서울%%' "
                f"AND {_SQL_KEY} = %s LIMIT 5", (_tenants(self._tenant), key))
            rows = cur.fetchall()
        distinct = {str(row[0]): row for row in rows}
        if len(distinct) != 1:
            return None
        content_id, content_type, title, address, lat, lon = next(iter(distinct.values()))
        return {"content_id": str(content_id), "content_type_id": str(content_type), "matched_title": str(title),
                "latitude": float(lat), "longitude": float(lon), "address": str(address or ""), "source": "place_catalog"}


class TourThenCatalog:
    """관광공사 조회가 못 찾았을 때만 `CatalogNames` 로 — 나머지(`misses` · 사진 등)는 원래 조회에 맡긴다."""

    def __init__(self, tour: Any, catalog: CatalogNames) -> None:
        self._tour, self._catalog = tour, catalog

    @property
    def misses(self) -> dict[str, int]:
        return getattr(self._tour, "misses", None) or {}

    def find(self, place_name: str, **kwargs: Any) -> dict[str, Any] | None:
        found = self._tour.find(place_name, **kwargs) if self._tour is not None else None
        return found if found is not None else self._catalog.find(place_name, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if self._tour is None:
            raise AttributeError(name)
        return getattr(self._tour, name)


def with_catalog(tour: Any, connect: Callable[[], Any], tenant_id: str) -> Any:
    """접수가 쓰는 관광공사 조회에 대체 길을 붙인다. 이미 붙어 있으면 그대로."""
    return tour if isinstance(tour, TourThenCatalog) else TourThenCatalog(tour, CatalogNames(connect, tenant_id))


__all__ = ["CatalogNames", "TourThenCatalog", "with_catalog"]
