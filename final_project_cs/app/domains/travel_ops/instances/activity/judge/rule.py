# -*- coding: utf-8 -*-
"""RuleJudge — **활동 팀의 지금 규칙**을 판정 모양으로 감싼다. 새 판정을 만들지 않는다.

평가(`eval/activity_judge`)의 규칙 쪽 점수가 **지금 서비스의 동작**을 재야 한다. 그래서 팀이 실제로 쓰는 함수를 그대로 부른다.
    ① 휴무      `closure_rules.read_closure`
    ② 운영시간  `place_hours.read_by_rule` 로 요일표를 펴고 `verdicts.hours_verdict` — 팀 · 원장(`ledger.state`)과 같다
    ③ 실내외    관광공사 분류(`itinerary.weather_from_class`). 요청에 분류 코드가 없으면 활동 장소 목록(CSV)에서 장소 이름으로 찾는다
               — 팀이 장소 행에 없을 때 관광공사 목록(`read.place_class`)에서 찾는 것과 같다
    ④ 재난      재난 정지 기준(`safety.classify`) 먼저, 그다음 장소의 구로 문자를 거르고 수정본 §8 분류표(`verdicts.disaster_verdict`)
⑤ 실시간 운영 상태는 규칙이 해석하지 않는다 — `unknown`.

★`[2026-10-12]` 10-09 판(코어 공유 점검의 유형 목록 · 심각 낱말을 흉내 낸 재난, 해석하지 않던 운영시간)이 10-11~12 의 팀 변경
  (§8 분류표 · D2-1 세 규칙 · 운영시간 규칙 판정)을 따라가지 못했다. 그대로 두면 규칙 정확도가 실제보다 낮게 나와 LLM 전환 판단(1.5)이
  틀어진다 — 1차 라벨 기준 재난 4/12(위험 2건)로 쟀는데, 같은 사례를 분류표로 재면 12/12 였다.
★바깥 데이터 코드(`ports/…`)를 부르지 않는다(팀 규율). 장소의 구 · 분류는 활동 팀 자신의 장소 목록에서 읽는다.
★모르면 모른다 — 장소를 못 찾아 구를 모르면, 구 단위 문자가 닿는지 모르므로 `unknown` 이다.
★import 는 함수 안에서 한다.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from .types import (
    CLOSURE,
    DISASTER_EFFECT,
    LIVE_STATUS,
    OPERATING_HOURS,
    UNKNOWN,
    WEATHER_SENSITIVE,
    JudgeContext,
    JudgeRequest,
    Verdict,
)

#: 재난문자가 구 이름 없이 닿는 지역 표기 — 시 전체 · 전국
WHOLE_REGIONS = ("서울특별시", "서울특별시 전체", "서울", "전국")


@lru_cache(maxsize=1)
def _lookup():
    from ..csv_places import CsvPlaceLookup

    return CsvPlaceLookup()


def place_facts(name: str | None) -> dict[str, Any]:
    """장소 이름 → 활동 장소 목록의 `{district, lcls1, lcls2}`. 못 찾으면 빈 dict(모름)."""
    lookup = _lookup()
    found = lookup.find(name or "") if name else None
    if not found:
        return {}
    row = lookup.find_by_content_id(found["content_id"]) or {}
    parts = str(found.get("address") or row.get("addr1") or "").split()
    return {"district": parts[1] if len(parts) > 1 and parts[1].endswith("구") else None,
            "lcls1": row.get("lclsSystm1"), "lcls2": row.get("lclsSystm2")}


def reaches(message: dict[str, Any], district: str | None) -> bool | None:
    """문자가 그 장소의 구에 닿나 — `read.disaster`(구 판정)가 하는 일. 시 전체 · 전국은 닿는다. 구를 모르면 `None`."""
    regions = [str(r).strip() for r in message.get("regions") or []]
    if any(r in WHOLE_REGIONS for r in regions):
        return True
    if district is None:
        return None
    return any(district in r for r in regions)


def _outdoor_from_class(lcls1: Any, lcls2: Any) -> bool | None:
    from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class

    middle = (str(lcls2 or "").strip().upper()) or None
    large = (str(lcls1 or "").strip().upper()) or (middle[:2] if middle else None)
    return weather_from_class(large, middle)


class RuleJudge:
    def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:  # noqa: ARG002 — 규칙은 Case 를 보지 않는다
        handler = {
            CLOSURE: self._closure,
            OPERATING_HOURS: self._operating_hours,
            WEATHER_SENSITIVE: self._weather_sensitive,
            DISASTER_EFFECT: self._disaster_effect,
            LIVE_STATUS: self._not_interpreted,
        }[request.kind]
        return handler(request)

    @staticmethod
    def _closure(request: JudgeRequest) -> Verdict:
        """`closure_rules.read_closure` — 성립 판정의 규칙 휴무 판정과 같다(fix/activity-closure-rule).

        `basis` 는 규칙이 어떻게 정했나(`weekly` · `nth_weekday` · `date` · `festive` · `holiday` · `unparsed` …),
        `quotes` 는 맞은 절, `metrics["needs_caveat"]` 는 공휴일 예외를 확인하지 못해 단서가 필요한지다.
        """
        from datetime import date

        from ..closure_rules import read_closure

        raw = request.inputs.get("holidays_raw") or {}
        holidays = {date.fromisoformat(day): info for day, info in raw.items()}
        result = read_closure(request.inputs.get("restdate_text"), request.inputs.get("starts_at_raw"),
                              holidays.get)
        value = {True: "closed", False: "not_closed"}.get(result.value, UNKNOWN)
        return Verdict(CLOSURE, value, "rule", basis=result.reason,
                       quotes=[result.quote] if result.quote else [],
                       metrics={"needs_caveat": result.needs_caveat})

    @staticmethod
    def _operating_hours(request: JudgeRequest) -> Verdict:
        """운영시간 원문 → 규칙 요일표 → `hours_verdict`(팀 · 원장과 같다). 규칙으로 못 펴면 `unknown`
        (그곳은 sLLM 이 미리 펴 둔 요일표를 팀이 쓴다 — `scripts/activity/read_hours.py`)."""
        from app.domains.travel_ops.components.places.place_hours import read_by_rule

        from ..verdicts import hours_verdict

        at = request.inputs.get("starts_at_raw")
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        usetime = request.inputs.get("usetime_text")
        if not isinstance(at, datetime) or not usetime:
            return Verdict(OPERATING_HOURS, UNKNOWN, "rule", basis="no_time_or_text")
        read = read_by_rule(usetime, None)
        week = read.week if read is not None else {}
        hours = {"known": bool(week), "attributes": {"hours_week": week} if week else {},
                 "usetime_text": usetime, "restdate_text": None}
        within = hours_verdict(hours, at)["within_hours"]
        value = {True: "within", False: "outside"}.get(within, UNKNOWN)
        return Verdict(OPERATING_HOURS, value, "rule", basis="rule_week" if week else "rule_cannot_read",
                       quotes=list(read.quotes) if read is not None and value != UNKNOWN else [])

    @staticmethod
    def _not_interpreted(request: JudgeRequest) -> Verdict:
        return Verdict(request.kind, UNKNOWN, "rule", basis="rule_does_not_interpret")

    @staticmethod
    def _weather_sensitive(request: JudgeRequest) -> Verdict:
        """관광공사 분류 — `itinerary.weather_from_class`(확실한 대 · 중분류만). 장소명으로 짐작하지 않는다.
        요청에 분류가 없으면 장소 목록에서 이름으로 찾은 분류를 쓴다(팀의 `read.place_class` 와 같은 자리)."""
        middle = (request.inputs.get("lclssystm2") or "").strip().upper() or None
        large = middle[:2] if middle else None
        basis = "tour_class"
        if middle is None:
            facts = place_facts(request.inputs.get("title"))
            large, middle, basis = facts.get("lcls1"), facts.get("lcls2"), "tour_class_from_catalog"
        known = _outdoor_from_class(large, middle)
        if known is None:
            return Verdict(WEATHER_SENSITIVE, UNKNOWN, "rule", basis=None)
        return Verdict(WEATHER_SENSITIVE, "outdoor" if known else "indoor", "rule", basis=basis)

    @staticmethod
    def _disaster_effect(request: JudgeRequest) -> Verdict:
        """재난 정지 기준(`safety.classify` — 팀 `_safety_event`) → 장소의 구로 거른 문자 → §8 분류표(`disaster_verdict`).
        실내외는 요청 값(`weather_sensitive_raw`), 없으면 장소 목록의 분류."""
        from app.domains.travel_ops.components.planning.safety import classify

        from ..verdicts import disaster_verdict

        messages = [m for m in request.inputs.get("messages") or [] if isinstance(m, dict)]
        name = request.inputs.get("place_name")
        facts = place_facts(name)
        kept, unsure = [], False
        for message in messages:
            hit = reaches(message, facts.get("district"))
            if hit is None:
                unsure = True
            elif hit:
                kept.append(message)
        if any(classify([{**m, "category": "disaster_msg"}]) is not None for m in kept):
            return Verdict(DISASTER_EFFECT, "blocks", "rule", basis="safety_stop")
        outdoor = request.inputs.get("weather_sensitive_raw")
        if outdoor is None:
            outdoor = _outdoor_from_class(facts.get("lcls1"), facts.get("lcls2"))
        at = request.inputs.get("starts_at_raw")
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        verdict = disaster_verdict(kept, outdoor=outdoor, at=at if isinstance(at, datetime) else None, place_name=name)
        if verdict["blocks"]:
            return Verdict(DISASTER_EFFECT, "blocks", "rule", basis="impact_table")
        if verdict["ask_outdoor"]:
            return Verdict(DISASTER_EFFECT, UNKNOWN, "rule", basis="outdoor_unknown")
        if unsure:
            return Verdict(DISASTER_EFFECT, UNKNOWN, "rule", basis="district_unknown")
        return Verdict(DISASTER_EFFECT, "no_effect", "rule", basis="impact_table")
