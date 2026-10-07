# -*- coding: utf-8 -*-
"""성립 판정 — 이 시각에 이 활동이 성립하는가(운영시간·재난문자·기상·대체 장소).

★`team.py` 에서 옮겼다(동작 변경 없음). 계산으로만 판정하고 LLM 을 부르지 않는다.

★`[2026-10-06]` 글을 해석하는 판정 넷(휴무 · 운영시간 · 실내외 · 재난문자)과 실시간 운영 상태는 **판정 계층**
  (`judge/`, D-CS-008)을 거친다. 판정 LLM 이 없거나 모드가 `rule` 이면 판정 계층은 지금 규칙 그대로다.
  섀도 모드에서도 고객 답변 · `decisions` · 실패 코드는 규칙 결과로 만든다 — LLM 결과가 이 파일의 출력에
  들어가는 것은 판정이 `source == "llm"` 일 때(LLM 모드)뿐이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.contracts import NextAction, TeamResult, TeamTask

from . import failure_codes as fc
from .closure_rules import holiday_dates_needed, read_closure
from .csv_places import CsvPlaceLookup as _CsvPlaceLookup
from .judge import JudgeContext, RuleJudge, Verdict, build_judge
from .judge import requests as judge_requests

_csv_lookup = _CsvPlaceLookup()


@dataclass
class _Check:
    """한 번의 성립 판정이 단계(운영시간 · 재난 · 기상 · 대체 장소)를 지나며 함께 쌓는 값."""

    task: TeamTask
    booking: dict
    place: dict
    seen: set[str]
    evidence: list
    answer_parts: list[str]
    decisions: dict[str, Any] = field(default_factory=lambda: {"feasible": True, "place_confirmed": True})
    warnings: list[str] = field(default_factory=list)
    #: ★`[2026-10-06]` 판정 계층용 — 시작까지 남은 시간 · 실내외 결과 · 판정기 · CSV 행(한 번만 찾는다).
    remaining: float | None = None
    weather_sensitive: bool | None = None
    judge: Any = None
    _csv_row: Any = field(default=None, repr=False)
    _csv_looked: bool = field(default=False, repr=False)

    @property
    def csv_row(self) -> dict[str, str] | None:
        """장소의 `source_content_id` 로 찾은 CSV(`activity_total_data.csv`) 행. 없으면 `None`."""
        if not self._csv_looked:
            self._csv_looked = True
            content_id = self.place.get("source_content_id") if isinstance(self.place, dict) else None
            self._csv_row = _csv_lookup.find_by_content_id(str(content_id)) if content_id else None
        return self._csv_row

    @property
    def lat(self) -> Any:
        return self.place.get("latitude") if isinstance(self.place, dict) else None

    @property
    def lng(self) -> Any:
        return self.place.get("longitude") if isinstance(self.place, dict) else None


class FeasibilityMixin:
    #: 날씨가 판정에 들어가는 활동만 기상을 본다. ★실내 활동에 기상 감시를 걸면
    #:  감시 소스가 둘로 갈려 Team 경계가 흐려진다(v10 §5 「객체 종류별로 나눈다」).
    #:  이 판단은 `read.place` 가 돌려주는 속성으로 하고, 모르면 **보지 않는다**.
    _WEATHER_SENSITIVE_KEY = "weather_sensitive"

    #: ★`[2026-10-06]` 판정 모드 · 섀도 실행기를 고정한다(시험용). `None` 이면 모드는 설정을, 실행기는 기본 스레드 풀을 쓴다.
    #:  설정은 판정 LLM(`judge_llm`)이 있을 때만 읽는다 — 없으면 언제나 규칙이고 설정 파일이 없어도 돈다.
    judge_mode: str | None = None
    judge_runner: Any | None = None

    def _build_activity_judge(self) -> Any:
        llm = getattr(self, "judge_llm", None)
        if llm is None:
            return RuleJudge()
        mode = self.judge_mode
        if mode is None:
            from app.core.settings import get_settings
            mode = get_settings().activity_judge_mode
        return build_judge(mode, llm, runner=self.judge_runner, sink=getattr(self, "judge_shadow_sink", None))

    def _judge(self, ck: "_Check", request: Any) -> Verdict:
        if ck.judge is None:
            ck.judge = self._build_activity_judge()
        return ck.judge.judge(JudgeContext(case_id=ck.task.case_id, capability=ck.task.capability,
                                           run_id=ck.task.run_id, tenant_id=ck.task.context.tenant_id), request)

    def _llm_evidence(self, ck: "_Check", verdict: Verdict, claim: str) -> None:
        """LLM 판정(LLM 모드)일 때만 근거로 남긴다 — 판정 · 인용 · 출처 URL. 웹 본문은 저장하지 않는다."""
        ck.evidence = self._evidence(
            ck.task, source_id=f"activity.judge.{verdict.kind}", claim=claim,
            value={"verdict": verdict.value, "quotes": verdict.quotes,
                   "citations": [{"url": c.get("url"), "published_at": c.get("published_at")}
                                 for c in verdict.citations],
                   "confidence": verdict.confidence},
            base=ck.evidence)

    def _check_feasible(self, task: TeamTask, booking: dict, policy: Any,  # noqa: ARG002
                        remaining: float | None, evidence: list, seen: set[str]) -> TeamResult:
        early = self._feasible_early_exit(task, booking, remaining, evidence)
        if early is not None:
            return early

        place = self._read(task, "read.place", {"place_id": booking.get("place_id")}, seen)
        evidence = self._evidence(task, source_id="read.place",
                                  claim="장소·운영 정보", value=place, base=evidence)

        # ★결함 1 수정(2026-09-21): 장소를 모르면 성립을 단정하지 않는다.
        if place is None:
            return self._result(
                task, outcome="completed", confidence=0.5, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer="장소·운영 정보가 확인되지 않아 판정하지 않았습니다.",
                decisions=[{"feasible": False, "status": "insufficient_info", "place_confirmed": False,
                            "failure_code": self._record_failure(task, fc.PLACE_UNKNOWN)}],
                warnings=["장소·운영 정보를 확인하지 못했다"])

        ck = _Check(task=task, booking=booking, place=place, seen=seen, evidence=evidence,
                    answer_parts=[f"확인한 범위에서는 성립합니다(시작까지 {remaining:.1f}시간)."],
                    remaining=remaining)
        self._feasible_operating(ck)
        self._feasible_disaster(ck)
        self._feasible_weather(ck)
        self._feasible_live_status(ck)
        self._feasible_alternatives(ck)

        return self._result(
            task, outcome="completed", confidence=0.8, evidence=ck.evidence,
            next_action=NextAction.RESPOND, answer=" ".join(ck.answer_parts),
            decisions=[ck.decisions], warnings=ck.warnings)

    def _feasible_early_exit(self, task: TeamTask, booking: dict, remaining: float | None,
                             evidence: list) -> TeamResult | None:
        """장소를 읽기 전에 끝나는 갈래 — 이미 시작됨 · 정원 초과 · 시각 모름. 해당 없으면 `None`."""
        # ★결함 2 수정(2026-09-21): 이미 시작된 예약은 성립 판정 없이 즉시 반환.
        #   `remaining is None` = 시각을 모른다(아래 「정보 부족」에서 다룬다).
        if remaining is not None and remaining < 0:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"이미 시작됐거나 종료된 활동입니다 — {-remaining:.1f}시간 전에 시작됐습니다.",
                decisions=[{"feasible": False, "status": "problem", "reason": "already_started",
                            "failure_code": self._record_failure(task, fc.ALREADY_STARTED),
                            "hours_elapsed": round(-remaining, 1)}])

        party = booking.get("party_size")
        capacity = booking.get("capacity")
        if party is not None and capacity is not None and party > capacity:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"인원이 정원을 넘습니다 — 신청 {party}명, 정원 {capacity}명.",
                decisions=[{"feasible": False, "status": "problem", "reason": "party_over_capacity",
                            "failure_code": self._record_failure(task, fc.PARTY_OVER_CAPACITY)}])

        # ★시각을 모르면 휴무 요일·운영시간·재난·기상 어느 것도 잴 수 없다 — 「모름」을 「성립」으로 읽지 않는다.
        #   정원 초과처럼 시각 없이 확인된 불가(위)는 이미 `problem` 으로 나갔다. 대체 장소는 찾지 않는다.
        if remaining is None:
            return self._result(
                task, outcome="completed", confidence=0.5, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer="예약 시각을 확인하지 못해 성립 여부를 판정하지 않았습니다.",
                decisions=[{"feasible": False, "status": "insufficient_info", "reason": "time_unknown",
                            "failure_code": self._record_failure(task, fc.TIME_UNKNOWN)}],
                warnings=["예약 시각을 확인하지 못했다"])
        return None

    # ── ① 운영시간 ─────────────────────────────────────────
    def _feasible_operating(self, ck: "_Check") -> None:
        operating = ck.place.get("operating") if isinstance(ck.place, dict) else None
        if operating is None:
            return
        usetime = operating.get("usetime_text")
        restdate = operating.get("restdate_text")
        starts_at = ck.booking.get("starts_at")
        # ★`[2026-10-06]` 휴무는 판정 계층을 거친다(섀도·LLM 모드). 규칙 쪽은 `closure_rules.read_closure`
        #   (fix/activity-closure-rule)이고, 공휴일이 걸린 원문만 `read.holiday` 를 불러 그 결과를 요청에 싣는다 —
        #   규칙과 LLM 이 같은 공휴일 사실을 본다.
        closure = (self._judge(ck, judge_requests.closure(restdate, starts_at,
                                                           self._holiday_facts(ck, restdate, starts_at)))
                   if restdate is not None else None)
        wm = None if closure is None else {"closed": True, "not_closed": False}.get(closure.value)
        closure_by_llm = closure is not None and closure.source == "llm"
        # 규칙이 어떻게 정했나(`weekly` · `nth_weekday` · `date` …). LLM 판정이면 이유 문장 대신 `llm` 으로 적는다.
        closure_reason = "empty" if closure is None else ("llm" if closure_by_llm else closure.basis)
        ck.decisions["operating"] = {
            "usetime_text": usetime,
            "restdate_text": restdate,
            "weekday_match": wm,
            "closure_reason": closure_reason,
            "source": operating.get("source"),
            "confirmed_at": operating.get("confirmed_at"),
        }
        ck.evidence = self._evidence(ck.task, source_id="read.place.operating",
                                     claim="운영시간 원문", value=operating, base=ck.evidence)
        if closure_by_llm:
            ck.decisions["operating"]["closure_judged_by"] = "llm"
            self._llm_evidence(ck, closure, "휴무 원문 LLM 해석")
            if not closure.known:
                ck.warnings.append("휴무 원문을 LLM 으로 해석하지 못했다 — 휴무 여부는 판정에 넣지 않았다")
        if not usetime and not restdate:
            ck.answer_parts.append("운영시간 정보를 받지 못해 판정에 넣지 않았습니다.")
        elif wm is True and closure_by_llm:
            ck.decisions["feasible"] = False
            ck.answer_parts.append(
                f"다만 휴무 안내({restdate})에 따르면 이 날짜는 휴무입니다(원문 해석: «{closure.quotes[0]}»).")
            ck.warnings.append("휴무 원문을 LLM 으로 해석했다 — 인용이 원문에 있는 것을 확인했다")
        elif wm is True and closure_reason.startswith("weekly"):
            ck.decisions["feasible"] = False
            needs_caveat = bool(closure.metrics.get("needs_caveat"))
            caveat = " 공휴일과 겹치는 경우 등 예외가 있을 수 있습니다." if needs_caveat else ""
            ck.answer_parts.append(f"다만 정기휴무 요일({restdate})에 해당합니다.{caveat}")
            ck.warnings.append("운영시간 정기휴무 요일 일치 — 예외 조건은 반영하지 않았다" if needs_caveat
                               else "운영시간 정기휴무 요일 일치 — 공휴일 예외를 확인했다")
        elif wm is True:
            # 몇째 주 · 날짜 · 명절 · 공휴일 — 어느 구절에 걸렸는지 함께 보인다
            quote = closure.quotes[0] if closure.quotes else restdate
            ck.decisions["feasible"] = False
            ck.answer_parts.append(f"다만 휴무 안내({restdate}) 중 「{quote}」에 해당해 이 날은 휴무입니다.")
            ck.warnings.append(f"휴무 원문 판정({closure_reason}) — 「{quote}」")
        elif usetime and self._feasible_hours_by_llm(ck, usetime, restdate, starts_at):
            pass
        else:
            if wm is None and restdate:
                # ★못 읽은 원문을 「휴무 아님」으로 확정하지 않는다 — 전에는 확정했다(결함 2026-10-06_1610)
                ck.answer_parts.append("휴무 원문 일부를 읽지 못해 이 날의 휴무 여부는 확정하지 않았습니다.")
                ck.warnings.append(f"휴무 원문을 다 읽지 못했다({closure_reason}) — 휴무 여부를 확정하지 않았다")
            parts = []
            if usetime:
                parts.append(f"운영시간 {usetime}")
            if restdate:
                parts.append(f"휴무 {restdate}")
            if parts:
                ck.answer_parts.append(
                    f"TourAPI 기준 {' / '.join(parts)}. 원문 그대로이며 자동 해석하지 않았습니다.")
            ck.warnings.append("TourAPI 운영시간 원문은 자동 판정에 쓰지 않았다 — 원문으로 전달")

    def _feasible_hours_by_llm(self, ck: "_Check", usetime: str, restdate: str | None, starts_at: Any) -> bool:
        """운영시간 원문 판정. LLM 이 판정했으면(LLM 모드) 안내를 쓰고 `True`, 아니면 `False` — 지금처럼 원문으로 전한다.

        ★규칙은 운영시간 원문을 해석하지 않는다(`unknown`). 그래서 섀도·규칙 모드에서는 언제나 `False` 다.
        """
        hours = self._judge(ck, judge_requests.operating_hours(usetime, starts_at))
        if hours.source != "llm" or not hours.known:
            if hours.source == "llm":
                ck.decisions["operating"]["hours_judged_by"] = "llm"
                ck.decisions["operating"]["hours_verdict"] = hours.value
                ck.warnings.append("운영시간 원문을 LLM 으로 해석하지 못했다 — 원문으로 전달")
            return False
        ck.decisions["operating"]["hours_judged_by"] = "llm"
        ck.decisions["operating"]["hours_verdict"] = hours.value
        self._llm_evidence(ck, hours, "운영시간 원문 LLM 해석")
        rest = f" / 휴무 {restdate}" if restdate else ""
        if hours.value == "outside":
            ck.decisions["feasible"] = False
            ck.answer_parts.append(
                f"다만 운영시간 안내(운영시간 {usetime}{rest})에 따르면 예약 시각은 운영시간 밖입니다"
                f"(원문 해석: «{hours.quotes[0]}»).")
        else:
            ck.answer_parts.append(
                f"운영시간 안내(운영시간 {usetime}{rest})에 따르면 예약 시각은 운영시간 안입니다"
                f"(원문 해석: «{hours.quotes[0]}»).")
        ck.warnings.append("운영시간 원문을 LLM 으로 해석했다 — 인용이 원문에 있는 것을 확인했다")
        return True

    def _holiday_facts(self, ck: "_Check", restdate: str | None, starts_at: Any) -> dict[str, Any]:
        """원문 판정에 필요한 날짜의 공휴일 여부를 `read.holiday` 로 묻는다. 필요 없으면 부르지 않는다.
        돌려주는 것: `{"YYYY-MM-DD": 특일 응답 | None}` — 판정 요청(`judge_requests.closure`)에 실린다.

        ★첫 날짜에서 모르면(`None`) 나머지는 묻지 않는다 — 같은 소스가 또 모른다고 할 것이고, 소스가 느리면
          (`travel.source_timeout_seconds`) 그만큼 고객 응답이 늦어진다.
        ★날짜마다 한 번만 묻는다 — 같은 인자로 두 번 부르면 `ToolLoopExceeded` 다.
        """
        found: dict[Any, Any] = {}
        for day in holiday_dates_needed(restdate, starts_at):
            info = self._read(ck.task, "read.holiday", {"on": day.isoformat()}, ck.seen)
            found[day] = info
            if info is None:
                break
        if found:
            ck.evidence = self._evidence(ck.task, source_id="read.holiday", claim="공휴일 여부",
                                         value={d.isoformat(): v for d, v in found.items()}, base=ck.evidence)
        return {d.isoformat(): v for d, v in found.items()}

    # ── ② 재난문자 ─────────────────────────────────────────
    def _feasible_disaster(self, ck: "_Check") -> None:
        # ★`[2026-10-07]` 도구는 시각을 `at` 으로 읽는다. 예전에는 `starts_at` 으로 넘겨 버려져서
        #   **일정 시각이 아니라 지금** 기준의 문자를 봤다(`read_tools.disaster`).
        disaster = self._read(ck.task, "read.disaster",
                              {"latitude": ck.lat, "longitude": ck.lng,
                               "at": ck.booking.get("starts_at")}, ck.seen)
        if disaster is None:
            return
        ck.evidence = self._evidence(ck.task, source_id="read.disaster",
                                     claim="재난문자", value=disaster, base=ck.evidence)
        messages = disaster.get("for_region") or []
        step_blocks = any(m.get("step") == "위급재난" for m in messages)
        # ★문자가 없으면 판정하지 않는다 — 막을 것이 없다.
        verdict = (self._judge(ck, judge_requests.disaster_effect(
            ck.place.get("name"), ck.place.get("kind"), messages, ck.booking.get("starts_at")))
            if messages else None)
        by_llm = verdict is not None and verdict.source == "llm"
        # ★LLM 이 판정하지 못하면(모름) 등급 기준(지금 규칙)으로 막는다 — 모름을 「막지 않음」으로 읽지 않는다.
        blocks = (verdict.value == "blocks") if by_llm and verdict.known else step_blocks
        ck.decisions["disaster"] = {
            "messages": messages,
            "blocks": blocks,
            "confirmed_at": disaster.get("confirmed_at"),
            "source": disaster.get("source"),
        }
        if by_llm:
            ck.decisions["disaster"]["judged_by"] = "llm"
            ck.decisions["disaster"]["verdict"] = verdict.value
            self._llm_evidence(ck, verdict, "재난문자 관련성 LLM 판정")
        if by_llm and verdict.known and blocks:
            kinds = ", ".join(sorted({str(m.get("kind", "")) for m in messages}))
            ck.decisions["feasible"] = False
            ck.answer_parts.append(
                f"재난문자({kinds})가 이 장소·시각의 활동을 막는 내용이라 이 일정은 성립하지 않습니다"
                f"(문자 해석: «{verdict.quotes[0]}»).")
            ck.warnings.append("재난문자 관련성을 LLM 으로 판정했다 — 인용이 문자 본문에 있는 것을 확인했다")
        elif by_llm and verdict.known and step_blocks:
            ck.answer_parts.append(
                f"위급재난 문자 {len(messages)}건이 있으나 이 장소·시각과 관련 없는 내용으로 판단했습니다"
                f"(문자 해석: «{verdict.quotes[0]}»).")
            ck.warnings.append("위급재난 문자를 LLM 이 「관련 없음」으로 판정했다 — 인용이 문자 본문에 있는 것을 확인했다")
        elif blocks:
            if by_llm:
                ck.warnings.append("재난문자 관련성을 LLM 이 판정하지 못해 등급 기준으로 판정했다")
            kinds = ", ".join(
                m.get("kind", "") for m in messages
                if m.get("step") == "위급재난")
            ck.decisions["feasible"] = False
            ck.answer_parts.append(
                f"위급재난({kinds})이 발령 중이라 이 일정은 성립하지 않습니다. "
                f"지역·주제가 이 활동과 관련 없을 수 있습니다.")
            ck.warnings.append("재난문자 위급재난 등급 확인 — 지역·주제 관련성은 확인하지 않았다")
        elif messages:
            grade = messages[0].get("step", "")
            ck.answer_parts.append(
                f"재난문자 {len(messages)}건 확인됨({grade}). 판정에 영향을 주는 등급은 아닙니다.")
        else:
            ck.answer_parts.append("확인 범위 내 재난문자는 없습니다.")

    # ── ③ 기상 ─────────────────────────────────────────────
    def _guess_weather_sensitive(self, ck: "_Check") -> tuple[bool | None, str | None]:
        """실내외를 정한다 — DB 값 → 장소명 추정 → 분류 유형 추정 순. 반환: (값, 어디서 추정했나 `title`/`category`/`None`)."""
        place = ck.place
        weather_sensitive = place.get(self._WEATHER_SENSITIVE_KEY)
        if weather_sensitive is not None:
            return weather_sensitive, None
        title = place.get("name") if isinstance(place, dict) else None
        lclssystm2 = (ck.csv_row or {}).get("lclsSystm2")
        # ★규칙 판정은 장소명 → 분류 유형 순이다(`judge/rule.py`) — 전과 같다.
        verdict = self._judge(ck, judge_requests.weather_sensitive(title, lclssystm2))
        if not verdict.known:
            return None, None
        ws = verdict.value == "outdoor"
        if verdict.source == "llm":
            self._llm_evidence(ck, verdict, "LLM 실내외 추정")
            return ws, "llm"
        if verdict.basis == "title":
            ck.evidence = self._evidence(
                ck.task, source_id="activity.weather_sensitive_from_title",
                claim="장소명 기반 실내외 추정",
                value={"title": title, "result": ws},
                base=ck.evidence)
            return ws, "title"
        ck.evidence = self._evidence(
            ck.task, source_id="activity.weather_sensitive_from_lclssystm2",
            claim="분류 유형 기반 실내외 추정",
            value={"lclsSystm2": lclssystm2, "result": ws},
            base=ck.evidence)
        return ws, "category"

    def _feasible_weather(self, ck: "_Check") -> None:
        weather_sensitive, guessed_from = self._guess_weather_sensitive(ck)
        ck.weather_sensitive = weather_sensitive
        if weather_sensitive is not True:
            return
        # ★`[2026-10-07]` `at` — 예전 `starts_at` 은 도구가 버려 **지금 시각의 예보**를 봤다(재난문자와 같은 결함).
        forecast = self._read(ck.task, "read.weather",
                              {"latitude": ck.lat, "longitude": ck.lng,
                               "at": ck.booking.get("starts_at")}, ck.seen)
        if forecast is None:
            return
        ck.evidence = self._evidence(ck.task, source_id="read.weather",
                                     claim="기상 예보", value=forecast, base=ck.evidence)
        note, advisories = self._weather_note(forecast)
        ck.answer_parts.append(note)
        ck.warnings.extend(advisories)
        w_dec: dict[str, Any] = {
            "matched_hour": forecast.get("matched_hour"),
            "precipitation_probability": forecast.get("precipitation_probability"),
            "wind_speed_kmh": forecast.get("wind_speed_kmh"),
            "source": forecast.get("source"),
            "fell_back_from": forecast.get("fell_back_from", []),
            "confirmed_at": forecast.get("confirmed_at"),
        }
        if guessed_from == "title":
            w_dec["weather_sensitive_guessed_from_title"] = True
            ck.warnings.append(
                "장소명으로 추정한 실내외 여부로 기상을 조회했다 — 확정 정보가 아닐 수 있다")
        elif guessed_from == "category":
            w_dec["weather_sensitive_guessed_from_category"] = True
            ck.warnings.append(
                "분류 유형(lclsSystm2)으로 추정한 실내외 여부로 기상을 조회했다 — 확정 정보가 아닐 수 있다")
        elif guessed_from == "llm":
            w_dec["weather_sensitive_guessed_by_llm"] = True
            ck.warnings.append("LLM 으로 추정한 실내외 여부로 기상을 조회했다 — 확정 정보가 아닐 수 있다")
        ck.decisions["weather"] = w_dec

    # ── ③-2 실시간 운영 상태(웹) ─────────────────────────────
    def _feasible_live_status(self, ck: "_Check") -> None:
        """웹 공지로 그 날의 임시휴무·통제를 본다. ★판정 LLM 이 없으면 부르지 않는다 — 규칙은 이 판정이 없다.

        실외(날씨가 영향을 주는 활동)이거나 시작까지 `travel.activity_judge.live_status_within_hours` 안일 때만
        부른다 — 웹 검색은 건당 약 $0.02~0.04(추정)다. 주소는 CSV 장소 목록(`addr1`·`addr2`)에서 가져온다.
        """
        if getattr(self, "judge_llm", None) is None:
            return
        name = ck.place.get("name") if isinstance(ck.place, dict) else None
        if not name:
            return
        from app.core.settings import get_guardrails

        within = float(get_guardrails().get("travel.activity_judge.live_status_within_hours"))
        soon = ck.remaining is not None and ck.remaining <= within
        if not (ck.weather_sensitive is True or soon):
            return
        row = ck.csv_row or {}
        address = " ".join(part for part in ((row.get("addr1") or "").strip(),
                                             (row.get("addr2") or "").strip()) if part) or None
        verdict = self._judge(ck, judge_requests.live_status(name, ck.place.get("kind"), address,
                                                             ck.booking.get("starts_at")))
        if verdict.source != "llm":
            return
        ck.decisions["live_status"] = {"verdict": verdict.value, "judged_by": "llm",
                                       "closed": verdict.value == "closed",
                                       "citations": [c.get("url") for c in verdict.citations]}
        if not verdict.known:
            ck.warnings.append("실시간 운영 상태를 웹에서 확인하지 못했다 — 판정에 넣지 않았다")
            return
        self._llm_evidence(ck, verdict, "웹 공지 기반 실시간 운영 상태")
        url = verdict.citations[0].get("url")
        if verdict.value == "closed":
            ck.decisions["feasible"] = False
            ck.answer_parts.append(f"웹 공지상 이 날짜는 휴무·통제로 확인됩니다(출처: {url}).")
        else:
            ck.answer_parts.append(f"웹 공지상 이 날짜는 정상 운영으로 확인됩니다(출처: {url}).")
        ck.warnings.append("실시간 운영 상태는 웹 공지를 LLM 이 읽은 것이다 — 현장 확인이 아니다")

    # ── ④ 대체 장소 — 이 장소가 **장소 때문에** 안 될 때만(휴무 요일 · 위급재난) ──
    def _feasible_alternatives(self, ck: "_Check") -> None:
        decisions = ck.decisions
        decisions["status"] = "ok" if decisions["feasible"] else "problem"
        # ★장소 때문에 불가일 때만 코드를 단다. 둘이 겹치면 위급재난이 앞선다(대체 장소 `withheld` 와 같은 우선순위).
        if (decisions.get("disaster") or {}).get("blocks"):
            decisions["failure_code"] = self._record_failure(ck.task, fc.DISASTER_BLOCKS)
        elif (decisions.get("operating") or {}).get("weekday_match") is True:
            decisions["failure_code"] = self._record_failure(ck.task, fc.CLOSED_WEEKDAY)
        elif (decisions.get("live_status") or {}).get("closed"):
            decisions["failure_code"] = self._record_failure(ck.task, fc.LIVE_CLOSED)
        elif (decisions.get("operating") or {}).get("hours_verdict") == "outside":
            decisions["failure_code"] = self._record_failure(ck.task, fc.OUTSIDE_HOURS)
        if decisions["feasible"] is False and self._blocked_by_place(decisions):
            alt, ck.evidence, alt_text, alt_warnings = self._recommend_alternatives(
                ck.task, ck.place, ck.booking.get("starts_at"), ck.seen, ck.evidence, decisions)
            decisions["alternatives"] = alt
            if alt_text:
                ck.answer_parts.append(alt_text)
            ck.warnings.extend(alt_warnings)

    @staticmethod
    def _weekday_closure_match(restdate_text: str | None, starts_at: Any, holiday: Any = None) -> bool | None:
        """그 날이 원문상 휴무인가 — True 휴무 · False 아님 · None 모름(원문이 없거나 다 못 읽었다).

        ★`[2026-10-06]` `closure_rules.read_closure` 의 얇은 감싸개다. 전에는 「매주 X 휴무」 정규식 하나였고,
          패턴이 없으면 `False` 로 확정해 실제 원문 「매주 X」 309건 중 307건을 놓쳤다(결함 2026-10-06_1610).
        """
        if restdate_text is None:
            return None
        return read_closure(restdate_text, starts_at, holiday).value
