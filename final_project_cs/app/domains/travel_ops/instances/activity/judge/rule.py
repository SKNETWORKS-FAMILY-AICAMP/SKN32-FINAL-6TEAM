# -*- coding: utf-8 -*-
"""RuleJudge — **지금 규칙 판정을 그대로** 감싼다. 동작을 바꾸지 않는다.

★이 클래스는 새 판정을 만들지 않는다. `feasibility.py` · `weather.py` · `csv_places.py` 의 함수를 부르고
  그 결과를 `Verdict` 로 옮길 뿐이다. 섀도 모드의 비교 기준이 「지금 동작」이어야 해서다.
★규칙이 해석하지 않는 판정(운영시간 원문 · 실시간 운영 상태)은 `unknown` 이다 — 지금 코드도 판정에 넣지 않는다.
★import 는 함수 안에서 한다 — 4단계에서 `feasibility.py` 가 이 패키지를 부르면 순환이 생긴다.
"""
from __future__ import annotations

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


class RuleJudge:
    def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:  # noqa: ARG002 — 규칙은 Case 를 보지 않는다
        handler = {
            CLOSURE: self._closure,
            OPERATING_HOURS: self._not_interpreted,
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
    def _not_interpreted(request: JudgeRequest) -> Verdict:
        return Verdict(request.kind, UNKNOWN, "rule", basis="rule_does_not_interpret")

    @staticmethod
    def _weather_sensitive(request: JudgeRequest) -> Verdict:
        """장소명 → 분류 유형 순 — `FeasibilityMixin._guess_weather_sensitive` 의 추정 단계와 같다.
        ★DB 값(`places.weather_sensitive`)은 판정 대상이 아니다. 값이 있으면 부르는 쪽이 판정을 부르지 않는다."""
        from ..csv_places import weather_sensitive_from_lclssystm2
        from ..weather import WeatherMixin

        guessed = WeatherMixin._weather_sensitive_from_title(request.inputs.get("title"))
        basis = "title"
        if guessed is None:
            guessed = weather_sensitive_from_lclssystm2(request.inputs.get("lclssystm2"))
            basis = "category"
        if guessed is None:
            return Verdict(WEATHER_SENSITIVE, UNKNOWN, "rule", basis=None)
        return Verdict(WEATHER_SENSITIVE, "outdoor" if guessed else "indoor", "rule", basis=basis)

    @staticmethod
    def _disaster_effect(request: JudgeRequest) -> Verdict:
        """위급재난이 하나라도 있으면 막는다(관련성은 보지 않는다). 그 밖은 막지 않는다.

        ★`[2026-10-08]` 성립 판정은 위급재난을 이 계층에 보내지 않고 **판정 전에 막는다**(`_feasible_disaster`) —
          그래서 운영 경로에서 이 함수가 받는 문자는 위급재난이 아니고, 답은 늘 `no_effect` 다.
        """
        messages = request.inputs.get("messages") or []
        blocks = any(m.get("step") == "위급재난" for m in messages)
        return Verdict(DISASTER_EFFECT, "blocks" if blocks else "no_effect", "rule", basis="step_only")
