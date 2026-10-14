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

import json
import logging
from datetime import UTC, datetime
from functools import partial
from typing import Any

from app.core.contracts import ActionProposal, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.idempotency import idempotency_key

from app.domains.travel_ops.instances._shared._base import TravelTeamBase
from app.domains.travel_ops.components.actions.itinerary_actions import ACTION_TYPE as ITINERARY_APPLY
from app.domains.travel_ops.components.actions.itinerary_actions import consent_arguments
from app.domains.travel_ops.components.itinerary.itinerary_changes import ACTIVITY_RECHECK_LIMIT, NoChange, plan_activity_adjustment, plan_nearby_store
from app.domains.travel_ops.instances._shared.itinerary_team import ITINERARY_TOOLS, Consent, ItineraryWork
from app.domains.travel_ops.components.planning.pending import needs_consent, weather_only
from app.domains.travel_ops.components.planning.safety import classify as classify_safety
from . import failure_codes as fc
from .disaster_impact import Impact, ImpactRules, assess
from .verdicts import holidays_needed, hours_verdict
from .judge import requests as judge_requests
from .judge.llm import LLMJudge
from .judge.modes import ShadowJudge, kind_mode, local_web_budget, rule_first
from .judge.types import LIVE_STATUS, JudgeContext, JudgeRequest, Verdict
from .notices import HOURS_AUTO_READ, with_notice
from .replacement import ReplacementMixin
from .similarity import distance_first, preference_of, score

_failure_log = logging.getLogger(fc.LOGGER_NAME)

# ★`[2026-10-11]` 고객 확인 요청(`wait_for_input`)이 묻는 값 — 계약상 `required_input_schema` 가 있어야 한다(JSON Schema 모양).
ASK_STARTS_AT: dict[str, Any] = {
    "type": "object", "required": ["starts_at"],
    "properties": {"starts_at": {"type": "string", "format": "date-time", "description": "방문 시각"}}}
#: ★`[2026-10-13]` 코어 회신 5번 — 고객 답은 선택지(`choices`)와 맞춰 읽는다(자유 글을 해석하는 모델은 쓰지 않는다 ·
#:   다른 팀의 `conversation_work.wait_for_input` 과 같은 모양). 답이 선택지와 같지 않으면 다시 묻는다.
#:   `outdoor` 는 「야외면 True」 — 장소의 `weather_sensitive` 와 같은 뜻이다.
OUTDOOR_CHOICES: list[dict[str, Any]] = [
    {"label": "실내", "message": "실내", "outdoor": False},
    {"label": "야외", "message": "야외", "outdoor": True}]
PROCEED_CHOICES: list[dict[str, Any]] = [
    {"label": "그대로 진행", "message": "그대로 진행", "proceed": "keep"},
    {"label": "다른 장소 보기", "message": "다른 장소 보기", "proceed": "change"}]
ASK_OUTDOOR: dict[str, Any] = {      # 수정본 UC-A3 `3b2`
    "type": "object", "required": ["outdoor"],
    "properties": {"outdoor": {"type": "boolean", "description": "야외 활동이면 true, 실내 활동이면 false"}},
    "choices": OUTDOOR_CHOICES}
ASK_PROCEED: dict[str, Any] = {      # 수정본 UC-A3 `4a`
    "type": "object", "required": ["proceed"],
    "properties": {"proceed": {"type": "string", "enum": ["keep", "change"],
                               "description": "keep: 운영 정보 미확인인 채로 그대로 진행 · change: 다른 장소를 본다"}},
    "choices": PROCEED_CHOICES}

class ActivityTeam(ReplacementMixin, ItineraryWork, TravelTeamBase):
    manifest = TeamManifest(
        team_id="activity",
        display_name="Activity Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=[
            "activity.check_cancelable",   # 지금 취소할 수 있나 · 위약금은 얼마인가
            "activity.check_feasible",     # 이 시각에 이 활동이 성립하나
            "activity.propose_change",     # 대안을 제안한다 (승인 대기)
            "activity.itinerary",          # ★`[2026-09-17]` 여행 일정 관리 — 감시 Case · 품절 · 재요청
            "activity.itinerary_question", # ★`[2026-09-25]` 규정 질문 — 규정을 읽는다(면제 아님)
            "activity.submit_itinerary",   # ★`[2026-10-09]` 일정 제출 — 여행 접수로 안내한다(team 통합 ⑥)
        ],
        accepted_case_types=["activity"],
        # ★`[2026-09-17]` `policy` 를 뺐다 — 규정은 `read.policy` 도구로 **직접** 읽고(없으면 모름),
        #   일정 관리는 실시간 사실로 판단한다. 선언에 두면 정책 검색 0건이 Case 전체를 degraded 로 만든다.
        # ★`[2026-09-22]` **되돌렸다.** 그때 0건이던 까닭은 코퍼스가 쇼핑몰 25문서뿐이고 여행 문서가
        #   0건이었기 때문이다(`knowledge/travel/` 12문서·130청크로 채웠다). 이제 아래 scope 에
        #   문서가 있어 검색이 0건으로 떨어지지 않는다. `policy` 를 선언해야 Controller 가 RAG 를
        #   돌고(`app/application/controller.py:134`) 그 결과가 ContextPack·Evidence 에 실린다 —
        #   「근거 없는 문장 금지」(CLAUDE.md §0.1)를 지키려면 근거가 실제로 실려야 한다.
        required_context=["case_state", "policy", "db_facts", "history"],
        # ★일정 관리만 면제한다 — 예보·운행·영업 같은 **실시간 사실**로 판단하는 일이라
        #   정책 검색 결과에 막히면 안 된다(감시 루프가 여는 Case 가 전부 사람에게 간다).
        # ★`[2026-10-09]` 일정 제출 안내도 규정을 쓰지 않는다 — 정책 검색 0건으로 사람에게 가지 않게.
        policy_optional_capabilities=["activity.itinerary", "activity.submit_itinerary"],
        # ★`[2026-09-23]` `read.booking_terms` 를 더했다 — **수치는 이 도구가** 댄다.
        #   `read.policy` 는 그대로 **문장 근거**를 댄다. 둘의 몫이 갈린다
        #   (`wiki/records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md`).
        # ★`[2026-10-03]` 뒤의 셋(`read.route_events` · `read.dining_state` · `read.dining_states`)은 **같은 여행의 문제 묶음**(`trip_watch_batch`) 때문이다 — 활동 Team 이
        #   조정자라 식당 · 이동 항목도 같은 초안 위에서 계산한다. 식당 원장 둘은 못 부르면 장소 목록으로 돌아간다(`dining.team.state_lookup_for` — `[2026-10-05]` 옛 `read.dining_alternatives` · `ToolLedgerView` 는 걷었다). 단일 항목 Case 는 이 셋을 안 쓴다.
        allowed_tools=["read.booking", "read.booking_terms", "read.policy", "read.place",
                       "read.disruptions", "read.route_events", "read.dining_state", "read.dining_states",
                       # ★`[2026-10-09]` 성립 판정의 휴무 · 운영시간(DB 만) · 공휴일 조건
                       "read.place_hours", "read.holiday",
                       # ★`[2026-10-09]` 휴무 · 운영시간 밖일 때 대체 장소 후보(관광공사 목록 — team 통합 ④)
                       "read.place_candidates",
                       # ★`[2026-10-09]` 장소 행에 실내외가 없을 때 관광공사 분류로 정한다(team 통합 ⑤)
                       "read.place_class",
                       # ★`[2026-10-11]` 재난문자를 수정본 §8 분류표로 가른다(구현 계획 2.4) · 재난으로 막혔을 때 대체 후보 위치를 다시 본다.
                       #   `read.disaster_points` 는 `replacement._recheck_disaster` 가 10-07 부터 부르는데 선언이 빠져 있었다.
                       "read.disaster", "read.disaster_points",
                       # ★`[2026-10-14]` 여행을 못 찾은 예약에서 설문 문항을 다시 물을 때 같은 고객의 지난 답(전달 8번 회신)
                       "read.last_survey_answer",
                       *ITINERARY_TOOLS],
        # ★`[2026-09-22]` 여행 scope 로 바꿨다. 앞 값(`activity`·`cancellation`·`refund`·`weather`)
        #   가운데 **`refund` 는 쇼핑몰 코퍼스에 실재하는 scope** 라, 정책을 켜는 순간 활동 판정이
        #   쇼핑몰 환불 문서를 근거로 집어 왔다. 이름이 겹치지 않게 `travel_` 을 붙이고
        #   겹침 0건을 `scripts/check_corpus.py` 검사 9 가 센다.
        knowledge_scope=["travel_activity", "travel_weather", "travel_cancellation", "travel_access"],
        # ★대안 후보마다 재점검한다(도구 1회씩) — 6 으로는 후보 셋에서 예산이 끝난다.
        max_steps=12,
        active=True,
        implementation_revision="2026-09-22",
        default_capability="activity.check_feasible",
    )

    #: 날씨가 판정에 들어가는 활동만 기상을 본다. ★실내 활동에 기상 감시를 걸면
    #:  감시 소스가 둘로 갈려 Team 경계가 흐려진다(v10 §5 「객체 종류별로 나눈다」).
    #:  이 판단은 `read.place` 가 돌려주는 속성으로 하고, 모르면 **보지 않는다**.
    _WEATHER_SENSITIVE_KEY = "weather_sensitive"

    #: ★`[2026-10-09]` 판정 LLM(D-CS-015) — 조립(`composition.build_registry`)이 섀도 모드일 때만 넣는다. `None` 이면 부르지 않는다.
    judge_llm: Any | None = None
    #: 섀도 기록을 표(`activity_judge_shadow`)에 쓰는 함수 — 조립이 넣는다.
    judge_shadow_sink: Any | None = None
    #: 섀도 판정을 돌리는 실행기. `None` 이면 판정 계층의 기본 스레드 풀(시험은 바로 끝나는 실행기를 넣는다).
    judge_runner: Any | None = None
    #: ★`[2026-10-12]` 판정 LLM 호출 예산 — 판정 종류 → 「불러도 되나」. 조립이 `external_call_budget` 으로 만들어 넣는다
    #:  (`judge.modes.budget_meter` · `budget_caps`, 코어 협의). `None` 이면 세지 않는다(지금까지와 같다).
    judge_budget: Any | None = None
    #: ★`[2026-10-13]` 저장된 실시간 운영 상태(웹 공지) 읽기 — `(tenant_id, place_id, 방문 날짜) -> 저장된 값 | None`.
    #:  조립이 `live_store.build_lookup(get_connection)` 으로 만들어 넣는다(코어 협의). `None` 이면 이 확인은 꺼져 있다(경고도 없다).
    #:  ★고객 요청은 웹을 부르지 않는다 — 웹 확인은 장소 · 날짜당 한 번 배치(`scripts/activity/check_live_status.py`)가 한다.
    live_lookup: Any | None = None
    #: 이 팀이 받는 판정 LLM 모드. ★`llm` 은 D-CS-015 범위 밖이다 — 조립이 기동 때 막는다(조용히 섀도로 바꾸지 않는다).
    #:  ★`[2026-10-12]` 종류별 `llm`(실시간 운영 · 휴무 · 재난)은 전역 `shadow` 로 판정 LLM 을 꽂은 뒤 `kind_modes` 로 켠다.
    judge_modes = ("rule", "shadow")

    @staticmethod
    def _hours_until(when: Any) -> float | None:
        """예약 시각까지 남은 시간. 모르면 `None`."""
        if not isinstance(when, datetime):
            return None
        reference = when if when.tzinfo else when.replace(tzinfo=UTC)
        return (reference - datetime.now(UTC)).total_seconds() / 3600

    def _record_failure(self, task: TeamTask, code: str, **meta: Any) -> str:
        """실패·예외 코드를 한 줄 JSON 으로 남기고 코드를 돌려준다(`failure_codes.py`). `[2026-10-05]` 활동 팀 구조.

        ★좌표·장소명·고객 문장은 싣지 않는다 — Case id · capability · 코드와 짧은 메타(도구 이름 · 예외 종류)만.
        ★기록은 **알리는 것**일 뿐 흐름을 바꾸지 않는다. 어디에 쓸지는 운영의 logging 설정이 정한다."""
        _failure_log.warning(json.dumps(
            {"event": "activity_failure", "code": code, "team": self.manifest.team_id,
             "case_id": str(task.case_id), "capability": task.capability, **meta},
            ensure_ascii=False, default=str))
        return code

    def _read(self, task: TeamTask, name: str, arguments: dict[str, Any], seen: set[str]) -> Any:
        """도구 예외(API·DB 실패)를 코드로 남기고 **그대로 다시 던진다** — 삼켜서 「모름」으로 바꾸지 않는다(RULE §3.2)."""
        try:
            return super()._read(task, name, arguments, seen)
        except Exception as exc:
            self._record_failure(task, fc.TOOL_ERROR, tool=name, error=type(exc).__name__)
            raise

    @staticmethod
    def select_capability(intent: str | None, input_text: str, state: dict | None = None) -> str | None:
        """★여행이 정해진 Case 는 일정 관리로 — 일정 제출은 안내로 — 그 밖은 기본 동작에 맡긴다.

        ★`[2026-10-09]` 일정 제출(`itinerary_submit`)을 받을 capability 가 없어 기본값(성립 판정)으로 갔고, 그러면 고객의
          **가장 임박한 예약**을 판정해 엉뚱한 답을 냈다. 일정 제출은 develop 여행 접수가 맡는다(team 통합 ⑥ — 사용자 결정).
        """
        route = ItineraryWork.itinerary_route("activity", state)
        if route is None and intent == "itinerary_submit":
            return "activity.submit_itinerary"
        # ★`[2026-10-09]` 「바꿔 주세요」(조정 거부) — 전에는 받을 곳이 없어 성립 판정으로 갔다(「성립합니다」로 답했다).
        #   role-activity 판의 연결을 되살린다. 여행이 정해진 Case 의 바꾸기는 위의 일정 관리가 맡는다.
        if route is None and intent == "adjust_reject":
            return "activity.propose_change"
        return route

    async def handle_trigger(self, task: TeamTask, ctx: dict[str, Any]) -> TeamResult:
        """감시가 연 Case — 그 항목을 **다시 점검**하고, 깨졌으면 대안을 계산해 제안한다."""
        trigger = task.context.current_state.get("trigger") or {}
        item = next((i for i in ctx["items"] if str(i.item_id) == str(trigger.get("item_id"))), None)
        if item is None:
            return self.settle(task, ctx, NoChange("gone"))
        plan = plan_activity_trigger(self, task, ctx, item)
        if isinstance(plan, Consent):
            return self._ask_consent(task, ctx, item, plan.report)
        if isinstance(plan, TeamResult):
            return plan
        return self.settle(task, ctx, plan)

    def _ask_consent(self, task: TeamTask, ctx: dict[str, Any], item: Any, report: dict[str, Any]) -> TeamResult:
        """★`[2026-09-29]` 실내·야외를 모르는 활동에 날씨 사건만 — 대체안을 **계산하지 않고** 「바꿀까요?」만 묻는다.

        대체안 계산은 후보마다 바깥 점검을 불러 비용이 든다. 고객이 「바꿔 줘」라고 하면 그때 계산한다
        (`pending.choose` → `_consented`). 사용자 결정 2026-09-29 · 코덱스 합의(모름이면 묻는다).
        """
        trip = ctx["trip"]
        causes = list(report.get("disruptions") or [])
        arguments = consent_arguments(trip_id=trip["trip_id"], base_version=trip["version"],
                                      item_id=item.item_id, causes=causes,
                                      indoor_unknown=bool(report.get("indoor_unknown")))
        proposal = ActionProposal(
            action_type=ITINERARY_APPLY, arguments=arguments,
            idempotency_key=idempotency_key(
                tenant_id=task.context.tenant_id,
                request_id=str(task.context.current_state.get("request_id") or task.case_id),
                action_type=ITINERARY_APPLY, business_subject=f"{trip['trip_id']}:v{trip['version']}"),
            # ★일정을 바꾸지 않는다 — 묻는 제안만 연다. 승인 대기 없이 적용기가 바로 연다
            approval_required=False, risk_level="low", rationale_evidence_ids=[])
        return self._result(task, outcome="completed", confidence=0.9, evidence=ctx["evidence"],
                            answer=(f"{item.title} — 이 장소가 실내인지 확인하지 못해 바꿀지 먼저 여쭙니다."
                                    if report.get("indoor_unknown") else
                                    f"{item.title} — 날씨 때문에 일정을 바꿀지 먼저 여쭙니다."),
                            next_action=NextAction.RESPOND, action_proposals=[proposal],
                            decisions=[{"itinerary": "consent_requested", "item_id": str(item.item_id)}])

    async def handle_report(self, task: TeamTask, kind: str, ctx: dict[str, Any]) -> TeamResult:
        if kind != "stock_out":
            return await super().handle_report(task, kind, ctx)
        products = list(ctx["report"].get("products") or [])
        if not products:
            return self._unknown(task, "품절 상품", ctx["evidence"])
        places = self.catalog(task, ctx)
        if places is None:
            return self._unknown(task, "장소 목록", ctx["evidence"])
        answer = plan_nearby_store(items=ctx["items"], places=places, at=ctx["at"], products=products,
                                   message=task.input_text,
                                   request_id=task.context.current_state.get("request_id"))
        if answer.get("status") != "answered":
            return self._escalate(task, "store_unresolved", ctx["evidence"],
                                  warnings=[str(answer.get("message") or "동선 위 매장을 찾지 못했다")])
        # ★일정은 바꾸지 않는다 — 제안 없이 답만. 재고는 `[미확인]` 으로 말한다.
        return self._result(task, outcome="completed", confidence=0.7, evidence=ctx["evidence"],
                            answer=answer["text"], next_action=NextAction.RESPOND,
                            decisions=[{"itinerary": "store_recommended",
                                        "recommendation": answer["recommendation"],
                                        "stock": answer["stock"],
                                        "other_options": answer["other_options"]}])

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked
        if task.capability in (self.itinerary_capability, self.question_capability):
            return await self.run_itinerary(task)
        if task.capability == "activity.submit_itinerary":
            return self._submit_itinerary(task)

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
        # ★`[2026-10-05]` 성립 판정(`check_feasible`)은 취소·환급 규정을 쓰지 않는다 — 규정이 없다고 멈추지 않는다(활동 팀 10/2 규칙).
        #   전에는 규정 검색이 0건이면 날씨·재난으로 판정할 수 있는 성립 질문까지 「모름」으로 끝났다.
        #   규정이 필요한 `check_cancelable` · `propose_change` 는 그대로 모르면 멈춘다.
        if not policy and task.capability != "activity.check_feasible":
            return self._unknown(task, "취소·환급 규정", evidence)

        remaining = self._hours_until(booking.get("starts_at"))
        # ★`[2026-10-09]` 시각을 모르면 성립 판정은 「정보 부족」으로 답한다(escalate 가 아니다 — 활동 팀 10/2 규칙, team 통합 ③).
        #   취소 · 변경은 시각이 있어야 계산되므로 그대로 멈춘다.
        if remaining is None and task.capability != "activity.check_feasible":
            return self._unknown(task, "예약 시각", evidence)

        if task.capability == "activity.check_cancelable":
            # ★수치는 규정 문장이 아니라 **이 예약의 조건**에서 온다(마이그레이션 023).
            terms = self._read(task, "read.booking_terms",
                               {"booking_id": booking.get("booking_id")}, seen)
            evidence = self._evidence(task, source_id="read.booking_terms",
                                      claim="이 예약의 취소 조건", value=terms, base=evidence)
            return self._check_cancelable(task, booking, terms, remaining, evidence)
        if task.capability == "activity.check_feasible":
            return self._check_feasible(task, booking, policy, remaining, evidence, seen)
        return self._propose_change(task, booking, evidence)

    # ── 일정 제출 — 여행 접수가 맡는다 ─────────────────────────
    #: 일정 제출을 받는 곳 — develop 여행 접수(문장에서 장소 · 시각 · 예약번호를 읽어 여행 · 일정 항목을 만들고 감시까지 잇는다)
    SUBMIT_ENTRY = "POST /v1/web/trip-intakes"

    def _submit_itinerary(self, task: TeamTask) -> TeamResult:
        """★`[2026-10-09]` team 통합 ⑥(사용자 결정: develop 접수에 맡김) — 일정을 **만들지 않고** 여행 접수로 안내한다.

        role-activity 판(`team_a._submit_itinerary`)은 장소 이름을 조회해 `activity.submit` 제안을 만들었지만, 그 입력
        (`requested_place_name` · `requested_activity_time`)을 채우는 곳도, 제안을 실행할 처리기 · `activities` 표도 develop 에
        없다 — 승인해도 아무 일도 안 일어난다. 예약을 읽지 않는다(문의와 상관없는 예약을 판정하지 않게).
        """
        evidence = self._evidence(task, source_id="case.capability", claim="요청 종류 — 일정 제출",
                                  value={"capability": task.capability, "handled_by": self.SUBMIT_ENTRY})
        return self._result(
            task, outcome="completed", confidence=0.9, evidence=evidence, next_action=NextAction.RESPOND,
            answer=("일정 등록은 여행 일정 화면에서 받고 있습니다. 일정을 그곳에 붙여 넣어 주시면 장소와 시각을 확인해 "
                    "일정을 만들고, 그 뒤로 날씨 · 재난 같은 변동을 살펴 드립니다."),
            decisions=[{"itinerary": "submit_redirected", "handled_by": "trip_intake", "entry": self.SUBMIT_ENTRY}])

    # ── ① 검증 — 계산으로만 ────────────────────────────────────
    def _check_cancelable(self, task: TeamTask, booking: dict, terms: Any,
                          remaining: float, evidence: list) -> TeamResult:
        deadline = self._terms_hours(terms, "cancel_deadline_hours")
        if deadline is None:
            return self._unknown(task, "취소 기한", evidence)

        if remaining < deadline:
            # ★`[2026-09-23 실측]` 두 값이 같은 자리에서 반올림되면 답변이 **자기모순으로
            #   보인다** — 「6시간 전까지 취소할 수 있는데 지금은 6.0시간 남았습니다」가
            #   실제로 나왔다(demo BK-GOLF-LATE, 기한 6시간 · 남은 5.98시간). 고객은 이걸
            #   읽고 「그럼 되는 거 아닌가」 하고 다시 묻는다. 겨우 넘긴 경우는 **분으로** 말한다.
            late_minutes = (deadline - remaining) * 60
            if round(remaining, 1) >= round(deadline, 1):
                how = (f"규정상 시작 {deadline:g}시간 전까지 취소할 수 있는데 "
                       f"{late_minutes:.0f}분 차이로 지났습니다.")
            else:
                how = (f"규정상 시작 {deadline:g}시간 전까지 취소할 수 있는데 "
                       f"지금은 {remaining:.1f}시간 남았습니다.")
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"취소 기한이 지났습니다. {how}",
                decisions=[{"cancelable": False, "hours_remaining": round(remaining, 1),
                            "deadline_hours": deadline,
                            # ★분자/분모를 남긴다 — 「얼마나 늦었나」가 재문의의 첫 질문이다
                            "late_by_minutes": round(late_minutes)}])

        penalty = self._penalty_rate(terms, remaining)
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
                        remaining: float | None, evidence: list, seen: set[str]) -> TeamResult:
        # ★`[2026-09-29]` 이미 시작한 예약은 성립을 다시 점검하지 않는다 — 지난 시각의 날씨·특보로
        #   「바꿔야 한다」는 제안을 만들면 되돌릴 수 없는 일을 권하게 된다. 출처: 활동 팀 PR #6(결함 2 수정)
        if remaining is not None and remaining < 0:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"이미 시작한 활동입니다 — {-remaining:.1f}시간 전에 시작했습니다.",
                decisions=[{"feasible": False, "reason": "already_started",
                            "failure_code": self._record_failure(task, fc.ALREADY_STARTED),
                            "hours_elapsed": round(-remaining, 1)}])
        # ★`[2026-10-12]` 여기 정원은 **예약 자체의 정원**(`bookings.capacity`)이다 — 넘으면 예약이 성립하지 않아 막는다.
        #   D3(「인원은 판정 항목이 아니다」)가 말하는 것은 장소의 수용 인원(관광공사 `accomcount`)이고, 그것은 대체 후보
        #   필터에만 쓴다. 둘을 섞어 이 판정을 뺐다가 되돌렸다(activity.md D3 범위 정정).
        party = booking.get("party_size")
        capacity = booking.get("capacity")
        if party is not None and capacity is not None and party > capacity:
            return self._result(
                task, outcome="completed", confidence=1.0, evidence=evidence,
                next_action=NextAction.RESPOND,
                answer=f"인원이 정원을 넘습니다 — 신청 {party}명, 정원 {capacity}명.",
                decisions=[{"feasible": False, "reason": "party_over_capacity",
                            "failure_code": self._record_failure(task, fc.PARTY_OVER_CAPACITY)}])
        # ★`[2026-10-09]` 인원 · 정원 중 하나라도 모르면 위 비교를 건너뛴다 — 「초과 아님」으로 확정한 것이 아니므로 조용히
        #   넘기지 않고 경고로 남긴다(사용자 결정, team 통합 ③). 막지는 않는다 — 인원은 성립을 정하는 다른 점검의 재료가 아니다.
        missing = [label for label, value in (("신청 인원", party), ("정원", capacity)) if value is None]
        headcount_warnings = ([f"{' · '.join(missing)}을 확인하지 못했다 — 정원 초과 여부는 판정하지 않았다"]
                              if missing else [])
        # ★`[2026-10-09]` 「모름」을 「성립」으로 읽지 않는다(team 통합 ③ — role-activity 판). 시각을 모르면 휴무 · 운영시간 ·
        #   재난 · 기상 어느 것도 잴 수 없어 장소를 읽지 않는다. 정원 초과처럼 시각 없이 확인된 불가(위)는 이미 나갔다.
        # ★`[2026-10-11]` 「정보 부족」(`insufficient_info` — 계약 밖 값)으로 끝내지 않고 고객에게 방문 시각을 묻는다(D4 · 수정본 §12).
        if remaining is None:
            return self._ask_customer(task, evidence, fc.TIME_UNKNOWN, schema=ASK_STARTS_AT, reason="time_unknown",
                                      answer="예약 시각을 확인하지 못해 성립 여부를 판정하지 않았습니다. 방문 시각을 알려 주세요.",
                                      warnings=["예약 시각을 확인하지 못했다", *headcount_warnings])

        place = self._read(task, "read.place", {"place_id": booking.get("place_id")}, seen)
        evidence = self._evidence(task, source_id="read.place",
                                  claim="장소·운영 정보", value=place, base=evidence)
        # ★전에는 장소를 몰라도 「확인한 범위에서는 성립합니다 … 판정하지 않았습니다」로 답했다 — 앞뒤가 어긋난다(활동 팀 결함 1).
        #   장소를 모르면 재난 · 휴무 점검에 넘길 좌표 · 구도 없다.
        # ★`[2026-10-11]` 예약에 붙은 장소를 못 읽은 것은 고객이 풀 수 있는 일이 아니다 — 운영 담당자에게 넘긴다(D4, 수정본 UC-A3 `1a`).
        #   「없음」으로 단정하지 않는다. 카카오로 실재를 확인하는 갈래(구현 계획 2.5)가 붙으면 그 앞에서 나뉜다.
        if place is None:
            return self._escalate(task, fc.PLACE_UNKNOWN, evidence,
                                  warnings=["장소·운영 정보를 확인하지 못했다 — 없음이 아니라 모르는 상태다",
                                            *headcount_warnings])

        # ★성립 점검은 **한 번**이다(`read.disruptions`). 예보·특보·(붙는 대로)
        #   재난문자·대기질을 도구가 한꺼번에 본다. 무엇을 볼지(실내면 예보 안 봄)는
        #   점검이 장소 속성으로 정한다 — Team 이 소스 조합을 들고 있지 않는다.
        report: dict[str, Any] | None = None
        indoor: dict[str, Any] = {}
        place_class: dict[str, Any] | None = None
        weather_pending: dict[str, Any] | None = None
        outdoor_ask: list[dict[str, Any]] = []
        disaster_warnings: list[str] = []
        if isinstance(place, dict):
            indoor, evidence, place_class = self._indoor_outdoor(task, booking, place, seen, evidence)
            # ★`[2026-10-13]` 코어 회신 5번 — 이전 재개에서 고객이 실내 · 야외로 답했으면 그 값을 쓴다(같은 질문을 되풀이하지 않는다).
            #   장소 기록이나 관광공사 분류가 알려 주지 못한 경우에만 쓴다 — 기록이 있으면 기록이 앞선다.
            if indoor.get("value") is None:
                answered = self._answered(task, "outdoor", OUTDOOR_CHOICES)
                if answered is not None:
                    indoor = {"value": bool(answered["outdoor"]), "source": "customer"}
            report = self._read(task, "read.disruptions", {
                "place_id": booking.get("place_id"),
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                # ★`[2026-10-09]` 전에는 `bool(...)` 이라 모름(`None`)이 「실내」가 되어 날씨를 아예 안 봤다 — 감시 경로는
                #   9/29 에 고친 결함이다(`disruptions.py` — 모르면 야외처럼 보고 `indoor_unknown`). 모름은 모름으로 넘긴다.
                "weather_sensitive": indoor.get("value"),
                "region": self._REGION,
                # ★구를 알면 넘긴다 — 강남 도로 통제로 종로 일정을 바꾸지 않게.
                "district": place.get("district"),
                "starts_at": booking.get("starts_at"),
            }, seen)
            evidence = self._evidence(task, source_id="read.disruptions",
                                      claim="일정 성립 점검", value=report, base=evidence)
            # ★결정 15 — 항목 하나라도 1차·대체 소스까지 못 가져오면 **치명**이다.
            #   조회 실패를 일정 변경 사유로 쓰지 않는다(멀쩡한 일정이 바뀐다).
            if report is None or report.get("verdict") == "fatal":
                failed = (report or {}).get("failed_categories") or ["성립 점검 전체"]
                return self._escalate(task, "fatal_source_failure", evidence, warnings=[
                    f"값을 끝까지 못 가져온 항목: {', '.join(failed)} — 대체 소스까지 "
                    f"실패했다(결정 15: 치명). 모르는 채로 성립이라고 답하지 않는다"])

            def safety_change(event: Any) -> TeamResult:
                return self._propose_change(
                    task, booking, evidence,
                    reason=f"재난 — {event.label}",
                    answer=(f"현재 {self._REGION}에 {event.label} 문자가 발령 중이라 이 일정은 바꿔야 합니다. "
                            f"변경 제안을 만들었고 승인 뒤에 진행됩니다."),
                    decisions={"feasible": False, "reason": "safety_event",
                               "failure_code": self._record_failure(task, fc.DISASTER_BLOCKS),
                               "safety": event.evidence()})
            # ★`[2026-10-11]` 재난문자는 수정본 §8 재해 분류표로 가른다(D2 — 등급이 아니라 재해 성격). 공유 점검이 이상으로
            #   센 재난문자는 빼고(`rest`) 분류 결과로 막는다. 나머지(예보 · 특보 · 교통 · 대기)는 공유 점검 판정 그대로다.
            impact, rest, evidence, stop = self._disaster_impact(task, booking, place, report, indoor, seen, evidence)
            if stop is not None:
                return stop
            # ★재난 정지 대상(그날 · 여행 전체)이 먼저다 — 정지는 대체 장소를 붙이지 않는 결정이다(`_closed_place_change` 참고).
            safety = self._safety_event(impact, report)
            if safety is not None:
                return safety_change(safety)
            # ★`[2026-10-12]` D-CS-015 개정 2 — 분류표에 없는 문자는 LLM 에 맡긴다. 「막는다」만 받는다(조심하는 쪽).
            if impact is not None and not impact.blocks and impact.unclassified:
                by_model = self._rule_first(task, judge_requests.disaster_effect(
                    place.get("name"), "activity", impact.unclassified, booking.get("starts_at"), indoor.get("value")),
                    basis="unclassified_kind")
                if by_model is not None:
                    impact.blocks.extend({**m, "impact": "llm"} for m in impact.unclassified)
                    impact.unclassified.clear()
            if impact is not None and impact.blocks:
                kinds = ", ".join(dict.fromkeys(str(m.get("kind")) for m in impact.blocks))
                return self._closed_place_change(
                    task, booking, place, seen, evidence, reason=f"재난 — {kinds}",
                    answer=(f"이 장소가 있는 지역에 {kinds} 문자가 발령 중이라 이 일정은 바꿔야 합니다. "
                            f"변경 제안을 만들었고 승인 뒤에 진행됩니다."),
                    decisions={"feasible": False, "reason": "disaster_blocks",
                               "failure_code": self._record_failure(task, fc.DISASTER_BLOCKS),
                               "disaster": impact.record()})
            if impact is not None:
                outdoor_ask = impact.ask
                disaster_warnings = [f"분류되지 않은 재해구분({m.get('kind')}) 문자가 있다 — 판정에 넣지 않고 근거로만 남겼다"
                                     for m in impact.unclassified]
            # ★`[2026-10-09]` 실내외를 모르는데 **날씨 사건만** 걸렸다 — 바꾸라고 단정하지 않고 먼저 묻는다(감시 경로의
            #   `pending.needs_consent` 와 같은 기준 · 사용자 결정 2026-09-29). 휴무가 더 확실한 불가라 휴무를 먼저 본 뒤에 답한다.
            if rest.get("verdict") == "disrupted" and rest.get("indoor_unknown") and weather_only(rest):
                weather_pending = rest
            # ★이상이 **하나라도** 있으면 일정 변경 대상이다.
            elif rest.get("verdict") == "disrupted":
                kinds = ", ".join(str(d.get("kind")) for d in rest.get("disruptions", []))
                return self._propose_change(
                    task, booking, evidence,
                    reason=f"일정 성립 점검 이상 — {kinds}",
                    answer=(f"현재 {self._REGION}에 {kinds}가 발효 중이라 이 일정은 "
                            f"바꿔야 합니다. 변경 제안을 만들었고 승인 뒤에 진행됩니다."),
                    decisions={"feasible": False, "reason": "disrupted",
                               "disruptions": rest.get("disruptions", [])})
            # ★`[2026-10-09]` 재난 기준을 재난 정지와 맞춘다(가 방안 — 사용자 결정). 공유 점검은 재해구분을 모르는 문자를
            #   `unclassified` 로만 남긴다(「민방공」 위급재난인데 본문에 공습경보 낱말이 없는 경우 등). 그런데 재난 정지
            #   (`planning/safety.classify` — 같은 서비스의 감시 경로)는 그 문자로 그날 · 여행 전체를 멈춘다. 성립 판정이
            #   「성립」으로 답하면 둘이 어긋나므로, **같은 기준**으로 정지 대상이면 막는다. 날씨형 위급재난은 develop 결정대로
            #   정지 대상이 아니다(실내 대체 · 안전 알림이 맡는다 — `[결정 2026-10-06 사용자]`).
            # ★`[2026-10-09]` 판정 LLM 섀도 ④(D-CS-015) — 공유 점검이 이상으로 세지 않고 재난 정지 대상도 아닌 문자(긴급재난 ·
            #   안전안내)의 주제 관련성. develop 판은 이 문자로 막지 않는다 — 그것이 비교 기준(`no_effect`)이다.
            quiet = self._unclassified_messages(report)
            if quiet:
                self._shadow(task, judge_requests.disaster_effect(place.get("name"), "activity", quiet,
                                                                  booking.get("starts_at"), indoor.get("value")),
                             value="no_effect", basis="shared_check_and_safety_stop")

        # ★`[2026-10-09]` 휴무 · 운영시간 — 공유 점검은 이것을 보지 않는다. 판정 순서는 이미 시작됨 → 재난(공유 점검) → 휴무 → 운영시간.
        hours_note: str | None = None
        hours_decision: dict[str, Any] | None = None
        live_decision: dict[str, Any] | None = None
        if isinstance(place, dict):
            closed, evidence, hours_note, hours_decision = self._hours_check(task, booking, place, seen, evidence)
            if closed is not None:
                return closed
            # ★`[2026-10-12 사용자 결정]` DB 에 있는 운영 정보로 규칙이 먼저 판정하고(위), 닫혔다고 정하지 못했을 때(연다 · 모름)
            #   웹 검색 LLM 으로 그 날짜의 운영 · 폐업(임시휴무 · 공지)을 본다. 규칙이 막으면 웹 검색을 부르지 않는다(비용 · 방침 —
            #   LLM 은 데이터의 보조). 10-12 실측: 웹을 맨 앞에 두었더니 정기휴무(매주 화요일)까지 웹이 먼저 정했다.
            live_decision, evidence, stop = self._live_status_check(task, booking, place, seen, evidence)
            if stop is not None:
                return stop
        # ★`[2026-10-11]` 고객 확인은 계약대로 `waiting` · `customer_input` 이다(D4 · 수정본 §12). 전에는 `completed` 로 답하며
        #   「말씀해 주세요」만 붙여, 코어가 답을 기다리는 Case 로 알지 못했다. 순서는 수정본 UC-A3 그대로 — 재난(`3b2`) → 운영 정보(`4a`).
        if weather_pending is not None or outdoor_ask:
            pending = [*(weather_pending or {}).get("disruptions", []), *outdoor_ask]
            kinds = ", ".join(dict.fromkeys(str(d.get("kind")) for d in pending))
            return self._ask_customer(
                task, evidence, fc.INDOOR_UNKNOWN, schema=ASK_OUTDOOR, reason="indoor_unknown_weather",
                answer=(f"현재 {self._REGION}에 {kinds}가 발효 중입니다. 이 장소가 실내인지 확인하지 못해 일정을 바꿔야 "
                        f"하는지는 판정하지 않았습니다. 야외 활동인지 알려 주세요. 1) 실내 2) 야외 — 번호나 글자로 답해 주세요."),
                disruptions=pending, indoor=indoor,
                warnings=["실내외를 모르는 장소에 야외에만 영향을 주는 사건이 걸렸다 — 변경을 단정하지 않고 고객에게 먼저 묻는다",
                          *disaster_warnings])
        kept_unknown_hours = False
        if hours_decision is not None and hours_decision.get("empty"):
            # ★`[2026-10-13]` 코어 회신 5번 — 고객이 이미 골랐으면 다시 묻지 않는다. 「다른 장소 보기」는 변경 제안(승인 대기)에
            #   대체 후보를 붙이고, 「그대로 진행」은 모르는 채로 성립을 답하되 경고를 남긴다(운영 정보를 지어내지 않는다).
            proceed = self._answered(task, "proceed", PROCEED_CHOICES)
            if proceed is None:
                return self._ask_customer(
                    task, evidence, fc.HOURS_UNKNOWN, schema=ASK_PROCEED, reason="hours_unknown", hours=hours_decision,
                    answer=("이 장소의 운영 정보(운영시간 · 휴무)를 확인하지 못해 그 부분은 판정하지 않았습니다. "
                            "그대로 진행할지, 다른 장소를 볼지 알려 주세요. 1) 그대로 진행 2) 다른 장소 보기 — 번호나 글자로 답해 주세요."),
                    warnings=["운영 정보가 비어 휴무 · 운영시간을 판정하지 못했다 — 「성립」으로 답하지 않고 고객에게 묻는다",
                              *headcount_warnings, *disaster_warnings])
            if proceed["proceed"] == "change" and isinstance(place, dict):
                return self._closed_place_change(
                    task, booking, place, seen, evidence, reason="고객 요청 — 운영 정보를 확인하지 못한 장소를 바꾼다",
                    answer=("운영 정보를 확인하지 못한 장소라 다른 장소를 보겠다고 하셔서 변경 제안을 만들었습니다. "
                            "승인 뒤에 진행됩니다."),
                    decisions={"feasible": None, "reason": "customer_chose_change", "hours": hours_decision})
            kept_unknown_hours = True

        forecast = self._checked_value(report, "forecast")
        warnings: list[str] = [*headcount_warnings, *disaster_warnings]
        decisions: dict[str, Any] = {"feasible": True, "place_confirmed": True,
                                     "headcount_checked": not missing}
        if report is not None:
            decisions["not_connected"] = report.get("not_connected", [])
        answer = f"확인한 범위에서는 성립합니다(시작까지 {remaining:.1f}시간)."
        if missing:
            answer += " 인원 · 정원 정보가 없어 정원 초과 여부는 판정하지 않았습니다."
        if hours_note:
            answer += " " + hours_note
            warnings.append("운영시간 · 휴무를 확인하지 못했다 — 판정에 넣지 않았다")
        if hours_decision is not None:
            decisions["hours"] = hours_decision
        if kept_unknown_hours:
            decisions["customer_choice"] = "keep"
            warnings.append("고객이 운영 정보를 확인하지 못한 채로 그대로 진행하기로 했다 — 휴무 · 운영시간은 판정하지 않았다")
        if live_decision is not None:
            decisions["live_status"] = live_decision
            if live_decision.get("value") in ("unchecked", "unknown"):
                warnings.append("정기 운영 정보 기준이다 — 임시휴무 · 폐업은 확인하지 못했다")
        if indoor:
            decisions["indoor"] = indoor
            if indoor.get("source") == "class":
                warnings.append("실내외는 관광공사 분류로 정한 값이다 — 장소에 적힌 값이 아니다")
            elif indoor.get("source") == "customer":
                warnings.append("실내외는 고객이 알려 준 값이다 — 장소 기록이 아니다")
            elif indoor.get("value") is None and forecast is not None:
                warnings.append("실내인지 확인하지 못해 야외 기준으로 날씨를 봤다")
        if forecast is not None:
            note, advisories = self._weather_note(forecast)
            answer += " " + note
            warnings.extend(advisories)
            decisions["weather"] = {
                "matched_hour": forecast.get("matched_hour"),
                "precipitation_probability": forecast.get("precipitation_probability"),
                "wind_speed_kmh": forecast.get("wind_speed_kmh"),
                "source": forecast.get("source"),
                "fell_back_from": forecast.get("fell_back_from", []),
                "confirmed_at": forecast.get("confirmed_at"),
            }

        return self._result(
            task, outcome="completed", confidence=0.8, evidence=evidence,
            next_action=NextAction.RESPOND, answer=answer,
            decisions=[decisions], warnings=warnings)

    # ── 판정 LLM 섀도(D-CS-015) — 고객 결과를 바꾸지 않는다 ────────────
    def _shadow(self, task: TeamTask, request: JudgeRequest, *, value: str, basis: str | None) -> None:
        """develop 판의 지금 판정(`value`)을 비교 기준으로, LLM 판정을 **백그라운드에서** 돌려 차이만 기록한다. `[2026-10-09]`

        ★판정 LLM 이 없으면(기본 `rule` — 조립이 넣지 않는다) 아무것도 안 한다. 돌려받는 값을 쓰지 않는다 — 고객 답변 ·
          `decisions` · 근거 · 실패 코드는 이 호출과 상관없다. 비교 기준은 role-activity 판 규칙(`RuleJudge`)이 아니라
          develop 판이 실제로 낸 값이다 — 섀도는 「지금 동작」과 비교해야 한다(D-CS-015 「지키는 것」).
        """
        if self.judge_llm is None or kind_mode(request.kind) != "shadow":      # ★`[2026-10-12]` 종류별로 끈다(1.4)
            return
        current = Verdict(request.kind, value, "rule", basis=basis)
        ctx = JudgeContext(case_id=task.case_id, capability=task.capability, run_id=task.run_id,
                           tenant_id=task.context.tenant_id)
        ShadowJudge(_CurrentVerdict(current), LLMJudge(self.judge_llm), runner=self.judge_runner,
                    sink=self.judge_shadow_sink, budget=self.judge_budget).judge(ctx, request)

    def _rule_first(self, task: TeamTask, request: JudgeRequest, *, basis: str | None) -> Verdict | None:
        """규칙이 「모름」인 판정을 LLM 에 맡긴다 — 종류 모드가 `llm` 이고 판정 LLM 이 꽂혀 있을 때만. `[2026-10-12]` D-CS-015 개정 2.
        휴무 · 재난은 조심하는 쪽만 받는다(`modes.rule_first`). 못 정하면 `None`."""
        if self.judge_llm is None or kind_mode(request.kind) != "llm":
            return None
        ctx = JudgeContext(case_id=task.case_id, capability=task.capability, run_id=task.run_id,
                           tenant_id=task.context.tenant_id)
        # ★`[2026-10-12]` 조립이 예산을 안 꽂았으면 웹 검색만 프로세스 안에서 센다(`LocalWebBudget` — 원문 해석은 세지 않는다)
        budget = self.judge_budget if self.judge_budget is not None else local_web_budget()
        verdict = rule_first(ctx, request, Verdict(request.kind, "unknown", "rule", basis=basis),
                             LLMJudge(self.judge_llm), budget=budget)
        return verdict if verdict.known else None

    def _live_status_check(self, task: TeamTask, booking: dict, place: dict, seen: set[str], evidence: list
                           ) -> tuple[dict[str, Any] | None, list, TeamResult | None]:
        """⑤ 실시간 운영 · 폐업(웹 공지) — **저장된 값만 읽는다.** `[2026-10-13 사용자 결정 A안]`

        ★전에는 고객 요청마다 웹 검색을 불렀다(요청 수에 비례 · p95 40.7초 · 429). 이제 웹 확인은 장소 · 날짜당 한 번 배치가 하고
          (`scripts/activity/check_live_status.py` → `activity.ac_live_status`), 여기서는 `live_lookup` 으로 읽기만 한다.
        ★`rule` · 읽기 함수 없음 → 꺼져 있다(`None`, 경고도 없다). 켜져 있는데 값이 없거나 모르면 숨기지 않는다 — `unchecked` ·
          `unknown` 으로 남기고 「임시휴무는 확인하지 못했다」 경고를 붙인다(근거 없이 성립을 확정하지 않는다).
        ★`shadow` → 값만 기록하고 고객 결과는 그대로다. `llm` → 「닫혔다」(인용이 있는 것만 저장돼 있다)이면 대체 장소를 붙여
          바꾸자고 제안한다(승인 대기). 「열었다」는 막지도 풀지도 않는다 — 규칙의 휴무 판정을 바꾸지 않는다.
        반환: (`decisions.live_status` 에 실을 값 | None, 근거, 여기서 멈출 결과 | None).
        """
        mode = kind_mode(LIVE_STATUS)
        if mode == "rule" or self.live_lookup is None or not place.get("name"):
            return None, evidence, None
        day = self._visit_date(booking.get("starts_at"))
        if day is None:
            return {"value": "unchecked", "source": "stored", "why": "visit_date_unknown"}, evidence, None
        try:
            stored = self.live_lookup(task.context.tenant_id, booking.get("place_id"), day)
        except Exception as exc:  # noqa: BLE001 — 읽지 못한 것을 「열었다」로 보지 않는다. 종류만 남기고 모름
            _failure_log.warning("live_status_lookup_failed %s", type(exc).__name__)
            return {"value": "unknown", "source": "stored", "why": f"lookup_failed:{type(exc).__name__}"}, evidence, None
        if stored is None:
            return {"value": "unchecked", "source": "stored", "visit_date": day.isoformat()}, evidence, None
        citations = [{"url": c.get("url"), "quote": c.get("quote"), "published_at": c.get("published_at")}
                     for c in stored.get("citations") or [] if isinstance(c, dict)]
        checked_at = stored.get("checked_at")
        decision = {"value": stored.get("value"), "source": "stored", "visit_date": day.isoformat(),
                    "checked_at": checked_at.isoformat() if hasattr(checked_at, "isoformat") else checked_at,
                    "citations": citations}
        if decision["value"] == "unknown":
            return decision, evidence, None
        evidence = self._evidence(task, source_id="judge.live_status", claim="웹 공지상 운영 상태(저장된 확인)",
                                  value={"value": decision["value"], "checked_at": decision["checked_at"],
                                         "citations": citations}, base=evidence)
        if decision["value"] != "closed" or mode != "llm":
            return decision, evidence, None
        quote = next((c["quote"] for c in citations if c.get("quote")), None)
        stop = self._closed_place_change(
            task, booking, place, seen, evidence, reason=f"웹 공지 — {quote or '휴무 · 폐업'}",
            answer=(f"웹 공지에서 이 장소가 예약 날짜에 운영하지 않는다고 확인했습니다"
                    f"{f'(「{quote}」)' if quote else ''}. 변경 제안을 만들었고 승인 뒤에 진행됩니다."),
            decisions={"feasible": False, "reason": "live_closed",
                       "failure_code": self._record_failure(task, fc.LIVE_CLOSED), "live_status": decision})
        return decision, evidence, stop

    @staticmethod
    def _visit_date(starts_at: Any):
        """방문 시각 → 한국 날짜. 읽지 못하면 `None`."""
        from .judge.requests import KST

        if isinstance(starts_at, str):
            try:
                starts_at = datetime.fromisoformat(starts_at)
            except ValueError:
                return None
        if not isinstance(starts_at, datetime):
            return None
        return (starts_at.astimezone(KST) if starts_at.tzinfo else starts_at).date()

    def _disaster_impact(self, task: TeamTask, booking: dict, place: dict, report: dict[str, Any],
                         indoor: dict[str, Any], seen: set[str], evidence: list
                         ) -> tuple[Impact | None, dict[str, Any], list, TeamResult | None]:
        """재난문자를 수정본 §8 분류표로 가른다(D2). `[2026-10-11]` 구현 계획 2.4.

        반환: (분류 결과 | None, 재난문자를 뺀 점검 결과, 근거, 여기서 멈출 결과 | None).
        ★공유 점검의 재난문자 항목이 `ok` 일 때만 한다. 미연결 · 실패는 공유 점검 판정 그대로 둔다(분류 결과 `None`).
        ★문자는 `read.disaster` 로 다시 읽는다 — 공유 점검은 실내 장소면 날씨형 문자(호우 · 산사태 …)를 미리 빼는데,
          §8 은 그중 여럿을 지역 위험형(실내도 막음)으로 본다. 같은 소스 · 같은 구 판정(`disaster_msg.near()`)이고 소스가
          지역 단위로 캐시해 외부 호출은 늘지 않는다.
        ★다시 읽지 못하면 「영향 없음」으로 보지 않고 운영 담당자에게 넘긴다(구현 계획 §2.5-E — 재난 사실을 최신으로 확인 못 함).
        """
        checks = [c for c in report.get("checks") or [] if isinstance(c, dict) and c.get("category") == "disaster_msg"]
        if not checks or checks[0].get("status") != "ok":
            return None, report, evidence, None
        found = self._read(task, "read.disaster", {"latitude": place.get("latitude"), "longitude": place.get("longitude"),
                                                   "at": booking.get("starts_at"), "address": place.get("address")}, seen)
        evidence = self._evidence(task, source_id="read.disaster", claim="장소 지역의 재난문자", value=found, base=evidence)
        if not isinstance(found, dict) or found.get("covered") is False:
            return None, report, evidence, self._escalate(task, fc.DISASTER_UNCONFIRMED, evidence, warnings=[
                "재난문자를 다시 읽지 못했다 — 「영향 없음」으로 보지 않는다"])
        messages = [*(found.get("for_region") or []), *(found.get("unclassified") or [])]
        starts_at = booking.get("starts_at")
        impact = assess(messages, indoor.get("value"), ImpactRules.load(),
                        at=starts_at if isinstance(starts_at, datetime) else None, place_name=place.get("name"))
        others = [d for d in report.get("disruptions") or [] if d.get("category") != "disaster_msg"]
        rest = {**report, "disruptions": others,
                "verdict": "disrupted" if others else ("clear" if report.get("verdict") == "disrupted" else report.get("verdict"))}
        return impact, rest, evidence, None

    @staticmethod
    def _unclassified_messages(report: dict[str, Any] | None) -> list[dict[str, Any]]:
        """공유 점검이 「모르는 구분」으로만 남긴 재난문자(정지 대상이 없다고 확인된 뒤에 부른다)."""
        if not isinstance(report, dict):
            return []
        return [message for check in report.get("checks") or []
                if isinstance(check, dict) and check.get("category") == "disaster_msg"
                for message in check.get("unclassified") or [] if isinstance(message, dict)]

    def _indoor_outdoor(self, task: TeamTask, booking: dict, place: dict, seen: set[str], evidence: list
                        ) -> tuple[dict[str, Any], list, dict[str, Any] | None]:
        """실내외 — 장소에 적힌 값 → 관광공사 분류(`read.place_class`) 순. `[2026-10-09]` team 통합 ⑤(사용자 결정: develop 기준 + 분류).

        ★분류 규칙은 develop 의 것(`itinerary.weather_from_class` — 확실한 대 · 중분류만)이다. role-activity 판의 장소명 짐작은
          옮기지 않았다 — 일정 짜기(`fill_weather_sensitive`)와 판단이 갈리지 않게.
        반환: (`{value: True|False|None, source: place|class|None}`, 근거, 읽은 분류 | None). `value` None 이면 모른다 — 공유
        점검이 야외처럼 보고 `indoor_unknown` 을 붙인다.
        ★`[2026-10-09]` 분류까지 모르면 판정 LLM 섀도(③)를 건다(D-CS-015) — 비교 기준은 develop 판의 지금 값(모름)이다.
        """
        known = place.get(self._WEATHER_SENSITIVE_KEY)
        if known is not None:
            return {"value": bool(known), "source": "place"}, evidence, None
        found = self._read(task, "read.place_class", {"place_id": booking.get("place_id")}, seen)
        found = found if isinstance(found, dict) else None
        value = (found or {}).get("weather_sensitive")
        if value is None:
            self._shadow(task, judge_requests.weather_sensitive(place.get("name"), (found or {}).get("lcls2")),
                         value="unknown", basis="place_and_tour_class_unknown")
            return {"value": None, "source": None}, evidence, found
        evidence = self._evidence(task, source_id="read.place_class", claim="관광공사 분류로 정한 실내외",
                                  value=found, base=evidence)
        return {"value": bool(value), "source": "class", "lcls1": found.get("lcls1"),
                "lcls2": found.get("lcls2")}, evidence, found

    @staticmethod
    def _answered(task: TeamTask, field: str, choices: list[dict[str, Any]]) -> dict[str, Any] | None:
        """고객이 `choices` 중 하나로 답했나 — 맞는 선택지를 돌려준다. 없으면 `None`(다시 묻는다). `[2026-10-13]` 코어 회신 5번.

        ★글자(「야외」 · 「그대로 진행」)는 이전 답 어디에 있어도 쓴다 — 질문이 둘 이어지면 앞 답을 잃지 않게.
        ★번호(「2번」)는 **방금 물은 질문**이 이 칸일 때만 쓴다 — 두 질문의 1번 · 2번이 다르다. 자유 글은 해석하지 않는다."""
        from app.domains.travel_ops.instances._shared.conversation_work import _choice, replies

        answers = replies(task)
        found: dict[str, Any] | None = None
        for answer in answers:
            exact = [c for c in choices if answer.strip() in (c["message"], c["label"])]
            if len(exact) == 1:
                found = exact[0]
        pending = task.context.current_state.get("required_input_schema") or {}
        if answers and pending.get("required") == [field]:
            option = _choice(choices, answers[-1])
            if option is not None:
                found = option
        return found

    def _ask_customer(self, task: TeamTask, evidence: list, code: str, *, schema: dict[str, Any], answer: str,
                      warnings: list[str], **decisions: Any) -> TeamResult:
        """고객 확인 요청 — `waiting` · `wait_for_input` · `wait_reason='customer_input'`(수정본 §12 · 계약 04 §5). `[2026-10-11]`

        ★전에는 `completed` + `status: insufficient_info`(계약에 없는 값)로 답했다(D4). 성립을 단정하지 않는 것은 그대로다 —
          `feasible` 은 `None`(판정하지 않음)이다. 실패 코드는 `decisions` 와 로그에만 싣는다 — 넘김(`escalated`)이 아니다.
        ★`[2026-10-13]` 재개는 `_answered` 가 읽는다 — 코어는 답을 `customer_input` 으로 이미 넘긴다(코어 회신 5번). 질문에 선택지
          (`choices`)를 붙여 두었고, 고객 답이 선택지와 같으면 그 값으로 다시 판정한다.
        """
        return self._result(
            task, outcome="waiting", confidence=0.5, evidence=evidence,
            next_action=NextAction.WAIT_FOR_INPUT, answer=answer, required_input_schema=schema,
            decisions=[{"feasible": None, **decisions, "failure_code": self._record_failure(task, code)}],
            warnings=warnings)

    @classmethod
    def _safety_event(cls, impact: Impact | None, report: dict[str, Any]):
        """재난 정지 대상 문자 — §8 분류를 했으면 다시 읽은 문자 전부에서, 못 했으면 전처럼 공유 점검의 「모르는 구분」에서. `[2026-10-11]`"""
        if impact is None:
            return cls._unclassified_safety_event(report)
        causes = [{**m, "category": "disaster_msg"}
                  for m in [*impact.blocks, *impact.ask, *impact.unclassified, *impact.no_effect]]
        return classify_safety(causes) if causes else None

    @staticmethod
    def _unclassified_safety_event(report: dict[str, Any] | None):
        """공유 점검이 「모르는 구분」(`unclassified`)으로만 남긴 재난문자 가운데 재난 정지 대상(그날 · 여행 전체)이 있으면
        가장 심각한 것 하나. 없으면 `None`. ★공유 점검이 이미 이상으로 센 문자는 위에서 막혔으므로 여기서 다시 보지 않는다."""
        if not isinstance(report, dict):
            return None
        causes = [{**message, "category": "disaster_msg"}
                  for check in report.get("checks") or []
                  if isinstance(check, dict) and check.get("category") == "disaster_msg"
                  for message in check.get("unclassified") or [] if isinstance(message, dict)]
        return classify_safety(causes) if causes else None

    def _hours_check(self, task: TeamTask, booking: dict, place: dict, seen: set[str], evidence: list
                     ) -> tuple[TeamResult | None, list, str | None, dict[str, Any] | None]:
        """휴무 · 운영시간 판정 — `[2026-10-09]` role-activity 판(정기휴무 규칙)을 develop 설계 위로 옮겼다.

        ★데이터는 **DB 에 읽어 둔 값**(`read.place_hours` — 새벽 작업 `catalog_hours`)만 본다. 바깥을 부르지 않는다.
        ★요일 칸은 develop 표준 함수(`place_hours.hours_on` · `fits`)가 읽는다. 요일표가 펴지 못하는 휴무(매월 n번째 주 ·
          공휴일 조건)는 휴무 **원문**을 휴무 규칙(`closure_rules.read_closure`)으로 읽는다 — 원문이 정한 값이 요일 칸보다 앞선다
          (「매주 화요일 휴무, 단 공휴일이면 개방」에서 공휴일 화요일은 연다).
        ★모르면 모른다: 「성립」으로 단정하지 않고 안내 문구 · `decisions.hours` 에 남긴다. 휴무 · 운영시간 밖이면
          공유 점검의 이상과 같은 길(`_propose_change` — 승인 대기)로 보낸다.
        반환: (불가 결과 | None, 근거, 안내 문구 | None, 판정 기록 | None)
        """
        starts_at = booking.get("starts_at")
        if not isinstance(starts_at, datetime):
            return None, evidence, None, None
        hours = self._read(task, "read.place_hours", {"place_id": booking.get("place_id"), "at": starts_at}, seen)
        evidence = self._evidence(task, source_id="read.place_hours", claim="운영시간 · 휴무", value=hours, base=evidence)
        # ★`[2026-10-11]` 운영 정보가 **비어 있음**(`empty` — 수정본 UC-A3 `4a`, 받는 쪽이 고객에게 묻는다)과 원문은 있는데
        #   **읽지 못함**(`5b` — 「운영시간 미확인」 단서 + 유지)을 가른다. 전에는 둘 다 단서만 붙여 「성립」으로 답했다(부록 A #3).
        #   「비어 있음」은 도구가 장소를 찾고 **값이 없다고 답한 것**만이다. `None`(장소 id 가 없어 조회하지 않음)은 비어 있다는
        #   사실이 아니라서 전처럼 단서만 붙인다.
        if not isinstance(hours, dict):
            return None, evidence, "운영시간 · 휴무를 확인하지 못해 그 부분은 판정하지 않았습니다.", {"known": False}
        # ★`[2026-10-12]` 판정 자체는 `verdicts.hours_verdict` 하나가 한다 — 코어 계획 검증 · 감시가 끼움 자리로 같은 함수를 부른다.
        #   여기서는 공휴일 조회(도구) · 근거 · 섀도 · 변경 제안만 맡는다.
        restdate = hours.get("restdate_text")
        holidays: dict[Any, Any] = {}
        for when in holidays_needed(restdate, starts_at):
            holidays[when] = self._read(task, "read.holiday", {"on": when.isoformat()}, seen)
            if holidays[when] is None:
                break      # ★같은 소스가 또 모른다고 할 것이다 — 응답만 늦어진다
        if holidays:
            evidence = self._evidence(task, source_id="read.holiday", claim="공휴일 여부",
                                      value={d.isoformat(): v for d, v in holidays.items()}, base=evidence)
        verdict = hours_verdict(hours, starts_at, holiday=holidays.get)
        if verdict["empty"]:
            return None, evidence, None, {k: verdict[k] for k in ("known", "empty", "source", "why_unknown")}
        if restdate:
            # ★`[2026-10-09]` 판정 LLM 섀도 ①(D-CS-015) — 같은 원문 · 같은 공휴일 사실로. 비교 기준은 위 규칙 값이다.
            self._shadow(task, judge_requests.closure(restdate, starts_at,
                                                      {d.isoformat(): v for d, v in holidays.items()}),
                         value={True: "closed", False: "not_closed"}.get(verdict["closed"], "unknown"),
                         basis=verdict["closure_reason"])
        # ★`[2026-10-12]` D-CS-015 개정 2 — 규칙이 휴무 원문을 못 읽었으면 LLM 에 맡긴다. 「휴무다」만 받는다(조심하는 쪽).
        if verdict["closed"] is None and restdate:
            by_model = self._rule_first(task, judge_requests.closure(
                restdate, starts_at, {d.isoformat(): v for d, v in holidays.items()}), basis=verdict["closure_reason"])
            if by_model is not None:
                verdict = {**verdict, "closed": True, "closure_reason": "llm", "auto_read": True,
                           "quote": by_model.quotes[0] if by_model.quotes else None}
        closed, fit = verdict["closed"], verdict["within_hours"]
        record: dict[str, Any] = {"known": verdict["known"], "source": verdict["source"],
                                  "closed": closed, "closure_reason": verdict["closure_reason"],
                                  "restdate_text": restdate, "usetime_text": verdict["usetime_text"],
                                  "auto_read": verdict["auto_read"]}
        # ★`[2026-10-12]` D-CS-015 개정 2 — 모델이 읽은 요일표로 판정했으면 안내를 붙인다(`notices`)
        auto = HOURS_AUTO_READ if verdict["auto_read"] else None
        if closed:
            quote = verdict["quote"]
            record["failure_code"] = self._record_failure(task, fc.CLOSED_WEEKDAY)
            told = f"휴무 안내({restdate}) 중 「{quote}」에 해당해" if quote and restdate else "정기휴무일이라"
            return (self._closed_place_change(
                task, booking, place, seen, evidence, reason=f"휴무 — {quote or '정기휴무일'}",
                answer=with_notice(f"이 날은 {told} 이 일정은 바꿔야 합니다. 변경 제안을 만들었고 승인 뒤에 진행됩니다.", auto),
                decisions={"feasible": False, "reason": "closed_weekday", "hours": record}),
                evidence, None, record)
        record["within_hours"] = fit
        if fit is False:
            record["failure_code"] = self._record_failure(task, fc.OUTSIDE_HOURS)
            return (self._closed_place_change(
                task, booking, place, seen, evidence, reason="운영시간 밖",
                answer=with_notice("예약 시각이 운영시간 밖이라 이 일정은 바꿔야 합니다. "
                                   "변경 제안을 만들었고 승인 뒤에 진행됩니다.", auto),
                decisions={"feasible": False, "reason": "outside_hours", "hours": record}),
                evidence, None, record)
        note = None if fit is True else "운영시간 · 휴무를 확인하지 못해 그 부분은 판정하지 않았습니다."
        if verdict["needs_caveat"] and fit is True:
            note = "공휴일과 겹치는 경우 등 휴무 예외가 있을 수 있습니다."
        if fit is True:
            note = with_notice(note, auto)
        return None, evidence, note, record

    def _closed_place_change(self, task: TeamTask, booking: dict, place: dict, seen: set[str], evidence: list, *,
                             reason: str, answer: str, decisions: dict[str, Any]) -> TeamResult:
        """그 장소가 그 시각에 닫혀 있다(휴무 · 운영시간 밖) — 변경 제안에 **대체 장소 후보**를 붙인다. `[2026-10-09]` team 통합 ④.

        ★role-activity 판의 대체 장소 계산(`ReplacementMixin._recommend_alternatives` — 관광공사 목록에서 비슷한 곳 → 가까운 곳,
          그 시각에 여는지 다시 확인된 곳만 안내문에)을 그대로 쓴다. 계산만 하고 고르지 않는다 — 제안은 여전히 `booking.change`
          (승인 대기)이고 후보는 `decisions.alternatives` 와 답변에만 실린다.
        ★장소를 바꾸면 풀리는 사유에만 붙인다. 재난 정지(`safety_event`)는 그날 · 여행 전체를 멈추는 결정이라 붙이지 않고,
          공유 점검의 이상(`disrupted` — 날씨 · 통제)은 감시 경로의 대체 계산(`plan_activity_adjustment`)이 맡는다.
        ★후보를 못 찾거나 확인하지 못하면 그렇다고 말한다(`status` unknown · ranked 0곳) — 변경 제안은 그대로 만든다.
        """
        alternatives, evidence, note, warnings = self._recommend_alternatives(
            task, place, booking.get("starts_at"), seen, evidence, decisions, booking=booking)
        return self._propose_change(task, booking, evidence, reason=reason,
                                    answer=f"{answer}\n{note}" if note else answer,
                                    decisions={**decisions, "alternatives": alternatives}, warnings=warnings)

    # ── 성립 점검 부품 ────────────────────────────────────────
    #: 점검할 지역. ★v11 §1 — 대상 도시는 서울 하나다.
    _REGION = "서울"

    @staticmethod
    def _checked_value(report: dict[str, Any] | None, category: str) -> dict[str, Any] | None:
        """점검 결과에서 한 항목의 값을 꺼낸다. 해당 없음·미연결이면 `None`."""
        for check in (report or {}).get("checks", []):
            if check.get("category") == category and check.get("status") == "ok":
                return check.get("value")
        return None

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
    def _propose_change(self, task: TeamTask, booking: dict, evidence: list, *,
                        reason: str | None = None, answer: str | None = None,
                        decisions: dict[str, Any] | None = None, warnings: list[str] | None = None) -> TeamResult:
        """★대안을 실행하지 않는다. `ActionProposal` 로 승인 대기에 올린다.

        `reason` 이 없으면 고객 문장 그대로(고객이 바꿔 달라고 한 경우), 있으면
        점검이 찾은 이상(감시·점검이 바꾸자고 하는 경우)이다.
        """
        # ★`[2026-09-29]` 제안 종류를 `activity.change` → `booking.change` 로 바꿨다. 전에는 승인해도
        #   **실행할 처리기가 없었다**(등록된 처리기: booking.cancel·booking.change·booking.revert·itinerary.apply,
        #   `build_action_handlers().types()` 실측). 인자(`booking_id`·`reason`)가 같고, 그 처리기는 업체 예약을
        #   건드리지 않고 `change_requested` + 변경 링크 인계만 한다(`booking_actions.BookingChange`).
        #   기록 — `wiki/records/reports/2026-09-28_1826_Activity_PR6_전수검수_리포트.md`
        proposal = self._proposal(
            task, "booking.change",
            {"booking_id": booking.get("booking_id"), "reason": reason or task.input_text},
            evidence)
        return self._result(
            task, outcome="completed", confidence=0.6, evidence=evidence,
            next_action=NextAction.WAIT_FOR_APPROVAL,
            answer=answer or "변경 제안을 만들었습니다. 승인 뒤에 진행됩니다.",
            action_proposals=[proposal],
            decisions=[{"proposed": "booking.change", **(decisions or {})}], warnings=list(warnings or []))

    # ── 취소 조건 읽기 ────────────────────────────────────────
    #
    # ★★`[2026-09-23]` **이 둘은 전에 언제나 `None` 을 냈다.** `read.policy` 가 주는
    #   `PolicyChunk` 를 `isinstance(chunk, dict)` 로 걸렀기 때문이다 — 그 검사가 항상
    #   거짓이라 어떤 코퍼스를 넣어도 취소 기한·위약금율이 안 나왔고, 제품이 약속한
    #   「지금 취소하면 얼마인가」가 한 번도 답해진 적이 없다. 이제 **구조화된 조건**
    #   (`read.booking_terms` · 마이그레이션 023)을 읽는다.
    #   기록 — `wiki/records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md`
    #
    # ★**청크 목록을 받으면 그건 잘못 부른 것이다.** 조용히 `None` 을 내면 그 오진이
    #   또 몇 달 간다 — 모양이 다르면 그렇게 말한다(아래 `_terms_dict`).

    @staticmethod
    def _terms_dict(terms: Any) -> dict[str, Any] | None:
        """구조화된 취소 조건만 받는다. `None`(모름)과 **잘못된 모양**을 가른다."""
        if terms is None:
            return None
        if isinstance(terms, dict):
            return terms
        raise TypeError(
            "취소 조건은 `read.booking_terms` 가 주는 dict 여야 한다 — 받은 것: "
            f"{type(terms).__name__}. RAG 청크에서 수치를 꺼내려던 옛 경로다"
            " (debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md)")

    @classmethod
    def _terms_hours(cls, terms: Any, key: str) -> float | None:
        found = cls._terms_dict(terms)
        if found is None or found.get(key) is None:
            return None
        try:
            return float(found[key])
        except (TypeError, ValueError):
            return None

    @classmethod
    def _penalty_rate(cls, terms: Any, remaining: float) -> float | None:
        """남은 시간 구간별 위약금율. 조건에 구간이 없으면 `None`(모름).

        ★표는 「남은 시간이 이 값보다 적으면 이 율」이다. 여러 구간에 걸리면 **가장 센
          율**을 고른다 — 고객에게 유리한 쪽으로 틀리면 나중에 더 받아야 하고, 그건
          우리가 말을 바꾸는 것이 된다.
        """
        found = cls._terms_dict(terms)
        table = (found or {}).get("penalty_by_hours")
        if not isinstance(table, dict):
            return None
        best: float | None = None
        for hours, rate in table.items():
            try:
                if remaining < float(hours):
                    value = float(rate)
                    best = value if best is None else max(best, value)
            except (TypeError, ValueError):
                continue
        return best


class _CurrentVerdict:
    """섀도의 비교 기준 — develop 판이 이미 낸 판정을 그대로 돌려준다(`ShadowJudge` 의 규칙 자리)."""

    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict

    def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:  # noqa: ARG002
        return self._verdict


def _without_cleared_disasters(report: dict[str, Any], item: Any) -> dict[str, Any]:
    """공유 점검 결과에서 활동 판정상 영향이 없는 재난문자 이상을 뺀다. 재난문자 말고는 그대로다.

    ★실내외를 모르는(야외 위험형 · `ask`) 문자와 분류되지 않은 문자는 **남긴다** — 감시 루프에서는 묻지 않고(멘토 #3),
      공유 점검이 이미 이상으로 센 것을 활동 쪽 「모름」으로 지우지 않는다.
    """
    disruptions = report.get("disruptions") or []
    messages = [d for d in disruptions if d.get("category") == "disaster_msg"]
    if not messages:
        return report
    starts_at = item.starts_at if isinstance(item.starts_at, datetime) else None
    place = item.place or {}
    rules = ImpactRules.load()

    def cleared(message: dict[str, Any]) -> bool:
        return bool(assess([message], place.get("weather_sensitive"), rules,
                           at=starts_at, place_name=place.get("name")).no_effect)

    others = [d for d in disruptions if d.get("category") != "disaster_msg" or not cleared(d)]
    if len(others) == len(disruptions):
        return report
    return {**report, "disruptions": others, "verdict": "disrupted" if others else "clear",
            "cleared_by_activity": len(disruptions) - len(others)}


def plan_activity_trigger(work: ItineraryWork, task: TeamTask, ctx: dict[str, Any], item: Any):
    """감시 — 활동 항목 하나를 **다시 점검**하고 대안을 계산한다(쓰지 않는다). 결과: 변경 · `NoChange` · `Consent`(먼저 묻기) · `TeamResult`(여기서 멈춤 — 점검 소스 실패 · 모름).

    ★`[2026-10-03]` `ActivityTeam.handle_trigger` 에서 떼어 냈다 — 같은 여행의 문제 묶음(`trip_watch_batch`)이 한 초안 위에서 항목마다 부른다. `work` 는 도구를 읽는 Team(도구 선언은 그 Team 의 것).
    """
    if item.kind != "activity" or item.place is None:
        return work._escalate(task, "target_kind_mismatch", ctx["evidence"])
    report = work._read(task, "read.disruptions", work.check_arguments(item.place, item.starts_at), ctx["seen"])
    ctx["evidence"] = work._evidence(task, source_id="read.disruptions", claim="성립 점검", value=report, base=ctx["evidence"])
    if report is None or report.get("verdict") == "fatal":
        # ★점검 소스가 대체까지 실패 — 「clear」로 읽지 않는다(결정 15).
        return work._escalate(task, "fatal_source_failure", ctx["evidence"])
    if report.get("verdict") != "disrupted":
        return NoChange("clear")
    # ★`[2026-10-12]` 공유 점검이 이상으로 센 **재난문자**를 활동 판정(수정본 §8 + D2-1)으로 다시 본다 — 「복구 완료」 · 통제 시간이
    #   지난 문자 · 실내 장소의 야외 위험형은 바꿀 사유가 아니다. 남는 이상이 없으면 일정을 바꾸지 않는다. 막는 쪽으로 더하지는
    #   않는다 — 감시 루프가 활동을 부르는 것은 공유 점검이 이상이라고 한 뒤뿐이라서다(코어 끼움 자리 `activity_verdicts` 협의 중).
    report = _without_cleared_disasters(report, item)
    if report.get("verdict") != "disrupted":
        return NoChange("clear")
    if needs_consent(report, (ctx.get("trip") or {}).get("constraints") or {}):
        return Consent(report)
    places = work.catalog(task, ctx)
    if places is None:
        return work._unknown(task, "장소 목록", ctx["evidence"])
    # ★`[2026-09-29]` 대체 활동은 「비슷한 곳(관광공사 분류·구) → 가까운 곳」 순 — 설문 우선순위가 선호를 정한다
    preference = preference_of((ctx.get("trip") or {}).get("constraints"))
    # ★`[2026-10-02 결함 인계 #1]` 재점검은 앞 순위 몇 곳만 · 도구 한도에 걸려도 예외로 터지지 않는다(못 본 곳은 고르지 않는다)
    plan = plan_activity_adjustment(item=item, report=report, places=places,
                                    check=work.safe_recheck(task, ctx), now=ctx["at"], items=ctx["items"],
                                    similarity=partial(score, preference=preference),
                                    distance_first=distance_first(preference),
                                    limit=ACTIVITY_RECHECK_LIMIT)
    if isinstance(plan, NoChange) and plan.status == "unresolved" and weather_only(report):
        # ★`[2026-09-29]` 자동으로 못 찾았으면 사람에게 넘기지 않고 「바꿀까요?」로 — 「바꿔 줘」면 관광공사 목록까지 뒤진다
        return Consent(report)
    return plan
