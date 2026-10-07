"""여행 시작 설문에서 요식 조건을 꺼낸다.

설문(`constraints.survey`, 코어 `survey.TripSurvey`)의 음식 세부 선택지는 「각 담당 팀이 정해서
알려 주기로」 했다(2026-09-24 회의). 이동은 `mobility/wiring.modes_from_survey` 로 이미 잇는다.
요식은 여기서 같은 방식으로 잇는다.

    priority_details.food 의 코드   →   요식 조건 코드(대안 · 판정이 쓰는 것)
        vegetarian                     vegetarian_menu
        halal                          halal

맛 · 친절 · 청결(taste · kindness · clean)은 조건이 아니라 취향이다. 대안을 거르지 않는다.
미쉐린 · 노포(michelin · nopo)도 취향이다 — 거르지 않고 일정 생성기가 그 표시가 있는 식당을 **앞에 세운다**
(`likes_from_survey` → `planner.Preference.likes`). `[2026-10-07]`
모르는 코드는 버린다. 설문 화면이 먼저 바뀌어도 여기서 깨지지 않게.

아이 동반(kids_allowed)은 설문에서 꺼내지 않는다. 「가족」이 아이를 뜻하지 않는다.
아이가 있는지는 따로 물어야 한다.
"""
from __future__ import annotations

from typing import Any, Mapping

#: 설문 음식 세부 코드 → 요식 조건 코드. 화면 선택지를 더하면 여기에 한 줄을 더한다.
SURVEY_CONDITIONS = {
    "vegetarian": "vegetarian_menu",
    "halal": "halal",
}


def conds_from_survey(constraints: Mapping[str, Any] | None) -> tuple[str, ...]:
    """설문의 음식 세부에서 요식 조건만 골라 정해진 순서로 돌려준다. 없으면 빈 튜플."""
    survey = (constraints or {}).get("survey") or {}
    if not isinstance(survey, Mapping):
        return ()
    details = survey.get("priority_details") or {}
    food = details.get("food") if isinstance(details, Mapping) else None
    codes = {SURVEY_CONDITIONS[c] for c in (food or []) if c in SURVEY_CONDITIONS}
    return tuple(sorted(codes))


#: 설문 음식 세부 코드 → 가게 표시 코드(`dining.ledger.BADGE_CODES`). 거르지 않고 앞에 세우는 취향이다. `[2026-10-07]`
SURVEY_LIKES = {
    "michelin": "michelin",
    "nopo": "nopo",
}


def likes_from_survey(constraints: Mapping[str, Any] | None) -> tuple[str, ...]:
    """설문의 음식 세부에서 취향(가게 표시)만 골라 정해진 순서로 돌려준다. 없으면 빈 튜플."""
    survey = (constraints or {}).get("survey") or {}
    if not isinstance(survey, Mapping):
        return ()
    details = survey.get("priority_details") or {}
    food = details.get("food") if isinstance(details, Mapping) else None
    codes = {SURVEY_LIKES[c] for c in (food or []) if c in SURVEY_LIKES}
    return tuple(code for code in SURVEY_LIKES.values() if code in codes)
