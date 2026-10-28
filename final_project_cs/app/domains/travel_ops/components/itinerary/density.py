"""D-019: 입력으로 확인 가능한 시간만 측정하는 밀도.

★`[2026-10-03 개정]` 등록·조회는 여전히 관측만 한다(거절 없음). 자동 변경(감시)은 **바꾼 뒤 하루 밀도가 나빠지는지**를 `density_regressions` 로 본다 — `itinerary_fit` 가 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any, Literal, Mapping
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.settings import get_guardrails
from app.domains.travel_ops.components.itinerary.itinerary_checks import STAY_KINDS, Part, particle

#: ★`[2026-10-28]` 아래 `reason` · `remedy` 는 여행 화면 「살펴볼 점」(`trip-attention.tsx`)에 그대로 보인다 — 해요체 고객 문장으로 쓰고,
#:   항목 순번(「항목 3」) 대신 일정 이름을, 내부 말(프리셋 · 완충시간 · 대기 주석 · 가용시간 창) 대신 고객 말을 쓴다.
_INVALID_INPUT = "하루 여유 설정 값을 읽지 못했어요"


def _name(part: Part) -> str:
    return str(part.title or "").strip() or "이름 없는 일정"


def _pair(previous: Part, current: Part, tail: str) -> str:
    """두 일정을 한 문장에 — 「궁과 시장의 시간이 겹쳐요」 「궁에서 시장으로 가는 …」(받침 조사는 `particle`)."""
    first, second = _name(previous), _name(current)
    return tail.format(first=first, second=second, wa=particle(first, "과/와"), ro=particle(second, "으로/로"))

KST = ZoneInfo("Asia/Seoul")


class DayWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime
    ends_at: datetime
    buffer_minutes: float = Field(ge=0, allow_inf_nan=False, strict=True)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def offset_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("하루 가용시간에는 UTC 오프셋이 필요합니다")
        return value.astimezone(KST)


class DensityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["low", "normal", "high", "very_high"] | None = None
    target_density: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False, strict=True)
    days: dict[date, DayWindow] = Field(min_length=1)

    @model_validator(mode="after")
    def one_preference(self) -> "DensityInput":
        if (self.level is None) == (self.target_density is None):
            raise ValueError("level 또는 target_density 중 하나를 지정하세요")
        return self


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) and value >= 0 else None


def _place_id(part: Part) -> Any:
    return (part.place or {}).get("place_id")


def measure_density(parts: list[Part], constraints: Mapping[str, Any]) -> dict[str, Any]:
    if "density" not in constraints:
        return {"density": [], "warnings": []}
    results: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    policy = get_guardrails().get("travel.density")
    basis = "undetermined"

    def add(day, target, available, occupied, reasons, breakdown=None):
        ratio = occupied / available if not reasons else None
        status = "unmeasurable" if reasons else ("exceeded" if occupied > available * target else "ok")
        results.append({"date": str(day) if day else None, "status": status,
                        "target_density": target, "policy_basis": basis,
                        "policy_id": policy["policy_id"], "research_as_of": policy["research_as_of"],
                        "measurement_scope": "submitted_schedule", "buffer_placement": "unallocated",
                        "breakdown": None if reasons else breakdown,
                        "available_minutes": available, "occupied_minutes": None if reasons else occupied,
                        "actual_density": ratio, "reasons": reasons})
        if status != "ok":
            warnings.append({"code": "density_" + status, "date": str(day) if day else None,
                             "policy_basis": basis,
                             "reason": " / ".join(reasons) if reasons else (
                                 "하루 일정이 고르신 여유 정도보다 빡빡해요" if basis == "research_calibrated"
                                 else ("하루 일정이 기본 여유 기준보다 빡빡해요" if basis == "estimated"
                                       else "하루 일정이 정하신 여유 목표보다 빡빡해요")),
                             "remedy": "빠지거나 잘못된 시간 · 이동 정보를 채워 주세요" if reasons
                             else "예약 · 식사 · 이동 시간과 여유 시간은 그대로 두고, 꼭 가지 않아도 되는 일정을 줄여 보세요"})

    try:
        spec = DensityInput.model_validate(constraints["density"])
        windows = sorted(spec.days.items(), key=lambda pair: pair[1].starts_at)
        for day, window in windows:
            if window.starts_at.date() != day or not timedelta(0) < window.ends_at - window.starts_at <= timedelta(days=1):
                raise ValueError("하루 활동 시간의 날짜나 길이가 맞지 않아요")
        if any(a.ends_at > b.starts_at for (_, a), (_, b) in zip(windows, windows[1:])):
            raise ValueError("날짜별로 정한 활동 시간이 서로 겹쳐요")
    except (ValidationError, ValueError) as exc:
        reason = _INVALID_INPUT if isinstance(exc, ValidationError) else str(exc)
        add(None, None, None, None, [reason])
        return {"density": results, "warnings": warnings}

    basis = "user_preference" if spec.target_density is not None else "estimated"
    target = spec.target_density if spec.target_density is not None else float(policy["targets"][spec.level])
    if spec.target_density is None:
        basis = "research_calibrated"
    if not isfinite(target) or not 0 < target < 1:
        raise ValueError("travel.density.targets must be between zero and one")
    buckets: dict[date, list[Part]] = {day: [] for day in spec.days}
    outside: dict[date | None, list[str]] = {}
    for part in parts:
        if part.kind in STAY_KINDS:
            continue        # `[2026-10-13]` 숙소는 하루 일정의 빽빽함에 세지 않는다(며칠에 걸친다 — `itinerary_quality._DAY_KINDS` 와 같은 뜻)
        if part.starts_at.tzinfo is None:
            outside.setdefault(None, []).append(f"{_name(part)}: 시작 시각에 시간대 정보가 없어요")
            continue
        start = part.starts_at.astimezone(KST)
        day = next((d for d, w in windows if w.starts_at <= start < w.ends_at), None)
        if day is None:
            outside.setdefault(start.date(), []).append(f"{_name(part)}: 정해 둔 활동 시간 밖에서 시작해요")
        else:
            buckets[day].append(part)

    for day, window in windows:
        reasons = list(outside.pop(day, []))
        items = sorted(buckets[day], key=lambda p: p.starts_at)
        scheduled = transfers = travel = known_queue = 0.0
        evidence_buffer = 0.0
        queue_unannotated = 0
        for part in items:
            end = part.ends_at
            if end is None or end.tzinfo is None or end <= part.starts_at or end > window.ends_at:
                reasons.append(f"{_name(part)}: 끝나는 시각을 알 수 없거나, 시작 시각보다 늦지 않거나, 정해 둔 활동 시간을 넘어요")
                continue
            minutes = (end - part.starts_at).total_seconds() / 60
            scheduled += minutes
            detail = part.detail or {}
            # 대기·예약 도착 여유는 해당 항목에 이미 포함된 시간이 아니면 한 번만 더한다.
            if detail.get("reservation"):
                evidence_buffer += float(detail.get("arrival_buffer_minutes") or (
                    policy["evidence"]["restaurant_arrival_minutes"] if part.kind == "dining"
                    else policy["evidence"]["reservation_arrival_minutes"]))
            if constraints.get("first_visit") and part.seq == items[0].seq:
                evidence_buffer += float(policy["evidence"]["first_visit_orientation_minutes"])
            if part.kind == "mobility":
                route = part.route or {}
                average_eta = _number(route.get("average_eta_min"))
                p95_eta = _number(route.get("p95_eta_min"))
                if average_eta is not None and p95_eta is not None and p95_eta >= average_eta:
                    evidence_buffer += max(0.0, p95_eta - average_eta)
                distance_m = _number(route.get("distance_m"))
                if constraints.get("mobility_ease") == "needs_rest" and distance_m is not None:
                    evidence_buffer += (distance_m / 30.0) * float(policy["evidence"]["mobility_rest_minutes_per_30m"])
            if "queue_minutes" in detail:
                queue = _number(detail["queue_minutes"])
                if part.kind == "mobility" or queue is None or queue > minutes:
                    reasons.append(f"{_name(part)}: 적힌 대기 시간이 맞지 않아요. 대기 시간은 방문 일정에만, 머무는 시간 안으로 적을 수 있어요")
                else:
                    known_queue += queue
            elif part.kind != "mobility":
                queue_unannotated += 1
            if part.kind == "mobility":
                travel += minutes
                route = part.route or {}
                options = route.get("options")
                # ★`[2026-10-03]` 고른 수단(`detail.option`)이 먼저 — 경로를 바꾼 항목의 소요를 옛 계획 수단과 비교하지 않는다(`itinerary_checks._planned_eta` 와 같다)
                chosen_option = (detail.get("option") or route.get("planned"))
                option = next((o for o in options if isinstance(o, dict) and o.get("id") == chosen_option), None) if isinstance(options, list) else None
                eta = _number(option.get("eta_min")) if option else None
                if eta is None or minutes < eta:
                    reasons.append(f"{_name(part)}: 이동 소요 시간을 모르거나 잡아 둔 이동 시간이 모자라요")
        for previous, current in zip(items, items[1:]):
            if previous.ends_at is None or previous.ends_at.tzinfo is None:
                continue
            gap = (current.starts_at - previous.ends_at).total_seconds() / 60
            if gap < 0:
                reasons.append(_pair(previous, current, "{first}{wa} {second}의 시간이 겹쳐요"))
            if previous.kind == "mobility" or current.kind == "mobility":
                continue
            if _place_id(previous) is not None and _place_id(previous) == _place_id(current):
                continue
            current_detail = current.detail or {}
            transfer_seconds = _number(current_detail.get("min_transfer_time_seconds"))
            transfer = (transfer_seconds / 60.0 if transfer_seconds is not None else
                        _number(current_detail.get("transfer_minutes_before")))
            if transfer is None or transfer > gap:
                reasons.append(_pair(previous, current, "{first}에서 {second}{ro} 가는 이동 시간을 모르거나 사이 간격이 모자라요"))
            else:
                transfers += transfer
        available = (window.ends_at - window.starts_at).total_seconds() / 60
        occupied = scheduled + transfers + window.buffer_minutes + evidence_buffer
        add(day, target, available, occupied, reasons, {
            "scheduled_minutes": scheduled, "transfer_minutes": transfers,
            "buffer_minutes": window.buffer_minutes, "evidence_buffer_minutes": evidence_buffer,
            "travel_minutes": travel + transfers,
            "known_queue_minutes": known_queue, "queue_unannotated_items": queue_unannotated,
            "unallocated_minutes": available - occupied})
    for day, reasons in outside.items():
        add(day, target, None, None, reasons)
    return {"density": results, "warnings": warnings}


# ── 자동 변경 판단에 쓰기 `[2026-10-03 사용자 지시 · D-019 개정]` ───────────────────────────
@dataclass(frozen=True)
class DayShift:
    """한 날의 밀도가 변경 때문에 **나빠진** 것. `kind`: `new_exceed`(목표 안 → 밖) · `worse`(이미 밖인데 더 밖으로) · `unmeasurable`(잴 수 있던 날을 못 재게 됨)."""

    date: str
    kind: str
    before: float | None
    after: float | None
    target: float | None

    @property
    def excess(self) -> float:
        """목표를 넘은 정도(비율) — 못 잰 날은 0 이라 고를 때 가장 뒤로 밀린다(`itinerary_fit` 가 따로 센다)."""
        return max(0.0, (self.after or 0.0) - (self.target or 0.0)) if self.kind != "unmeasurable" else 0.0

    def sentence(self) -> str:
        """고객에게 보이는 한 줄 — 「밀도」 같은 말 없이."""
        month, day = int(self.date[5:7]), int(self.date[8:10])
        when = f"{month}월 {day}일"
        pct = lambda value: f"{round(value * 100)}%"            # noqa: E731
        if self.kind == "unmeasurable":
            return f"{when} 하루 일정이 얼마나 빡빡한지 확인하지 못했어요"
        if self.kind == "worse":
            return f"{when} 일정이 이미 원하신 여유보다 빡빡한데 더 빡빡해졌어요(하루의 {pct(self.before)} → {pct(self.after)}, 목표 {pct(self.target)})"
        return f"{when} 일정이 원하신 여유보다 빡빡해졌어요(하루의 {pct(self.before)} → {pct(self.after)}, 목표 {pct(self.target)})"

    def as_dict(self) -> dict[str, Any]:
        return {"date": self.date, "kind": self.kind, "before": self.before, "after": self.after, "target": self.target}


def density_regressions(constraints: Mapping[str, Any], before: list[Part], after: list[Part]) -> list[DayShift]:
    """바꾸기 전(`before`)과 바꾼 뒤(`after`)의 하루 밀도를 같은 함수로 재서, 변경이 **나쁘게 만든 날**만 낸다.

    ★규칙(D-019 개정): ①잴 수 있던 날이 목표 안 → 밖: `new_exceed` ②이미 밖이던 날이 허용 오차(`travel.density.gate.worsen_tolerance`)보다 더 밖으로: `worse`
    ③잴 수 있던 날을 못 재게 됨: `unmeasurable`(결정 15 — 값을 모르는 상황을 변경이 만들지 않는다) ④바꾸기 전에 못 쟀던 날은 비교할 수 없어 탓하지 않는다.
    ⑤밀도 목표가 없는 여행(`constraints.density` 없음)은 아무것도 안 낸다. 잘못된 입력은 `measure_density` 가 `unmeasurable` 로 내는데 바꾸기 전에도 같아 ④로 넘어간다.
    """
    if "density" not in constraints:
        return []
    tolerance = float(get_guardrails().get("travel.density.gate.worsen_tolerance"))
    was = {row["date"]: row for row in measure_density(before, constraints)["density"] if row["date"]}
    shifts: list[DayShift] = []
    for row in measure_density(after, constraints)["density"]:
        prior = was.get(row["date"])
        if row["date"] is None or prior is None or prior["status"] == "unmeasurable":
            continue
        if row["status"] == "unmeasurable":
            shifts.append(DayShift(row["date"], "unmeasurable", prior["actual_density"], None, row["target_density"]))
        elif row["status"] == "exceeded" and prior["status"] == "ok":
            shifts.append(DayShift(row["date"], "new_exceed", prior["actual_density"], row["actual_density"], row["target_density"]))
        elif row["status"] == "exceeded" and row["actual_density"] - prior["actual_density"] > tolerance:
            shifts.append(DayShift(row["date"], "worse", prior["actual_density"], row["actual_density"], row["target_density"]))
    return shifts
