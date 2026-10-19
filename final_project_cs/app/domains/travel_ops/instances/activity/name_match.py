# -*- coding: utf-8 -*-
"""장소 이름이 **정확히는 안 맞을 때**의 비교 도구 — 어순이 다른 이름 · 오타. 활동 팀 이름 찾기 둘이 같이 쓴다. `[2026-10-19]`

    `csv_places.CsvPlaceLookup.find(fuzzy=True)`          관광공사 CSV
    `db_search/place_by_name.find_place_by_name(fuzzy=True)` 활동 원장(`activity.ac_place`)

★**계산만 한다.** DB · LLM · 외부 호출 없음. 정확 일치가 못 찾았을 때만 부르는 뒷단계다.
★모두 **꺼 둔 채로 시작**한다(부르는 쪽이 `fuzzy=True` 를 줘야 한다). 이 결과는 짐작이라 부르는 쪽이 「확인 필요」로 다뤄야 한다 —
  `needs_review` 를 안 보는 판정 호출이 짐작한 장소로 판정하지 않게.
★오타 기준은 접수(`intake/places.TYPO_RATIO`) · 다이닝 원장(`dining/ledger.NAME_TYPO_RATIO`)과 같다(자모 거리 ÷ 긴 이름, 0.2 이하).
  **하나로 정해질 때만** 받는다 — 같은 거리의 다른 이름이 있으면 고르지 않는다.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

#: 길이 차 · 글자 겹침으로 거리 계산 전에 거르는 한도(자모 편집거리는 느려서 후보를 먼저 줄인다)
MAX_LENGTH_GAP = 2
MIN_KEY_LENGTH = 3


def word_set(text: str) -> frozenset[str]:
    """어순 무시 비교용 단어 집합 — 괄호 · 기호를 빼고, 단어 끝의 「점」(지점 표시)을 뗀다."""
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", unicodedata.normalize("NFKC", text or ""))
    words = (re.sub(r"[·\-_/]+", "", w).lower() for w in text.split())
    return frozenset(re.sub(r"(?<=[가-힣a-z0-9]{2})점$", "", w) for w in words if w)


class TypoIndex:
    """`(비교 키, 값)` 목록에서 오타로 볼 수 있는 하나를 찾는다. 자모 변환은 처음 한 번만 한다."""

    def __init__(self, items: Iterable[tuple[str, Any]]) -> None:
        from app.domains.travel_ops.components.intake.places import jamo

        self._items = [(key, jamo(key), value, frozenset(key)) for key, value in items]

    def best(self, key: str) -> tuple[Any, float] | None:
        """자모 거리 비율이 가장 작은 값 — 기준 이하이고 같은 비율의 **다른 이름**이 없을 때만. 없으면 `None`."""
        if len(key) < MIN_KEY_LENGTH:
            return None
        from app.domains.travel_ops.components.intake.places import TYPO_RATIO, edit_distance, jamo

        target, letters = jamo(key), frozenset(key)
        scored: list[tuple[float, str, Any]] = []
        for name, other, value, chars in self._items:
            longest = max(len(target), len(other))
            if abs(len(other) - len(target)) > TYPO_RATIO * longest or abs(len(name) - len(key)) > MAX_LENGTH_GAP:
                continue                            # 길이 차만으로 기준을 넘는 이름은 거리 계산을 건너뛴다
            if len(letters & chars) < len(letters) - 2:
                continue                            # 글자가 절반 넘게 다르면 오타일 수 없다
            ratio = edit_distance(target, other) / longest
            if 0 < ratio <= TYPO_RATIO:
                scored.append((ratio, name, value))
        if not scored:
            return None
        scored.sort(key=lambda s: s[0])
        if len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][1] != scored[0][1]:
            return None
        return scored[0][2], scored[0][0]
