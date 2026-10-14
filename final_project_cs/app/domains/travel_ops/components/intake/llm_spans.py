# -*- coding: utf-8 -*-
"""남은 줄 — 모델이 **어디가 무엇인지만** 가리키고, 값은 서버가 원문에서 잘라 낸다. `[2026-09-27]` 설계서 §3-4

★규칙이 못 읽은 줄(「점심은 토속촌에서 먹을래」 「저녁엔 광장시장 가 보고 싶어」)만 모델에 보낸다.
★모델이 내는 것: `{"spans": [{"line": 줄 번호, "quote": 원문 조각, "role": 역할}]}`.
  ☆설계서 §3-4 는 (시작, 끝) **글자 위치**를 받으라 했다. 언어 모델은 글자 수 세기가 약해서, 여기서는 **원문 조각을
    그대로 인용**하게 하고 서버가 그 조각을 원문에서 찾는다. ★원문에 **글자 그대로 없는** 인용은 버린다 — 실측
    (triPilot : RAG, 2026-09-26)에서 모델이 「토속촌」을 「토속툰」으로 바꿔 적었다. 그런 값은 원문에 없으니 들어오지 못한다.
★시각·날짜는 인용 조각을 **규칙으로 다시 읽어** 값을 만든다 — 모델이 정규화한 값을 쓰지 않는다.
★모델 호출: gemma4:12b · think=false · 온도 0 · JSON(설계서 §3-4). 실패하면 이 단계만 건너뛰고 그 줄은 남은 줄로 둔다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .rules import TIME, Claim, Span, _date_in, _hhmm, _narrow, meal_mention
from .span_segments import split_segments

ROLES = ("place", "time", "date", "meal", "booking_no", "party", "plan_request", "ignore")

SYSTEM = (
    "You label parts of a traveller's itinerary lines (usually Korean). You get numbered lines. "
    "For each useful part, return the line number, the EXACT substring copied character-for-character from that line "
    "(never fix typos, never translate, never add words), and its role.\n"
    "Roles: place (a place/shop/sight the traveller will visit), time (a clock time or time of day), "
    "date (a date or relative day such as 내일), time also includes relative-now expressions such as 지금/당장/현재, "
    "meal (breakfast/lunch/dinner word), booking_no (reservation number), "
    "party (number of people), plan_request (they ask us to make a plan, e.g. '일정 짜 줘'), ignore.\n"
    'Return JSON only: {"spans": [{"line": 1, "quote": "...", "role": "place"}]}. '
    "If nothing is useful, return {\"spans\": []}.")



@dataclass
class SpanItem:
    """남은 줄의 장소 하나에서 모은 항목 — 규칙 항목과 같은 모양으로 합친다. ★한 줄에 장소가 여럿이면 항목도 여럿이다."""

    line: int
    title: Span | None
    start: str | None
    meal: str | None
    date: str | None
    time_claim: Claim | None = None
    segment: Span | None = None


def label_lines(lines: list[str], unread: list[int], chat: Any, *, now: datetime | None = None) -> tuple[list[Claim], list[SpanItem], dict[str, Any]]:
    """(claims, 항목, 보고). ★모델이 가리킨 조각 중 원문에 그대로 있는 것만 받는다.

    ★`[2026-10-14]` 한 줄을 장소마다 나눈다 — 줄마다 항목 하나로 묶었더니 「서촌 … 저녁 무렵 남산타워」에서 남산타워가 빠지고
      「저녁」이 서촌에 붙었다(테스트 서버 접수 87858b77). 시각 · 날짜 · 끼니는 같은 원문 구간의 장소에 붙인다.
    ★끼니는 모델이 가리키지 않아도 **그 장소 몫의 원문**에서 규칙으로 다시 본다(`rules.meal_mention`) — 같은 접수에서 모델이
      「점심은 통인시장 근처에서」의 「점심」을 가리키지 않아 식사가 활동이 됐다."""
    report: dict[str, Any] = {"asked_lines": len(unread), "spans": 0, "accepted": 0, "rejected": [], "plan_request": False}
    if not unread or chat is None:
        return [], [], report
    user = "\n".join(f"{n}: {lines[n - 1]}" for n in unread)
    raw = chat.json(SYSTEM, user)
    spans = raw.get("spans") if isinstance(raw, dict) else None
    accepted: dict[int, list[tuple[int, int, str, str]]] = {}
    cursors: dict[tuple[int, str, str], int] = {}
    for entry in spans or []:
        report["spans"] += 1
        try:
            number, quote, role = int(entry["line"]), str(entry["quote"]), str(entry["role"])
        except (KeyError, TypeError, ValueError):
            report["rejected"].append({"why": "모양이 다르다", "entry": str(entry)[:80]})
            continue
        if number not in unread or role not in ROLES or not quote.strip():
            report["rejected"].append({"why": "남은 줄이 아니거나 모르는 역할", "line": number, "role": role})
            continue
        key = number, role, quote
        at = lines[number - 1].find(quote, cursors.get(key, 0))
        if at < 0:
            # ★원문에 글자 그대로 없다 — 모델이 바꿔 적었다. 받지 않는다
            report["rejected"].append({"why": "원문에 없는 인용", "line": number, "quote": quote})
            continue
        cursors[key] = at + len(quote)
        if role == "plan_request":
            report["plan_request"] = True
        accepted.setdefault(number, []).append((at, at + len(quote), quote, role))
        report["accepted"] += 1
    claims: list[Claim] = []
    items: list[SpanItem] = []
    for number in sorted(accepted):
        text = lines[number - 1]
        mine = _line_items(number, text, accepted[number])
        for start, end, quote, role in sorted(accepted[number]):
            if role in ("place", "plan_request", "ignore", "booking_no", "party") or not mine:
                continue
            item = _owner(mine, start)
            if role == "time" and item.time_claim is None:
                claim = _time_claim(number, start, quote, now, item)
                if claim is not None:
                    item.time_claim = claim
                    claims.append(claim)
            elif role == "date":
                value, match = _date_in(quote)
                if match:
                    item.date = value
            # 끼니는 _line_items가 항목의 전체 구간과 장소 위치로 판정한다.
            # 모델이 따로 낸 meal 조각으로 다른 항목의 판정을 덮지 않는다.
        items += mine
    return claims, items, report


def _line_items(number: int, text: str, spans: list[tuple[int, int, str, str]]) -> list[SpanItem]:
    """줄의 장소 조각마다 항목 하나 — 겹치지 않는 원문 구간을 보존한다."""
    places: list[tuple[int, int]] = []
    for start, end, _, role in sorted(spans):
        if role != "place":
            continue
        s, e = _narrow(text, start, end)
        if e > s and not any(s < pe and ps < e for ps, pe in places):    # 겹치는 조각은 앞 것만
            places.append((s, e))
    # 모델이 끼니 말을 **시각**(숫자 없는 때)으로 짚었으면 그 판단을 따른다 — 「저녁엔 광장시장 가 보고 싶어」는 저녁에 가는 것이다.
    # 짚지 않았거나 끼니로 짚었으면 규칙이 정한다(「점심은 통인시장 근처에서」 — 모델이 아무것도 안 짚었다).
    as_time = [(start, end) for start, end, quote, role in spans if role == "time" and not TIME.search(quote)]
    items: list[SpanItem] = []
    for (s, e), (left, right) in zip(places, split_segments(text, places)):
        mention = meal_mention(text[left:right], place_start=s - left)
        meal = mention[1] if mention and mention[2] else None
        if meal and any(left <= start < right and mention[0] in text[start:end] for start, end in as_time):
            meal = None
        items.append(SpanItem(number, Span(number, s, e, text[s:e]), None, meal, None,
                              segment=Span(number, left, right, text[left:right])))
    return items


def _owner(items: list[SpanItem], at: int) -> SpanItem:
    """조각이 포함된 원문 구간의 장소. 장소 뒤의 「지금」도 그 장소에 붙는다."""
    return next((item for item in items if item.segment.start <= at < item.segment.end), items[-1])


def _time_claim(number: int, at: int, quote: str, now: datetime | None, item: SpanItem) -> Claim | None:
    match = TIME.search(quote)
    if match:
        value, review, note = _hhmm(match)
        if value:
            item.start = value
            return Claim("", value, Span(number, at + match.start(), at + match.end(), match.group(0)),
                         needs_review=review, note=note, method="llm_span")
    elif now is not None and any(word in quote for word in ("지금", "현재", "당장")):
        from zoneinfo import ZoneInfo
        instant = now.astimezone(ZoneInfo("Asia/Seoul"))
        value = instant.strftime("%H:%M")
        item.start = value
        item.date = instant.date().isoformat()
        return Claim("", value, Span(number, at, at + len(quote), quote), note="접수 시각 기준 현재 시각",
                     method="llm_span")
    return None


def make_labeler(chat: Any) -> Callable[[list[str], list[int]], tuple[list[Claim], list[SpanItem], dict[str, Any]]]:
    return lambda lines, unread: label_lines(lines, unread, chat)


__all__ = ["ROLES", "SYSTEM", "SpanItem", "label_lines", "make_labeler"]
