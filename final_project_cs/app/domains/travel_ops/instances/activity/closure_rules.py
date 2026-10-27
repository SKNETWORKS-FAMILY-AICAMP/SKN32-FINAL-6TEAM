# -*- coding: utf-8 -*-
"""정기휴무 원문(TourAPI `restdate` · CSV `closed_days`) → 그 날 휴무인가. 성립 판정과 대체 장소가 함께 쓴다.

★`[2026-10-06]` 왜 새로 만들었나 — 결함 리포트
  `wiki/records/reports/debugs/2026-10-06_1610_정기휴무_규칙이_매주X_원문_307건을_놓친다.md`.
  성립 판정의 정규식(`매주 X (휴무|휴관)`)이 실제 원문 「매주 X」 309건 중 307건을 못 읽고 **「휴무 아님」으로 확정**했다.
  대체 장소 쪽 `closed_on` 은 더 나았지만 날짜 · 「매월 둘째 주」 · 공휴일 조건은 역시 「아님」으로 확정했다. 둘을 이것 하나로 합친다.

★원칙
  1. 원문을 **절**로 나눈다(`/` · 줄바꿈 · `<br>` · 괄호 · `※`). 절마다 판정하고 합친다 —
     하나라도 휴무면 휴무, 아니면 하나라도 모름이면 모름, 다 아니면 아님.
  2. 한 절 안의 패턴(요일 · 몇째 주 · 날짜 · 날짜 범위 · 명절 · 공휴일)은 **모두** 본다. 하나라도 맞으면 휴무다.
     날짜 범위(「12월 29일~1월 2일」)는 양 끝만이 아니라 **사이 날짜까지** 휴무로 본다(해 넘김 포함) — `[2026-10-21]`
  3. **못 읽은 조각이 남으면 그 절은 모름**이다 — 전처럼 「아님」으로 확정하지 않는다(CLAUDE.md §0).
  4. 공휴일이 걸린 조건은 `holiday(날짜)` 로 묻는다(`read.holiday` — 한국천문연구원 특일). 모르면(`None`) 모름이다.
     ★예외 — 「매주 X요일 (단, 공휴일이면 개방)」은 요일이 맞고 공휴일 여부를 모르면 **휴무**로 두고 단서를 단다
       (`needs_caveat`). 대부분의 날은 공휴일이 아니고, 전에도 이렇게 단서를 달아 안내했다. 공휴일인 걸 알면 「아님」이다.
  5. 날짜 계산(몇째 주 · 마지막 주 · 월·일)은 코드가 한다.
  6. `[2026-10-14 사용자]` 「(매)월 N회」(백화점 「명절, 월1회」 등)는 **날짜가 정해지지 않은 휴무**다 — 요일이 없으면
     어느 날이든 모름(`monthly_irregular`), 요일이 함께 있으면(「월2회 일요일」) 그 요일만 모름이고 다른 요일은 아님.
     ★「월」은 달이지 월요일이 아니다 — 결함 `wiki/records/reports/debugs/2026-10-14_2208_정기휴무_규칙이_월N회를_매주_월요일로_읽는다.md`.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.places.place_hours import DAYS, NOT_A_DAY_AFTER, days_in

HolidayLookup = Callable[[date], "dict[str, Any] | None"]

#: ★휴무는 장소의 **현지(한국) 날짜**로 따진다 — 예약 시각이 UTC 로 와도(15:00Z = 다음 날 00:00 KST) 한국 날짜의 요일을 본다.
#:  시간대가 없는 값은 현지 벽시계 시각으로 읽는다.
KST = ZoneInfo("Asia/Seoul")


def local_date(at: datetime) -> date:
    return (at.astimezone(KST) if at.tzinfo else at).date()

_KO = "월화수목금토일"
#: 이 말이 있는 절은 해석하지 않는다(모름) — 장소·공연마다 다르거나 밖에서 확인하라는 뜻이다.
UNKNOWN_MARKERS = ("상이", "참조", "확인", "문의", "별도", "변동", "공연별", "공연 별")
_ALWAYS_OPEN = re.compile(r"^(?:연중\s*무휴|연중\s*개방|연중\s*운영|휴무(?:일)?\s*없음|휴관(?:일)?\s*없음|무휴|없음)(?:\s*운영)?$")
_ORD = {"첫째": 1, "첫번째": 1, "첫 번째": 1, "둘째": 2, "두번째": 2, "두 번째": 2, "셋째": 3, "세번째": 3,
        "세 번째": 3, "넷째": 4, "네번째": 4, "네 번째": 4, "다섯째": 5, "마지막": -1,
        # 「매월 5번째 월요일」 — 숫자 서수(결함 2026-10-14_2208 함께 발견)
        **{f"{n}{sp}번째": n for n in range(1, 6) for sp in ("", " ")}}
_ORD_WORD = "|".join(sorted((re.escape(k) for k in _ORD), key=len, reverse=True))
#: 「2·4주차 일요일」 · 「2,4주 수요일」 — 숫자만 쓴 서수. 뒤에 「주차 · 주 · 번째 · 째」가 와야 서수다(「3월 토요일」은 아니다)
#: 「매달 1, 3, 5번째 일요일」 — 「번째」가 없으면 1 · 3 을 놓치고 5 만 읽는다(2026-10-15)
_ORD_NUM = r"(?<!\d)[1-5](?=[\s·,/및1-5]*(?:주차|주|번째|째))"
_ORD_TOKEN = rf"(?:{_ORD_WORD}|{_ORD_NUM})"
_NTH = re.compile(rf"((?:{_ORD_TOKEN})(?:\s*(?:주차|주|째))?(?:\s*[·,/및]\s*(?:{_ORD_TOKEN})(?:\s*(?:주차|주|째))?)*)"
                  rf"\s*(?:주차|주)?\s*([월화수목금토일])요일")
_DATE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
#: 날짜 범위 — 「12월 29일~1월 2일」 · 「12월 29일 - 31일」 · 「12월 29일부터 1월 2일까지」. 끝의 달을 빼면 시작과 같은 달이다.
#: ★양 끝 날짜만 맞춰 보면 사이 날짜(12-30 · 12-31 · 1-1)를 「해당 없음」으로 읽는다(2026-10-21 x600 서버 자료 1건). 해를 넘길 수 있다.
_DATE_RANGE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(?:부터|[~\-–～])\s*(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일(?:\s*까지)?")
#: 끝에 달만 있는 범위 — 「12월 29일~1월 초」. 끝 날짜를 모르니 어느 날이 사이인지 정하지 못한다(모름).
_DATE_RANGE_OPEN_END = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일\s*(?:부터|[~\-–～])\s*\d{1,2}\s*월(?!\s*\d)")
_MONTH_LIST = re.compile(r"(\d{1,2})\s*월")
_HOLIDAY = re.compile(r"공휴일|국경일|대체\s*휴일")
_FESTIVE = re.compile(r"명절|설날|설|추석|구정")
_FESTIVE_NAME = re.compile(r"설|추석")
_EXCEPT_OPEN = re.compile(r"(?:단|다만)[,\s].*(?:공휴일|휴일).*(?:개방|정상|운영|개관|개장)")
_CARRY_OVER = re.compile(r"다음|익일|이튿날|첫\s*번째\s*(?:평일|비공휴일)")
_WEEKEND = re.compile(r"주말")
#: 「월 1회」 · 「매월 2회」 · 「월 한 번」 — 한 달에 몇 번(날짜 미정). 「매월 두 번째」 같은 서수는 아니다.
_MONTHLY = re.compile(r"(?:매월|(?<![가-힣\d])월)\s*(?:\d+|한|두|세)\s*(?:회|번|차례)(?!\s*째)")
_IRREGULAR = re.compile(r"비정기|부정기")
#: 요일 글자만 쓴 나열 — 「매주 월, 화」 · 「월·화」
_BARE_DAY = re.compile(rf"(?<![가-힣])([월화수목금토일])(?=\s*(?:[,·~]|요일|$|\s)){NOT_A_DAY_AFTER}")
#: 판정에 쓰지 않는 군말 — 이것만 남으면 「못 읽은 조각」이 아니다
_FILLER = re.compile(r"매주|매월|매달|매년|정기\s*휴(?:무|관|일|실일)?|휴(?:무|관|궁|장|업|실)(?:일)?|당일|및|그리고|[\s,·~\-.:;]|"
                     r"요일|주|일|월|\[|\]|법정|날")


@dataclass(frozen=True)
class ClosureRead:
    #: True 휴무 · False 아님 · None 모름
    value: bool | None
    #: 판정을 정한 절(원문 조각). 없으면 `None`.
    quote: str | None
    #: 어떻게 정했나 — `weekly` · `nth_weekday` · `date` · `festive` · `holiday` · `always_open` · `unknown_marker` · `unparsed` …
    reason: str
    #: 휴무로 냈지만 공휴일 예외를 확인하지 못했다 — 답변에 「공휴일과 겹치면 다를 수 있다」를 단다.
    needs_caveat: bool = False
    guidance: tuple[str, ...] = ()


def holiday_dates_needed(text: str | None, at: Any) -> list[date]:
    """이 원문을 판정하려면 어느 날짜의 공휴일 여부가 필요한가. 필요 없으면 빈 목록(도구를 부르지 않는다)."""
    if not text or not isinstance(at, datetime):
        return []
    d = local_date(at)
    if _FESTIVE.search(text) and re.search(r"연휴|전일|전날|익일|다음\s*날|당일", text):
        return [d, d - timedelta(days=1), d + timedelta(days=1)]
    if _FESTIVE.search(text) or _HOLIDAY.search(text) or _EXCEPT_OPEN.search(text):
        return [d]
    return []


def read_closure(text: str | None, at: Any, holiday: HolidayLookup | None = None, *, until: datetime | None = None) -> ClosureRead:
    """그 시각(`at`)이 원문상 휴무인가. `holiday` 가 없으면 공휴일 조건은 모름으로 읽는다."""
    lookup = holiday or (lambda _d: None)
    raw = (text or "").strip()
    if not raw:
        return ClosureRead(None, None, "empty")
    if not isinstance(at, datetime):
        return ClosureRead(None, None, "time_unknown")
    restriction = _read_visit_condition(raw, at, until, holiday)
    if restriction is not None:
        return restriction
    raw = _REST_LABEL.sub("", raw, count=1)
    d = local_date(at)
    clauses = _clauses(raw)
    exception = next((c for c in clauses if _EXCEPT_OPEN.search(c)), None)
    results = [(c, *_clause(c, d, lookup)) for c in clauses if c is not exception]

    weekly_hit = next(((c, why) for c, v, why in results if v is True and why == "weekly"), None)
    if exception is not None and weekly_hit is not None:
        # 「매주 X (단, 공휴일이면 개방 …)」 — 요일이 맞은 날만 예외를 따진다
        info = lookup(d)
        if info is None:
            return ClosureRead(True, weekly_hit[0], "weekly_holiday_exception_unverified", needs_caveat=True)
        if info.get("is_holiday"):
            return ClosureRead(False, exception, "holiday_exception_open")
        return ClosureRead(True, weekly_hit[0], "weekly")
    if exception is not None and _CARRY_OVER.search(exception) and not weekly_hit:
        # 「… 공휴일이면 개방하고 다음 평일 휴관」 — 전날이 공휴일이었는지 모르면 오늘을 확정하지 않는다
        prev = lookup(d - timedelta(days=1))
        if prev is None or prev.get("is_holiday"):
            return ClosureRead(None, exception, "holiday_carry_over_unverified")

    for c, v, why in results:
        if v is True:
            return ClosureRead(True, c, why, needs_caveat=(why == "weekly"))
    for c, v, why in results:
        if v is None:
            return ClosureRead(None, c, why)
    return ClosureRead(False, None, "no_clause_matches")


def closed_on_weekday(text: str | None, at: Any, holiday: HolidayLookup | None = None) -> bool | None:
    """옛 호출부(`_weekday_closure_match` · `closed_on`)를 위한 얇은 감싸개 — 값만 돌려준다."""
    return read_closure(text, at, holiday).value


# ── 내부 ────────────────────────────────────────────────────────
def _clauses(text: str) -> list[str]:
    text = re.sub(r"<br\s*/?>", "/", text, flags=re.I)
    text = re.sub(r"[()（）※\[\]]", "/", text)
    # 「매주 화요일 휴무. 단 공휴일과 겹치면 개방」 — 예외 조항을 앞 절과 떼어 따로 판정한다(「단체」 같은 낱말은 건드리지 않는다)
    text = re.sub(r"(?:^|(?<=[\s.,]))(?=(?:단|다만)\s*[,，]?\s)", "/", text)
    return [c.strip(" .,") for c in re.split(r"[/\n]", text) if c.strip(" .,")]


def _nth_of(d: date) -> tuple[int, bool]:
    return (d.day - 1) // 7 + 1, (d + timedelta(days=7)).month != d.month


def _in_date_range(start: tuple[int, int], end: tuple[int, int], day: date) -> bool:
    """(월, 일) 범위에 그 날이 드는가 — 양 끝 포함. 끝이 시작보다 앞이면 해를 넘기는 범위(12월 29일~1월 2일)다."""
    today = (day.month, day.day)
    return start <= today <= end if start <= end else (today >= start or today <= end)


def _weekday_days(c: str) -> set[str]:
    found = days_in(c)
    if not found and ("매주" in c or "휴" in c):
        found = {DAYS[_KO.index(ch)] for ch in _BARE_DAY.findall(c)}
    return found


def _clause(c: str, d: date, holiday: HolidayLookup) -> tuple[bool | None, str]:
    """한 절 → (휴무/아님/모름, 이유). 절 안의 패턴을 **모두** 본다."""
    if any(m in c for m in UNKNOWN_MARKERS):
        return None, "unknown_marker"
    if _ALWAYS_OPEN.match(re.sub(r"\s+", " ", c)):
        return False, "always_open"

    verdicts: list[tuple[bool | None, str]] = []
    rest = c

    for m in _NTH.finditer(c):
        wd = _KO.index(m.group(2))
        n, last = _nth_of(d)
        wanted = [_ORD[w] if w in _ORD else int(w) for w in re.findall(rf"{_ORD_WORD}|[1-5]", m.group(1))]
        months = {int(x) for x in _MONTH_LIST.findall(c[:m.start()])}       # 「매년 3월, 6월 … 첫 번째 월요일」
        in_month = not months or d.month in months
        hit = in_month and d.weekday() == wd and any((w == -1 and last) or w == n for w in wanted)
        verdicts.append((hit, "nth_weekday"))
        rest = rest.replace(m.group(0), " ")

    for m in _DATE_RANGE.finditer(rest):
        start = (int(m.group(1)), int(m.group(2)))
        end = (int(m.group(3) or m.group(1)), int(m.group(4)))
        verdicts.append((_in_date_range(start, end, d), "date_range"))
    rest = _DATE_RANGE.sub(" ", rest)
    if _DATE_RANGE_OPEN_END.search(rest):
        verdicts.append((None, "date_range_open_end"))
        rest = _DATE_RANGE_OPEN_END.sub(" ", rest)

    for m in _DATE.finditer(rest):
        verdicts.append((int(m.group(1)) == d.month and int(m.group(2)) == d.day, "date"))
    rest = _DATE.sub(" ", rest)

    if _FESTIVE.search(rest):
        verdicts.append(_festive(rest, d, holiday))
        rest = _FESTIVE.sub(" ", re.sub(r"연휴|전일|전날|익일|다음\s*날|당일", " ", rest))

    if _HOLIDAY.search(rest):
        info = holiday(d)
        verdicts.append((None, "holiday_unknown") if info is None else (bool(info.get("is_holiday")), "holiday"))
        rest = _HOLIDAY.sub(" ", rest)

    if _WEEKEND.search(rest):
        verdicts.append((d.weekday() >= 5, "weekend"))
        rest = _WEEKEND.sub(" ", rest)

    # ★「월 N회」의 「월」은 달이다 — 요일보다 먼저 떼어 낸다(결함 2026-10-14_2208)
    monthly = bool(_MONTHLY.search(rest))
    if monthly:
        rest = _IRREGULAR.sub(" ", _MONTHLY.sub(" ", rest))

    days = _weekday_days(rest)
    if days:
        on_day = DAYS[d.weekday()] in days
        # 「월2회 일요일」 — 그 요일 가운데 어느 날인지 모른다. 다른 요일은 이 절로는 휴무가 아니다
        verdicts.append(((None if on_day else False), "monthly_irregular") if monthly else (on_day, "weekly"))
        rest = re.sub(r"[월화수목금토일](?:요일)?", " ", rest)
    elif monthly:
        verdicts.append((None, "monthly_irregular"))

    leftover = _FILLER.sub("", rest)
    leftover = re.sub(r"\d+", "", leftover)
    if leftover:
        # ★못 읽은 조각 — 맞은 휴무가 있으면 휴무, 없으면 모름(「아님」으로 확정하지 않는다)
        verdicts.append((None, "unparsed"))
    if not verdicts:
        return None, "unparsed"
    for v, why in verdicts:
        if v is True:
            return True, why
    for v, why in verdicts:
        if v is None:
            return None, why
    return False, verdicts[0][1]


def _festive(c: str, d: date, holiday: HolidayLookup) -> tuple[bool | None, str]:
    """명절 조건. 특일 이름에 「설」·「추석」이 있는 날을 명절로 본다.

    ★「당일」은 명절 사흘(전날·당일·다음날 — 특일 이름이 모두 「설날」·「추석」으로 온다고 본다) 가운데 **가운데 날**이다.
      앞뒤가 둘 다 명절이 아니면(대체공휴일 등 이름이 다른 경우) 당일인지 확정하지 않는다 — 모름.
      `[확인 필요]` 특일 API 가 사흘을 같은 이름으로 주는지는 실측하지 못했다(2026-10-06 현재 키가 403).
    """
    today = holiday(d)
    if today is None:
        return None, "festive_unknown"
    festive_today = bool(_FESTIVE_NAME.search(str(today.get("holiday_name") or today.get("name") or "")))
    if re.search(r"연휴|전일|전날|익일|다음\s*날", c):
        if festive_today:
            return True, "festive"
        around = [holiday(d + timedelta(days=k)) for k in (-1, 1)]
        if any(i is None for i in around):
            return None, "festive_unknown"
        near = any(_FESTIVE_NAME.search(str(i.get("holiday_name") or i.get("name") or "")) for i in around)
        return (True, "festive") if near and re.search(r"전일|전날|익일|다음\s*날", c) else (False, "festive")
    if not festive_today:
        return False, "festive"
    around = [holiday(d + timedelta(days=k)) for k in (-1, 1)]
    if any(i is None for i in around):
        return None, "festive_unknown"
    middle = all(_FESTIVE_NAME.search(str(i.get("holiday_name") or i.get("name") or "")) for i in around)
    return (True, "festive") if middle else (None, "festive_day_ambiguous")


#: 조건 문장 앞의 라벨 — 「쉬는 날: 연중무휴」 (`catalog_hours` 가 「쉬는 날: …」 원문을 인용해 담는다)
_REST_LABEL = re.compile(r"^\s*(?:쉬는\s*날|휴무일|휴관일|정기\s*휴무일?|정기\s*휴관일?|휴무|휴관)\s*[:：]\s*")
#: 구역·시설의 **방문 제한시간** 문장의 표지 — 이 말이 있어야 시간대 제한으로 읽는다(그냥 시간 범위는 무엇의 시간인지 모른다)
_VISIT_LIMIT = re.compile(r"(?:방문|입장|출입)\s*(?:제한|금지)")
_CLOCK_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[~\-–～]\s*(익일|다음\s*날)?\s*(\d{1,2}):(\d{2})")
#: 요일 · 달 · 계절 · 주차 단서가 붙은 제한은 이 날에 적용되는지 이 함수가 모른다 → 모름
_RESTRICTION_QUALIFIER = re.compile(r"\d+\s*월|[월화수목금토일]요일|평일|주말|공휴일|하절기|동절기|여름|겨울|봄|가을|매주|매월|주차|첫째|둘째|셋째|넷째|마지막")


def _split_restrictions(text: str) -> list[tuple[str, bool]] | None:
    """방문 제한시간 표지가 있는 문장이면 (조각, 제한시간 조각인가) 목록, 아니면 `None`. 조각은 줄바꿈 · `;` 로 나눈다."""
    if not _VISIT_LIMIT.search(text):
        return None
    pieces = [p.strip() for p in re.split(r"[;\n]", text) if p.strip()]
    return [(piece, bool(_VISIT_LIMIT.search(piece))) for piece in pieces] or None


def _restriction_verdict(segment: str, start: datetime, end: datetime | None) -> str:
    """`clear`(방문 시각과 안 겹침이 확정) · `hit`(겹침) · `unknown`(모호 — 시각이 하나가 아니거나 단서가 붙었거나 끝이 시작과 같음 …).

    ★경계는 반개구간이다 — 제한 `[시작, 끝)`. 방문이 정확히 끝 시각(10:00)에 시작하거나 시작 시각(17:00)에 끝나는 것은 겹침이 아니다
      (그 장소의 운영시간 줄 「10:00–17:00」과 같은 읽기). 끝 시각이 없으면 시작 한 시각만 본다.
    ★「익일」이 있거나 끝이 시작보다 앞이면 밤을 넘기는 구간이다. 「익일」인데 끝이 시작 이후이면 24시간을 넘어 모호하므로 모름.
    ★해석은 문장 안의 시각에서만 나온다 — 장소 이름 · 번호 · 날짜 · 시각을 코드에 두지 않는다."""
    found = _CLOCK_RANGE.findall(segment)
    if len(found) != 1 or _RESTRICTION_QUALIFIER.search(segment):
        return "unknown"
    match = _CLOCK_RANGE.search(segment)
    if segment[match.end():].strip(" ."):
        return "unknown"
    residue = _CLOCK_RANGE.sub("", segment)
    prefix = segment[:match.start()]
    if not re.fullmatch(r"\s*※?\s*(?:입장\s*금지\s*시간\s*안내\s*-\s*)?(?:방문|입장|출입)\s*(?:제한|금지)\s*(?:시간)?\s*(?:\([^\d]*\))?\s*[:：]?\s*", prefix):
        return "unknown"
    if re.search(r"\d|휴무|휴관|종일|매일|또는|및|않|아니|불가|휴일|예외|제외|단[, :]|외에는|이외|이후|이전|별도|상이|참조|확인|문의|변동|공연|[월화수목금토일][·,/ ~]", residue):
        return "unknown"
    sh, sm, next_day, eh, em = found[0]
    begin, finish = int(sh) * 60 + int(sm), int(eh) * 60 + int(em)
    if not (0 <= begin < 24 * 60 and 0 <= int(sm) < 60 and 0 <= int(em) < 60 and 0 <= finish <= 24 * 60) or (int(eh) == 24 and int(em)):
        return "unknown"
    if begin == finish or (next_day and finish > begin):
        return "unknown"
    wraps = bool(next_day) or finish < begin
    seoul = KST
    s = start.astimezone(seoul).replace(tzinfo=None) if start.tzinfo else start
    e = (end.astimezone(seoul).replace(tzinfo=None) if end.tzinfo else end) if end is not None else None
    if e is not None and e <= s:
        return "unknown"
    if e is not None and e - s >= timedelta(days=1):
        return "hit"
    for offset in (-1, 0, 1):
        day0 = datetime.combine(s.date(), datetime.min.time()) + timedelta(days=offset)
        w0 = day0 + timedelta(minutes=begin)
        w1 = day0 + timedelta(days=1 if wraps else 0, minutes=finish)
        if (s < w1 and e > w0) if e is not None else (w0 <= s < w1):
            return "hit"
    return "clear"



def _read_visit_condition(text: str, at: datetime, until: datetime | None, holiday: HolidayLookup | None) -> ClosureRead | None:
    segments = _split_restrictions(text)
    if segments is None:
        return None
    left, guidance = [], []
    for segment, restricted in segments:
        if restricted:
            if _restriction_verdict(segment, at, until) == "clear":
                guidance.append(segment)
                continue
        elif read_closure(segment, at, holiday).value is False:
            continue
        left.append(segment)
    return ClosureRead(None if left else False, "; ".join(left) if left else None,
                       "visit_restriction", guidance=tuple(guidance))

