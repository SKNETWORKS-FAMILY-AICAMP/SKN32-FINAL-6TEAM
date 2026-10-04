# -*- coding: utf-8 -*-
"""관광공사 영업시간·휴무 **글** → 요일별 칸(`hours_week`) — 규칙만으로, 모델을 부르지 않는다. `[2026-10-01]`

★출처: 활동 팀(조직 develop `activity/alternatives.py` 의 `open_at`·`closed_on`)이 후보 거르기용으로 만든 읽기 규칙.
  우리 `place_hours.read_by_rule` 은 단순한 한 구간만 읽어 팀 데이터 1,951행 중 296행만 읽었고, 팀 규칙은 1,754행을 읽었다
  (2026-10-01 두 코드를 같은 데이터로 돌려 측정). 읽는 범위가 넓은 쪽을 가져오되 **우리 저장 모양**(`hours_week`)으로 낸다.
★그대로 가져오지 않고 고친 것:
  - 「매주 일요일 / 월요일」·「매주 월요일 / 토요일 / 일요일」에서 슬래시 뒤 요일을 놓쳐 월요일 휴무를 「연다」로 읽던 결함
    (팀 데이터로 돌려 찾음). 슬래시 뒤 조각이 **요일 말뿐일 때만** 이어 읽는다 — 「/ 매월 둘째 일요일」은 잇지 않는다.
  - 「매월 둘째 주 월요일」처럼 **격주·n번째** 휴무는 매주 쉬는 날로 읽지 않는다(그 칸은 모름으로 둔다).
★모르면 모른다: 읽을 수 없는 칸은 비워 둔다(`hours_week` 에서 없는 요일 = 모름). 한 요일에 구간이 둘 이상이거나(점심 휴게 등)
  휴게·계절·층별 표현이 있으면 그 글은 열린 시간을 읽지 않는다. 휴무 요일만 아는 글은 휴무 요일만 낸다.
★계산만 한다. DB·도구·LLM 을 부르지 않는다.
"""
from __future__ import annotations

import re
from typing import Any

from ..place_hours import DAYS, HoursRead, clean, days_in

#: 이 말이 있으면 열린 시간을 읽지 않는다 — 층·시설·계절·휴게처럼 시간표 하나로 못 읽는 표현
_HOURS_UNSURE = ("상이", "참조", "확인", "문의", "별도", "변동", "브레이크", "휴게", "[", "<br", "하계", "동계",
                 "성수기", "비수기", "라스트", "예약")
#: 휴무 글이 모른다고 말하는 표현 — 휴무를 모르면 열린 시간도 내지 않는다(쉬는 날에 열린다고 하지 않게)
_REST_UNSURE = ("상이", "참조", "확인", "문의", "별도", "[", "하계", "동계", "성수기", "비수기")
_ALWAYS_OPEN = re.compile(r"상시|24\s*시간")
_TIME_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[~\-–]\s*(\d{1,2}):(\d{2})")
_HOLIDAY = re.compile(r"공휴일|휴일")
_LAST = re.compile(r"(?:입장\s*마감|입장마감|마감)\s*[:：]?\s*(\d{1,2}):(\d{2})")
_DAY_TOKENS = {"평일": ("mon", "tue", "wed", "thu", "fri"), "주말": ("sat", "sun"), "매일": DAYS}
_DAY_RANGE = re.compile(r"([월화수목금토일])(?:요일)?\s*[~\-]\s*([월화수목금토일])(?:요일)?")
#: 휴무 글: 매주 → 그 요일이 매주 쉰다. n번째·격주·매월은 매주가 아니다.
_WEEKLY = re.compile(r"매주\s*([^<(※]*)")
_NOT_WEEKLY = re.compile(r"[첫둘셋넷다섯]째|\d\s*째|격주|매월|매달|월\s*\d+회")
_DAYS_ONLY = re.compile(r"^(?:[월화수목금토일](?:요일)?\s*[,·~\-]?\s*)+(?:정기)?(?:휴무|휴관|휴업)?\.?$")
_NONE_REST = ("연중무휴", "없음", "휴무없음", "무휴")
_IRREGULAR = re.compile(r"부정기|비정기|불규칙|수시|임시|사정에")


def _hm(hour: str, minute: str) -> str:
    return f"{int(hour):02d}:{minute}"


def closed_weekdays(rest: str | None) -> set[str] | None:
    """휴무 글에서 **매주 쉬는 요일**. 연중무휴·휴무 없음은 빈 집합, 읽을 수 없으면 `None`(모름).

    ★「매주」가 붙은 조각과 그 뒤 **요일 말뿐인** 조각만 읽는다. 예외 조건(공휴일 등)은 읽지 않는다."""
    text = clean(rest)
    if not text:
        return set()
    if any(marker in text for marker in _REST_UNSURE):
        return None
    compact = re.sub(r"\s+", "", text)
    if any(compact.startswith(word) for word in _NONE_REST):
        return set()
    body = re.sub(r"\(.*?\)", "", text)          # 괄호 안 예외는 읽지 않는다
    body = re.sub(r"※.*", "", body)
    if _IRREGULAR.search(body):
        return None
    closed: set[str] = set()
    if "주말" in body:
        closed.update(("sat", "sun"))
    matched = False
    for weekly in _WEEKLY.findall(body):
        for position, piece in enumerate(part.strip() for part in weekly.split("/")):
            cut = _NOT_WEEKLY.search(piece)
            if cut:                                   # 「매주 월요일, 매월 둘째 화요일」 — 뒤쪽 n번째 휴무는 모델 밖
                piece = piece[:cut.start()]
            if position == 0 or _DAYS_ONLY.match(piece):
                found = days_in(piece)
                matched = matched or bool(found)
                closed |= found
    if matched or closed:
        return closed
    if _NOT_WEEKLY.search(body) or re.search(r"[월화수목금토일]요일", body):
        return None                                   # 매월·n번째 휴무만 있거나, 「매주」 없이 요일만 있다 — 모른다
    return set()                                      # 공휴일·명절만 있다 — 매주 쉬는 요일은 없다(공휴일은 펴지 않는다)


def _segment_days(label: str) -> set[str] | None:
    """구간 앞뒤 글자에서 적용 요일. 라벨이 없으면 매일, 못 읽는 글자가 남으면 `None`."""
    rest = _HOLIDAY.sub("", label)
    days: set[str] = set()
    for first, last in _DAY_RANGE.findall(rest):
        days |= days_in(f"{first}~{last}")
    rest = _DAY_RANGE.sub("", rest)
    for token, covered in _DAY_TOKENS.items():
        if token in rest:
            days.update(covered)
            rest = rest.replace(token, "")
    rest = rest.replace("요일", "")
    for char in "월화수목금토일":
        if char in rest:
            days |= days_in(char)
            rest = rest.replace(char, "")
    if re.search(r"[가-힣A-Za-z0-9]", rest):
        return None
    if not days:
        return set(DAYS) if not _HOLIDAY.search(label) else set()
    return days


def _open_windows(business_hours: str | None) -> dict[str, tuple[str, str]] | None:
    """요일 → (여는 시각, 닫는 시각). 못 읽으면 `None`. ★요일마다 구간이 하나로 정해질 때만 낸다."""
    raw = clean(business_hours)
    if not raw or any(marker in raw for marker in _HOURS_UNSURE):
        return None
    text = re.sub(r"\(.*?\)", "", raw).strip()
    has_range = _TIME_RANGE.search(text) is not None
    if _ALWAYS_OPEN.search(text):
        return {day: ("00:00", "23:59") for day in DAYS} if not has_range else None
    if not has_range:
        return None
    by_day: dict[str, set[tuple[str, str]]] = {day: set() for day in DAYS}
    holiday: set[tuple[str, str]] = set()
    for segment in re.split(r"[/;\n]", text):
        segment = segment.strip()
        if not segment:
            continue
        spans = [(_hm(a, b), _hm(c, d)) for a, b, c, d in _TIME_RANGE.findall(segment)]
        if not spans:
            return None
        days = _segment_days(_TIME_RANGE.sub("", segment))
        if days is None:
            return None
        if _HOLIDAY.search(segment):
            holiday.update(spans)
        for day in days:
            by_day[day].update(spans)
    out: dict[str, tuple[str, str]] = {}
    for day, spans in by_day.items():
        if len(spans) == 1:
            out[day] = next(iter(spans))
    if holiday and not holiday <= {span for spans in by_day.values() for span in spans}:
        return None                               # 공휴일 시간이 따로 있으면 오늘이 공휴일인지 몰라 단정하지 않는다
    return out or None


def read_week(business_hours: str | None, closed_days: str | None) -> HoursRead | None:
    """영업시간·휴무 글 → `hours_week` 모양. 아무 요일도 알 수 없으면 `None`.

    돌려주는 `HoursRead.week` 의 요일 칸: `{"open","close","last_entry"}` · `"closed"` · (없음 = 모름)."""
    rest = closed_weekdays(closed_days)
    windows = _open_windows(business_hours) if rest is not None else None
    last = _LAST.search(clean(business_hours))
    last_entry = _hm(*last.groups()) if last else None
    week: dict[str, Any] = {}
    for day in DAYS:
        if rest is not None and day in rest:
            week[day] = "closed"
        elif windows and day in windows:
            week[day] = {"open": windows[day][0], "close": windows[day][1], "last_entry": last_entry}
    if not week:
        return None
    return HoursRead(week=week, method="rule", quotes=[q for q in (clean(business_hours), clean(closed_days)) if q])


__all__ = ["closed_weekdays", "read_week"]
