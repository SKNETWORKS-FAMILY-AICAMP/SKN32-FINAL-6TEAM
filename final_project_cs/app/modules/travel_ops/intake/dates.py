# -*- coding: utf-8 -*-
"""날짜 해석 — 항목마다 실제 날짜(YYYY-MM-DD)를 정한다. `[2026-09-27]` 설계서 §3-5

★우선순위(높은 것이 이긴다)
    ① 고객이 고친 값              (확인 화면 — `method=customer`)
    ② 예약서                      (2주차 뒤: 예약 문서 연결 — 지금은 없다)
    ③ 본문에 적힌 날짜             「2026-10-15」 · 해 없는 「10월 15일」은 **오늘(서울) 기준 다가오는 날**로 해를 채운다
    ④ 같은 접수의 시작일 + 일차    「2일차」 = 첫날 + 1
    ⑤ 세션 출발일                 (웹이 따로 받은 출발일 — 있으면)
    ⑥ 상대 날짜                   「오늘」「내일」「모레」 — 오늘(서울) 기준
  다 없으면 **「첫날 날짜」 하나만** 묻는다(`ask_first_day`) — 날짜를 지어내지 않는다.

★해를 채운 것·일차로 계산한 것은 값과 함께 **어떻게 정했는지**(`how`)를 남긴다 — 확인 화면이 배지로 보인다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any

RELATIVE = {"오늘": 0, "내일": 1, "모레": 2, "글피": 3}
_RELATIVE = re.compile(r"(오늘|내일|모레|글피)")
#: 일차 머리줄 — 상대 날짜를 찾으러 올라갈 때 여기서 멈춘다(`rules.DAY_HEADING` 과 같은 모양의 앞머리)
_HEADING = re.compile(r"^\s*(?:\d+\s*일\s*차|DAY\s*\d+|첫째\s*날|둘째\s*날|셋째\s*날)", re.IGNORECASE)


@dataclass
class DayDate:
    value: str | None          # YYYY-MM-DD, 모르면 None
    how: str                   # written · year_filled · day_offset · departure · relative · unknown
    needs_review: bool
    note: str | None = None


def resolve_dates(items: list[dict[str, Any]], *, today: date, departure: date | None = None,
                  lines: list[str] | None = None) -> tuple[list[DayDate], bool]:
    """`items` = [{"day": 몇째 날|None, "date": "YYYY-MM-DD"|"--MM-DD"|None, "line": 줄 번호}].
    (항목마다 날짜, 첫날을 물어야 하나)."""
    lines = lines or []
    first = _first_day(items, today=today, departure=departure, lines=lines)
    out: list[DayDate] = []
    for item in items:
        written = item.get("date")
        if written and not written.startswith("--"):
            out.append(DayDate(written, "written", False))
            continue
        if written:
            filled = _fill_year(written, today)
            out.append(DayDate(filled.isoformat(), "year_filled", True,
                               f"해가 적혀 있지 않아 오늘 기준 다가오는 날로 두었다({filled.year}년)"))
            continue
        relative = _relative_on_line(lines, item.get("line"))
        if relative is not None:
            value = today + timedelta(days=relative[1])
            out.append(DayDate(value.isoformat(), "relative", False, f"「{relative[0]}」 — 오늘 기준"))
            continue
        if first is not None and item.get("day"):
            value = first[0] + timedelta(days=int(item["day"]) - 1)
            out.append(DayDate(value.isoformat(), "day_offset", first[1],
                               f"첫날({first[0].isoformat()}) + {int(item['day']) - 1}일"))
            continue
        if first is not None:
            out.append(DayDate(first[0].isoformat(), "day_offset", True, "일차가 없어 첫날로 두었다"))
            continue
        out.append(DayDate(None, "unknown", True, "날짜를 알 수 없다"))
    ask = any(d.value is None for d in out)
    return out, ask


def _first_day(items, *, today: date, departure: date | None, lines: list[str]) -> tuple[date, bool] | None:
    """(첫날, 확인 필요). ★본문의 날짜가 있으면 그것에서 거꾸로 첫날을 계산한다(「2일차 10월 16일」 → 10월 15일)."""
    for item in items:
        written, day = item.get("date"), item.get("day")
        if not written:
            continue
        known = date.fromisoformat(written) if not written.startswith("--") else _fill_year(written, today)
        offset = (int(day) - 1) if day else 0
        return known - timedelta(days=offset), written.startswith("--")
    if departure is not None:
        return departure, False
    for item in items:
        relative = _relative_on_line(lines, item.get("line"))
        if relative is not None:
            offset = (int(item["day"]) - 1) if item.get("day") else 0
            return today + timedelta(days=relative[1] - offset), False
    return None


def _fill_year(month_day: str, today: date) -> date:
    """「--10-15」 → 오늘 이후 가장 가까운 그 날(오늘 포함)."""
    month, day = int(month_day[2:4]), int(month_day[5:7])
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return date(today.year + 1, month, min(day, 28))


def _relative_on_line(lines: list[str], line_no: int | None) -> tuple[str, int] | None:
    """그 줄에 상대 날짜가 있으면 그것, 없으면 **그 줄이 속한 일차 머리줄**(「1일차 · 내일」)에서 찾는다.
    ☆2026-09-28 평가셋: 「내일」이 머리줄에만 있어 그날 항목 셋의 날짜를 못 정했다."""
    if not line_no or line_no > len(lines):
        return None
    match = _RELATIVE.search(lines[line_no - 1])
    if match:
        return match.group(1), RELATIVE[match.group(1)]
    for back in range(line_no - 1, 0, -1):
        text = lines[back - 1]
        if _HEADING.match(text):
            found = _RELATIVE.search(text)
            return (found.group(1), RELATIVE[found.group(1)]) if found else None
    return None


__all__ = ["DayDate", "RELATIVE", "resolve_dates"]
