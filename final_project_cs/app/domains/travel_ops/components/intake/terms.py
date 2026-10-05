# -*- coding: utf-8 -*-
"""장소 설명 말 표 읽기 — `config/place_terms.yaml`. `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]`

★코드에 단어를 박지 않는다: 종류 말(식당 · 쇼핑 …) · 끼니 말(조식 · 저녁 …) · 근처 말(인근 …) · 예약 말 · 군더더기와 지역 설정은 전부 표에 있다.
  새 말이 나오면 표에 한 줄을 더하면 같은 길을 탄다(`Terms.from_dict` 로 임시 표를 만들어 시험한다).
이 모듈은 DB 를 안 건드린다 — 지역 말은 DB 에서 만든다(`areas.py`).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.settings import REPO_ROOT

TERMS_PATH = REPO_ROOT / "config" / "place_terms.yaml"


@dataclass(frozen=True)
class Category:
    label: str                       # 화면에 보일 이름 — 「식당」 · 「쇼핑」
    kind: str                        # activity · dining
    content_type: str | None         # 관광공사 분류 번호(후보를 같은 분류로 거른다)


@dataclass(frozen=True)
class Terms:
    #: 정규화한 말 → 종류 / 끼니 이름 / 예약 값 — 한 말이 한 곳에만 있다(앞의 것이 이긴다)
    categories: dict[str, Category] = field(default_factory=dict)
    meals: dict[str, str] = field(default_factory=dict)
    proximity: frozenset[str] = frozenset()
    booking: dict[str, bool | None] = field(default_factory=dict)       # 값 None = 군더더기 「예약」
    fillers: frozenset[str] = frozenset()
    area_priority: tuple[str, ...] = ("hub", "dong", "district")
    area_radius_m: dict[str, int] = field(default_factory=dict)
    area_short_forms: tuple[str, ...] = ()
    area_min_length: int = 2
    area_aliases: dict[str, str] = field(default_factory=dict)
    content_types: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Terms":
        from .places import normalize_full

        categories: dict[str, Category] = {}
        for group in raw.get("categories") or []:
            category = Category(str(group["label"]), str(group["kind"]), str(group["content_type"]) if group.get("content_type") else None)
            for term in group.get("terms") or []:
                categories.setdefault(normalize_full(str(term)), category)
        meals: dict[str, str] = {}
        for group in raw.get("meals") or []:
            for term in group.get("terms") or []:
                meals.setdefault(normalize_full(str(term)), str(group["label"]))
        booking: dict[str, bool | None] = {}
        for group in raw.get("booking") or []:
            for term in group.get("terms") or []:
                booking.setdefault(normalize_full(str(term)), group.get("value"))
        areas = raw.get("areas") or {}
        return cls(
            categories=categories, meals=meals,
            proximity=frozenset(normalize_full(str(t)) for t in raw.get("proximity") or []),
            booking=booking, fillers=frozenset(normalize_full(str(t)) for t in raw.get("fillers") or []),
            area_priority=tuple(areas.get("priority") or ("hub", "dong", "district")),
            area_radius_m={str(k): int(v) for k, v in (areas.get("radius_m") or {}).items()},
            area_short_forms=tuple(str(s) for s in areas.get("short_forms") or ()),
            area_min_length=int(areas.get("min_length") or 2),
            area_aliases={str(k): str(v) for k, v in (areas.get("aliases") or {}).items()},
            content_types={str(k): str(v) for k, v in (raw.get("content_types") or {}).items()})


_lock = threading.Lock()
_cached: Terms | None = None


def load_terms(path: Path | None = None) -> Terms:
    """표를 읽는다 — 파일은 한 번만 읽고 기억한다(`reset()` 으로 비운다). 파일이 없거나 깨졌으면 **빈 표**다: 이름 없는 줄을 못 알아볼 뿐 읽기는 계속된다."""
    global _cached
    if path is not None:
        return _read(path)
    with _lock:
        if _cached is None:
            _cached = _read(TERMS_PATH)
        return _cached


def _read(path: Path) -> Terms:
    try:
        return Terms.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    except Exception:                                  # noqa: BLE001 — 표 장애가 계획 읽기를 막지 않는다(없는 것과 같다 — 이름으로 찾는 옛 길)
        import logging

        logging.getLogger(__name__).warning("place terms table unreadable path=%s", path, exc_info=True)
        return Terms()


def reset() -> None:
    """시험용 — 기억한 표를 비운다."""
    global _cached
    with _lock:
        _cached = None


def category_label(content_type_id: Any, terms: Terms | None = None) -> str | None:
    """관광공사 분류 번호 → 화면에 보일 종류 이름(표에 없으면 None — 지어내지 않는다)."""
    if content_type_id in (None, ""):
        return None
    return (terms or load_terms()).content_types.get(str(content_type_id))


__all__ = ["Category", "TERMS_PATH", "Terms", "category_label", "load_terms", "reset"]
