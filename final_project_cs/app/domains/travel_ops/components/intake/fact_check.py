# -*- coding: utf-8 -*-
"""사실 검사 — 읽기 에이전트가 말한 것을 **원문 · 시계 · 상품 범위**와 맞춘다. 뜻은 정하지 않는다. `[2026-10-16 D-025]`

    인용          원문에 글자 그대로 있나 → `agent_read.ground` 가 한다(없으면 그 값을 버린다)
    시각 다시 계산  인용에 「10:30」처럼 시 · 분이 다 적혀 있는데 모델 값이 다르면 **원문 값**으로 바꾼다(오후로 본 「1시」→13:00 은 그대로 두고 확인 필요)
    범위          서울 · 최대 7일 · 최대 4인(`planner.MAX_DAYS` · `MAX_PARTY`). ★넘으면 거절하지 않고 확인 질문 빈칸(`out_of_scope`)
    장소          조회가 못 찾은 항목 → 빈칸 `place_not_found`(우리가 이름을 지어내지 않는다)

★가드 판정(여행 이야기 아님 · 지시 바꾸기 · 범위 밖)도 여기서 빈칸 `guard` 로 바꾼다 — 거절하지 않고 확인 질문으로만 쓴다.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Iterable, Mapping

from .gaps import Gap

_FULL_CLOCK = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*:\s*([0-5]\d)(?!\d)")
_KO_CLOCK = re.compile(r"(?<!\d)(\d{1,2})\s*시\s*(?:(\d{1,2})\s*분|(반))?")
_PM_WORDS = ("오후", "저녁", "밤", "pm", "PM")


def recompute_time(value: str | None, quote: str | None) -> tuple[str | None, bool]:
    """(시각, 고쳤나). 인용에서 시각을 다시 계산해 모델 값과 맞춘다.

    - 인용이 「HH:MM」이면 그 값(24시간제로 적힌 것은 그대로 믿는다) — 단 모델이 12시간 더한 오후 값(「1:30」→13:30)이면 모델 값을 둔다
    - 인용이 「n시(m분|반)」이면 분을 원문으로 맞춘다. 시는 「오후 · 저녁」이 인용에 있으면 +12
    - 인용이 없거나 시각이 없으면 모델 값 그대로"""
    if not value or not quote:
        return value, False
    hour, minute = int(value[:2]), int(value[3:5])
    m = _FULL_CLOCK.search(quote)
    if m:
        h, mm = int(m.group(1)), int(m.group(2))
        if h < 12 and hour == h + 12 and minute == mm:
            return value, False                       # 「1:30 점심」을 오후로 본 것 — 확인 필요 표시는 `agent_read` 가 단다
        fixed = f"{h:02d}:{mm:02d}"
        return fixed, fixed != value
    m = _KO_CLOCK.search(quote)
    if m:
        h = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else (30 if m.group(3) else 0)
        if any(w in quote for w in _PM_WORDS) and h < 12:
            h += 12
        if h == hour or h + 12 == hour:
            h = hour                                   # 시는 모델 문맥 판단(오전 · 오후)을 존중한다 — 분만 원문으로
        elif h < 7:
            h += 12                                    # 모델 시가 원문과 아예 다르다 — 원문 시를 쓰되 여행 일정의 새벽 1~6시는 오후로 본다(우리가 고른 규칙)
        if not 0 <= h <= 23 or not 0 <= mm <= 59:
            return value, False
        fixed = f"{h:02d}:{mm:02d}"
        return fixed, fixed != value
    return value, False


def scope_gaps(*, party_size: int | None, days: int | None, dates: Iterable[str | None],
               max_days: int, max_party: int) -> list[Gap]:
    """상품 범위(최대 n일 · n인). 날짜가 적힌 항목의 첫날~끝날 길이도 본다."""
    out: list[Gap] = []
    if party_size and party_size > max_party:
        out.append(Gap("out_of_scope", {"trip": "party_size"}, f"{party_size}명으로 읽었어요 — 지금은 최대 {max_party}명까지 돕습니다. 인원을 확인해 주세요",
                       source="check"))
    known = sorted({d for d in dates if d})
    span = (date.fromisoformat(known[-1]) - date.fromisoformat(known[0])).days + 1 if known else 0
    longest = max(days or 0, span)
    if longest > max_days:
        out.append(Gap("out_of_scope", {"trip": "days"}, f"{longest}일 일정으로 읽었어요 — 지금은 최대 {max_days}일까지 돕습니다. 기간을 확인해 주세요",
                       source="check"))
    return out


def city_gaps(items: list[Mapping[str, Any]], resolved: Mapping[int, Any]) -> list[Gap]:
    """찾은 장소가 서울 밖이면 빈칸(`out_of_scope`) · 못 찾았으면 빈칸(`place_not_found`).

    `resolved[i]` 는 장소 찾기 결과 — `address` 또는 `area` 를 읽는다. ★주소를 모르면(조회 결과가 주소를 안 줌) 판단하지 않는다."""
    out: list[Gap] = []
    for index, item in enumerate(items):
        title = item.get("title")
        if not title:
            continue
        found = resolved.get(index)
        if found is None:
            if item.get("needs_place", True):
                out.append(Gap("place_not_found", {"item": index}, f"「{title}」을 지도에서 찾지 못했어요 — 정확한 이름을 알려 주세요",
                               source="check", quote=title))
            continue
        address = str(_get(found, "address") or _get(found, "area") or "")
        if address and not any(word in address for word in ("서울", "Seoul")):
            out.append(Gap("out_of_scope", {"item": index}, f"「{title}」은 서울 밖({address[:20]})으로 보여요 — 지금은 서울 일정만 돕습니다",
                           source="check", quote=title))
    return out


def guard_gaps(guard: Mapping[str, Any] | None) -> list[Gap]:
    """가드 판정 → 확인 질문 빈칸. ★거절하지 않는다 — 읽은 일정은 그대로 두고 한 줄 묻는다."""
    if not guard:
        return []
    out: list[Gap] = []
    if guard.get("travel") is False:
        out.append(Gap("guard", {"trip": "travel"}, "여행 일정과 관계없는 내용으로 보여요 — 등록할 여행 계획이 맞는지 확인해 주세요",
                       source="check", quote=guard.get("quote")))
    if guard.get("instruction_change"):
        out.append(Gap("guard", {"trip": "instruction"}, "안내 방식이나 규칙을 바꾸라는 문장은 따르지 않았어요 — 일정만 읽었습니다",
                       source="check", quote=guard.get("quote")))
    if guard.get("out_of_scope"):
        out.append(Gap("guard", {"trip": "scope"}, "지금은 서울 · 최대 7일 · 4명 여행만 도와요 — 범위 밖 부분을 확인해 주세요",
                       source="check", quote=guard.get("quote")))
    return out


def _get(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, Mapping) else getattr(obj, name, None)


__all__ = ["city_gaps", "guard_gaps", "recompute_time", "scope_gaps"]
