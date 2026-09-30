# -*- coding: utf-8 -*-
"""activity CSV 기반 장소 조회 — 관광공사 rate limit · 카카오 403 우회 로컬 폴백.

intake/places.py 의 _tour() 계약(find + misses)을 구현한다.
외부 API 없이 activity_total_data.csv 에서 찾는다.

정확일치(정규화 기준) → 접두사 단독일치 순으로 찾는다.
places.py NOT_THERE 집합과 같은 실패 키를 쓴다.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

_CSV_PATH = Path(__file__).parent / "data_processing" / "activity_total_data.csv"
_BRANCH = re.compile(r"\s*(본점|직영점|\S+점)$")


def _normalize(text: str) -> str:
    """places.py normalize()와 동일 — 동작을 반드시 맞춰야 한다."""
    text = unicodedata.normalize("NFKC", text or "").strip()
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", text)
    text = _BRANCH.sub("", text)
    return re.sub(r"[\s·\-_/]+", "", text).lower()


def _to_float(value: Any) -> float | None:
    try:
        v = float(value)
        return v if v else None
    except (TypeError, ValueError):
        return None


class CsvPlaceLookup:
    """activity_total_data.csv 기반 장소 조회 — intake 의 tour= 자리에 주입한다."""

    name = "csv_activity"

    def __init__(self, csv_path: Path = _CSV_PATH) -> None:
        self.misses: dict[str, int] = {}
        self._rows: list[dict[str, str]] = []
        self._by_norm: dict[str, dict[str, str]] = {}
        self._load(csv_path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            return
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                title = (row.get("title") or "").strip()
                if not title:
                    continue
                self._rows.append(row)
                key = _normalize(title)
                if key not in self._by_norm:
                    self._by_norm[key] = row

    def find(self, place_name: str, *, area_code: str | None = None, **_kwargs: Any) -> dict[str, Any] | None:
        """이름으로 장소 하나를 찾는다. 없으면 None."""
        if not place_name or not place_name.strip():
            self.misses["no_place_name"] = self.misses.get("no_place_name", 0) + 1
            return None

        key = _normalize(place_name.strip())

        # ① 정확 일치
        row = self._by_norm.get(key)

        # ② 접두사 일치 — 단독 1건만(ambiguous 방지)
        if row is None:
            prefix = [r for r in self._rows if _normalize(r.get("title", "")).startswith(key)]
            if len(prefix) == 1:
                row = prefix[0]
            elif len(prefix) > 1:
                self.misses["ambiguous"] = self.misses.get("ambiguous", 0) + 1
                return None

        if row is None:
            self.misses["not_found"] = self.misses.get("not_found", 0) + 1
            return None

        lat = _to_float(row.get("mapy"))
        lon = _to_float(row.get("mapx"))
        if lat is None or lon is None:
            self.misses["no_coordinates"] = self.misses.get("no_coordinates", 0) + 1
            return None

        addr = (row.get("addr1") or "").strip()
        if not addr.startswith("서울"):
            self.misses["not_found"] = self.misses.get("not_found", 0) + 1
            return None

        return {
            "content_id": str(row.get("contentid") or ""),
            "content_type_id": str(row.get("contenttypeid") or ""),
            "large_class_code": str(row.get("lclsSystm1") or "") or None,
            "large_class_name": None,
            "matched_title": str(row.get("title") or ""),
            "latitude": lat,
            "longitude": lon,
            "address": addr,
        }
