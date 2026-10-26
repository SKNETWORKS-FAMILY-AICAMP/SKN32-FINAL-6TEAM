"""Rule parser for hours/closure sentences printed on an official page body (no model).

Only a fixed grammar is read: a schedule label (운영시간 · 관람시간 …) followed by optional weekday
spec and ``HH:MM~HH:MM`` (or ``H시~H시``), and a closure label (휴관일 · 휴무일 …) with ``매주 X요일``
or a label-adjacent weekday. Anything conditional (season/month, holidays-only, nth week, break or
last-entry times, reservations) is dropped; two different values for the same days make the
whole page ``ambiguous`` and the caller keeps it unknown. Every returned quote is a verbatim
substring of the returned visible text, so the caller can re-check its position server-side.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_DAY_CHAR = dict(zip("월화수목금토일", DAYS, strict=True))
_BLOCK = {"p", "div", "br", "li", "tr", "td", "th", "dt", "dd", "h1", "h2", "h3", "h4", "h5",
          "h6", "section", "article", "table", "ul", "ol", "dl", "header", "footer", "title"}
_SKIP = {"script", "style", "noscript", "template", "svg"}
HOURS_LABEL = re.compile(r"(운영|관람|이용|개방|개관|영업)\s*시간")
CLOSED_LABEL = re.compile(r"(정기\s*)?(휴관|휴무|휴장)(일)?")
# Conditions this grammar cannot apply to a weekday: season/month, holidays, nth week, events.
_CONDITIONAL = re.compile(r"하절기|동절기|여름|겨울|\d{1,2}\s*월|공휴일|명절|설날|추석|둘째|넷째|첫째|셋째|"
                          r"다섯째|격주|경우|익일|다음\s*날|예약|행사|시즌|성수기|비수기|임시|단축|변경|연장|조정")
# A dated notice (「2026년 9월 3일 관람시간 단축 안내」) is about one day, never the weekly schedule.
_DATED = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일|20\d\d\s*[년.]|단축|변경|연장|조정|임시")
_EXCLUDE = re.compile(r"휴게|준비|점심|브레이크|break|입장\s*마감|매표\s*마감|마감|라스트|last", re.I)
_TIME = r"(오전|오후)?\s*(\d{1,2})\s*(?::\s*(\d{2})|시(?:\s*(\d{1,2})\s*분)?)"
_RANGE = re.compile(_TIME + r"\s*[~∼〜\-–—]\s*" + _TIME)
_DAYTOKEN = r"[월화수목금토일](?:요일)?"
_DAYRANGE = re.compile(r"(" + _DAYTOKEN + r")\s*[~∼〜\-–]\s*(" + _DAYTOKEN + r")")
_DAYLIST = re.compile(_DAYTOKEN + r"(?:\s*[·,、ㆍ]\s*" + _DAYTOKEN + r")*")
_WEEKEND_HOLIDAY = re.compile(r"(주말|토요일|일요일)\s*(?:및|·|ㆍ|,|/)?\s*공휴일")
# Anchor text of an official page link that leads to its visiting guide (link nomination only).
GUIDE_LINK = re.compile(r"(이용|관람|운영|방문|시설)\s*안내|(운영|관람|이용|개방|개관)\s*시간")
_ALLDAY = re.compile(r"24\s*시간|상시\s*개방")
_OPEN_ALL_YEAR = re.compile(r"연중\s*무휴")


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        if tag in _BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._anchor = []

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip:
            self.skip -= 1
        if tag in _BLOCK:
            self.parts.append("\n")
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._anchor).split())))
            self._href = None

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self._href is not None:
                self._anchor.append(data)


def visible(html: str) -> tuple[str, list[tuple[str, str]]]:
    """Visible text (one normalized line per block) and (href, anchor text) pairs."""
    parser = _Visible()
    parser.feed(html)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).split("\n"))
    return "\n".join(line for line in lines if line), parser.links


def _minutes(half, h, m, m2):
    hour, minute = int(h), int(m or m2 or 0)
    if half is not None and not 1 <= hour <= 12:
        return None
    if half == "오후" and hour < 12:
        hour += 12
    elif half == "오전" and hour == 12:
        hour = 0
    if hour > 24 or minute > 59 or (hour == 24 and minute):
        return None
    return f"{hour:02d}:{minute:02d}"


def _days_of(prefix: str) -> list[str] | None:
    """Weekdays named in the clause before a range; None = no weekday spec (unspecified)."""
    days: list[str] = []
    for word, value in (("평일", DAYS[:5]), ("주말", DAYS[5:]), ("매일", DAYS)):
        if word in prefix:
            days.extend(value)
    rest = prefix
    for m in _DAYRANGE.finditer(prefix):
        a, b = DAYS.index(_DAY_CHAR[m.group(1)[0]]), DAYS.index(_DAY_CHAR[m.group(2)[0]])
        days.extend(DAYS[a:b + 1] if a <= b else DAYS[a:] + DAYS[:b + 1])
        rest = rest.replace(m.group(0), " ")
    for m in _DAYLIST.finditer(rest):
        # A lone day char inside a word (e.g. 「일반」) is not a weekday: require 요일 or a list.
        token = m.group(0)
        if "요일" in token or re.search(r"[·,、ㆍ]", token):
            days.extend(_DAY_CHAR[c] for c in re.findall(r"([월화수목금토일])(?:요일)?", token))
    return sorted(set(days), key=DAYS.index) or None


def _segments(text: str, label: re.Pattern) -> list[str]:
    """Label line, plus the next line when the label line carries no value (table/dl layouts)."""
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        if not label.search(line):
            continue
        out.append(line)
        if label is HOURS_LABEL and not _RANGE.search(line) and not _ALLDAY.search(line) and i + 1 < len(lines):
            out.append(lines[i + 1])
        if label is CLOSED_LABEL and not re.search(_DAYTOKEN, line.split(label.search(line).group(0), 1)[1]) \
                and not _OPEN_ALL_YEAR.search(line) and i + 1 < len(lines):
            out.append(lines[i + 1])
    return out


def parse(text: str) -> dict:
    """{'hours': [...], 'closed': [...], 'open_all_year': bool, 'quotes': [...]} or {'ambiguous': reason}."""
    hours: dict[tuple[str, ...] | None, tuple[str, str]] = {}
    quotes: list[str] = []
    lines = text.split("\n")
    if any(HOURS_LABEL.search(line) and _DATED.search(line) for line in lines):
        return {"ambiguous": "dated_notice"}
    for seg in _segments(text, HOURS_LABEL):
        # 「주말·공휴일 10:00~17:00」: keep the weekend claim, never infer a holiday schedule.
        if _CONDITIONAL.search(_WEEKEND_HOLIDAY.sub(r"\1", seg)):
            # Seasonal/holiday-specific schedules cannot be pinned to a weekday by this grammar.
            if _RANGE.search(seg):
                return {"ambiguous": "conditional_hours"}
            continue
        start, used = 0, False
        for m in _RANGE.finditer(seg):
            prefix = seg[start:m.start()]
            start = m.end()
            if _EXCLUDE.search(prefix[-12:]):
                continue
            a, b = _minutes(*m.group(1, 2, 3, 4)), _minutes(*m.group(5, 6, 7, 8))
            # 「오전 10시 ~ 4시」 or an overnight span is not a reading this grammar can confirm.
            if a is None or b is None or b <= a:
                return {"ambiguous": "invalid_time"}
            days = _days_of(_WEEKEND_HOLIDAY.sub(r"\1", HOURS_LABEL.sub(" ", prefix)))
            key = tuple(days) if days else None
            if key in hours and hours[key] != (a, b):
                return {"ambiguous": "conflicting_hours"}
            hours[key] = (a, b)
            used = True
        if not used and _ALLDAY.search(seg):
            if None in hours and hours[None] != ("00:00", "24:00"):
                return {"ambiguous": "conflicting_hours"}
            hours[None] = ("00:00", "24:00")
            used = True
        if used and seg not in quotes:
            quotes.append(seg)
    covered = [d for key in hours if key for d in key]
    if len(covered) != len(set(covered)):
        return {"ambiguous": "overlapping_days"}
    closed: list[str] = []
    open_all_year = False
    for seg in _segments(text, CLOSED_LABEL):
        found = []
        for m in re.finditer(r"매주\s*(" + _DAYTOKEN + r"(?:\s*(?:[~∼〜\-–·,、ㆍ]|및)\s*" + _DAYTOKEN + r")*)", seg):
            found.extend(_days_of(m.group(1).replace("및", "·")) or [])
        label = CLOSED_LABEL.search(seg)
        if label and not found:
            tail = seg[label.end():]
            m = re.match(r"\s*[:：]?\s*(" + _DAYTOKEN + r"(?:\s*[~∼〜\-–·,、ㆍ]\s*" + _DAYTOKEN + r")*)", tail)
            if m and not re.match(r"\s*(이|인|일)\s*경우", tail[m.end():]):
                found.extend(_days_of(m.group(1)) or [])
        if _OPEN_ALL_YEAR.search(seg):
            open_all_year = True
        if found or _OPEN_ALL_YEAR.search(seg):
            closed.extend(found)
            if seg not in quotes:
                quotes.append(seg)
    closed = sorted(set(closed), key=DAYS.index)
    if open_all_year and closed:
        return {"ambiguous": "closed_conflict"}
    # A weekly closure narrows a group (평일 · 주말 · 화~일); a single named day that is both
    # open and closed is a real conflict.
    narrowed = {}
    for key, value in hours.items():
        if key and len(key) == 1 and key[0] in closed:
            return {"ambiguous": "closed_conflict"}
        keep = tuple(d for d in key if d not in closed) if key else None
        if key and not keep:
            continue
        if keep in narrowed and narrowed[keep] != value:
            return {"ambiguous": "conflicting_hours"}
        narrowed[keep] = value
    hours = narrowed
    if not hours:
        return {"ambiguous": "no_hours"}
    if None in hours and len(hours) > 1:
        # 「10:00~17:00」 next to 「평일 10시-16시」: which days the bare range covers is unknown.
        return {"ambiguous": "mixed_day_scope"}
    return {
        "hours": [{"days": list(key) if key else None, "open": a, "close": b}
                  for key, (a, b) in sorted(hours.items(), key=lambda kv: (kv[0] is not None, kv[0] or ()))],
        "closed": closed,
        "open_all_year": open_all_year,
        "quotes": quotes,
    }
