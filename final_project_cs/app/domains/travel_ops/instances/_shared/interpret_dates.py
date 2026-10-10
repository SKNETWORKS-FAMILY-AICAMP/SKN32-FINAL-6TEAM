# -*- coding: utf-8 -*-
"""숙소 · 항공 해석이 함께 쓰는 **날짜 검증 부품** — 모델에 줄 달력, 근거 조각 확인, 연도 · 날(일) 맞추기. `[2026-10-10]`

팀끼리는 서로 import 하지 않으므로(숙소 ↔ 항공) 공용 부품을 `_shared` 에 둔다. 뜻을 서버가 해석하지 않는다 — 모델이 낸 값과
모델이 인용한 근거 조각이 **서로 · 고객 문장과 맞는지**만 본다.

☆2026-10-10 17:47 · 17:55 · 17:58 playdata 해석 측정(`scripts/eval_interpret.py`)에서 나온 것들:
- 연도: 「1월 3일」 → 2024, 「11월 21일」 → 2023, 지난 「10월 5일」 → 올해. → `settle_dates` 가 연도만 계산한다.
- 요일 셈: 「다음달 첫째 주 금요일」 → 11-03(화). → `model_context` 의 달력에서 찾게 한다.
- 모델의 `missing` 이 믿을 수 없었다: 날짜를 채우고 근거도 맞게 적고서 missing 에 그 날짜(심지어 keyword · adults 까지)를 넣었다
  (「11/20~11/22」 · 「다음 달 6일부터 9일까지」). 전에는 「missing 에 적은 값은 버린다」였는데 이것이 맞는 날짜를 지웠다.
  → missing 은 보지 않는다. 그 규칙이 막던 경우(10-08 15:30 「서울에서 3박」에 체크인을 오늘로 채우고 근거로 「3박」)는
  「박 수만 적힌 근거는 시작 날짜의 근거가 아니다」로 막는다.
- 범위 표기: 「11월 6~8일」에 근거를 「11월 6일」로 적었다(글자 그대로가 아님). → 근거의 숫자가 문장에 **같은 순서로** 있고 근거의
  글자(숫자 · 공백 빼고)가 다 문장에 있으면 받는다.
- 「11월 6일 체크인 9일 체크아웃 … 1박 30만원」에 체크아웃 근거를 「9일」로 적고 값은 11-07 로 냈다. → 근거에 날(일)이 하나만
  있으면 값의 날을 그 수로 맞춘다(「2박 3일」처럼 박이 들어간 근거는 건드리지 않는다).
"""
from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any

#: 모델에 주는 달력 길이(오늘부터 날 수). 우리가 고른 값
CALENDAR_DAYS = 70
WEEKDAYS = "월화수목금토일"
_YEAR = re.compile(r"(?:19|20)\d{2}")
_NUMBER = re.compile(r"\d+")
_NIGHTS_ONLY = re.compile(r"^\d+\s*박(\s*\d+\s*일)?$")
_DAY = re.compile(r"(\d{1,2})\s*일")
_MONTH = re.compile(r"(\d{1,2})\s*월")


def model_context(today: date, trip: dict[str, Any] | None = None) -> dict[str, Any]:
    """모델에 주는 context — 오늘 · 오늘 요일 · 앞으로 `CALENDAR_DAYS` 일의 달력(「YYYY-MM-DD 요일」) · 여행 요약."""
    days = (today + timedelta(days=offset) for offset in range(CALENDAR_DAYS))
    return {"today": today.isoformat(), "today_weekday": WEEKDAYS[today.weekday()],
            "calendar": [f"{day.isoformat()} {WEEKDAYS[day.weekday()]}" for day in days], **({"trip": trip} if trip else {})}


def quote_found(quote: str | None, text: str) -> bool:
    """근거 조각이 고객 문장에 있나 — 글자 그대로(공백 무시), 또는 숫자가 같은 순서로 있고 나머지 글자가 다 문장에 있을 때."""
    if not quote:
        return False
    squeezed, wanted = "".join(text.split()), "".join(quote.split())
    if wanted in squeezed:
        return True
    numbers = _NUMBER.findall(wanted)
    if not numbers:
        return False
    found, at = _NUMBER.findall(squeezed), 0
    for number in numbers:
        try:
            at = found.index(number, at) + 1
        except ValueError:
            return False
    letters = set(_NUMBER.sub("", wanted))
    return letters <= set(squeezed)


def ground_dates(found: Any, text: str, *, grounds: dict[str, str], start: str, end: str | None,
                 has_trip: bool, trip: dict[str, Any] | None = None) -> tuple[Any, list[str]]:
    """값마다 모델이 적은 근거 조각을 확인해 맞지 않는 값을 비운다. (해석, 비운 칸)

    - 근거가 `"trip"` 이면 Case 에 여행이 붙어 있을 때만 받는다.
    - 근거가 문장에 없더라도 값이 여행 일정의 첫날(시작 칸) · 마지막 날(끝 칸)과 같으면 받는다 — ☆17:55 「이번 여행 숙소 …」에
      값은 여행 날짜로 맞게 내고 근거를 지어 적었다(「11월 6일부터」).
    - 박 수만 적힌 근거(「3박」)는 시작 날짜의 근거가 아니다. 시작 날짜가 없으면 박 수로 만든 끝 날짜도 비운다.
    """
    trip_days = {start: (trip or {}).get("first_day"), **({end: (trip or {}).get("last_day")} if end else {})}
    cleared: list[str] = []
    for field, evidence in grounds.items():
        value, quote = getattr(found, field), getattr(found, evidence)
        if value is None:
            continue
        if field == start and quote and _NIGHTS_ONLY.match(quote.strip()):
            cleared.append(field)
            continue
        if quote == "trip" and has_trip:
            continue
        if quote != "trip" and quote_found(quote, text):
            continue
        if isinstance(value, date) and trip_days.get(field) and value.isoformat() == trip_days[field]:
            continue
        cleared.append(field)
    if end:
        start_gone = start in cleared or getattr(found, start) is None
        quote = getattr(found, grounds[end])
        if start_gone and end not in cleared and getattr(found, end) is not None and quote and _NIGHTS_ONLY.match(quote.strip()):
            cleared.append(end)
    return found.model_copy(update={field: None for field in cleared}), cleared


def _on_or_after(value: date, floor: date) -> date:
    for year in (floor.year, floor.year + 1):
        try:
            moved = value.replace(year=year)
        except ValueError:                            # 2월 29일
            continue
        if moved >= floor:
            return moved
    return value


def _align_day(value: date, quote: str) -> date:
    """근거에 날(일)이 하나만 있으면 값의 날을 그 수로(월도 하나 적혀 있으면 그 달로). 박이 든 근거 · 없는 날짜는 그대로."""
    if "박" in quote:
        return value
    days, months = _DAY.findall(quote), _MONTH.findall(quote)
    if len(days) != 1 or len(months) > 1:
        return value
    try:
        return value.replace(month=int(months[0]) if months else value.month, day=int(days[0]))
    except ValueError:
        return value


def settle_dates(found: Any, *, grounds: dict[str, str], today: date) -> tuple[Any, list[str]]:
    """날 · 연도를 근거 조각과 맞춘다. (해석, 고친 칸)

    - 날: 근거에 날(일)이 하나만 있으면 값의 날을 그 수로.
    - 연도: 근거 어디에든 네 자리 연도가 있으면(고객이 연도를 말함) 아무 날짜의 연도도 바꾸지 않는다. 없으면 「오늘 이후 처음 오는
      그 월 · 일」(프롬프트 규칙 그대로)로. 기준은 모두 오늘이다 — 돌아오는 날을 떠나는 날 뒤로 밀지 않는다(앞뒤가 틀리면 `needs` 가 묻는다).
    - 근거가 `"trip"` 인 날짜는 건드리지 않는다.
    """
    quotes = [getattr(found, evidence, None) for evidence in grounds.values()]
    year_said = any(isinstance(quote, str) and _YEAR.search(quote) for quote in quotes)
    update: dict[str, date] = {}
    for field, evidence in grounds.items():
        value, quote = getattr(found, field, None), getattr(found, evidence, None)
        if not isinstance(value, date) or quote in (None, "trip"):
            continue
        moved = _align_day(value, quote)
        if not year_said:
            moved = _on_or_after(moved, today)
        if moved != value:
            update[field] = moved
    return found.model_copy(update=update), list(update)


__all__ = ["CALENDAR_DAYS", "WEEKDAYS", "ground_dates", "model_context", "quote_found", "settle_dates"]
