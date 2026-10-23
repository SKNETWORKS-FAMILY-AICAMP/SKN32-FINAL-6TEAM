# -*- coding: utf-8 -*-
"""활동 장소 별칭 — 정식 제목과 **완전히 다른 이름**(「남산타워」 · 「N서울타워」 = 「남산서울타워」). `[2026-10-19 사용자 결정]`

☆왜: 띄어쓰기 · 기호 · 괄호 · 지점 표시 차이는 정규화(`intake.places.normalize_full`)가 처리한다. 글자가 아예 다른 이름은 규칙으로 못 잡는다 —
  이름 유사도로 짐작하면 남산도서관 · 용산도서관(0.92, 다른 곳)과 남산서울타워 · N서울타워(0.80, 같은 곳)가 가려지지 않는다.
  그래서 **사람이 확인한 별칭**을 둔다. 6천 곳을 다 채우지 않는다 — 고객이 많이 쓰는 유명한 곳부터 쌓는다.

★별칭은 **두 곳**에서 합쳐 읽는다(`merged`):
    ① 시드 파일 `data_processing/place_aliases.csv` — **기본 별칭**. 이미지에 실려 배포되므로 **적재 없이도 항상 적용된다**(git 에서 검토).
    ② DB 표 `activity.ac_place_alias`(마이그레이션 306) — **추가 별칭**. 이미지를 다시 만들지 않고 운영 중에 더한다(고객이 쓴 말 모으기 등).
       시드를 표에 복사하려면 `scripts/activity/load_place_aliases.py`(원장 `load_places.py` 와 같은 수동 적재) — 선택이다.
  두 곳이 같은 별칭을 서로 다른 장소로 가리키면 모호한 별칭이다 — 쓰지 않는다.
★**우리가 직접 정리한 이름과 고객이 쓴 말만** 넣는다 — 카카오 응답에서 이름을 뽑아 넣지 않는다(카카오 운영정책 제5조: 응답 저장 금지).
★한 별칭이 둘 이상의 장소를 가리키면(모호) 같다고 보지 않는다 — `is_alias_of` 는 장소가 **하나로 정해질 때만** 참이다.
★이 파일은 표를 읽지 않는다 — `AliasTable` 은 계산만 한다. 후보 조회(`db_search/place_candidates.py`)가 표를 읽어 결과에 싣는다(`aliases`).
  표를 못 읽으면(마이그레이션 전) 빈 표다 — 별칭이 없을 뿐 판정은 이름 일치 · 후보 표시로 그대로 돈다.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.domains.travel_ops.components.intake.places import normalize_full

#: 시드 파일 — 열: `content_id` · `canonical_title` · `alias` · `source`
SEED_CSV = Path(__file__).parent / "data_processing" / "place_aliases.csv"


def key_of(text: str | None) -> str:
    """찾는 키 — 정규화한 이름(공백 · 기호 · 괄호 · 대소문자 무시). 표 `alias_norm` 과 같다."""
    return normalize_full(text or "")


class AliasTable:
    """정규화한 별칭 → 가리키는 contentid 들. 계산만 한다(DB 를 읽지 않는다)."""

    def __init__(self, pairs: Iterable[tuple[str, str]] = ()) -> None:
        found: dict[str, set[str]] = {}
        for alias, content_id in pairs:
            key, cid = key_of(alias), str(content_id or "").strip()
            if key and cid:
                found.setdefault(key, set()).add(cid)
        self._table = {key: frozenset(ids) for key, ids in found.items()}

    def __len__(self) -> int:
        return len(self._table)

    def pairs(self) -> list[tuple[str, str]]:
        """`(정규화한 별칭, contentid)` 쌍들 — 다른 표와 합칠 때 쓴다."""
        return [(key, cid) for key, ids in self._table.items() for cid in ids]

    def content_ids_for(self, name: str | None) -> frozenset[str]:
        """이 이름을 별칭으로 가진 장소들의 contentid. 없으면 빈 집합."""
        return self._table.get(key_of(name), frozenset())

    def content_id_for(self, name: str | None) -> str | None:
        """이 이름이 **한 장소의 별칭일 때만** 그 contentid. 없거나 둘 이상이면 `None`."""
        ids = self.content_ids_for(name)
        return next(iter(ids)) if len(ids) == 1 else None

    def is_alias_of(self, name: str | None, content_id: str | None) -> bool:
        """`name` 이 `content_id` 장소의 별칭인가 — 그 별칭이 이 장소 **하나만** 가리킬 때만 참."""
        return bool(content_id) and self.content_id_for(name) == str(content_id)


EMPTY = AliasTable()


@lru_cache(maxsize=1)
def seed_table() -> AliasTable:
    """시드 파일의 별칭 표 — 이미지에 실려 있어 DB 적재와 상관없이 늘 있다. 처음 쓸 때 한 번 읽는다."""
    return AliasTable((row.get("alias") or "", row.get("content_id") or "") for row in read_seed())


@lru_cache(maxsize=1)
def _seed_titles() -> dict[str, str]:
    return {str(row.get("content_id") or "").strip(): str(row.get("canonical_title") or "").strip()
            for row in read_seed() if row.get("content_id") and row.get("canonical_title")}


def seed_title(content_id: str | None) -> str | None:
    """시드 파일에 적힌 그 장소의 정식 제목 — DB 를 못 읽을 때 별칭이 가리키는 이름을 알려 준다. 없으면 `None`."""
    return _seed_titles().get(str(content_id or "").strip()) or None


def reload_seed() -> None:
    """시드 파일을 다시 읽게 한다 — 시험 · 파일을 고친 직후용."""
    seed_table.cache_clear()
    _seed_titles.cache_clear()


def merged(rows: Iterable[Any] | None) -> AliasTable:
    """시드 파일 + DB 표(`rows` — 후보 조회 결과의 `aliases`). DB 를 못 읽었으면(`rows` 없음) 시드만."""
    extra = from_rows(rows)
    return seed_table() if not len(extra) else AliasTable([*seed_table().pairs(), *extra.pairs()])


def from_rows(rows: Iterable[Any] | None) -> AliasTable:
    """후보 조회 결과의 `aliases`(`[{"alias", "content_id"}, ...]`)를 표로. 없으면 빈 표."""
    if not rows:
        return EMPTY
    return AliasTable((str(r.get("alias") or ""), str(r.get("content_id") or "")) for r in rows if isinstance(r, dict))


def read_seed(path: Path = SEED_CSV) -> list[dict[str, str]]:
    """시드 CSV 의 행들(`content_id` · `canonical_title` · `alias` · `source`). 파일이 없으면 빈 목록."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))
