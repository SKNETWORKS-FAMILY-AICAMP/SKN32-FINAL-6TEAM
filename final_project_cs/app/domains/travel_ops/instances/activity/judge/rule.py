# -*- coding: utf-8 -*-
"""RuleJudge — **develop 판 활동 팀의 지금 규칙**을 판정 모양으로 감싼다. 새 판정을 만들지 않는다.

★`[2026-10-09]` 비교 기준을 role-activity 판 규칙에서 **develop 판 규칙**으로 바꿨다(D-CS-015). 평가(`eval/activity_judge`)의
  규칙 쪽 점수가 지금 서비스의 동작을 재야 해서다. 바뀐 것: ③ 실내외는 장소명 짐작 대신 관광공사 분류(`weather_from_class`),
  ④ 재난문자는 「위급재난이면 막음」 대신 공유 점검의 유형 목록 · 심각 낱말 + 재난 정지 기준(`safety.classify`).
  운영 경로의 섀도는 이 클래스가 아니라 팀이 실제로 낸 값을 비교 기준으로 쓴다(`team._shadow`).
★규칙이 해석하지 않는 판정(운영시간 원문 · 실시간 운영 상태)은 `unknown` 이다 — 지금 코드도 판정에 넣지 않는다.
★import 는 함수 안에서 한다.
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
        """관광공사 분류 — develop 규칙 `itinerary.weather_from_class`(확실한 대 · 중분류만). 장소명으로 짐작하지 않는다.
        대분류는 중분류 앞 두 글자다(`NA01` → `NA`). ★DB 값(`places.weather_sensitive`)이 있으면 부르는 쪽이 판정을 부르지 않는다."""
        from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class

        middle = (request.inputs.get("lclssystm2") or "").strip().upper() or None
        known = weather_from_class(middle[:2] if middle else None, middle)
        if known is None:
            return Verdict(WEATHER_SENSITIVE, UNKNOWN, "rule", basis=None)
        return Verdict(WEATHER_SENSITIVE, "outdoor" if known else "indoor", "rule", basis="tour_class")

    @staticmethod
    def _disaster_effect(request: JudgeRequest) -> Verdict:
        """develop 판 기준 — 공유 점검(`disaster_msg.judge` · `disruptions._disaster`)과 재난 정지(`safety.classify`).

        - 해제 · 훈련 문자는 막지 않는다.
        - 장소형 유형(통제 · 화재 …)이나 심각 낱말이 있으면 막는다. 재난 정지 대상(그날 · 여행 전체)도 막는다.
        - 날씨형 유형은 **실외에만** 영향이다 — 장소의 실내외(`weather_sensitive_raw`)를 모르면 `unknown`
          (develop 판은 그때 바꾸라고 단정하지 않고 먼저 묻는다).
        """
        from app.domains.travel_ops.components.planning.safety import classify
        from app.domains.travel_ops.ports.data_sources.disaster_msg import PLACE_KINDS, WEATHER_KINDS, _safety_words

        severe, exclude = _safety_words()
        sensitive = request.inputs.get("weather_sensitive_raw")
        value = "no_effect"
        for message in request.inputs.get("messages") or []:
            text, kind = str(message.get("text") or ""), message.get("kind")
            if "해제" in text or any(word in text for word in exclude):
                continue
            if (kind in PLACE_KINDS or any(word in text for word in severe)
                    or classify([{**message, "category": "disaster_msg"}]) is not None):
                return Verdict(DISASTER_EFFECT, "blocks", "rule", basis="shared_check_and_safety_stop")
            if kind in WEATHER_KINDS:
                if sensitive is True:
                    return Verdict(DISASTER_EFFECT, "blocks", "rule", basis="weather_kind_outdoor")
                if sensitive is None:
                    value = UNKNOWN
        return Verdict(DISASTER_EFFECT, value, "rule", basis="shared_check_and_safety_stop")
