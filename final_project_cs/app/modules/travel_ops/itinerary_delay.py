# -*- coding: utf-8 -*-
"""앞 일정이 늦어지면 **뒤 일정이 아직 성립하는지** — 체크리스트 L2. `[2026-10-03]`

☆왜: 「N분 늦어요」(`plan_delay`)는 그 시각 뒤 **첫 식사 하나**의 영업·브레이크·라스트오더만 봤다. 식당이 괜찮으면 「지금 일정 그대로도 괜찮아요」로 끝났다 —
식사가 N분 밀려 **뒤 일정(활동 · 이동)이 겹치거나, 밀린 뒤 시각에 이미 문을 닫는 곳이 있어도** 말하지 않았다(체크리스트 L2: 감시·응답 길의 ◐ — 활동 · 이동 · 뒤 일정 겹침은 안 봄).

★하는 일: 늦어진 항목이 끝나는 시각 뒤로 **겹치는 항목만 차례로 민다**(밀린 만큼, 길이는 그대로 — 이동 항목도 같이). 밀리지 않는 항목에서 멈춘다. 밀린 항목마다
①예약 · 고정 · 잠긴 일정이면(시각을 우리가 못 바꾼다) 「그 시각에 늦는다」 ②영업시간 · 휴무 · 브레이크 · 입장 마감에 걸리면 그 이유(`check_itinerary` 의 **같은** 장소 판정 — 새 규칙을 만들지 않는다).
★**일정은 바꾸지 않는다.** 시각을 밀어 새 판을 쓰는 일은 하지 않는다 — 고객이 요청한 것이 아니고, 밀면 예약 · 도착 안내가 틀어진다. 알려서 고객이 고르게 한다.
★모르는 것은 세지 않는다: 영업시간 · 예약 표시가 없으면 그 칸은 걸리지 않는다(`check_itinerary` 와 같다). 늦어진 항목의 끝 시각이 없으면 1시간으로 본다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .itinerary import Item
from .itinerary_checks import Part, check_itinerary

KST = ZoneInfo("Asia/Seoul")
_DEFAULT_LENGTH = timedelta(hours=1)


@dataclass(frozen=True)
class Knock:
    """밀려서 성립하지 않게 된 뒤 일정 하나."""

    item: Item
    new_start: datetime
    new_end: datetime
    reasons: list[str] = field(default_factory=list)

    def sentence(self) -> str:
        when = self.new_start.astimezone(KST).strftime("%H:%M")
        prefix = f"{self.item.title}: "                      # `check_itinerary` 의 이유는 항목 이름으로 시작한다 — 문장 머리에 이미 있다
        return f"{self.item.title}({when} 시작) — {'; '.join(reason.removeprefix(prefix) for reason in self.reasons)}"


def _fixed(item: Item) -> bool:
    """시각을 우리가 못 바꾸는 일정 — 고객이 고정했거나 · 잠긴 예약이거나 · 예약번호가 있다(`pending.protected_reason` 과 같은 표시)."""
    return bool(item.detail.get("customer_pinned") or item.locked or item.detail.get("booking"))


def delay_knock_on(items: list[Item], delayed: Item, minutes: int) -> list[Knock]:
    """`delayed` 가 `minutes` 분 늦어졌을 때 성립하지 않게 되는 뒤 일정들(시각순). 겹치는 것이 없거나 밀려도 괜찮으면 빈 목록."""
    shifted_end = (delayed.ends_at or delayed.starts_at + _DEFAULT_LENGTH) + timedelta(minutes=minutes)
    cursor = shifted_end
    later = sorted((i for i in items if i.item_id != delayed.item_id and i.starts_at >= delayed.starts_at
                    and i.starts_at >= (delayed.ends_at or delayed.starts_at)), key=lambda i: (i.starts_at, i.seq))
    found: list[Knock] = []
    for item in later:
        if item.starts_at >= cursor:
            break                                              # 밀리지 않는다 — 이 뒤로는 그대로다
        length = (item.ends_at - item.starts_at) if item.ends_at else timedelta(0)
        new_start, new_end = cursor, cursor + length
        reasons: list[str] = []
        if _fixed(item):
            reasons.append(f"예약·고정한 시각({item.starts_at.astimezone(KST):%H:%M})에 늦는다")
        elif item.kind != "mobility" and item.place is not None:
            part = Part(seq=item.seq, kind=item.kind, title=item.title, starts_at=new_start, ends_at=new_end, place=item.place)
            reasons += [violation.reason for violation in check_itinerary([part])]
        if reasons:
            found.append(Knock(item, new_start, new_end, reasons))
        cursor = max(cursor, new_end)
    return found


def knock_on_text(delayed: Item, minutes: int, knocks: list[Knock]) -> str:
    """고객에게 보일 문장 — 일정은 안 바꿨다는 것과 무엇이 걸리는지만. 원인에 있는 말만 쓰고 사람 대기 약속은 하지 않는다."""
    listed = " / ".join(knock.sentence() for knock in knocks)
    return (f"{delayed.title}은(는) {minutes}분 늦어도 괜찮지만, 그만큼 뒤 일정이 밀려 이렇게 걸려요: {listed}. "
            "일정은 바꾸지 않았어요 — 뒤 일정의 시각을 직접 조정하시거나 말씀해 주세요.")


__all__ = ["Knock", "delay_knock_on", "knock_on_text"]
