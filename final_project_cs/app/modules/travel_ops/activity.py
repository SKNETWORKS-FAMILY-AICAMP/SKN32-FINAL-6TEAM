# -*- coding: utf-8 -*-
"""Activity Team — 활동 예약이 지금 성립하는지 판정한다.

대상은 **활동 그 자체**다 — 골프(티타임)·수상레저·스키 같은 레저뿐 아니라
경복궁 관람처럼 시각이 정해진 활동도 포함한다.

★**판정은 계산으로 한다. LLM 을 부르지 않는다**(v10 §4-D).
  취소 기한·인원·운영시간·날씨 조건은 전부 계산이다. 대안 생성(③)만 LLM 이고
  그건 별도 capability 로 나온다.

★**「모름」을 「없음」으로 읽지 않는다.** 도구가 `None` 을 돌려주면 그건
  "그런 게 없다" 가 아니라 "확인 못 했다" 이고, 그때는 확정 답을 만들지 않는다.
  커머스에서 이걸 빠뜨려 반품 제한을 안 보고 "정책 근거상 가능합니다" 라고
  답한 결함이 있었다.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import NextAction, TeamManifest, TeamResult, TeamTask

from ._base import TravelTeamBase


class ActivityTeam(TravelTeamBase):
    manifest = TeamManifest(
        team_id="activity",
        display_name="Activity Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=[
            "activity.check_cancelable",   # 지금 취소할 수 있나 · 위약금은 얼마인가
            "activity.check_feasible",     # 이 시각에 이 활동이 성립하나
            "activity.propose_change",     # 대안을 제안한다 (승인 대기)
        ],
        accepted_case_types=["activity"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.booking", "read.policy", "read.place", "read.weather"],
        knowledge_scope=["activity", "cancellation", "refund", "weather"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-09",
        default_capability="activity.check_feasible",
    )

    #: 날씨가 판정에 들어가는 활동만 기상을 본다. ★실내 활동에 기상 감시를 걸면
    #:  감시 소스가 둘로 갈려 Team 경계가 흐려진다(v10 §5 「객체 종류별로 나눈다」).
    #:  이 판단은 `read.place` 가 돌려주는 속성으로 하고, 모르면 **보지 않는다**.
    _WEATHER_SENSITIVE_KEY = "weather_sensitive"

    @staticmethod
    def _hours_until(when: Any) -> float | None:
        """예약 시각까지 남은 시간. 모르면 `None`."""
        if not isinstance(when, datetime):
            return None
        reference = when if when.tzinfo else when.replace(tzinfo=UTC)
        return (reference - datetime.now(UTC)).total_seconds() / 3600

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked

        seen: set[str] = set()
        booking = self._read(task, "read.booking", {"case_id": str(task.case_id)}, seen)
        policy = self._read(task, "read.policy", {"query": task.input_text}, seen)

        evidence = self._evidence(task, source_id="read.booking",
                                  claim="예약 내역", value=booking)
        evidence = self._evidence(task, source_id="read.policy",
                                  claim="취소·환급 규정", value=policy, base=evidence)

        # ★예약을 모르면 아무것도 판정하지 않는다. 여기서 지어내면 그 오류가
        #   그대로 고객 답변까지 간다.
        if booking is None:
            return self._unknown(task, "예약 내역", evidence)
        if not policy:
            return self._unknown(task, "취소·환급 규정", evidence)

        remaining = self._hours_until(booking.get("starts_at"))
        if remaining is None:
            return self._unknown(task, "예약 시각", evidence)

        if task.capability == "activity.check_cancelable":
            return self._check_cancelable(task, booking, policy, remaining, evidence)
        if task.capability == "activity.check_feasible":
            return self._check_feasible(task, booking, policy, remaining, evidence, seen)
        return self._propose_change(task, booking, evidence)

    # ── ① 검증 — 계산으로만 ────────────────────────────────────
    def _check_cancelable(self, task: TeamTask, booking: dict, policy: Any,
                          remaining: float, evidence: list) -> TeamResult:
        deadline = self._policy_hours(policy, "cancel_deadline_hours")
        if deadline is None:
            return self._unknown(task, "취소 기한", evidence)

        if remaining < deadline:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"취소 기한이 지났습니다. 규정상 시작 {deadline:g}시간 전까지 "
                       f"취소할 수 있는데 지금은 {remaining:.1f}시간 남았습니다.",
                decisions=[{"cancelable": False, "hours_remaining": round(remaining, 1),
                            "deadline_hours": deadline}])

        penalty = self._penalty_rate(policy, remaining)
        if penalty is None:
            # ★위약금율을 모르면 **금액을 만들지 않는다.** 취소 가능 여부만 말한다.
            return self._result(
                task, outcome="completed", confidence=0.7, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"취소 기한 안입니다(시작까지 {remaining:.1f}시간). "
                       f"다만 이 구간의 위약금율은 확인되지 않아 금액은 안내하지 못합니다.",
                decisions=[{"cancelable": True, "hours_remaining": round(remaining, 1),
                            "penalty_rate": None}],
                warnings=["위약금율을 확인하지 못했다 — 금액을 만들지 않았다"])

        return self._result(
            task, outcome="completed", confidence=1.0, evidence=evidence,
            next_action=NextAction.RESPOND,
            answer=f"취소할 수 있습니다. 시작까지 {remaining:.1f}시간 남았고 "
                   f"규정상 위약금율은 {penalty:.0%}입니다.",
            decisions=[{"cancelable": True, "hours_remaining": round(remaining, 1),
                        "penalty_rate": penalty}])

    def _check_feasible(self, task: TeamTask, booking: dict, policy: Any,
                        remaining: float, evidence: list, seen: set[str]) -> TeamResult:
        party = booking.get("party_size")
        capacity = booking.get("capacity")
        if party is not None and capacity is not None and party > capacity:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"인원이 정원을 넘습니다 — 신청 {party}명, 정원 {capacity}명.",
                decisions=[{"feasible": False, "reason": "party_over_capacity"}])

        place = self._read(task, "read.place", {"place_id": booking.get("place_id")}, seen)
        evidence = self._evidence(task, source_id="read.place",
                                  claim="장소·운영 정보", value=place, base=evidence)

        # ★기상은 **날씨가 판정에 들어가는 활동**에만 본다. 모르면 안 본다 —
        #   실내 활동에 기상 판정을 걸면 틀린 이유로 불가 판정이 난다.
        forecast: dict[str, Any] | None = None
        if isinstance(place, dict) and place.get(self._WEATHER_SENSITIVE_KEY):
            forecast = self._read(task, "read.weather", {
                "place_id": booking.get("place_id"),
                # ★좌표와 시각을 **넘겨야** 답이 온다. "어디인지 모르는 곳의
                #   날씨" 는 없다 — 좌표가 없으면 소스가 「모름」을 돌려준다.
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "at": booking.get("starts_at"),
            }, seen)
            evidence = self._evidence(task, source_id="read.weather",
                                      claim="기상 예보", value=forecast, base=evidence)
            if forecast is None:
                return self._unknown(task, "기상 정보", evidence)

        warnings = [] if place is not None else ["장소·운영 정보를 확인하지 못했다"]
        decisions: dict[str, Any] = {"feasible": True,
                                     "place_confirmed": place is not None}
        answer = f"확인한 범위에서는 성립합니다(시작까지 {remaining:.1f}시간)."
        if place is None:
            answer += " 운영 정보는 확인되지 않아 그 부분은 판정하지 않았습니다."
        if forecast is not None:
            note, advisories = self._weather_note(forecast)
            answer += " " + note
            warnings.extend(advisories)
            decisions["weather"] = {
                "matched_hour": forecast.get("matched_hour"),
                "precipitation_probability": forecast.get("precipitation_probability"),
                "wind_speed_kmh": forecast.get("wind_speed_kmh"),
                "source": forecast.get("source"),
                "confirmed_at": forecast.get("confirmed_at"),
            }

        return self._result(
            task, outcome="completed", confidence=0.8, evidence=evidence,
            next_action=NextAction.RESPOND, answer=answer,
            decisions=[decisions], warnings=warnings)

    # ── 기상 문구 ──────────────────────────────────────────────
    @staticmethod
    def _weather_note(forecast: dict[str, Any]) -> tuple[str, list[str]]:
        """예보를 **사실로만** 전한다.

        ★★**여기서 「불가」를 만들지 않는다.** 강수확률이 얼마부터 취소·순연
          인지는 **운영 규정**이 정할 일이고, 그 규정은 `read.policy` 가 대야
          한다. 가드레일의 수치는 판정 기준이 아니라 **주의 문구 기준**이며,
          측정이 아니라 우리가 고른 값이다. 그걸로 확정 답을 만들면
          근거 없는 확정이 된다(CLAUDE.md §0.1).

        ★예보를 관찰처럼 말하지 않는다 — 「조회 시각」과 「예보 대상 시각」을
          둘 다 밝힌다(v10 §4-D).
        """
        from app.core.settings import get_guardrails

        guardrails = get_guardrails()
        pop = forecast.get("precipitation_probability")
        wind = forecast.get("wind_speed_kmh")
        hour = forecast.get("matched_hour")

        parts = []
        if pop is not None:
            parts.append(f"강수확률 {pop}%")
        if wind is not None:
            parts.append(f"풍속 {wind}km/h")
        if not parts:
            # ★값이 하나도 없으면 「예보를 봤다」고 말하지 않는다.
            return ("기상 예보 값을 읽지 못해 날씨는 판정에 넣지 않았습니다.",
                    ["기상 예보에 필요한 값이 비어 있었다"])

        note = (f"예보상 {hour} 기준 {', '.join(parts)}입니다"
                f"(예보이며 현장 확인이 아닙니다).")

        advisories: list[str] = []
        pop_limit = guardrails.get("travel.weather.advisory_precipitation_probability")
        wind_limit = guardrails.get("travel.weather.advisory_wind_speed_kmh")
        if pop is not None and pop >= pop_limit:
            advisories.append(
                f"강수확률 {pop}% — 주의 기준({pop_limit}%) 이상이다. "
                f"취소·순연 기준은 운영 규정에서 확인해야 한다")
        if wind is not None and wind >= wind_limit:
            advisories.append(
                f"풍속 {wind}km/h — 주의 기준({wind_limit}km/h) 이상이다. "
                f"취소·순연 기준은 운영 규정에서 확인해야 한다")
        if advisories:
            note += " 다만 취소·순연 기준은 규정에서 확인되지 않아 판정하지 않았습니다."
        return note, advisories

    # ── ③ 재계획 — 제안까지만 ──────────────────────────────────
    def _propose_change(self, task: TeamTask, booking: dict,
                        evidence: list) -> TeamResult:
        """★대안을 실행하지 않는다. `ActionProposal` 로 승인 대기에 올린다."""
        proposal = self._proposal(
            task, "activity.change",
            {"booking_id": booking.get("booking_id"), "reason": task.input_text},
            evidence)
        return self._result(
            task, outcome="completed", confidence=0.6, evidence=evidence,
            next_action=NextAction.WAIT_FOR_APPROVAL,
            answer="변경 제안을 만들었습니다. 승인 뒤에 진행됩니다.",
            action_proposals=[proposal],
            decisions=[{"proposed": "activity.change"}])

    # ── 규정 읽기 ──────────────────────────────────────────────
    @staticmethod
    def _policy_hours(policy: Any, key: str) -> float | None:
        for chunk in policy if isinstance(policy, list) else []:
            if isinstance(chunk, dict) and chunk.get(key) is not None:
                try:
                    return float(chunk[key])
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _penalty_rate(policy: Any, remaining: float) -> float | None:
        """남은 시간 구간별 위약금율. 규정에 구간이 없으면 `None`(모름)."""
        best: float | None = None
        for chunk in policy if isinstance(policy, list) else []:
            if not isinstance(chunk, dict):
                continue
            table = chunk.get("penalty_by_hours")
            if not isinstance(table, dict):
                continue
            for hours, rate in table.items():
                try:
                    if remaining < float(hours):
                        value = float(rate)
                        best = value if best is None else max(best, value)
                except (TypeError, ValueError):
                    continue
        return best
