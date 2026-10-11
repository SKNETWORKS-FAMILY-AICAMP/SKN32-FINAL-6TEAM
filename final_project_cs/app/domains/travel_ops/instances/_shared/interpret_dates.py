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
#: 박 수 · 기간만 적힌 근거 — 시작 날짜의 근거가 아니다(「3박」 「2박 3일」 「하루만」 「하룻밤」)
_NIGHTS_ONLY = re.compile(r"^(\d+\s*박(\s*\d+\s*일)?|하루(만|동안)?|하룻밤|이틀|사흘|나흘)$")
#: 날짜 근거로 볼 수 있는 모양 — 숫자 뒤 날짜 단위(일 · 월 · 박 · / · . · - · ~) 또는 날짜 말. ☆21:59 「명동 2명」에 근거 「명동」 · 「2명」으로 날짜를 지어냈다
_DATE_SHAPE = re.compile(r"\d+\s*(일|월|박|/|\.|-|~)|\d+/\d+")
_DATE_WORDS = ("오늘", "내일", "낼", "모레", "글피", "주말", "요일", "다음", "이번", "담주", "하루", "하룻밤", "이틀", "사흘", "첫날",
               "마지막", "크리스마스", "연말", "새해", "신정", "trip")
#: 요일 이름 — 근거에 하나만 있으면 값의 요일을 맞춘다. ☆21:59 「월요일부터 금요일까지」 체크아웃이 10-14(수)
_DAY = re.compile(r"(\d{1,2})\s*일")
_MONTH = re.compile(r"(\d{1,2})\s*월")
_WEEKDAY = re.compile(r"([월화수목금토일])요일")
_BARE_DAY = re.compile(r"^\d{1,2}$")
#: 「N일 · N주 · N달 뒤(후)」 — 기준일(시작 날짜는 오늘, 끝 날짜는 시작 날짜)에서 센다. ☆10-11 16:13 사용자 문장 측정 — 「3일뒤」 「20일 뒤」
#  「2주뒤」 「1달뒤」를 모델이 틀리게 셌고(10-20 · 11-02), 「3일」을 날(일) 숫자로 맞추던 규칙이 10-03 으로 망가뜨렸다
_OFFSET = re.compile(r"(\d+|일|이|삼|사|오|한|두|세|네)?\s*(주일|일|주|달|개월)\s*(뒤|후|있다가|지나서)")
_KOREAN_NUMBER = {"일": 1, "한": 1, "이": 2, "두": 2, "삼": 3, "세": 3, "사": 4, "네": 4, "오": 5}
#: 기간 — 「3일정도」 「4일동안」 「2박간」. 날(일) 숫자가 아니다
_DURATION = re.compile(r"\d+\s*(일|박)\s*(정도|동안|간|쯤)")
#: 날 없이 주만 — 「다다음주에」. 날짜가 아니다(요일 · 날 숫자 · 주말이 있으면 날짜)
_WEEK_ONLY = re.compile(r"(다다음|다음|이번|담|저번)\s*주(?!말)")
#: 고쳐 말한 날 — 「7일로 바꿔줘」 「8일로 변경」
_CORRECTED = re.compile(r"(\d{1,2})\s*일\s*로\s*(?:바꿔|바꾸|변경|옮겨|해\s*줘|할게|하자)")
#: 근거에 이 말이 있으면 월 · 일을 그 날로(앞의 것이 먼저). ☆22:28 「크리스마스에 2박」 — 프롬프트에 12-25 라고 적어도 12-24 로 냈다
HOLIDAYS = (("크리스마스이브", (12, 24)), ("크리스마스 이브", (12, 24)), ("크리스마스", (12, 25)), ("성탄절", (12, 25)),
            ("신정", (1, 1)), ("새해", (1, 1)))
#: 영어 날짜 — ☆22:25 「flight … on Nov 6」 근거 「Nov 6」를 날짜 모양이 아니라고 지웠다
_ENGLISH = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d|\b(today|tomorrow|tonight|next|this)\b"
                      r"|\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*day\b|\d+\s*(st|nd|rd|th)\b|\bnights?\b", re.IGNORECASE)


def looks_like_date(quote: str | None) -> bool:
    """근거 조각이 날짜를 말할 수 있는 모양인가(숫자 + 날짜 단위, 또는 날짜 말). 사람 수 · 지역 이름만이면 아니다."""
    if not quote:
        return False
    return (bool(_OFFSET.search(quote)) or bool(_DATE_SHAPE.search(quote)) or any(word in quote for word in _DATE_WORDS) or bool(_WEEKDAY.search(quote))
            or bool(_ENGLISH.search(quote)))


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
    found = _trip_day(found, text, grounds=grounds, start=start, end=end, trip=trip)
    for field, evidence in grounds.items():
        value, quote = getattr(found, field), getattr(found, evidence)
        if value is None:
            continue
        if field == start and quote and (_NIGHTS_ONLY.match(quote.strip()) or _duration_only(quote)):
            cleared.append(field)
            continue
        if isinstance(value, date) and quote and quote != "trip" and _week_only(quote):
            cleared.append(field)                     # ☆16:13 「다다음주에 출발」 — 날이 없는데 10-24 를 골랐다
            continue
        if quote == "trip" and has_trip:
            continue
        if quote != "trip" and quote_found(quote, text) and (not isinstance(value, date) or looks_like_date(quote)):
            continue
        if field != start and quote and _BARE_DAY.match(quote.strip()) and quote_found(quote, text) \
                and looks_like_date(getattr(found, grounds[start], None)):
            continue                                  # ☆22:28 「Nov 6-9」 — 끝 날짜 근거가 「9」뿐. 시작 근거가 날짜 모양이면 받는다
        if isinstance(value, date) and trip_days.get(field) and value.isoformat() == trip_days[field]:
            continue
        cleared.append(field)
    if end:
        start_gone = start in cleared or getattr(found, start) is None
        quote = getattr(found, grounds[end])
        if start_gone and end not in cleared and getattr(found, end) is not None and quote and _NIGHTS_ONLY.match(quote.strip()):
            cleared.append(end)
    return found.model_copy(update={field: None for field in cleared}), cleared


#: 여행 일정의 첫날 · 마지막 날을 가리키는 말
_TRIP_FIRST, _TRIP_LAST = ("첫날", "첫 날", "도착하는 날"), ("마지막 날", "마지막날", "떠나는 날")
_NIGHT_COUNT = re.compile(r"(\d+)\s*박")
#: 문장 속 머무는 기간 말(가격 말 「하루에 15만원」은 아니다)
_STAY_WORDS = re.compile(r"\d+\s*박|하루만|하루\s*묵|하룻밤|이틀")


def _nights(quote: str | None) -> int | None:
    if not quote:
        return None
    if any(word in quote for word in ("하루", "하룻밤")):
        return 1
    if "이틀" in quote:
        return 2
    match = _NIGHT_COUNT.search(quote)
    return int(match.group(1)) if match else None


def _trip_day(found: Any, text: str, *, grounds: dict[str, str], start: str, end: str | None,
              trip: dict[str, Any] | None) -> Any:
    """시작 근거가 「여행 첫날 · 마지막 날」이면 시작 날짜를 여행 일정의 그 날로(끝 근거가 박 수면 끝 날짜도). 여행이 없으면 그대로.

    ☆2026-10-11 16:21 playdata 「이번 여행 마지막 날 하루만 공항 근처 호텔」 — 근거는 맞게 적고 값은 10-11(내일)로 냈다.
    ☆2026-10-11 16:50 playdata 같은 문장 — 이번엔 시작 근거를 「하루만」(박 수)으로 적어 시작이 비고 되물었다.
      시작 근거가 박 수뿐이고 **문장**에 첫날 · 마지막 날 말이 한쪽만 있으면 문장의 그 말을 근거로 삼는다(박 수는 끝 날짜에).
    """
    quote = getattr(found, grounds[start], None) or ""
    nights_quote = getattr(found, grounds[end], None) if end else None
    if trip and _NIGHTS_ONLY.match(quote.strip()):
        said = [words for words in (_TRIP_LAST, _TRIP_FIRST) if any(word in text for word in words)]
        if len(said) == 1:
            nights_quote = nights_quote or quote
            quote = next(word for word in said[0] if word in text)
            found = found.model_copy(update={grounds[start]: quote, **({grounds[end]: nights_quote} if end else {})})
    day = None
    if trip and any(word in quote for word in _TRIP_LAST):
        day = trip.get("last_day")
    elif trip and any(word in quote for word in _TRIP_FIRST):
        day = trip.get("first_day")
    if not day:
        return found
    begin = date.fromisoformat(day)
    update: dict[str, Any] = {start: begin}
    nights = _nights(nights_quote) if end else None
    if end and not nights:
        # ☆17:49 같은 문장 — 시작 근거는 「마지막 날」로 맞게 적고 끝 근거를 "null" 로 적어 끝 날짜가 비었다. 문장에 박 수 말이 하나뿐이면 그것으로
        said = _STAY_WORDS.findall(text)
        if len(said) == 1:
            nights, update[grounds[end]] = _nights(said[0]), said[0]
    if end and nights:
        update[end] = begin + timedelta(days=nights)
    return found.model_copy(update=update)


def keep_quoted(items: list[str] | None, text: str, *, limit: int = 5) -> list[str]:
    """모델이 적은 「반영 못 하는 요청」 조각 중 고객 문장에 실제로 있는 것만(근거 확인과 같은 방식), 앞에서 `limit` 개."""
    kept: list[str] = []
    for item in items or []:
        if isinstance(item, str) and item.strip() and quote_found(item.strip(), text) and item.strip() not in kept:
            kept.append(item.strip())
    return kept[:limit]


def _duration_only(quote: str) -> bool:
    return bool(_DURATION.search(quote)) and not (_MONTH.search(quote) or _OFFSET.search(quote) or _WEEKDAY.search(quote))


def _week_only(quote: str) -> bool:
    return bool(_WEEK_ONLY.search(quote)) and not (_WEEKDAY.search(quote) or _DAY.search(quote) or _OFFSET.search(quote))


def _offset(quote: str, base: date) -> date | None:
    """「N일 · N주 · N달 뒤」 → base 에서 센 날. 없으면 None."""
    match = _OFFSET.search(quote)
    if not match:
        return None
    raw, unit = match.group(1), match.group(2)
    count = int(raw) if raw and raw.isdigit() else _KOREAN_NUMBER.get(raw or "", 1)
    if unit == "주일" and raw in (None, "일"):        # 「일주일」
        count = 1
    if unit in ("일",):
        return base + timedelta(days=count)
    if unit in ("주", "주일"):
        return base + timedelta(days=7 * count)
    month = base.month - 1 + count                    # 달 · 개월
    year, month = base.year + month // 12, month % 12 + 1
    for day in (base.day, 30, 29, 28):
        try:
            return base.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return None


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
    if "박" in quote or _OFFSET.search(quote) or _DURATION.search(quote):
        return value                                  # 「3일뒤」 「4일동안」의 숫자는 날(일)이 아니다
    days, months = _DAY.findall(quote), _MONTH.findall(quote)
    if len(days) != 1 or len(months) > 1 or len(_NUMBER.findall(quote)) != len(days) + len(months):
        return value                                  # ☆21:59 「다음달 13~15일」 — 범위(숫자가 더 있음)는 맞추지 않는다
    try:
        return value.replace(month=int(months[0]) if months else value.month, day=int(days[0]))
    except ValueError:
        return value


def _holiday(value: date, quote: str) -> date | None:
    squeezed = "".join(quote.split())
    for word, (month, day) in HOLIDAYS:
        if "".join(word.split()) in squeezed:
            return value.replace(month=month, day=day)
    return None


def _snap_weekday(value: date, quote: str) -> date:
    """근거에 요일이 하나만 있고 값의 요일이 다르면, 그 요일인 가장 가까운 날(±3일)로. 날(일) 숫자가 있으면 숫자를 믿는다."""
    names = _WEEKDAY.findall(quote)
    if len(names) != 1 or _DAY.search(quote):
        return value
    want = "월화수목금토일".index(names[0])
    shift = (want - value.weekday()) % 7
    return value + timedelta(days=shift if shift <= 3 else shift - 7)


def settle_dates(found: Any, *, grounds: dict[str, str], today: date, text: str = "") -> tuple[Any, list[str]]:
    """날 · 연도를 근거 조각과 맞춘다. (해석, 고친 칸)

    - 「N일 · N주 · N달 뒤」: 시작 날짜는 오늘에서, 끝 날짜는 시작 날짜에서 센다(모델 값보다 먼저).
    - 날: 근거에 날(일)이 하나만 있으면 값의 날을 그 수로(범위 「13~15일」 · 「3일뒤」 · 「4일동안」은 안 맞춤).
    - 요일: 근거에 요일이 하나만 있고 날 숫자가 없으면, 값을 그 요일인 가장 가까운 날로(☆21:59 「금요일까지」 → 10-14(수)).
    - 연도: 근거 어디에든 네 자리 연도가 있으면(고객이 연도를 말함) 아무 날짜의 연도도 바꾸지 않는다. 없으면 「오늘 이후 처음 오는
      그 월 · 일」(프롬프트 규칙 그대로)로. 기준은 모두 오늘이다 — 돌아오는 날을 떠나는 날 뒤로 밀지 않는다(앞뒤가 틀리면 `needs` 가 묻는다).
    - 근거가 `"trip"` 인 날짜는 건드리지 않는다.
    - 고쳐 말한 날(「7일로 바꿔줘」 — 문장에 「N일로」)과 값의 날이 같으면 근거의 날로 되돌리지 않는다. ☆2026-10-11 17:58 playdata
      F40 「11월 6일 … 아 날짜는 7일로 바꿔줘」 — 값은 11-07 로 맞게 내고 근거를 「11월 6일」로 적어 서버가 6일로 되돌렸다.
    - 끝 날짜 근거가 박 수뿐(「4박」)이면 끝 = 시작 + 박 수(모델 셈보다 먼저). ☆2026-10-11 17:50 playdata 「3박 아니 4박으로」 —
      근거는 「4박」으로 맞게 적고 값은 3박(11-09)으로 냈다.
    """
    quotes = [getattr(found, evidence, None) for evidence in grounds.values()]
    year_said = any(isinstance(quote, str) and _YEAR.search(quote) for quote in quotes)
    update: dict[str, date] = {}
    shift = timedelta(0)                              # 첫 날짜(시작)를 옮긴 만큼 — 박 수로 만든 끝 날짜도 같이 옮긴다
    start_field = next(iter(grounds))
    corrected = {int(day) for day in _CORRECTED.findall(text or "")}
    for index, (field, evidence) in enumerate(grounds.items()):
        value, quote = getattr(found, field, None), getattr(found, evidence, None)
        if not isinstance(value, date) or quote in (None, "trip"):
            continue
        if index > 0 and shift and _NIGHTS_ONLY.match(quote.strip()):
            update[field] = value + shift
            continue
        base = today if index == 0 else (update.get(start_field) or getattr(found, start_field, None) or today)
        counted = _offset(quote, base)
        if counted is not None:
            if counted != value:
                update[field] = counted
                if index == 0:
                    shift = counted - value
            continue
        moved = _holiday(value, quote) or (value if value.day in corrected else _align_day(value, quote))
        if not year_said:
            moved = _on_or_after(moved, today)
        moved = _snap_weekday(moved, quote)
        if moved != value:
            update[field] = moved
            if index == 0:
                shift = moved - value
    for index, (field, evidence) in enumerate(grounds.items()):
        quote, value = getattr(found, evidence, None), update.get(field, getattr(found, field, None))
        begin = update.get(start_field) or getattr(found, start_field, None)
        if index == 0 or not isinstance(value, date) or not isinstance(begin, date) or not isinstance(quote, str) \
                or not _NIGHTS_ONLY.match(quote.strip()):
            continue
        nights = _nights(quote)
        if nights and value != begin + timedelta(days=nights):
            update[field] = begin + timedelta(days=nights)
    return found.model_copy(update=update), list(update)


__all__ = ["CALENDAR_DAYS", "WEEKDAYS", "ground_dates", "keep_quoted", "looks_like_date", "model_context", "quote_found", "settle_dates"]
