# -*- coding: utf-8 -*-
"""대체 활동의 「비슷한 정도」 — 관광공사 분류·구가 원래 장소와 얼마나 같은가. `[2026-09-29]`

★출처: 활동 팀 PR #6 의 `activity/alternatives.py`(대안 생성 규칙 ②·③). 그쪽은 유사도를 **거르는 조건**으로
  썼다 — 필드가 모두 같아야 남고, 0건이면 뒤 필드부터 하나씩 풀었다. 여기서는 **순위 점수**로만 쓴다
  (코덱스와 2회차 합의 · 전수검수 리포트 2026-09-28_1826). 거르기는 우리 규칙(거리·실내·가격·영업·재점검)
  그대로 두고, 살아남은 후보 사이에서 **비슷한 곳을 앞에** 세운다. 비슷한 곳이 없다고 후보를 잃지 않는다.

★필드 순서(앞이 무겁다)는 PR #6 의 `FIELD_PRIORITY` 를 그대로 옮겼다.
  설문 우선순위(`survey.priority`)에 activity 가 먼저면 「활동 중요」, mobility 가 먼저면 「이동 중요」다.
  설문이 없으면 「활동 중요」 순서를 쓴다 — 대체 활동은 먼저 「같은 종류의 활동」이어야 한다.

★모르는 값끼리 「같다」고 읽지 않는다 — 한쪽이라도 비면 그 필드는 0점이다.

계산만 한다. DB·도구·LLM 을 부르지 않는다.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

#: 원래 장소·후보가 들고 오는 분류 값의 키(`TripStore.places` 가 `catalog_class` 로 붙인다).
#: ★`brand` 도 같이 오지만 점수 필드가 아니다 — 「같은 브랜드 · 가까운 곳」은 거리가 필요해 `replan.py` 가 따로 본다.
FIELDS = ("lcls1", "lcls2", "lcls3")

#: 선호별 필드 순서 — 앞이 무겁다. ★`[2026-10-05]` **구(시군구)를 뺐다.** 활동 팀이 10/2 에 시군구를 반경으로 바꾼 이유(같은 구의 먼 곳이
#: 옆 구의 가까운 곳보다 앞서는 경계 문제 · 구마다 넓이가 달라 기준이 일정하지 않음)가 우리 순위에도 그대로 있었다. 코덱스와 맞췄다
#: (2026-10-05): 거리는 순위의 다음 키(`replan.Candidate.rank`)가 이미 보고, **이동 중요면 분류보다 거리가 앞선다**(`distance_first`).
#: 그래서 두 선호의 점수 필드는 같다 — 차이는 거리와 점수의 앞뒤뿐이다.
ORDER: dict[str, tuple[str, ...]] = {
    "activity": ("lcls1", "lcls2", "lcls3"),
    "mobility": ("lcls1", "lcls2", "lcls3"),
}
DEFAULT_PREFERENCE = "activity"


def preference_of(constraints: Mapping[str, Any] | None) -> str | None:
    """여행 조건의 설문에서 선호를 읽는다. `priority` 에 activity·mobility 중 먼저 나온 것. 없으면 None."""
    survey = (constraints or {}).get("survey") or {}
    for area in survey.get("priority") or []:
        if area in ORDER:
            return str(area)
    return None


def distance_first(preference: str | None) -> bool:
    """이동 중요(설문 우선순위에서 mobility 가 먼저)면 분류보다 **거리**를 앞세운다. 활동 중요·설문 없음은 분류가 먼저."""
    return preference == "mobility"


def _value(classes: Mapping[str, Any] | None, field: str) -> str:
    return str((classes or {}).get(field) or "").strip()


def score(origin: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None,
          preference: str | None = None) -> int:
    """같은 필드마다 무게를 더한 점수. 앞 필드 하나가 뒤 필드 전부보다 무겁다(사전식)."""
    order: Iterable[str] = ORDER.get(preference or DEFAULT_PREFERENCE, ORDER[DEFAULT_PREFERENCE])
    order = tuple(order)
    total = 0
    for i, field in enumerate(order):
        mine, theirs = _value(origin, field), _value(candidate, field)
        if mine and mine == theirs:
            total += 1 << (len(order) - 1 - i)
    return total
