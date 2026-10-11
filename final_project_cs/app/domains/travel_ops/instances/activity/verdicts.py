# -*- coding: utf-8 -*-
"""활동 장소 판정 — 휴무 · 운영시간 · 재난 영향. 활동 팀이 **판정 규칙의 정본**이다. `[2026-10-12]`

★왜 따로 두나. 같은 판정을 세 곳이 쓴다 — 고객 문의(`team._check_feasible`), 계획 검증(코어 접수 확인 화면),
  감시 루프(코어 공유 점검 뒤). 요식 팀이 식당 영업 판정을 `team_hooks/dining_ledger` 로 내놓는 것과 같은 모양으로,
  활동 팀은 이 함수들을 조립 때 코어의 끼움 자리에 꽂는다(`composition.wire_activity_verdicts`). 규칙이 두 벌로 갈라져
  같은 장소인데 확인 화면과 문의 답이 달라지는 일을 막는다(2026-10-12 사용자 결정 — 「다이닝과 같은 구조로 판정까지 연결」).

★**계산만 한다.** DB · 도구 · LLM 을 부르지 않는다. 사실(운영시간 원문 · 요일표 · 공휴일 · 재난문자)은 부르는 쪽이 모아 넘긴다 —
  코어는 사실, 활동 팀은 판정(D-017).
★모르면 모른다 — 값은 `True`/`False`/`None` 이고 `None` 을 「열었다」 · 「영향 없음」으로 바꾸지 않는다.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from app.domains.travel_ops.components.places.place_hours import fits, hours_on

from .closure_rules import holiday_dates_needed, local_date, read_closure
from .disaster_impact import ImpactRules, assess

#: 공휴일 사실 — 날짜 → `read.holiday` 와 같은 모양(`{"is_holiday": bool, "holiday_name": str | None}`) · None(모름)
HolidayLookup = Callable[[date], "dict[str, Any] | None"]


def holidays_needed(restdate_text: str | None, at: datetime) -> list[date]:
    """휴무 원문을 읽는 데 공휴일 여부가 필요한 날짜. 부르는 쪽이 이 날짜만 조회해 `hours_verdict(holiday=)` 로 넘긴다."""
    return list(holiday_dates_needed(restdate_text, at)) if restdate_text else []


def hours_verdict(hours: dict[str, Any] | None, at: datetime, *, holiday: HolidayLookup | None = None) -> dict[str, Any]:
    """휴무 · 운영시간 판정 — `hours` 는 `read.place_hours` 와 같은 모양(`known` · `attributes` · `source` · `why_unknown` ·
    `usetime_text` · `restdate_text`).

    반환 `{"known", "empty", "closed", "within_hours", "closure_reason", "quote", "needs_caveat", "source",
    "restdate_text", "usetime_text", "why_unknown"}`.
        closed        True 휴무 · False 휴무 아님 · None 모름
        within_hours  True 운영시간 안 · False 밖 · None 모름(휴무 아님이 확인된 뒤에만 잰다)
        empty         운영 정보가 **비어 있다**(원문도 요일표도 없다 — 수정본 UC-A3 `4a`, 고객에게 물을 일)
    ★요일표(`place_hours.hours_on` · `fits` — 코어 표준)가 펴지 못하는 휴무(매월 n번째 주 · 공휴일 조건)는 휴무 원문을
      휴무 규칙(`closure_rules.read_closure`)으로 읽는다 — 원문이 정한 값이 요일 칸보다 앞선다.
    """
    if not isinstance(hours, dict):
        return {"known": False, "empty": False, "closed": None, "within_hours": None}
    restdate = hours.get("restdate_text")
    base = {"known": bool(hours.get("known")), "source": hours.get("source"), "why_unknown": hours.get("why_unknown"),
            "restdate_text": restdate, "usetime_text": hours.get("usetime_text")}
    if not hours.get("known") and not hours.get("usetime_text") and not restdate:
        return {**base, "empty": True, "closed": None, "within_hours": None}
    attributes = hours.get("attributes") or {}
    day = hours_on(attributes, local_date(at))
    closure = read_closure(restdate, at, holiday or (lambda _day: None)) if restdate else None
    closed = (closure.value if closure is not None and closure.value is not None
              else (day == "closed") if day is not None else None)
    within = fits(attributes, at, at) if closed is False and day not in (None, "closed") else None
    return {**base, "empty": False, "closed": closed, "within_hours": within,
            "closure_reason": closure.reason if closure else None,
            "quote": closure.quote if closure is not None and closure.value else None,
            "needs_caveat": bool(closure is not None and closure.needs_caveat)}


def disaster_verdict(messages: list[dict[str, Any]], *, outdoor: bool | None, at: datetime | None = None,
                     place_name: str | None = None, rules: ImpactRules | None = None) -> dict[str, Any]:
    """재난문자 → 이 활동을 막나(수정본 §8 + D2-1 세 규칙). `messages` 는 그 장소 구 · 시각으로 이미 걸러진 문자
    (`disaster_msg.active()` 의 `for_region` + `unclassified`).

    반환 `{"blocks": bool, "ask_outdoor": bool, "blocking": [...], "ask": [...], "unclassified": [...], "no_effect": int}`.
        ask_outdoor  야외 위험형인데 실내외를 모른다 — 계획 검증이면 고객에게 묻고, 감시 루프면 묻지 않고 보류한다(멘토 #3)
    """
    impact = assess(messages, outdoor, rules or ImpactRules.load(), at=at, place_name=place_name)
    record = impact.record()
    return {**record, "ask_outdoor": bool(impact.ask)}
