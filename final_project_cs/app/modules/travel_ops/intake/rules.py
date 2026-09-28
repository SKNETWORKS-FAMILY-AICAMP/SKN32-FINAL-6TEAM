# -*- coding: utf-8 -*-
"""규칙 읽기 — 줄 번호가 붙은 글에서 **규칙으로 읽히는 것만** 읽고, 나머지는 「남은 줄」로 돌린다. `[2026-09-27]`

설계서 §3-3. 프런트 데모 파서(`frontend/apps/web/src/lib/demo/parse-plan.ts`)의 규칙을 옮기되
**거절하지 않는다** — 데모 파서는 형식이 조금만 달라도 오류를 냈다. 여기서는 읽은 줄 / 남은 줄로 나눈다.

읽는 것
    일차 머리줄    「1일차」「DAY 1」「첫째 날」(+ 같은 줄의 날짜)
    날짜           「2026-09-15」「9월 15일」「9/15」 — 해가 없으면 해는 비운다(날짜 해석은 2주차)
    시각 줄        「09:00 경복궁」「오전 9시 경복궁」「9시 반에 경복궁」「14시~16시 한강 카약」
                   ★한 줄에 시각이 여럿이면 시각마다 나눈다 — 채팅처럼 「9시에 경복궁, 12시에 토속촌」
    끝 시각        「09:00~11:00」「09:00-11:00」「11:00 종료」「~11시」
    예약           「예약번호 KY-20931」·「예약 완료」「예약 없음」
    여행 전체      「2박3일」「4명」「넷이서」
    화살표 나열    「경복궁 → 광장시장 → 명동」(시각 없는 순서 — 배치는 뒤 단계가 한다)

★**값은 원문에서 잘라 낸다.** 이름·예약번호는 원문의 (줄, 시작, 끝) 조각 그대로다 — 바꿔 적지 않는다.
  시각은 원문 조각을 `HH:MM` 으로 **정규화**하되 원문 조각을 근거로 같이 둔다.
★모르는 것은 채우지 않는다. 「3시」처럼 오전·오후가 갈리지 않으면 값을 내되 `needs_review` 로 표시한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

# ── 패턴 ─────────────────────────────────────────────────────────
_KO_ORDINAL = {"첫": 1, "첫째": 1, "둘째": 2, "두째": 2, "셋째": 3, "세째": 3, "넷째": 4, "네째": 4,
               "다섯째": 5, "여섯째": 6, "일곱째": 7}
_KO_COUNT = {"혼자": 1, "둘이서": 2, "둘이": 2, "셋이서": 3, "셋이": 3, "넷이서": 4, "넷이": 4}

DAY_HEADING = re.compile(
    r"^\s*[\[(【]?\s*(?:(?P<n>\d{1,2})\s*일\s*차|day\s*(?P<d>\d{1,2})|(?P<ko>첫째|첫|둘째|두째|셋째|세째|넷째|네째|"
    r"다섯째|여섯째|일곱째)\s*(?:날|일))", re.IGNORECASE)
ISO_DATE = re.compile(r"(?P<y>20\d{2})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})")
KO_DATE = re.compile(r"(?:(?P<y>20\d{2})\s*년\s*)?(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일")
SLASH_DATE = re.compile(r"(?<![\d:])(?P<m>\d{1,2})/(?P<d>\d{1,2})(?![\d:/])")

# 시각: 「09:00」 또는 「(오전|오후|아침|점심|저녁|밤|새벽) 9시 (30분|반)」
_TIME = (r"(?:(?P<ampm>오전|오후|아침|점심|저녁|밤|새벽)\s*)?"
         r"(?:(?P<h>\d{1,2}):(?P<min>\d{2})|(?P<kh>\d{1,2})\s*시(?:\s*(?P<km>\d{1,2})\s*분|\s*(?P<half>반))?)")
TIME = re.compile(_TIME)
RANGE_SEP = re.compile(r"^\s*(?:~|-|–|—|부터|에서)\s*")
END_MARK = re.compile(r"^\s*(?:까지|종료|끝)")
BOOKING_NO = re.compile(r"(?:예약\s*번호|예약\s*No\.?|booking\s*(?:no|number|#)|confirmation\s*(?:no|number|#))"
                        r"\s*[:：#]?\s*(?P<no>[A-Za-z0-9][A-Za-z0-9-]{3,})", re.IGNORECASE)
BARE_BOOKING_NO = re.compile(r"(?<![A-Za-z0-9-])(?P<no>[A-Z]{2,4}-\d{3,})(?![A-Za-z0-9-])")
BOOKED = re.compile(r"예약\s*(?:있음|완료|확정|함|했)|\b(?:reserved|booked)\b", re.IGNORECASE)
NOT_BOOKED = re.compile(r"예약\s*(?:없이|없음|안\s*함)|미예약|\b(?:not\s+(?:booked|reserved)|walk[- ]in)\b",
                        re.IGNORECASE)
NIGHTS_DAYS = re.compile(r"(?P<n>\d{1,2})\s*박\s*(?P<d>\d{1,2})\s*일")
#: ☆2026-09-27 실제 화면 — 「19:00 명동난타극장」의 「00 명」을 인원 0명으로 읽어 등록이 422 로 막혔다.
#:  그래서 숫자 앞에 `:`·숫자가 오면 안 받고(시각), 0 은 안 받고, 「명·인」 뒤에 **다른 한글 음절**이 붙으면
#:  안 받는다(명동 · 인사동 · 인분). 뒷말 「이서 · 과 · 와 · 이 · 은 · 는 · 도 · 의 · 가족」은 받는다.
PARTY = re.compile(r"(?<![\d:])(?P<n>[1-9]\d?)\s*(?:명|인)(?=$|[^가-힣]|이서|이|과|와|은|는|도|의|가족)")
PARTY_KO = re.compile(r"(혼자|둘이서|둘이|셋이서|셋이|넷이서|넷이)")
ARROW = re.compile(r"\s*(?:→|->|⇒|>)\s*")

# 이름 조각을 좁히는 데 쓰는 것 — ★잘라 낼 뿐 바꾸지 않는다
_LEAD = re.compile(r"^[\s,.:·|/\-~에는은도]+")
#: 이름 뒤에 붙는 **말**(동사·식사·연결어) — 이것이 있을 때만 그 앞의 조사도 함께 자른다.
#: ☆`[2026-09-27]` 조사만 있어도 잘랐더니 「북촌한옥마을」이 「북촌한옥마」가 됐다 — 이름 끝 글자가 조사와 같다.
_WORDS = (r"(?:점심|저녁|아침|식사|밥|커피|쇼핑|구경|관람|체험|산책)?\s*"
          r"(?:가고|가기|가서|가요|가|방문|들르고|들러서|보고|먹고|먹기|먹어요|먹을|먹|하고|해요|하기|할|"
          r"예정|그다음|그리고|다음에)")
_TAIL_WORDS = re.compile(r"\s*(?:에서|에|은|는|을|를|으로|로)?\s*" + _WORDS + r"\s*$")
_TAIL_MEAL = re.compile(r"\s*(?:에서|에)\s*(?:점심|저녁|아침|식사|밥|커피)\s*$")
_TAIL_PUNCT = re.compile(r"[\s,.;·|/\-]+$")
#: 이름 뒤에 **띄어 쓴 끼니 말**(「토속촌삼계탕 점심」) — 이름에서 떼고 「식사 항목」 단서로 남긴다
_MEAL_SUFFIX = re.compile(r"\s+(?P<meal>아침|조식|점심|중식|저녁|석식|식사)\s*$")


@dataclass
class Span:
    """원문 조각 — ★모든 값의 근거. `line` 은 1부터."""

    line: int
    start: int
    end: int
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"line": self.line, "start": self.start, "end": self.end, "text": self.text}


@dataclass
class Claim:
    """값 하나 = 줄 하나(`intake_claims`). `method` 는 여기서 늘 `rule`."""

    field: str                     # 예: trip.party_size · items[3].starts_at
    value: Any
    span: Span
    needs_review: bool = False
    note: str | None = None
    method: str = "rule"

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "value": self.value, "method": self.method,
                "evidence": {"source": "text", **self.span.as_dict()},
                "needs_review": self.needs_review, "note": self.note}


@dataclass
class ReadItem:
    day: int | None                 # 몇째 날(머리줄에서) — 모르면 None
    date: str | None                # YYYY-MM-DD 또는 --MM-DD(해 모름) — 모르면 None
    start: str | None               # HH:MM
    end: str | None
    title: Span | None
    booking_no: Span | None = None
    booked: bool | None = None
    order_only: bool = False        # 화살표 나열 — 시각 없이 순서만


@dataclass
class ReadResult:
    lines: list[str]
    items: list[ReadItem] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    read_lines: set[int] = field(default_factory=set)
    party_size: int | None = None
    nights: int | None = None
    days: int | None = None

    @property
    def unread_lines(self) -> list[int]:
        """규칙이 못 읽은 줄(빈 줄 제외) — LLM 이 위치만 가리키는 단계(2주차)로 간다."""
        return [n for n, text in enumerate(self.lines, start=1) if text.strip() and n not in self.read_lines]


# ── 부품 ─────────────────────────────────────────────────────────
def _hhmm(match: re.Match) -> tuple[str, bool, str | None]:
    """시각 → (HH:MM, 확인 필요, 메모). ★오전·오후를 모르면 값은 내되 확인 필요로 둔다."""
    ampm = match.group("ampm")
    if match.group("h") is not None:
        hour, minute = int(match.group("h")), int(match.group("min"))
    else:
        hour = int(match.group("kh"))
        minute = 30 if match.group("half") else int(match.group("km") or 0)
    review, note = False, None
    if ampm in ("오후", "저녁", "밤") and hour < 12:
        hour += 12
    elif ampm == "점심" and hour < 6:
        hour += 12                              # 「점심 1시」 = 13시
    elif ampm is None and match.group("kh") is not None and 1 <= hour <= 6:
        review, note = True, "오전·오후가 적혀 있지 않다 — 적힌 숫자 그대로 두었다"
    if not (0 <= hour <= 24 and 0 <= minute < 60):
        return "", True, "시각 범위를 벗어난다"
    return f"{hour % 24:02d}:{minute:02d}", review, note


def _narrow(line: str, start: int, end: int) -> tuple[int, int]:
    """이름 조각의 앞뒤 군더더기(조사·동사·구두점)를 **잘라 낸다**. 바꾸지 않는다."""
    piece = line[start:end]
    lead = _LEAD.match(piece)
    if lead:
        start += lead.end()
    piece = line[start:end]
    while True:
        tail = _TAIL_PUNCT.search(piece) or _TAIL_WORDS.search(piece) or _TAIL_MEAL.search(piece)
        if not tail or tail.start() == len(piece) or tail.start() == 0:
            break
        end = start + tail.start()
        piece = line[start:end]
    return start, end


def _date_in(text: str) -> tuple[str | None, re.Match | None]:
    for pattern in (ISO_DATE, KO_DATE, SLASH_DATE):
        match = pattern.search(text)
        if match:
            year = match.groupdict().get("y")
            month, day = int(match.group("m")), int(match.group("d"))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            return (f"{year}-{month:02d}-{day:02d}" if year else f"--{month:02d}-{day:02d}"), match
    return None, None


# ── 본체 ─────────────────────────────────────────────────────────
def read_plan(text: str) -> ReadResult:
    lines = text.splitlines()
    result = ReadResult(lines=lines)
    day: int | None = None
    date: str | None = None
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if _trip_level(result, number, line) and not TIME.search(line) and not DAY_HEADING.match(line):
            result.read_lines.add(number)           # 여행 전체 정보(인원·박일)만 있는 줄

        heading = DAY_HEADING.match(line)
        date_value, date_match = _date_in(line)
        times = list(TIME.finditer(line))
        if heading or (date_match and not times):
            if heading:
                raw = heading.group("n") or heading.group("d")
                day = int(raw) if raw else _KO_ORDINAL.get(heading.group("ko"), None)
                result.claims.append(Claim(f"days[{day}].heading", day, Span(number, heading.start(),
                                                                                 heading.end(), heading.group(0).strip())))
            if date_match:
                date = date_value
                result.claims.append(Claim(f"days[{day or '?'}].date", date_value,
                                           Span(number, date_match.start(), date_match.end(), date_match.group(0)),
                                           needs_review=date_value.startswith("--"),
                                           note="해가 적혀 있지 않다" if date_value.startswith("--") else None))
            elif heading:
                date = None                     # 새 날인데 날짜가 없다 — 앞 날짜를 끌어 쓰지 않는다
            result.read_lines.add(number)
            if not times:
                # ★표 행 — 「1일차 | 2026-10-10 | 광장시장 빈대떡」(시각 칸이 빈 행). 머리줄·날짜 뒤에 제목이 더 있으면
                #   시각 없는 항목이다. ☆2026-09-28 평가셋: 이 행이 머리줄로 흡수돼 항목이 통째로 사라졌다
                rest = _table_rest(line, heading, date_match)
                if rest is not None:
                    _untimed_item(result, number, line, rest, day, date, note="표에서 시각 칸이 비어 있다")
                continue
        if times:
            _time_items(result, number, line, times, day, date)
            continue
        if ARROW.search(line) and len(ARROW.split(line.strip())) >= 2:
            _arrow_items(result, number, line, day, date)
    _sandwiched(result)
    return result


#: 문장으로 끝나는 줄 — 끼인 줄 규칙이 받지 않는다(모델에게 넘긴다). 「점심은 토속촌에서 먹을래」
_SENTENCE_END = re.compile(r"(요|다|래|자|까|죠|게|어|아|지|네|[?!.~])\s*$")
_PARTICLE = re.compile(r"(은|는|을|를|에서|으로|에게|한테)\s")


def _table_rest(line: str, heading, date_match) -> tuple[int, int] | None:
    """표 행에서 머리줄·날짜 칸을 뺀 나머지 제목의 (시작, 끝). 표 행이 아니거나 남는 글이 없으면 None."""
    if " | " not in line:
        return None
    cells, at = [], 0
    for cell in line.split("|"):
        start = line.index(cell, at)
        at = start + len(cell)
        stripped = cell.strip()
        if not stripped:
            continue
        s = start + cell.index(stripped)
        e = s + len(stripped)
        covered = any(m and m.start() <= s and e <= m.end() + 1 for m in (heading, date_match))
        if not covered:
            cells.append((s, e))
    if not cells:
        return None
    s, e = cells[0]
    return (s, e) if re.search(r"[가-힣A-Za-z]", line[s:e]) else None


def _untimed_item(result: ReadResult, number: int, line: str, span: tuple[int, int], day, date, *, note: str) -> None:
    s, e = _narrow(line, span[0], span[1])
    meal = _MEAL_SUFFIX.search(line[s:e])
    position = len(result.items)
    if meal and meal.start() > 0:
        m0, m1 = s + meal.start("meal"), s + meal.end("meal")
        result.claims.append(Claim(f"items[{position}].kind", "dining", Span(number, m0, m1, line[m0:m1]),
                                   note="이름 뒤의 끼니 말"))
        e = s + meal.start()
    if e <= s:
        return
    item = ReadItem(day, date, None, None, Span(number, s, e, line[s:e]))
    result.items.append(item)
    result.claims.append(Claim(f"items[{position}].title", line[s:e], item.title, note=note))
    booking = BOOKING_NO.search(line)
    if booking:
        b0, b1 = booking.start("no"), booking.end("no")
        item.booking_no = Span(number, b0, b1, line[b0:b1])
        result.claims.append(Claim(f"items[{position}].booking_no", line[b0:b1], item.booking_no))
    result.read_lines.add(number)


def _sandwiched(result: ReadResult) -> None:
    """못 읽은 짧은 줄의 **앞뒤가 모두 읽은 일정 줄**이면 시각 없는 항목이다(「09:30 경복궁 / 광장시장 빈대떡 /
    15:00 인사동」). 문장(「~해요」)·조사가 붙은 말은 받지 않는다 — 그런 줄은 모델이 가리킨다.
    ☆2026-09-28 평가셋: 시각 없는 줄을 모델이 가리키지 않아 항목이 빠졌다(글자 PDF)."""
    item_lines = {it.title.line for it in result.items if it.title}
    heading_lines = {c.span.line for c in result.claims if c.field.startswith("days[")}
    nonblank = [n for n, line in enumerate(result.lines, start=1) if line.strip()]
    marks: list[tuple[int, int | None, str | None]] = []
    for claim in result.claims:
        if claim.field.startswith("days[") and claim.field.endswith(".heading"):
            marks.append((claim.span.line, claim.value, None))
        elif claim.field.startswith("days[") and claim.field.endswith(".date"):
            marks.append((claim.span.line, None, claim.value))
    for i, number in enumerate(nonblank):
        if number in result.read_lines:
            continue
        line = result.lines[number - 1].strip()
        before = nonblank[i - 1] if i > 0 else None
        after = nonblank[i + 1] if i + 1 < len(nonblank) else None
        if before not in item_lines or not (after in item_lines or after in heading_lines or after is None):
            continue
        if len(line) > 30 or _SENTENCE_END.search(line) or _PARTICLE.search(line + " ") or not re.search(r"[가-힣A-Za-z]", line):
            continue
        day = date = None
        for mark_line, mark_day, mark_date in sorted(marks, key=lambda m: m[0]):
            if mark_line > number:
                break
            if mark_day is not None:
                day, date = mark_day, None
            if mark_date is not None:
                date = mark_date
        raw = result.lines[number - 1]
        start = raw.index(line)
        _untimed_item(result, number, raw, (start, start + len(line)), day, date, note="시각이 없는 줄 — 앞뒤 일정 사이")


def _trip_level(result: ReadResult, number: int, line: str) -> bool:
    """여행 전체 정보를 읽었으면 True."""
    before = len(result.claims)
    nd = NIGHTS_DAYS.search(line)
    if nd and result.nights is None:
        result.nights, result.days = int(nd.group("n")), int(nd.group("d"))
        span = Span(number, nd.start(), nd.end(), nd.group(0))
        result.claims.append(Claim("trip.nights", result.nights, span))
        result.claims.append(Claim("trip.days", result.days, span))
    party = PARTY.search(line)
    if party and result.party_size is None and not TIME.search(line[party.start():party.end()]):
        result.party_size = int(party.group("n"))
        result.claims.append(Claim("trip.party_size", result.party_size,
                                   Span(number, party.start(), party.end(), party.group(0))))
    else:
        ko = PARTY_KO.search(line)
        if ko and result.party_size is None:
            result.party_size = _KO_COUNT[ko.group(1)]
            result.claims.append(Claim("trip.party_size", result.party_size,
                                       Span(number, ko.start(), ko.end(), ko.group(0))))
    return len(result.claims) > before


def _time_items(result: ReadResult, number: int, line: str, times: list[re.Match],
                day: int | None, date: str | None) -> None:
    """한 줄의 시각들 — 「시작~끝」 짝은 하나로, 나머지는 시각마다 항목 하나."""
    index = 0
    produced = 0
    while index < len(times):
        start_match = times[index]
        end_match = None
        after = line[start_match.end():]
        nxt = times[index + 1] if index + 1 < len(times) else None
        if nxt is not None and RANGE_SEP.match(line[start_match.end():nxt.start()]) \
                and not line[start_match.end():nxt.start()].strip(" ~-–—부터에서"):
            end_match, index = nxt, index + 1
        elif nxt is None and re.match(r"^\s*~\s*$", after):
            pass
        body_start = (end_match or start_match).end()
        following = times[index + 1] if index + 1 < len(times) else None
        body_end = following.start() if following is not None else len(line)
        # 「11:00 종료」처럼 끝을 말하는 시각은 항목이 아니다 — 앞 항목의 끝
        if END_MARK.match(line[start_match.end():]) and result.items and result.items[-1].end is None \
                and produced > 0:
            value, _, _ = _hhmm(start_match)
            result.items[-1].end = value
            index += 1
            continue
        start_value, review, note = _hhmm(start_match)
        if not start_value:
            index += 1
            continue
        position = len(result.items)
        item = ReadItem(day=day, date=date, start=start_value, end=None, title=None)
        result.claims.append(Claim(f"items[{position}].starts_at", start_value,
                                   Span(number, start_match.start(), start_match.end(), start_match.group(0)),
                                   needs_review=review, note=note))
        if end_match is not None:
            end_value, end_review, end_note = _hhmm(end_match)
            if end_value:
                item.end = end_value
                result.claims.append(Claim(f"items[{position}].ends_at", end_value,
                                           Span(number, end_match.start(), end_match.end(), end_match.group(0)),
                                           needs_review=end_review, note=end_note))
        segment = line[body_start:body_end]
        booking = BOOKING_NO.search(segment) or BARE_BOOKING_NO.search(segment)
        title_end = body_start + (booking.start() if booking else len(segment))
        # 끝 표시(「까지」「종료」)와 이름 사이의 괄호 설명은 이름에서 뺀다
        # ★표 행(「09:00 | 경복궁」)처럼 **앞머리의** 구분자는 건너뛰고 찾는다 — 전에는 그것을 설명의 시작으로 보고
        #   이름을 통째로 잘랐다(docx·xlsx 시험에서 찾았다)
        lead = _LEAD.match(line[body_start:title_end])
        name_start = body_start + (lead.end() if lead else 0)
        cut = re.search(r"[(\[（【]|\s[·|]\s", line[name_start:title_end])
        if cut:
            title_end = name_start + cut.start()
        s, e = _narrow(line, body_start, title_end)
        meal = _MEAL_SUFFIX.search(line[s:e])
        if meal and meal.start() > 0:
            m0, m1 = s + meal.start("meal"), s + meal.end("meal")
            result.claims.append(Claim(f"items[{position}].kind", "dining", Span(number, m0, m1, line[m0:m1]),
                                       note="이름 뒤의 끼니 말"))
            e = s + meal.start()
        if e > s:
            item.title = Span(number, s, e, line[s:e])
            result.claims.append(Claim(f"items[{position}].title", line[s:e], item.title))
        if booking:
            b0 = body_start + booking.start("no")
            b1 = body_start + booking.end("no")
            item.booking_no = Span(number, b0, b1, line[b0:b1])
            item.booked = True
            result.claims.append(Claim(f"items[{position}].booking_no", line[b0:b1], item.booking_no))
        elif NOT_BOOKED.search(segment):
            item.booked = False
        elif BOOKED.search(segment):
            item.booked = True
        if item.booked is not None:
            marker = (NOT_BOOKED if item.booked is False else BOOKED).search(segment)
            if marker:
                result.claims.append(Claim(f"items[{position}].booked", item.booked,
                                           Span(number, body_start + marker.start(), body_start + marker.end(),
                                                marker.group(0))))
        result.items.append(item)
        produced += 1
        index += 1
    if produced:
        result.read_lines.add(number)


def _arrow_items(result: ReadResult, number: int, line: str, day: int | None, date: str | None) -> None:
    cursor = 0
    for piece in ARROW.split(line):
        start = line.index(piece, cursor) if piece else cursor
        end = start + len(piece)
        cursor = end
        s, e = _narrow(line, start, end)
        if e <= s:
            continue
        position = len(result.items)
        span = Span(number, s, e, line[s:e])
        result.items.append(ReadItem(day=day, date=date, start=None, end=None, title=span, order_only=True))
        result.claims.append(Claim(f"items[{position}].title", line[s:e], span, needs_review=True,
                                   note="시각이 없다 — 순서만 적혀 있다"))
    result.read_lines.add(number)


__all__ = ["Claim", "ReadItem", "ReadResult", "Span", "read_plan"]
