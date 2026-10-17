# -*- coding: utf-8 -*-
"""빈칸 목록 → 담당 연결 → 제안 → 초안에 대 보기. `[2026-10-16 D-025]`

    Gap        빈칸 하나 — 모델이 분류한 것(`source="model"`) + 사실 검사가 찾은 것(`source="check"`)
    ROUTES     분류 이름 → 담당(코드 연결표). 모델이 담당을 고르지 않는다 — 분류만 하고, 누구에게 갈지는 이 표가 정한다
    Proposal   담당이 내는 **같은 모양**의 제안 — 후보 1~3 · 이유 · 검사 결과. ★담당은 적용하지 않는다
    settle     코드가 장소 → 이동 → 시각 순으로 초안에 대 보고 다시 검사한다. 새 충돌이 생기면 **최대 2회** 다시 돈다

★담당은 이 파일이 모른다 — 부르는 쪽(`pipeline`)이 담당 이름마다 함수를 넣는다(`owners`). 그래서 식당 팀 · 활동 팀 · 이동 판정 · 계획 에이전트를
  바꿔 끼워도 이 파일은 그대로고, 시험은 가짜 담당으로 돈다.
★고객만 아는 값(첫날 날짜 · 예약한 숙소·가게 이름)은 묻는다. 미정 숙소는 숙소 추천에 연결한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

#: 분류 이름 → 담당. ★모델이 내는 분류 이름(`agent_read.GAP_KINDS`)과 사실 검사가 내는 이름(`fact_check`)을 모두 여기서 받는다.
ROUTES: dict[str, str] = {
    "meal_place": "dining_team",          # 「저녁은 숙소 근처에서」 — 끼니는 있는데 가게가 없다
    "activity_place": "activity_team",    # 「오후엔 근처 구경」 — 활동 자리는 있는데 장소가 없다
    "lodging_place": "lodging_team",      # 아직 정하지 않은 호텔·조식 — 여행 공통 숙소 추천
    "move_mode": "mobility",              # 구간 수단이 없다 · 고른 수단으로 못 닿는다
    "tight_move": "mobility",             # 사실 검사 — 앞 일정 끝에서 다음 일정까지 이동이 빠듯하다
    "free_slot": "planner",               # 「둘째 날은 알아서」 「오후는 채워 주세요」 — 하루 · 시간대를 통째로
    "place_not_found": "ask_customer",    # 사실 검사 — 장소 조회가 못 찾았다(우리가 지어내지 않는다)
    "first_day_date": "ask_customer",
    "lodging_name": "ask_customer",
    "booked_place_name": "ask_customer",
    "out_of_scope": "ask_customer",       # 사실 검사 — 서울 밖 · 7일 넘음 · 4인 넘음. 거절하지 않고 확인 질문
    "guard": "ask_customer",              # 가드 판정 — 여행 이야기 아님 · 지시를 바꾸려는 문장. 거절하지 않고 확인 질문
}

#: 초안에 대 보는 순서 — 장소가 정해져야 이동을 재고, 이동이 정해져야 시각을 다시 맞춘다
APPLY_ORDER = ("place", "move", "time")
#: 담당 이름 → 그 제안이 바꾸는 것
CHANGES: dict[str, str] = {"dining_team": "place", "activity_team": "place", "lodging_team": "place", "planner": "place", "mobility": "move",
                           "ask_customer": "question"}
MAX_ROUNDS = 2
MAX_CANDIDATES = 3


@dataclass
class Gap:
    kind: str
    where: dict[str, Any]                 # {"item": i} · {"day": d, "window": ["12:00", "14:00"]} · {"pair": [a, b]} · {"trip": True}
    reason: str                           # 고객에게 보일 수 있는 한 줄(왜 빈칸인가)
    source: str = "model"                 # model · check
    quote: str | None = None              # 원문 근거(있으면)

    @property
    def owner(self) -> str:
        return ROUTES.get(self.kind, "ask_customer")

    @property
    def key(self) -> str:
        return f"{self.kind}:{sorted(self.where.items())}"

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "where": self.where, "reason": self.reason, "source": self.source, "quote": self.quote,
                "owner": self.owner}


@dataclass
class Proposal:
    """담당의 제안 — 모든 담당이 같은 모양. `candidates[0]` 이 담당의 첫 추천이다."""

    gap: Gap
    owner: str
    candidates: list[dict[str, Any]] = field(default_factory=list)   # 각 후보: {"title"|"mode"|"question", …, "reason"}
    reason: str = ""
    checks: list[dict[str, Any]] = field(default_factory=list)        # [{"code", "ok": bool, "note"}]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"gap": self.gap.as_dict(), "owner": self.owner, "candidates": self.candidates[:MAX_CANDIDATES],
                "reason": self.reason, "checks": self.checks, "error": self.error}


Owner = Callable[[Gap, Mapping[str, Any]], Proposal]
#: 한 회차의 쓸 제안을 **순서대로**(장소 → 이동 → 시각) 받아 한 번에 초안에 댄다 — 판(revision)을 제안마다 만들지 않게
Apply = Callable[[dict[str, Any], list[Proposal]], dict[str, Any]]
Recheck = Callable[[dict[str, Any]], list[Gap]]


def collect(model_gaps: Iterable[Gap], check_gaps: Iterable[Gap]) -> list[Gap]:
    """빈칸 목록 = 모델이 분류한 빈칸 + 사실 검사가 찾은 빈칸. 같은 자리 같은 분류는 하나로(모델 쪽 근거를 남긴다)."""
    out: dict[str, Gap] = {}
    for gap in list(model_gaps) + list(check_gaps):
        out.setdefault(gap.key, gap)
    return list(out.values())


def ask(gaps: Iterable[Gap], owners: Mapping[str, Owner], draft: Mapping[str, Any]) -> list[Proposal]:
    """빈칸마다 담당에게 묻는다. 담당이 없거나 실패하면 그 빈칸은 「고객 질문」으로 넘어간다(지어내지 않는다)."""
    out: list[Proposal] = []
    for gap in gaps:
        owner = owners.get(gap.owner)
        if owner is None:
            out.append(Proposal(gap, "ask_customer", [{"question": gap.reason}], reason="담당이 연결되지 않았다",
                                error=f"no owner: {gap.owner}"))
            continue
        try:
            proposal = owner(gap, draft)
        except Exception as exc:                       # noqa: BLE001 — 담당 하나의 실패가 확인 화면을 막지 않는다
            proposal = Proposal(gap, "ask_customer", [{"question": gap.reason}], reason="담당이 답하지 못했다",
                                error=f"{type(exc).__name__}: {exc}"[:200])
        proposal.candidates = proposal.candidates[:MAX_CANDIDATES]
        out.append(proposal)
    return out


def settle(draft: dict[str, Any], gaps: list[Gap], owners: Mapping[str, Owner], apply: Apply, recheck: Recheck, *,
           max_rounds: int = MAX_ROUNDS,
           retry_unfilled: Callable[[Proposal], bool] | None = None) -> tuple[dict[str, Any], list[Proposal], list[dict[str, Any]]]:
    """빈칸을 담당 제안으로 채운 초안 · 쓴 제안 · 회차 기록. ★적용은 여기(코드)만 한다 — 담당은 제안만.

    한 회차: 담당에게 묻기 → 장소 → 이동 → 시각 순으로 첫 후보를 대 보기 → 다시 검사. 다시 검사가 **새** 빈칸을 내면 그것만 다음 회차로.
    부르는 쪽이 `retry_unfilled`로 고른 미해결 제안은 다른 적용으로 판이 바뀐 때만 다시 볼 수 있다.
    `max_rounds` 를 넘기면 남은 빈칸은 고객 질문(제안 없이 이유만)으로 둔다 — 끝없이 돌지 않는다."""
    used: list[Proposal] = []
    log: list[dict[str, Any]] = []
    seen = {g.key for g in gaps}
    pending = list(gaps)
    for round_no in range(1, max_rounds + 1):
        if not pending:
            break
        before_revision = draft.get("revision")
        proposals = ask(pending, owners, draft)
        order = {name: i for i, name in enumerate(APPLY_ORDER)}
        ordered = sorted(proposals, key=lambda p: order.get(CHANGES.get(p.owner, ""), len(order)))
        usable = [p for p in ordered if p.owner != "ask_customer" and p.candidates and p.error is None]
        if usable:
            draft = apply(draft, usable)
        used.extend(ordered)
        remaining = recheck(draft)
        fresh = [g for g in remaining if g.key not in seen]
        retry_keys = {p.gap.key for p in ordered if retry_unfilled is not None and not p.candidates
                      and p.error is None and retry_unfilled(p)} if draft.get("revision") != before_revision else set()
        retried = [g for g in remaining if g.key in seen and g.key in retry_keys]
        entry = {"round": round_no, "asked": len(pending), "new_gaps": [g.as_dict() for g in fresh]}
        if retried:
            entry["retried_gaps"] = [g.as_dict() for g in retried]
        log.append(entry)
        seen |= {g.key for g in fresh}
        pending = fresh + retried
    for gap in pending:                                # 회차를 다 써도 남은 것
        used.append(Proposal(gap, "ask_customer", [{"question": gap.reason}], reason=f"{max_rounds}회 맞춰 봐도 남았다"))
    return draft, used, log


__all__ = ["APPLY_ORDER", "CHANGES", "Gap", "MAX_ROUNDS", "Proposal", "ROUTES", "ask", "collect", "settle"]
