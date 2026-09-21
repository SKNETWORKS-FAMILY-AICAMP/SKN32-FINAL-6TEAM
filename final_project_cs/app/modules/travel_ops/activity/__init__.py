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

import re
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import NextAction, TeamManifest, TeamResult, TeamTask

from .._base import TravelTeamBase


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
            "activity.submit_itinerary",   # 고객이 새로 말한 일정을 받는다 (승인 대기)
        ],
        accepted_case_types=["activity"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.booking", "read.policy", "read.place", "read.weather",
                       "read.disaster", "read.place_search"],
        knowledge_scope=["activity", "cancellation", "refund", "weather", "disaster"],
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
    def select_capability(intent: str | None, input_text: str) -> str | None:
        """`intent`에 따라 capability를 고른다. `registry.capability_for()`의 훅.

        ★INTENTS 5종(`itinerary_submit`·`incident_report`·`confirm_request`·
          `adjust_reject`·`other`)은 모두 `activity.*` 네임스페이스와 겹치지
          않는다 — 이 훅 없이는 `registry.py:115~119`의 이름 매칭이 항상 실패하고
          `default_capability`("check_feasible")만 선택된다.

        | intent           | capability              | 이유 |
        |------------------|-------------------------|------|
        | itinerary_submit | activity.submit_itinerary | 예약 없이 새 일정 제출 |
        | adjust_reject    | activity.propose_change   | 고객이 현재 상태를 거부하고 대안 요청 |
        | 나머지           | None → 기존 규칙          | check_feasible·check_cancelable 등 |
        """
        if intent == "itinerary_submit":
            return "activity.submit_itinerary"
        if intent == "adjust_reject":
            return "activity.propose_change"
        return None   # 신호가 없으면 기존 규칙(네임스페이스 → default)에 맡긴다

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

        # ★★여기서 먼저 갈린다. 아래 공통 경로는 **예약이 있다고 전제**하고
        #   `read.booking`부터 부른다(다음 줄) — 없으면 즉시 `unknown_예약
        #   내역`으로 escalate 한다. 일정 제출은 애초에 예약이 없는 게
        #   정상이라, 공통 경로를 타면 100% escalate 로 끝난다(실측
        #   2026-09-20). 그래서 예약을 찾기 **전에** 끊는다.
        if task.capability == "activity.submit_itinerary":
            return self._submit_itinerary(task, seen)

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
        # ★이미 시작됐거나 종료된 활동은 성립하지 않는다 — `remaining`이 음수면
        #   지금 이 순간 이미 과거다. 「성립합니다(-2.0시간)」는 틀린 답이다.
        if remaining < 0:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"이미 시작됐거나 종료된 활동입니다({-remaining:.1f}시간 경과).",
                decisions=[{"feasible": False, "reason": "already_started",
                            "hours_elapsed": round(-remaining, 1)}])

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

        # ★TourAPI 운영시간 원문(있으면). `read.place`가 신원이 해소된 장소만
        #   채운다(`read_tools._fill_operating`). `usetime_text`·`restdate_text`는
        #   자연어라 **전체를 boolean으로 해석하지 않는다** — 근거·안내 문구로
        #   전하는 게 기본이다. `[2026-09-20]` 딱 하나, "요청 요일이 정기휴무
        #   요일과 같은가"만 좁게 본다(`_weekday_closure_match`). 예외 조건
        #   ("단 공휴일과 겹치면 개방" 류)은 반영하지 않고, 반영 안 했다는
        #   사실을 안내문에 반드시 남긴다 — TourAPI가 「지금 여는가」를 답하지
        #   않는다는 사실(`answers_open_at_slot: False`) 자체는 안 바뀐다.
        operating = place.get("operating") if isinstance(place, dict) else None
        weekday_match: bool | None = None
        if operating is not None:
            evidence = self._evidence(task, source_id="read.place.operating",
                                      claim="TourAPI 운영시간·휴무 원문",
                                      value=operating, base=evidence)
            weekday_match = self._weekday_closure_match(
                operating.get("restdate_text"), booking.get("starts_at"))

        # ★기상은 **날씨가 판정에 들어가는 활동**에만 본다. 모르면 안 본다 —
        #   실내 활동에 기상 판정을 걸면 틀린 이유로 불가 판정이 난다.
        #
        # ★★`[2026-09-20]` `places.weather_sensitive`는 TourAPI가 안 주고
        #   (실내/실외 필드 자체가 없다), `places`에 실제로 쓰는 프로덕션
        #   경로도 없어서(`scripts/seed_travel.py`뿐) **실 데이터에서는 영원히
        #   NULL이다.** DB 값이 없을 때만 장소 **이름**의 단서로 추정한다
        #   (`_weather_sensitive_from_title`) — 확정이 아니라 근사이므로
        #   추정했다는 사실을 근거·안내문에 남긴다.
        weather_sensitive = place.get(self._WEATHER_SENSITIVE_KEY) if isinstance(place, dict) else None
        weather_sensitive_guessed = False
        if weather_sensitive is None and isinstance(place, dict):
            weather_sensitive = self._weather_sensitive_from_title(place.get("name"))
            weather_sensitive_guessed = weather_sensitive is not None

        forecast: dict[str, Any] | None = None
        if weather_sensitive:
            if weather_sensitive_guessed:
                evidence = self._evidence(
                    task, source_id="activity.weather_sensitive_from_title",
                    claim="장소명으로 추정한 실내·실외", value={
                        "name": place.get("name"), "weather_sensitive": weather_sensitive},
                    base=evidence)
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

        # ★재난문자. 날씨와 달리 **날씨 민감 여부와 무관하게 항상 본다** —
        #   재난은 실내외를 안 가린다. 좌표를 모르면(`place`가 없거나 좌표가
        #   비면) 소스가 알아서 「모름」을 돌려준다(`read_tools.disaster()`).
        #   `[미구현 2026-09-20]` 실제 클라이언트가 없어 지금은 항상 `None`이다
        #   — 배선과 판정 함수만 먼저 만들어 둔다.
        disaster = self._read(task, "read.disaster", {
            "latitude": place.get("latitude") if isinstance(place, dict) else None,
            "longitude": place.get("longitude") if isinstance(place, dict) else None,
            "at": booking.get("starts_at"),
        }, seen)
        disaster_blocks = False
        if disaster is not None:
            evidence = self._evidence(task, source_id="read.disaster",
                                      claim="재난문자 목록", value=disaster, base=evidence)
            disaster_blocks = self._disaster_blocks(disaster.get("messages"))

        warnings = [] if place is not None else ["장소·운영 정보를 확인하지 못했다"]
        # ★장소 정보가 없으면 운영 여부를 알 수 없다 — 성립을 단정하지 않는다.
        #   `place is None`이면 weekday_match·disaster_blocks와 무관하게 False.
        decisions: dict[str, Any] = {
            "feasible": place is not None and not (weekday_match or disaster_blocks),
            "place_confirmed": place is not None}
        # ★첫 문장이 뒤의 판정과 어긋나면 안 된다 — 이미 불가를 아는 순간에도
        #   "성립합니다"로 시작하지 않는다.
        if weekday_match:
            answer = (f"요청하신 시각(시작까지 {remaining:.1f}시간)은 운영시간 "
                      f"원문상 정기휴무 요일로 보입니다.")
        elif disaster_blocks:
            answer = (f"요청하신 시각(시작까지 {remaining:.1f}시간) 인근에 "
                      f"위급재난 문자가 확인됩니다.")
        elif place is None:
            answer = (f"장소·운영 정보를 확인하지 못했습니다(시작까지 {remaining:.1f}시간). "
                      f"운영 여부를 알 수 없어 성립 여부를 판정하지 않았습니다.")
        else:
            answer = f"확인한 범위에서는 성립합니다(시작까지 {remaining:.1f}시간)."
        if operating is not None:
            answer += " " + self._operating_note(operating)
            if weekday_match:
                # ★여기가 이 판정이 `feasible`을 바꾸는 유일한 자리다. 요일
                #   하나만 본 근사 판정이라는 것을 answer에 반드시 남긴다 —
                #   그래야 고객이 원문을 다시 확인할지 판단할 수 있다.
                answer += (" 단, 이 판단은 요일만 비교한 것이고 공휴일과 겹치는 "
                           "경우 같은 예외 조건은 반영하지 않았습니다 — 정확한 "
                           "개방 여부는 원문을 직접 확인하세요.")
                warnings.append(
                    "휴무 요일 대조는 예외 조건(공휴일 등)을 반영하지 않은 단순 비교다")
            else:
                warnings.append("TourAPI 운영시간·휴무는 원문이라 자동 판정에 쓰지 않았다")
            decisions["operating"] = {
                "usetime_text": operating.get("usetime_text"),
                "restdate_text": operating.get("restdate_text"),
                "source": operating.get("source"),
                "confirmed_at": operating.get("confirmed_at"),
                "weekday_match": weekday_match,
            }
        if forecast is not None:
            note, advisories = self._weather_note(forecast)
            answer += " " + note
            warnings.extend(advisories)
            if weather_sensitive_guessed:
                warnings.append(
                    "실내·실외를 장소명으로 추정해 날씨를 조회했다 — DB에 확인된 값이 아니다")
            decisions["weather"] = {
                "matched_hour": forecast.get("matched_hour"),
                "precipitation_probability": forecast.get("precipitation_probability"),
                "wind_speed_kmh": forecast.get("wind_speed_kmh"),
                "source": forecast.get("source"),
                "confirmed_at": forecast.get("confirmed_at"),
                "weather_sensitive_guessed_from_title": weather_sensitive_guessed,
            }
        if disaster is not None:
            answer += " " + self._disaster_note(disaster.get("messages"), disaster_blocks)
            if disaster_blocks:
                warnings.append(
                    "재난문자 판정은 지역·주제 관련성을 확인하지 않은 단순 등급 대조다")
            decisions["disaster"] = {
                "messages": [
                    {"SN": m.get("SN"), "EMRG_STEP_NM": m.get("EMRG_STEP_NM"),
                     "DST_SE_NM": m.get("DST_SE_NM")}
                    for m in (disaster.get("messages") or []) if isinstance(m, dict)
                ],
                "blocks": disaster_blocks,
                "confirmed_at": disaster.get("confirmed_at"),
                "source": disaster.get("source"),
            }

        return self._result(
            task, outcome="completed", confidence=0.8, evidence=evidence,
            next_action=NextAction.RESPOND, answer=answer,
            decisions=[decisions], warnings=warnings)

    # ── 장소명으로 실내·실외 추정 ──────────────────────────────
    #: ★★`[2026-09-20]` DB가 모를 때(`weather_sensitive IS NULL`)만 쓰는
    #:  **근사**다. TourAPI가 실내/실외 필드를 안 주고, `places`를 실제로
    #:  채우는 프로덕션 경로가 없어서(`scripts/seed_travel.py`뿐) 실 데이터는
    #:  이 컬럼이 영원히 NULL이다 — 그래서 이름 단서로 추정하는 자리가 필요해졌다.
    #:  둘 다 걸리거나 아무것도 안 걸리면 **추정하지 않는다**(`None`) — 억지로
    #:  고르면 실내 활동에 기상을 걸어 틀린 이유로 판정이 흔들릴 수 있다.
    _OUTDOOR_TITLE_MARKERS = ("옥상", "광장", "공원", "거리", "운동장")
    _INDOOR_TITLE_MARKERS = ("홀", "실내", "전시실")
    #: "1F"·"3층"·"B1" 같은 층수 표기. ★★실내를 시사하는 가장 흔한 패턴이라
    #:  단어 목록과 별도로 정규식을 둔다.
    _FLOOR_PATTERN = re.compile(r"(?:\d+\s*(?:층|F)|B\d+)", re.IGNORECASE)

    @classmethod
    def _weather_sensitive_from_title(cls, name: str | None) -> bool | None:
        """장소명의 단서로 실내·실외를 **근사**한다. 모르면(단서 없음·상충) `None`.

        ★확정이 아니다 — 이름에 "공원"이 들어가도 그 공원 안의 실내 전시관일
          수 있다. 그래서 호출부(`_check_feasible`)가 이 함수를 쓴 사실을
          반드시 근거·경고에 남긴다.
        """
        if not name:
            return None
        outdoor = any(marker in name for marker in cls._OUTDOOR_TITLE_MARKERS)
        indoor = (any(marker in name for marker in cls._INDOOR_TITLE_MARKERS)
                  or cls._FLOOR_PATTERN.search(name) is not None)
        if outdoor and indoor:
            return None   # ★상충 — 예: "○○공원 전시홀". 억지로 고르지 않는다
        if outdoor:
            return True
        if indoor:
            return False
        return None

    # ── TourAPI 휴무 요일 대조 ─────────────────────────────────
    _WEEKDAY_NAMES = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")

    @classmethod
    def _weekday_closure_match(cls, restdate_text: str | None, at: Any) -> bool | None:
        """"매주 <요일> 휴무" 형태만 좁게 본다. ★예외 조건은 절대 반영하지 않는다.

        `[2026-09-20]` 이 프로젝트가 `restdate_text`를 통으로 파싱하지 않기로
        한 이유(자연어 예외 조건 — "단 공휴일과 겹치면 개방" 류)는 그대로
        유효하다. 이 함수는 그 경고를 무시하지 않는다 — **"정기휴무 요일과
        요청 요일이 같다"는 가장 단순한 사실 하나만** 본다. 예외 조건은 여기서
        안 보고, 호출부(`_check_feasible`)가 "반영 안 했다"는 사실을 안내문에
        반드시 남긴다.

        ★요일 텍스트가 없거나 시각을 모르면(`None`) 판정하지 않는다 — 모르면
          `None`을 돌려주고, 호출부는 이걸 "휴무 아님"으로 읽지 않는다.
        """
        if not restdate_text or not isinstance(at, datetime):
            return None
        when = at if at.tzinfo else at.replace(tzinfo=UTC)
        weekday_name = cls._WEEKDAY_NAMES[when.weekday()]
        return weekday_name in restdate_text and "휴무" in restdate_text

    # ── 재난문자 등급 대조 ─────────────────────────────────────
    #: ★**최고 등급 하나만** 막는다. `EMRG_STEP_NM` 셋(긴급재난·안전안내·
    #:  위급재난) 중 "위급재난"만 본다 — 나머지 둘은 근거로만 전하고
    #:  `feasible`을 안 바꾼다. wiki/teams/activity.md에 남겼던 미확보
    #:  ("긴급단계 몇 단계부터 막을지")를 가장 보수적인 쪽으로 좁혀서 닫았다.
    _BLOCKING_EMRG_STEPS = frozenset({"위급재난"})

    @classmethod
    def _disaster_blocks(cls, messages: list[dict[str, Any]] | None) -> bool:
        """재난문자 목록 중 **최고 등급 하나만** 본다. ★지역·주제 관련성은 안 본다.

        `MSG_CN`(메시지 본문)은 자연어라 통으로 해석하지 않는다 — TourAPI
        운영시간과 같은 이유다. 이 함수가 보는 건 `EMRG_STEP_NM` 하나뿐이고,
        그 문자가 실제로 이 장소·이 활동과 관련 있는지(재해구분·수신지역이
        정확히 맞는지)는 **확인하지 않는다.** 그 한계를 호출부가 안내문에
        반드시 남긴다.

        ★목록이 없거나 비어 있으면(`None`/`[]`) 막지 않는다 — 모르면
          막지 않는다.
        """
        if not messages:
            return False
        return any(isinstance(m, dict) and m.get("EMRG_STEP_NM") in cls._BLOCKING_EMRG_STEPS
                   for m in messages)

    @staticmethod
    def _disaster_note(messages: list[dict[str, Any]] | None, blocks: bool) -> str:
        """재난문자 목록을 **사실로만** 전한다. ★"관련 있다"고 단정하지 않는다."""
        if not messages:
            return "확인 범위 내 재난문자는 없습니다."
        steps = [m.get("EMRG_STEP_NM") for m in messages if isinstance(m, dict)]
        summary = f"재난문자 {len(messages)}건 확인(등급: {', '.join(s for s in steps if s)})."
        if not blocks:
            return summary + " 판정에 영향을 주는 등급은 아닙니다."
        return (summary + " 다만 이 판정은 등급만 본 것이고 지역·주제가 이 활동과 "
                "실제로 관련 있는지는 확인하지 않았습니다 — 메시지 원문을 직접 "
                "확인하세요.")

    # ── TourAPI 운영시간 문구 ──────────────────────────────────
    @staticmethod
    def _operating_note(operating: dict[str, Any]) -> str:
        """TourAPI 운영시간·휴무 **원문**을 사실로만 전한다.

        ★★**여기서 "연다/닫는다"를 만들지 않는다.** `tour_api.py.operating()`
          이 `parsed=False`·`answers_open_at_slot=False`로 이미 밝히고
          있다 — `restdate_text`가 "매주 화요일 휴무. 단 공휴일과 겹치면
          개방, 그 다음 첫 비공휴일이 휴무"처럼 조건이 겹칠 수 있어서
          규칙으로 펴면 하나 틀린 게 고객을 문 닫힌 곳 앞에 세운다.
        """
        usetime = operating.get("usetime_text")
        restdate = operating.get("restdate_text")
        parts = []
        if usetime:
            parts.append(f"운영시간 원문 \"{usetime}\"")
        if restdate:
            parts.append(f"휴무 원문 \"{restdate}\"")
        if not parts:
            return "TourAPI에서 운영시간 정보를 받지 못해 이 부분은 판정에 넣지 않았습니다."
        return ("TourAPI 확인: " + ", ".join(parts)
                + " (자동 해석하지 않았습니다 — 정확한 개방 여부는 원문을 직접 확인하세요).")

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

    # ── 일정 제출 — 예약 없이 시작한다 ─────────────────────────
    def _submit_itinerary(self, task: TeamTask, seen: set[str]) -> TeamResult:
        """고객이 새로 말한 일정 하나를 장소까지 찾아 제안으로 만든다.

        ★★기존 셋(①②③)과 전제가 다르다 — **예약이 없다.** `execute()`가
          이 capability만 `read.booking` 앞에서 분기시키는 이유다.

        ★고객 문장을 여기서 자연어로 해석하지 않는다. `requested_place_name`·
          `requested_activity_time`은 이미 추출돼 `current_state`에 있다고
          본다 — "문장에서 장소·시각을 뽑아내는 일"은 분류·추출 계층의 몫이고
          이 Team의 경계 밖이다(`ToolContext.from_pack`이 이미 `customer_id`를
          같은 자리에서 그렇게 읽는다).

        ★★Phase 1 — **여기서 `places`/`activities`에 쓰지 않는다.** 이 Team은
          side effect를 실행하지 않는다(팀 경계, 「이 Team이 하지 않는 것」).
          `ActionProposal`만 만들고, 승인 뒤 실제 반영은 아직 없는 실행
          계층(outbox worker가 `Phase 1`이라 명시적으로 스텁이다) 몫이다 —
          `activity.change`와 같은 수준에 맞춘다.
        """
        state = task.context.current_state
        place_name = state.get("requested_place_name")
        requested_at = state.get("requested_activity_time")
        evidence = list(task.context.evidence)

        if not place_name:
            return self._unknown(task, "요청 장소명", evidence)
        if not isinstance(requested_at, datetime):
            return self._unknown(task, "요청 시각", evidence)

        # ★고객이 실제로 제출한 값 자체를 근거로 남긴다. 검색이 실패해도
        #   (아래 `found is None`) 이 근거는 남는다 — "무엇을 물었는지"는
        #   찾았는지와 무관하게 항상 사실이다. `WAIT_FOR_INPUT`도 `answer`가
        #   있으면 근거가 최소 1건 있어야 한다(계약 검증) — 검색 결과가
        #   비었다고 근거까지 없어지면 안 된다.
        evidence = self._evidence(task, source_id="case.current_state",
                                  claim="고객이 제출한 일정",
                                  value={"requested_place_name": place_name,
                                         "requested_activity_time": requested_at.isoformat()},
                                  base=evidence)

        found = self._read(task, "read.place_search",
                           {"name": place_name, "kind": "activity"}, seen)
        evidence = self._evidence(task, source_id="read.place_search",
                                  claim="장소 후보 검색", value=found, base=evidence)

        if found is None:
            # ★애매함도 「모름」이다 — 정확일치 1건이 아니면 `read.place_search`가
            #   골라내지 않고 `None`을 준다(`tour_api.py.find()`). 이걸 사람이
            #   보는 escalate가 아니라 **고객에게 되묻는** WAIT_FOR_INPUT으로
            #   보낸다 — 이 계약 갈래의 첫 실사용 사례다(`required_input_schema`
            #   가 이전까지 선언만 되고 아무도 안 썼다).
            return self._result(
                task, outcome="completed", confidence=0.3, evidence=evidence,
                next_action=NextAction.WAIT_FOR_INPUT,
                answer=(f'"{place_name}"을(를) 찾지 못했거나 후보가 여럿이라 '
                        f"특정하지 못했습니다. 정확한 장소명이나 지역을 알려주세요."),
                required_input_schema={
                    "type": "object",
                    "properties": {"place_hint": {"type": "string",
                                                  "description": "정확한 장소명 또는 지역"}},
                    "required": ["place_hint"],
                },
                warnings=["장소를 특정하지 못했다 — 이름이 애매하거나 후보가 없다"])

        proposal = self._proposal(
            task, "activity.submit",
            {"place_name": place_name,
             "content_id": found.get("content_id"),
             "content_type_id": found.get("content_type_id"),
             "matched_title": found.get("matched_title"),
             "latitude": found.get("latitude"), "longitude": found.get("longitude"),
             "activity_time": requested_at.isoformat()},
            evidence, risk="low")
        return self._result(
            task, outcome="completed", confidence=0.7, evidence=evidence,
            next_action=NextAction.WAIT_FOR_APPROVAL,
            answer=(f'"{found.get("matched_title")}" 일정으로 등록 제안을 만들었습니다. '
                    f"승인 뒤 반영됩니다."),
            action_proposals=[proposal],
            decisions=[{"proposed": "activity.submit",
                       "matched_title": found.get("matched_title")}])

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
