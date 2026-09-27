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
from typing import Any, Callable

from .rules import TIME, Claim, Span, _date_in, _hhmm, _narrow

ROLES = ("place", "time", "date", "meal", "booking_no", "party", "plan_request", "ignore")

SYSTEM = (
    "You label parts of a traveller's itinerary lines (usually Korean). You get numbered lines. "
    "For each useful part, return the line number, the EXACT substring copied character-for-character from that line "
    "(never fix typos, never translate, never add words), and its role.\n"
    "Roles: place (a place/shop/sight the traveller will visit), time (a clock time or time of day), "
    "date (a date or relative day such as 내일), meal (breakfast/lunch/dinner word), booking_no (reservation number), "
    "party (number of people), plan_request (they ask us to make a plan, e.g. '일정 짜 줘'), ignore.\n"
    'Return JSON only: {"spans": [{"line": 1, "quote": "...", "role": "place"}]}. '
    "If nothing is useful, return {\"spans\": []}.")

_MEAL = {"아침": "breakfast", "조식": "breakfast", "점심": "lunch", "중식": "lunch", "저녁": "dinner", "석식": "dinner"}


@dataclass
class SpanItem:
    """남은 줄 하나에서 모은 항목 — 규칙 항목과 같은 모양으로 합친다."""

    line: int
    title: Span | None
    start: str | None
    meal: str | None
    date: str | None


def label_lines(lines: list[str], unread: list[int], chat: Any) -> tuple[list[Claim], list[SpanItem], dict[str, Any]]:
    """(claims, 항목, 보고). ★모델이 가리킨 조각 중 원문에 그대로 있는 것만 받는다."""
    report: dict[str, Any] = {"asked_lines": len(unread), "spans": 0, "accepted": 0, "rejected": [], "plan_request": False}
    if not unread or chat is None:
        return [], [], report
    user = "\n".join(f"{n}: {lines[n - 1]}" for n in unread)
    raw = chat.json(SYSTEM, user)
    spans = raw.get("spans") if isinstance(raw, dict) else None
    claims: list[Claim] = []
    by_line: dict[int, SpanItem] = {}
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
        text = lines[number - 1]
        at = text.find(quote)
        if at < 0:
            # ★원문에 글자 그대로 없다 — 모델이 바꿔 적었다. 받지 않는다
            report["rejected"].append({"why": "원문에 없는 인용", "line": number, "quote": quote})
            continue
        start, end = at, at + len(quote)
        item = by_line.setdefault(number, SpanItem(number, None, None, None, None))
        if role == "plan_request":
            report["plan_request"] = True
        elif role == "place":
            s, e = _narrow(text, start, end)
            if e > s and item.title is None:
                item.title = Span(number, s, e, text[s:e])
        elif role == "time":
            match = TIME.search(quote)
            if match:
                value, review, note = _hhmm(match)
                if value:
                    item.start = value
                    claims.append(Claim("", value, Span(number, start + match.start(), start + match.end(),
                                                        match.group(0)), needs_review=review, note=note,
                                        method="llm_span"))
        elif role == "date":
            value, match = _date_in(quote)
            if match:
                item.date = value
        elif role == "meal":
            for word, meal in _MEAL.items():
                if word in quote:
                    item.meal = meal
                    break
        report["accepted"] += 1
    items = [item for item in by_line.values() if item.title is not None]
    return claims, items, report


def make_labeler(chat: Any) -> Callable[[list[str], list[int]], tuple[list[Claim], list[SpanItem], dict[str, Any]]]:
    return lambda lines, unread: label_lines(lines, unread, chat)


__all__ = ["ROLES", "SYSTEM", "SpanItem", "label_lines", "make_labeler"]
