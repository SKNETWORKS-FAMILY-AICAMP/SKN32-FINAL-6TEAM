# -*- coding: utf-8 -*-
"""장소 영업시간 — 관광공사 **원문**을 요일별 시각으로 옮기고, 날짜마다 그날의 시간을 돌려준다. `[2026-09-28]`

★왜. 일정 생성기가 영업시간을 모른 채 짰다 — 실제 일정 활동 24 · 식사 14 중 영업시간을 아는 항목 **0/38**
  (2026-09-28 `demo` 테넌트 실측). 그래서 「13:00~17:00 운영 · 매주 일요일~목요일 휴무」인 곳이 **월요일 09:00**에
  들어갔다. 판정기(`check_itinerary`)는 모르는 영업시간을 보지 않으니 한 번도 걸리지 않았다.

★사용자 결정(2026-09-28): **관광공사 원문을 구조화한다.** 앞 규칙(`tour_api.py` 머리 「원문을 파싱해 boolean 으로
  만들지 않는다」)을 이 결정이 바꾼다. 그 규칙이 막으려던 위험(잘못 편 규칙 → 고객이 닫힌 문 앞에 선다)은 이렇게 줄인다:
    1. 규칙으로 읽을 수 있는 **단순한 원문만** 규칙으로 읽는다(「HH:MM~HH:MM」 · 「매주 X요일」 · 「연중무휴」).
    2. 나머지는 모델이 옮기되 **원문에 글자 그대로 있는 인용**이 붙은 것만 받는다. 인용에 없는 시각·요일은 버린다.
    3. 계절·월마다 시간이 다르면 **가장 짧은 시간대(늦게 열고 일찍 닫는 쪽)**를 쓴다 — 계획은 보수적으로.
    4. 공휴일 조건처럼 한 주 규칙으로 못 펴는 것은 **펴지 않는다**(`conditions` 에 원문으로 남긴다).
    5. **최종 판정은 당일 새벽 구글 확인**이 한다(`dawn_check`) — 여기는 계획을 덜 틀리게 하는 몫이다.
  못 읽으면 모른다(`None`) — 지금과 같다. 지어내지 않는다.

★저장 모양 — 장소 `attributes.hours_week`:
    {"mon": {"open": "13:00", "close": "17:00", "last_entry": null} | "closed", ... }   # 없는 요일 = 모름
  와 `attributes.hours_read`(어디서 · 어떻게 · 인용). 하루 한 칸짜리 옛 모양 `attributes.hours` 는 그대로 읽는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Mapping

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_KO = "월화수목금토일"
_KO_DAY = {ch: DAYS[i] for i, ch in enumerate(_KO)}


# ── 날짜 → 그날의 영업시간 ────────────────────────────────────────
@dataclass(frozen=True)
class DayHours:
    opens: time
    closes: time
    last_entry: time | None = None


def _clock(text: Any) -> time | None:
    try:
        hour, minute = (int(x) for x in str(text).split(":"))
    except (TypeError, ValueError):
        return None
    if hour == 24 and minute == 0:
        return time(23, 59)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return time(hour, minute)


def hours_on(attributes: Mapping[str, Any] | None, day: date) -> DayHours | str | None:
    """그날의 영업시간. `"closed"`(쉬는 날) · `DayHours` · `None`(모름).

    ★요일별 칸(`hours_week`)이 먼저다. 그 요일이 비어 있으면 하루 한 칸(`hours`)을 본다."""
    attributes = attributes or {}
    week = attributes.get("hours_week")
    if isinstance(week, Mapping):
        entry = week.get(DAYS[day.weekday()])
        if entry == "closed":
            return "closed"
        if isinstance(entry, Mapping):
            opens, closes = _clock(entry.get("open")), _clock(entry.get("close"))
            if opens and closes:
                return DayHours(opens, closes, _clock(entry.get("last_entry")) if entry.get("last_entry") else None)
    hours = attributes.get("hours")
    if isinstance(hours, (list, tuple)) and len(hours) == 2:
        opens, closes = _clock(hours[0]), _clock(hours[1])
        if opens and closes:
            return DayHours(opens, closes)
    return None


def knows_hours(attributes: Mapping[str, Any] | None) -> bool:
    attributes = attributes or {}
    return "hours" in attributes or bool(attributes.get("hours_week"))


def fits(attributes: Mapping[str, Any] | None, start: datetime, end: datetime) -> bool | None:
    """그 칸(시작~끝)에 열려 있나. 모르면 `None`."""
    found = hours_on(attributes, start.date())
    if found is None:
        return None
    if found == "closed":
        return False
    if start.time() < found.opens or end.time() > found.closes:
        return False
    return not (found.last_entry and start.time() > found.last_entry)


# ── 원문 → 요일별 ───────────────────────────────────────────────
@dataclass
class HoursRead:
    week: dict[str, Any] = field(default_factory=dict)       # hours_week 모양
    method: str = "none"                                     # rule | llm | none
    quotes: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)      # 펴지 않은 조건(공휴일 등) — 원문
    dropped: list[str] = field(default_factory=list)         # 인용 검증에서 버린 것과 이유

    def as_record(self, *, source: str, read_at: str) -> dict[str, Any]:
        return {"source": source, "method": self.method, "quotes": self.quotes, "conditions": self.conditions,
                "dropped": self.dropped, "read_at": read_at}


def clean(text: str | None) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(text or ""), flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[~\-–]\s*(\d{1,2}):(\d{2})")
_LAST = re.compile(r"(?:입장\s*마감|입장마감|마감)\s*[:：]?\s*(\d{1,2}):(\d{2})")
_WEEKLY = re.compile(r"^매주\s*([월화수목금토일](?:요일)?(?:\s*[,·/~]\s*[월화수목금토일](?:요일)?)*)\s*(?:휴무|휴관|정기휴무|정기휴관)?\.?$")
_NONE = ("연중무휴", "없음", "휴무없음", "무휴")


def _hm(hour: str, minute: str) -> str:
    return f"{int(hour):02d}:{minute}"


_DAY_TOKEN = re.compile(r"(?<![가-힣\d])([월화수목금토일])(?:요일)?(?![가-힣])|([월화수목금토일])요일")


def days_in(quote: str) -> set[str]:
    """인용에 적힌 요일 — 「일요일~목요일」·「월~금」 같은 범위를 편다. 요일 말이 없으면 빈 집합.

    ★요일 말만 센다 — 숫자 뒤 「월」은 달(「1월~2월」), 낱말 속 「일」은 요일이 아니다(「당일」·「평일」·「공휴일」).
      둘 다 실제 원문에서 요일로 잘못 읽었다(경복궁 · 자하손만두)."""
    text = re.sub(r"\d+\s*월", " ", quote)
    tokens = [(m.start(), m.end(), m.group(1) or m.group(2)) for m in _DAY_TOKEN.finditer(text)]
    found = {_KO_DAY[ch] for _, _, ch in tokens}
    for (_, end_a, a), (start_b, _, b) in zip(tokens, tokens[1:]):
        if re.fullmatch(r"\s*[~\-–]\s*", text[end_a:start_b]):
            i, j = _KO.index(a), _KO.index(b)
            span = range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1))
            found.update(DAYS[k] for k in span)
    return found


def read_by_rule(usetime: str | None, restdate: str | None) -> HoursRead | None:
    """단순한 원문만. 하나라도 규칙 밖이면 `None` — 모델로 넘긴다."""
    use, rest = clean(usetime), clean(restdate)
    if not use:
        return None
    one = _RANGE.fullmatch(_LAST.sub("", use).strip(" ()\n")) if _RANGE.search(use) else None
    if one is None or len(_RANGE.findall(use)) != 1 or re.search(r"\d+월|\[|평일|주말|공휴일|하절기|동절기", use):
        return None
    closed: set[str] = set()
    if rest and _norm(rest) not in _NONE:
        weekly = _WEEKLY.match(rest.strip())
        if weekly is None:
            return None
        closed = days_in(weekly.group(1))
    last = _LAST.search(use)
    window = {"open": _hm(*one.groups()[:2]), "close": _hm(*one.groups()[2:]),
              "last_entry": _hm(*last.groups()) if last else None}
    week = {day: ("closed" if day in closed else dict(window)) for day in DAYS}
    return HoursRead(week=week, method="rule", quotes=[q for q in (use, rest) if q])


SYSTEM = (
    "You convert Korean opening-hours text into weekly hours. Output JSON only: "
    '{"open": [{"days": ["mon",...], "open": "HH:MM", "close": "HH:MM", "last_entry": "HH:MM"|null, '
    '"quote": "<exact substring of the text>"}], "closed": [{"days": [...], "quote": "<exact substring>"}], '
    '"conditions": ["<exact substring>"]}. '
    "Days are mon tue wed thu fri sat sun. Every quote MUST be copied character-for-character from the text. "
    "If hours differ by season or month, output one open entry per season with its own quote. "
    "Put holiday rules or anything that is not a fixed weekly rule into conditions (quoted), not into closed. "
    "If an open entry names no days, it applies to every day that is not closed. Never invent times."
)


def read_by_model(usetime: str | None, restdate: str | None, chat: Any) -> HoursRead:
    """모델이 옮긴다. ★인용이 원문에 **그대로** 있고, 시각·요일이 **인용 안에** 있는 것만 받는다."""
    use, rest = clean(usetime), clean(restdate)
    source = f"운영시간: {use}\n쉬는 날: {rest}"
    haystack = _norm(source)
    read = HoursRead(method="llm")
    if chat is None:
        read.dropped.append("모델이 연결돼 있지 않다")
        read.method = "none"
        return read
    raw = chat.json(SYSTEM, source) or {}

    def quoted(entry: Mapping[str, Any]) -> str | None:
        quote = str(entry.get("quote") or "")
        return quote if quote and _norm(quote) in haystack else None

    closed: set[str] = set()
    for entry in raw.get("closed") or []:
        quote = quoted(entry)
        days = {d for d in entry.get("days") or [] if d in DAYS}
        if quote is None:
            read.dropped.append(f"쉬는 날 인용이 원문에 없다: {entry.get('quote')!r}")
            continue
        allowed = days_in(quote)
        if not days or not days <= allowed:
            read.dropped.append(f"쉬는 날 요일이 인용에 없다: {sorted(days - allowed)} ← {quote!r}")
            continue
        closed |= days
        read.quotes.append(quote)
    windows: dict[str, list[tuple[time, time, time | None]]] = {}
    for entry in raw.get("open") or []:
        quote = quoted(entry)
        if quote is None:
            read.dropped.append(f"운영시간 인용이 원문에 없다: {entry.get('quote')!r}")
            continue
        opens, closes = _clock(entry.get("open")), _clock(entry.get("close"))
        stamps = {_hm(h, m) for h, m in re.findall(r"(\d{1,2}):(\d{2})", quote)}
        if not (opens and closes) or entry.get("open") not in stamps or entry.get("close") not in stamps:
            read.dropped.append(f"운영 시각이 인용에 없다: {entry.get('open')}~{entry.get('close')} ← {quote!r}")
            continue
        last = entry.get("last_entry")
        last_time = _clock(last) if last and last in stamps else None
        named = days_in(quote)
        days = {d for d in entry.get("days") or [] if d in DAYS}
        if named and not days <= named:
            read.dropped.append(f"운영 요일이 인용에 없다: {sorted(days - named)} ← {quote!r}")
            continue
        for day in ((days or named) if named else set(DAYS)):
            windows.setdefault(day, []).append((opens, closes, last_time))
        read.quotes.append(quote)
    for text in raw.get("conditions") or []:
        if _norm(str(text)) in haystack:
            read.conditions.append(str(text))
    week: dict[str, Any] = {}
    for day in DAYS:
        if day in closed:
            week[day] = "closed"
        elif windows.get(day):
            # ★계절마다 다르면 가장 짧은 시간대 — 늦게 여는 쪽 · 일찍 닫는 쪽 · 이른 입장 마감
            spans = windows[day]
            opens = max(s[0] for s in spans)
            closes = min(s[1] for s in spans)
            lasts = [s[2] for s in spans if s[2]]
            if opens >= closes:
                read.dropped.append(f"{day}: 계절 시간대를 겹치니 남는 시간이 없다")
                continue
            week[day] = {"open": opens.strftime("%H:%M"), "close": closes.strftime("%H:%M"),
                         "last_entry": min(lasts).strftime("%H:%M") if lasts else None}
    read.week = week
    if not week:
        read.method = "none"
    return read


def read_hours(usetime: str | None, restdate: str | None, chat: Any = None) -> HoursRead:
    """규칙 먼저, 안 되면 모델. 모델이 실패해도 예외를 올리지 않고 `dropped` 에 적는다."""
    ruled = read_by_rule(usetime, restdate)
    if ruled is not None:
        return ruled
    if not clean(usetime) and not clean(restdate):
        return HoursRead(method="none", dropped=["원문이 비어 있다"])
    try:
        return read_by_model(usetime, restdate, chat)
    except Exception as exc:                         # noqa: BLE001 — 모델 실패는 「모름」이다(지어내지 않는다)
        return HoursRead(method="none", dropped=[f"모델 호출 실패 {type(exc).__name__}"])


__all__ = ["DAYS", "DayHours", "HoursRead", "clean", "days_in", "fits", "hours_on", "knows_hours",
           "read_by_model", "read_by_rule", "read_hours"]
