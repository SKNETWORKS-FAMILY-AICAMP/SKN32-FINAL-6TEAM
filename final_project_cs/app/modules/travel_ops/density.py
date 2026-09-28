"""D-019: 입력으로 확인 가능한 시간만 측정하는 관측용 밀도. 거절/재조정 없음."""
from __future__ import annotations

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
                option = next((o for o in options if isinstance(o, dict) and o.get("id") == route.get("planned")), None) if isinstance(options, list) else None
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
