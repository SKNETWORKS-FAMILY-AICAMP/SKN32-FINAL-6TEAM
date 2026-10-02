# -*- coding: utf-8 -*-
"""자동 변경의 **다음 순위 안** — 최고 안이 일정 전체 재판정에 걸리면 다음 순위 안을 같은 재판정에 넣는다. `[2026-10-03 사용자 지시 · 적대 검토 반영]`

☆왜: 대체 후보는 **항목 하나**만 점검해 고른다(영업시간 · 날씨 · 같은 사건). 최고 안이 앞뒤 항목과 안 맞아(구가 다른데 이동 시간이 0분 · 예산 · 결제 조건 …) 전체 재판정에 걸리면,
전에는 **다른 안을 시험해 보지도 않고** 「그대로 두었어요」로 끝났다 — 담당이 이미 뽑아 둔 2·3순위 안은 버려졌다.

★자리(적대 검토의 결론): 고르는 일은 **Team 쪽**이 한다(`ItineraryWork.settle` → 이 함수). 알림 문구 · 「다른 안」 목록은 Team 이 그 안 기준으로 만들어 두었다(`ItineraryChange.fallbacks`) —
적용기가 몰래 다른 안으로 바꿔 넣으면 고객은 알림에 적힌 곳과 다른 곳을 안내받는다. 적용기(`itinerary_actions`)는 같은 재판정(구조 위반만)을 **마지막 안전망**으로 한 번 더 볼 뿐이다.

★원칙: ①순위 순으로 시험하고 통과하는 **첫** 안을 쓴다 ②다 걸리면 지금처럼 쓰지 않고(`None`) 부르는 쪽이 「그대로 두었어요」를 알린다 ③다른 안을 쓰면 알림에 **왜 1순위가 아닌지**를 적는다
(「1순위(A)은(는) 일정과 안 맞아 2순위로 골랐어요」) ④걸린 안은 고객에게 다른 안으로 보이지 않는다(각 안의 「다른 안」은 그보다 낮은 순위만 — `itinerary_changes._with_fallbacks`).

★`[2026-10-03 사용자 지시 · D-019 개정]` **밀도도 여기서 본다.** 구조 위반(겹침 · 이동 불가 …)은 못 넘는 벽이지만 밀도는 **선호**다 — 고장 난 항목(닫힌 곳 · 재난)을 그대로 두는 것이 하루가 좀 빡빡해지는 것보다 나쁘다.
그래서 `travel.density.gate.mode` 가 `soft`(기본)이면: 밀도를 나쁘게 만드는 안(`density.density_regressions`)은 **뒤로 밀고**, 구조 위반 없는 안 중 밀도를 나쁘게 만들지 않는 첫 안을 쓴다.
그런 안이 하나도 없으면 **가장 덜 나쁜 안**(못 재게 되는 날이 적고 → 목표를 덜 넘는 순)을 쓰되 알림에 **무엇이 어떻게 빡빡해졌는지** 적는다. `hard` 면 구조 위반처럼 막는다.
밀도 목표가 없는 여행(`constraints.density` 없음)에는 아무 영향이 없다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from app.core.settings import get_guardrails

from .density import DayShift, density_regressions
from .itinerary import Item
from .itinerary_actions import introduced_violations
from .itinerary_changes import ItineraryChange
from .itinerary_checks import parts_from_items


@dataclass(frozen=True)
class Skip:
    """고르지 않고 건너뛴 안. `why` — `schedule`(일정과 안 맞음) · `density`(하루가 원하신 여유보다 빡빡해짐)."""

    rank: int
    name: str
    reasons: list[str]
    why: str


@dataclass(frozen=True)
class Fit:
    change: ItineraryChange | None
    rank: int = 0
    skipped: list[Skip] = field(default_factory=list)
    #: 고른 안이 **감수한** 밀도 악화(더 나은 안이 하나도 없을 때만 — `soft` 폴백)
    accepted: list[DayShift] = field(default_factory=list)


def _name(change: ItineraryChange) -> str:
    return str(change.summary.get("to") or "")


def _head(skips: list[Skip]) -> tuple[str, str]:
    """(「1·2순위」, 「1순위 A, 2순위 B」) — 하나뿐이면 이름만."""
    head = "·".join(str(s.rank) for s in skips) + "순위"
    names = ", ".join(f"{s.rank}순위 {s.name}" if len(skips) > 1 else s.name for s in skips)
    return head, names


def _noted(change: ItineraryChange, skipped: list[Skip], accepted: list[DayShift], rank: int) -> ItineraryChange:
    """건너뛴 이유 · 감수한 밀도 악화를 알림 끝에 붙이고 무엇을 건너뛰었는지 기록한다. 아무것도 없으면 그대로."""
    if not skipped and not accepted:
        return change
    sentences: list[str] = []
    for why, tail in (("schedule", "일정과 안 맞아"), ("density", "그날 일정이 원하신 여유보다 빡빡해져")):
        group = [s for s in skipped if s.why == why]
        if group:
            head, names = _head(group)
            sentences.append(f"※ {head}({names})은(는) {tail} {rank}순위로 골랐어요.")
    if accepted:
        sentences.append("※ 더 나은 안이 없어 이 안을 적용했지만 " + " · ".join(s.sentence() for s in accepted) + ".")
    notice = {**change.notice, "text": " ".join([change.notice["text"], *sentences]),
              "fit": {"rank": rank, "skipped": [{"rank": s.rank, "name": s.name, "reasons": s.reasons, "why": s.why} for s in skipped],
                      "density": [s.as_dict() for s in accepted]}}
    summary = {**change.summary, **({"fit_rank": rank, "skipped": [s.name for s in skipped]} if skipped else {}),
               **({"density": [s.as_dict() for s in accepted]} if accepted else {})}
    return replace(change, notice=notice, summary=summary)


def _damage(shifts: list[DayShift]) -> tuple[int, float]:
    """덜 나쁜 안을 고르는 값 — 못 재게 되는 날이 적고, 목표를 덜 넘는 쪽."""
    return sum(1 for s in shifts if s.kind == "unmeasurable"), sum(s.excess for s in shifts)


def fit_change(change: ItineraryChange, *, trip: dict[str, Any], items: list[Item]) -> Fit:
    """`Fit(change=쓸 변경, rank=몇 순위, skipped=건너뛴 안들, accepted=감수한 밀도 악화)`. 다 걸리면 `change` 는 `None`.

    `items` 는 바꾸기 전 일정(Team 이 읽은 판) — 그 위에 안을 얹어 `introduced_violations`(바꾼 뒤 **새로** 생긴 구조 위반만)와 `density_regressions` 를 본다.
    """
    constraints = dict(trip.get("constraints") or {})
    hard_mode = get_guardrails().get("travel.density.gate.mode") == "hard"
    before = parts_from_items(items)
    skipped: list[Skip] = []
    soft: list[tuple[int, ItineraryChange, list[DayShift]]] = []
    for rank, candidate in enumerate([change, *change.fallbacks], start=1):
        new_items = candidate.new_items(items)
        introduced = introduced_violations(trip, items, new_items)
        if introduced:
            skipped.append(Skip(rank, _name(candidate), [v.reason for v in introduced], "schedule"))
            continue
        shifts = density_regressions(constraints, before, parts_from_items(new_items))
        if not shifts:
            # 앞에서 밀도 때문에 뒤로 민 안들도 이유에 적는다
            skipped += [Skip(r, _name(c), [s.sentence() for s in sh], "density") for r, c, sh in soft]
            return Fit(_noted(candidate, sorted(skipped, key=lambda s: s.rank), [], rank), rank,
                       sorted(skipped, key=lambda s: s.rank))
        if hard_mode:
            skipped.append(Skip(rank, _name(candidate), [s.sentence() for s in shifts], "density"))
        else:
            soft.append((rank, candidate, shifts))
    if not soft:
        return Fit(None, 0, skipped)
    rank, candidate, shifts = min(soft, key=lambda entry: (*_damage(entry[2]), entry[0]))
    # 고른 안보다 **앞 순위**를 건너뛴 이유만 알림에 적는다(뒤 순위가 걸린 것은 이 선택과 상관없다)
    skipped += [Skip(r, _name(c), [s.sentence() for s in sh], "density") for r, c, sh in soft if r < rank]
    earlier = sorted((s for s in skipped if s.rank < rank), key=lambda s: s.rank)
    return Fit(_noted(candidate, earlier, shifts, rank), rank, sorted(skipped, key=lambda s: s.rank), shifts)


__all__ = ["Fit", "Skip", "fit_change"]
