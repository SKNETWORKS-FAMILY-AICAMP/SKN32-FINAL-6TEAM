# -*- coding: utf-8 -*-
"""여행 시작 설문 — 받는 모양과, 지금 판정에 **실제로 쓰는 것**. `[2026-09-24]` D-020

★★받는 것과 쓰는 것을 나눈다. 설문 문항 가운데 **지금 판정에 쓰는 것은 둘뿐**이다.

    on_disruption  15번 「갑자기 일정이 꼬이면」 — replace(비슷한 곳으로) / ask_first(먼저 물어봐)
    pace           16번 「여유」 — relaxed / moderate / packed → 밀도 목표(`travel.survey.pace_to_density_level`)

  나머지(테마 · 여행자 구성 · 선호 이동수단 · 내국인 여부 · 우선순위 · 실내/실외 · 세부 테마)는
  **받아 두기만 한다.** 세부 선택지(예: 음식 → 맛·친절·청결, 활동 → 익스트림·힐링·DIY·쇼핑)와
  세부 테마는 **각 담당 팀이 정해서 알려 주기로 했다**(2026-09-24 회의). 그래서 그 값들은 코드에
  목록으로 박지 않고 문자열로 받는다. 팀이 목록을 주면 그때 좁힌다.
  ★받아 둔 값을 「반영했다」고 말하지 않는다 — 판정에 연결되기 전까지는 기록일 뿐이다.

★판(`version`)을 박는다. 문항이 바뀌어도 옛 여행의 답을 해석할 수 있어야 한다.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Iterable, Literal, Mapping
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import get_guardrails

KST = ZoneInfo("Asia/Seoul")
SURVEY_VERSION = "2026-09-24.v1"

Area = Literal["food", "activity", "mobility"]


class TripSurvey(BaseModel):
    """설문 한 벌. `extra="forbid"` — 모르는 문항은 조용히 흘리지 않고 거절한다."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["2026-09-24.v1"]
    # ── 판정에 쓰는 것 ─────────────────────────────────────────
    #: 15번. 기본은 replace — 지금까지의 동작(최고 안을 먼저 적용하고 알린다)과 같다
    on_disruption: Literal["replace", "ask_first"] = "replace"
    #: 16번. 없으면 밀도 목표를 설문에서 채우지 않는다
    pace: Literal["relaxed", "moderate", "packed"] | None = None
    # ── 받아 두기만 하는 것 (팀이 세부를 정하면 판정에 연결한다) ──────
    theme: str | None = None
    party: str | None = None                                   # 여행자 구성
    preferred_mobility: list[str] = Field(default_factory=list)
    domestic: bool | None = None                               # 내국인 여부
    priority: list[Area] = Field(default_factory=list)         # 우선순위1 — 앞이 더 중요하다
    priority_details: dict[Area, list[str]] = Field(default_factory=dict)   # 우선순위2 — 팀이 정할 값
    indoor_outdoor: dict[Literal["dining", "activity"],
                         Literal["indoor", "outdoor", "any"]] = Field(default_factory=dict)
    theme_details: list[str] = Field(default_factory=list)     # 세부 테마 — 팀이 정할 값


def _clock(text: str) -> time:
    hour, minute = str(text).split(":")
    return time(int(hour), int(minute))


def apply_survey(constraints: Mapping[str, Any], item_days: Iterable[date]) -> dict[str, Any]:
    """설문을 확인하고, **판정에 쓰는 몫**을 `constraints` 에 채운다. 새 dict 를 돌려준다.

    ★밀도(16번) — 사용자가 `density` 를 직접 줬으면 **그것이 이긴다.** 설문은 빈 곳만 채운다.
      - `density` 가 있는데 목표(level·target_density)가 없으면 → 목표만 채운다
      - `density` 가 아예 없으면 → 목표 + **기본 하루 활동 시간**(`travel.day_window`, 회의에서 정한
        08:00~22:00)으로 여행 날짜마다 창을 만든다. ★D-019 는 「분모는 사용자가 명시한 시간」이라고
        했다 — 이 기본값은 추측이 아니라 **팀이 정한 기본값**이고, 무엇을 채웠는지 `derived` 에 남긴다.
    ★잘못된 설문은 `pydantic.ValidationError` 로 올린다 — 부르는 쪽이 422 로 바꾼다.
    """
    out = dict(constraints)
    if "survey" not in out:
        return out
    survey = TripSurvey.model_validate(out["survey"])
    out["survey"] = survey.model_dump(mode="json")
    if survey.pace is None:
        return out

    guard = get_guardrails()
    level = guard.get("travel.survey.pace_to_density_level")[survey.pace]
    derived: dict[str, Any] = dict(out.get("derived") or {})
    density = out.get("density")
    if isinstance(density, dict):
        if density.get("level") is None and density.get("target_density") is None:
            out["density"] = {**density, "level": level}
            derived["density"] = f"목표를 설문 16번({survey.pace})에서 채웠다 → {level}"
    elif density is None:
        start = _clock(guard.get("travel.day_window.default_start"))
        end = _clock(guard.get("travel.day_window.default_end"))
        buffer = float(guard.get("travel.day_window.default_buffer_minutes"))
        days = sorted(set(item_days))
        if days:
            out["density"] = {"level": level, "days": {
                day.isoformat(): {"starts_at": datetime.combine(day, start, tzinfo=KST).isoformat(),
                                  "ends_at": datetime.combine(day, end, tzinfo=KST).isoformat(),
                                  "buffer_minutes": buffer}
                for day in days}}
            derived["density"] = (f"설문 16번({survey.pace}) → {level}, 하루 활동 시간은 팀 기본값 "
                                  f"{start:%H:%M}~{end:%H:%M} (사용자가 시간을 주지 않았다)")
    if derived:
        out["derived"] = derived
    return out


def on_disruption(constraints: Mapping[str, Any] | None) -> str:
    """이 여행이 일정이 꼬였을 때 어떻게 하길 원하나. 설문이 없으면 지금까지의 동작(replace)."""
    survey = (constraints or {}).get("survey") or {}
    return str(survey.get("on_disruption") or "replace")


__all__ = ["SURVEY_VERSION", "TripSurvey", "apply_survey", "on_disruption"]
