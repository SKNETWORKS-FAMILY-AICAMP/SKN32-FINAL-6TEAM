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

from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.places.place_hours import DayHours, fits, hours_on

from .closure_rules import holiday_dates_needed, local_date, read_closure
from .disaster_impact import ImpactRules, assess
from .notices import hours_read_by_model

#: 공휴일 사실 — 날짜 → `read.holiday` 와 같은 모양(`{"is_holiday": bool, "holiday_name": str | None}`) · None(모름)
HolidayLookup = Callable[[date], "dict[str, Any] | None"]
_SEOUL = ZoneInfo("Asia/Seoul")


def holidays_needed(restdate_text: str | None, at: datetime) -> list[date]:
    """휴무 원문을 읽는 데 공휴일 여부가 필요한 날짜. 부르는 쪽이 이 날짜만 조회해 `hours_verdict(holiday=)` 로 넘긴다."""
    return list(holiday_dates_needed(restdate_text, at)) if restdate_text else []


def _within(attributes: dict[str, Any], at: datetime, until: datetime | None) -> bool | None:
    """`at`~`until` 내내 운영시간 안인가. `until` 이 없거나 `at` 보다 늦지 않으면 도착 순간만 본다.
    ★`[2026-10-12]` 자정을 넘기면 밖이다 — 요일표는 그날 자정까지만 인정한다(`place_hours._same_day_close`, 보수적)."""
    if not isinstance(until, datetime) or until <= at:
        return fits(attributes, at, at)
    if local_date(until) != local_date(at):
        return False
    return fits(attributes, at, until)


def _cut_short(attributes: dict[str, Any], day: Any, at: datetime, until: datetime | None) -> dict[str, Any]:
    """도착 때는 열려 있는데 끝나기 전에 닫나 — `{"cut_short", "closes_at", "usable_minutes"}`. `[2026-10-12 사용자 요청]`
    ★「이미 닫힘」(다른 곳으로)과 「중간에 닫힘」(N분만 머물 수 있다 · 앞당기기)은 안내 · 대안이 다르다. `within_hours` 는 둘 다 False 로
      두고(막는 판정은 그대로) 이 칸이 둘을 가른다. 끝 시각이 없거나 도착 때 이미 밖이면 `cut_short` 는 False(밖) · None(못 잼)."""
    if not isinstance(until, datetime) or until <= at or not isinstance(day, DayHours):
        return {"cut_short": None, "closes_at": None, "usable_minutes": None}
    arrival_open = fits(attributes, at, at)
    if arrival_open is not True or _within(attributes, at, until) is not False:
        return {"cut_short": False if arrival_open is not None else None, "closes_at": None, "usable_minutes": None}
    local = at.astimezone(_SEOUL) if at.tzinfo else at
    usable = (day.closes.hour * 60 + day.closes.minute) - (local.hour * 60 + local.minute)
    if usable <= 0:
        # ★코어 `fits` 는 닫는 시각 정각 도착(19:00 도착 · 19:00 닫음)을 「안」으로 본다 — 머물 시간이 없으니 이미 닫힘이다
        return {"cut_short": False, "closes_at": None, "usable_minutes": None}
    return {"cut_short": True, "closes_at": day.closes.strftime("%H:%M"), "usable_minutes": usable}


def hours_verdict(hours: dict[str, Any] | None, at: datetime, *, until: datetime | None = None,
                  holiday: HolidayLookup | None = None) -> dict[str, Any]:
    """휴무 · 운영시간 판정 — `hours` 는 `read.place_hours` 와 같은 모양(`known` · `attributes` · `source` · `why_unknown` ·
    `usetime_text` · `restdate_text`).

    반환 `{"known", "empty", "closed", "within_hours", "closure_reason", "quote", "needs_caveat", "source",
    "restdate_text", "usetime_text", "why_unknown"}`.
        closed        True 휴무 · False 휴무 아님 · None 모름
        within_hours  True 운영시간 안 · False 밖 · None 모름(휴무 아님이 확인된 뒤에만 잰다).
                      `until`(끝나는 시각)을 주면 끝날 때까지 안이어야 `True` — 안 주면 도착 순간만 본다
                      (고객 문의는 예약에 끝 시각이 없어 도착 순간만 본다)
        cut_short     True 도착 때는 열려 있지만 끝나기 전에 닫는다(`closes_at` 닫는 시각 · `usable_minutes` 머물 수 있는 분)
                      · False 그렇지 않다 · None 못 쟀다(끝 시각 없음 · 운영시간 모름)
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
    measurable = closed is False and day not in (None, "closed")
    within = _within(attributes, at, until) if measurable else None
    cut = _cut_short(attributes, day, at, until) if measurable else {"cut_short": None, "closes_at": None,
                                                                     "usable_minutes": None}
    # ★`[2026-10-12]` D-CS-015 개정 2 — 모델이 읽은 요일표로 판정했으면 고객 답에 안내를 붙인다(`notices.HOURS_AUTO_READ`).
    #   휴무를 원문 규칙(`closure`)이 정했으면 요일표를 안 쓴 것이라 붙이지 않는다.
    auto_read = hours_read_by_model(hours) and day is not None and not (closure is not None and closure.value is not None)
    return {**base, "empty": False, "closed": closed, "within_hours": within, **cut, "auto_read": auto_read,
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
