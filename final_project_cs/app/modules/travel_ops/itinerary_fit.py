# -*- coding: utf-8 -*-
"""자동 변경의 **다음 순위 안** — 최고 안이 일정 전체 재판정에 걸리면 다음 순위 안을 같은 재판정에 넣는다. `[2026-10-03 사용자 지시 · 적대 검토 반영]`

☆왜: 대체 후보는 **항목 하나**만 점검해 고른다(영업시간 · 날씨 · 같은 사건). 최고 안이 앞뒤 항목과 안 맞아(구가 다른데 이동 시간이 0분 · 예산 · 결제 조건 …) 전체 재판정에 걸리면,
전에는 **다른 안을 시험해 보지도 않고** 「그대로 두었어요」로 끝났다 — 담당이 이미 뽑아 둔 2·3순위 안은 버려졌다.

★자리(적대 검토의 결론): 고르는 일은 **Team 쪽**이 한다(`ItineraryWork.settle` → 이 함수). 알림 문구 · 「다른 안」 목록은 Team 이 그 안 기준으로 만들어 두었다(`ItineraryChange.fallbacks`) —
적용기가 몰래 다른 안으로 바꿔 넣으면 고객은 알림에 적힌 곳과 다른 곳을 안내받는다. 적용기(`itinerary_actions`)는 같은 재판정을 **마지막 안전망**으로 한 번 더 볼 뿐이다.

★원칙: ①순위 순으로 시험하고 통과하는 **첫** 안을 쓴다 ②다 걸리면 지금처럼 쓰지 않고(`None`) 부르는 쪽이 「그대로 두었어요」를 알린다 ③다른 안을 쓰면 알림에 **왜 1순위가 아닌지**를 적는다
(「1순위(A)은(는) 일정과 안 맞아 2순위로 골랐어요」) ④걸린 안은 고객에게 다른 안으로 보이지 않는다(각 안의 「다른 안」은 그보다 낮은 순위만 — `itinerary_changes._with_fallbacks`).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from .itinerary import Item
from .itinerary_actions import introduced_violations
from .itinerary_changes import ItineraryChange


def _name(change: ItineraryChange) -> str:
    return str(change.summary.get("to") or "")


def _noted(change: ItineraryChange, blocked: list[tuple[int, str, list[str]]], rank: int) -> ItineraryChange:
    """다른 안을 쓸 때 알림 끝에 이유를 붙이고 무엇을 건너뛰었는지 기록한다."""
    skipped = ", ".join(f"{r}순위 {name}" if len(blocked) > 1 else f"{name}" for r, name, _ in blocked)
    head = "·".join(str(r) for r, _, _ in blocked) + "순위"
    sentence = f"※ {head}({skipped})은(는) 일정과 안 맞아 {rank}순위로 골랐어요."
    notice = {**change.notice, "text": f"{change.notice['text']} {sentence}",
              "fit": {"rank": rank, "skipped": [{"rank": r, "name": name, "reasons": reasons} for r, name, reasons in blocked]}}
    return replace(change, notice=notice, summary={**change.summary, "fit_rank": rank,
                                                    "skipped": [name for _, name, _ in blocked]})


def fit_change(change: ItineraryChange, *, trip: dict[str, Any], items: list[Item]
               ) -> tuple[ItineraryChange | None, int, list[tuple[int, str, list[str]]]]:
    """(쓸 변경, 몇 순위, 걸린 안들 `[(순위, 이름, 새 위반 이유들)]`). 다 걸리면 쓸 변경은 `None`.

    `items` 는 바꾸기 전 일정(Team 이 읽은 판) — 그 위에 안을 얹어 `introduced_violations`(바꾼 뒤 **새로** 생긴 위반만)를 본다.
    """
    blocked: list[tuple[int, str, list[str]]] = []
    for rank, candidate in enumerate([change, *change.fallbacks], start=1):
        introduced = introduced_violations(trip, items, candidate.new_items(items))
        if not introduced:
            return (_noted(candidate, blocked, rank) if blocked else candidate), rank, blocked
        blocked.append((rank, _name(candidate), [v.reason for v in introduced]))
    return None, 0, blocked


__all__ = ["fit_change"]
