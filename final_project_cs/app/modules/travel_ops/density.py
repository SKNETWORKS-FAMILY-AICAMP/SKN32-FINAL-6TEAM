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
from .itinerary_checks import Part

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
                                 "하루 일정이 연구 보정 프리셋의 목표를 초과합니다" if basis == "research_calibrated"
                                 else ("하루 일정이 추정 프리셋의 목표를 초과합니다" if basis == "estimated"
                                       else "하루 일정이 사용자가 지정한 목표를 초과합니다")),
                             "remedy": "누락되거나 잘못된 시간·이동 정보를 보완하세요" if reasons
                             else "고정 예약·식사·이동·완충시간을 유지하며 선택 활동 축소를 검토하세요"})

    try:
        spec = DensityInput.model_validate(constraints["density"])
        windows = sorted(spec.days.items(), key=lambda pair: pair[1].starts_at)
        for day, window in windows:
            if window.starts_at.date() != day or not timedelta(0) < window.ends_at - window.starts_at <= timedelta(days=1):
                raise ValueError("가용시간 시작 날짜 또는 길이가 잘못되었습니다")
        if any(a.ends_at > b.starts_at for (_, a), (_, b) in zip(windows, windows[1:])):
            raise ValueError("하루 가용시간 창이 서로 겹칩니다")
    except (ValidationError, ValueError) as exc:
        reason = "밀도 입력 형식이 잘못되었습니다" if isinstance(exc, ValidationError) else str(exc)
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
        if part.starts_at.tzinfo is None:
            outside.setdefault(None, []).append(f"항목 {part.seq}: 시작 시간대 누락")
            continue
        start = part.starts_at.astimezone(KST)
        day = next((d for d, w in windows if w.starts_at <= start < w.ends_at), None)
        if day is None:
            outside.setdefault(start.date(), []).append(f"항목 {part.seq}: 가용시간 창 없음 또는 창 밖 시작")
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
                reasons.append(f"항목 {part.seq}: 종료 누락·시간 순서 오류·가용시간 초과")
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
                    reasons.append(f"항목 {part.seq}: 대기 주석은 비이동 항목 소요 안의 유효한 시간이어야 합니다")
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
                    reasons.append(f"항목 {part.seq}: 경로 소요 누락 또는 이동시간 부족")
        for previous, current in zip(items, items[1:]):
            if previous.ends_at is None or previous.ends_at.tzinfo is None:
                continue
            gap = (current.starts_at - previous.ends_at).total_seconds() / 60
            if gap < 0:
                reasons.append(f"항목 {previous.seq}/{current.seq}: 시간 겹침")
            if previous.kind == "mobility" or current.kind == "mobility":
                continue
            if _place_id(previous) is not None and _place_id(previous) == _place_id(current):
                continue
            current_detail = current.detail or {}
            transfer_seconds = _number(current_detail.get("min_transfer_time_seconds"))
            transfer = (transfer_seconds / 60.0 if transfer_seconds is not None else
                        _number(current_detail.get("transfer_minutes_before")))
            if transfer is None or transfer > gap:
                reasons.append(f"항목 {previous.seq}/{current.seq}: 이동시간 누락 또는 간격 부족")
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
