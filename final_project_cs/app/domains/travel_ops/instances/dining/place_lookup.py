"""일정 접수의 이름 찾기에 넣는 요식 원장 — 관광공사 자리와 같은 계약(`find` + `misses`). `[2026-10-01]`

★미리 적재해 둔 원장 DB 만 읽는다. 외부 API 가 아니다. 원장에 없으면 이름 찾기가 다음 단계(카카오)로 간다.
★못 읽으면(요식 표가 없는 DB · 연결 실패) `misses["unavailable"]` 를 센다 — 이름 찾기가 「없는 곳」이 아니라
  「조회가 막혔다」로 적는다(`intake/places.py` 의 NOT_THERE 밖의 사유).
★`[2026-10-07 팀]` `near`(앞 일정 좌표)를 원장 이름 찾기에도 넘긴다 — 같은 이름 여럿 · 「근처 칼국수집」에서 가까운 곳을 고르는 단서.
  `find_dish_near` — 「광장시장 빈대떡」처럼 장소를 먼저 찾은 뒤 그 좌표 근처의 메뉴 가게를 찾는다(`intake/places.resolve`).
"""
from __future__ import annotations

from typing import Any, Callable

from .ledger import find_dish_near, find_license_shop_by_name, find_place_by_name


class LedgerPlaceLookup:
    name = "dining_ledger"

    def __init__(self, connection_factory: Callable[[], Any],
                 on_found: Callable[[dict[str, Any]], None] | None = None,
                 near: Callable[[], tuple[float, float] | None] | None = None) -> None:
        self._connect = connection_factory
        #: 앞 일정의 좌표 — 같은 이름이 여럿일 때 · 「근처 ○○집」에서 가까운 곳을 고르는 단서(원장 · 인허가 이름 찾기 모두)
        self._near = near
        #: 찾은 가게를 알린다 — 일정 접수가 그 좌표를 다음 항목의 근처 힌트로 쓴다(`trip_api._PlaceCtx`)
        self._on_found = on_found
        self.misses: dict[str, int] = {}

    def find(self, place_name: str, *, area_code: str | None = None, **_: Any) -> dict[str, Any] | None:
        try:
            with self._connect() as conn:
                found = find_place_by_name(conn, place_name, near=self._near() if self._near else None)
                if found is None:
                    # ★`[2026-10-05]` 원장(관광공사 위주 1,600곳)에 없으면 인허가(사업자 등록) 영업 중 식당에서 — 영업시간은 모른다
                    found = find_license_shop_by_name(conn, place_name, near=self._near() if self._near else None)
        except Exception:   # noqa: BLE001 — 드라이버를 import 하지 않는다(Team 경계). 못 읽으면 막힌 것
            self.misses["unavailable"] = self.misses.get("unavailable", 0) + 1
            return None
        return self._seen(found)

    def find_dish_near(self, text: str, latitude: float, longitude: float) -> dict[str, Any] | None:
        """장소 좌표 근처에서 메뉴 말이 이름에 든 원장 가게(「광장시장 빈대떡」 → 광장시장 좌표 근처 빈대떡집). 언제나 확인 필요."""
        try:
            with self._connect() as conn:
                found = find_dish_near(conn, text, (float(latitude), float(longitude)))
        except Exception:   # noqa: BLE001
            self.misses["unavailable"] = self.misses.get("unavailable", 0) + 1
            return None
        return self._seen(found)

    def _seen(self, found: dict[str, Any] | None) -> dict[str, Any] | None:
        if found is None:
            self.misses["not_found"] = self.misses.get("not_found", 0) + 1
        elif self._on_found is not None:
            self._on_found(found)
        return found
