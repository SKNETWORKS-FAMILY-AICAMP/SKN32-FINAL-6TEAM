# -*- coding: utf-8 -*-
"""감시·안내 대상 여행을 좁히는 **끼움 자리**. `[2026-10-06]` D-CS-013

★왜 있나. 전에는 일정 저장 부품이 웹 로그인 기능의 규칙(`guest_policy.not_guest_sql`)을 직접
  import 했다. 그 규칙은 로그인 표(`web_social_links`)를 조회하므로, **로그인 쪽을 바꾸면 감시와
  일정 안내가 통째로 멈추는 길**이 열려 있었다 — 로그인과 아무 상관없는 기능인데도.

지금은 이렇게 돈다.

    일정 저장 부품   "감시 대상만 고르고 싶다"  →  여기(`extra_sql`)
    끌 수 있는 기능  "게스트 여행은 빼 주세요"  →  조립 때 `register()`

  아무도 등록하지 않으면 **아무것도 빼지 않는다**(`TRUE`). 조용한 축소가 아니다 —
  「모두 감시」가 기본이고, 좁히는 쪽이 자기 규칙을 들고 와서 꽂는다.

★SQL 조각을 받는 이유. 대상이 수천 건이라 한 번의 질의로 걸러야 한다. 파이썬으로 받아서 거르면
  여행 수만큼 질의가 늘어난다. 꽂는 쪽은 **매개변수 없는 조각**만 줄 수 있다(값은 질의가 넘긴다).
"""
from __future__ import annotations

from typing import Callable

#: (별칭) -> SQL 조각. 별칭은 `trips` 표의 별칭이다(예: "t").
Narrower = Callable[[str], str]

_narrowers: list[tuple[str, Narrower]] = []


def register(name: str, narrower: Narrower) -> None:
    """조립 때 한 번 부른다. 같은 이름을 다시 등록하면 **교체**한다(재조립 대비)."""
    global _narrowers
    _narrowers = [(n, f) for n, f in _narrowers if n != name] + [(name, narrower)]


def clear() -> None:
    """시험에서 되돌릴 때."""
    _narrowers.clear()


def registered() -> tuple[str, ...]:
    return tuple(name for name, _ in _narrowers)


def extra_sql(alias: str = "t") -> str:
    """`WHERE … AND {이 조각}` 에 붙일 한 덩어리. 등록이 없으면 `TRUE`."""
    parts = [f"({f(alias)})" for _, f in _narrowers]
    return " AND ".join(parts) if parts else "TRUE"
