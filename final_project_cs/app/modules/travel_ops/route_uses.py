# -*- coding: utf-8 -*-
"""`routes{<키>}.options[].uses` 표기 검사. `[2026-09-23]`

★★**왜 검사하나.** `uses` 는 감시 루프 · 출발 안내 · 재계획 · Mobility Team 이 운행·통제
  사건과 **문자열로 대조**하는 칸이다(`trip_watch_cases.py` · `trip_reminders.py` ·
  `replan.py` · `itinerary_changes.py`). 표기가 다르면 사건이 있어도 **못 잡고, 오류도 안
  난다.** 전에는 아무 모양이나 받았다 — `잠실역`·`02호선`·`버스:성수동` 이 와도 등록되고,
  나중에 그 구간의 사건을 **조용히 놓친다.** 그래서 받을 때 거절한다.

★계약 정본은 `wiki/external/rest-endpoints.md` 「`routes{<키>}.options[].uses`」 절이다.
  이 파일은 그 표를 코드로 옮긴 것이다 — 둘이 어긋나면 계약을 먼저 본다.

★**모양만 본다.** 그 역이 실제로 그 노선에 있는지, 그 버스가 실제로 있는 번호인지는
  보지 않는다 — 우리 쪽에 노선 자료가 붙어 있지 않다. 「모양이 맞다」는 「대조가 된다」까지고
  「맞는 값이다」가 아니다.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

#: 1~9호선 밖의 노선 이름. ★서울 권역에서 우리가 받는 것만 적었다 — 여기 없는 이름은 거절하고
#: 그 사실을 말한다(모르는 노선을 받으면 대조할 사건 소스도 모른다).
OTHER_LINES = frozenset({
    "경의중앙선", "공항철도", "신분당선", "수인분당선", "경춘선", "서해선", "경강선",
    "우이신설선", "신림선", "김포골드라인", "의정부경전철", "용인경전철",
    "인천1호선", "인천2호선", "GTX-A",
})

_NUMBERED_LINE = re.compile(r"^[1-9]호선$")
_ZERO_PADDED = re.compile(r"^0[1-9]호선$")
#: 서울 시내·광역·심야·마을버스 번호. 예 `2224` · `N26` · `M7106` · `성동10` · `9401-1`
_BUS_NO = re.compile(r"^(?:[NM]?\d{1,4}(?:-\d{1,2})?|[가-힣]{2,4}\d{1,3}(?:-\d{1,2})?)$")
#: 도로명으로 쓰면 무관한 사건까지 걸리는 **일반 명사**. UTIC 대조가 「포함 여부」라서다
#: (`app/infrastructure/travel/utic.py`).
_TOO_GENERIC_ROADS = frozenset({"대로", "로", "길", "도로", "고속도로", "간선도로"})


def problem(value: Any) -> str | None:
    """표기 하나. 맞으면 `None`, 틀리면 **왜 틀렸는지**와 고칠 모양."""
    if not isinstance(value, str) or ":" not in value:
        return "`<종류>:<대상>` 모양이어야 한다 — 예 `2호선:잠실` · `버스:2224` · `도로:세종대로`"
    head, _, tail = value.partition(":")
    head, tail = head.strip(), tail.strip()
    if not tail:
        return "`:` 뒤가 비었다"
    if head == "도보":
        return ("`도보:` 는 쓰지 않는다 — 지나는 큰길을 `도로:` 로 적고, "
                "큰길을 안 지나는 짧은 도보는 `uses: []`")
    if head == "버스":
        if not _BUS_NO.match(tail):
            return (f"버스는 **노선번호**를 적는다 — `{tail}` 은 번호 모양이 아니다"
                    " (정류장·동네 이름은 안 된다. 예 `버스:2224` · `버스:N26` · `버스:성동10`)")
        return None
    if head == "도로":
        if tail in _TOO_GENERIC_ROADS or len(tail) < 2:
            return (f"`도로:{tail}` 은 너무 짧다 — 통제 대조가 포함 여부라 무관한 사건까지 걸린다."
                    " 도로명 **전체**를 적는다(예 `도로:세종대로`)")
        return None
    # ── 지하철 `<노선명>:<역명>` ──
    if _ZERO_PADDED.match(head):
        return f"노선명은 `{head.lstrip('0')}` 로 적는다(`{head}` ✗)"
    if not (_NUMBERED_LINE.match(head) or head in OTHER_LINES):
        return (f"`{head}` 는 모르는 종류다 — 지하철 노선명(`2호선`·`경의중앙선` 등) · `버스` · `도로`"
                " 중 하나여야 한다")
    if "(" in tail or ")" in tail:
        return f"역명의 괄호 병기는 뺀다 — `{tail}` → `{tail.split('(')[0].strip()}`"
    if tail.endswith("역") and tail != "서울역":
        return f"역명 끝의 「역」은 뺀다 — `{tail}` → `{tail[:-1]}` (역 이름이 「서울역」일 때만 그대로)"
    if tail == "서울":
        return "역 이름이 「서울역」이면 그대로 `서울역` 이다(`서울` ✗)"
    return None


def route_problems(routes: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """`routes` 전체를 훑어 틀린 표기를 **전부** 모은다(첫 하나에서 멈추지 않는다)."""
    found: list[dict[str, Any]] = []
    for route_key, route in (routes or {}).items():
        for index, option in enumerate(_options(route)):
            for value in option.get("uses") or []:
                reason = problem(value)
                if reason is not None:
                    found.append({"route": route_key, "option": option.get("id", index),
                                  "value": value, "reason": reason})
    return found


def _options(route: Any) -> Iterable[Mapping[str, Any]]:
    options = route.get("options") if isinstance(route, Mapping) else None
    return [option for option in options or [] if isinstance(option, Mapping)]


__all__ = ["OTHER_LINES", "problem", "route_problems"]
