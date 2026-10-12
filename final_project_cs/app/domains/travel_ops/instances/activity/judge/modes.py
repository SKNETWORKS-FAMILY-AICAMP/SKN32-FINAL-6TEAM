# -*- coding: utf-8 -*-
"""모드별 판정기 — `rule` · `shadow` · `llm` (설정 `activity_judge_mode`).

★섀도 모드(이 브랜치의 기본값): **규칙 판정을 즉시 돌려주고**, LLM 판정은 백그라운드 스레드에서 돌려
  둘의 차이를 한 줄 JSON 로그(`acop.activity.judge_shadow`)로만 남긴다. 고객 답변 · `decisions` ·
  실패 코드는 지금과 같다. 웹 검색이 20초를 넘을 수 있어(스파이크 Q4) 응답 경로에 두지 않는다(계획서 §5.6 (가)).
★로그에는 좌표 · 장소명 · 고객 문장 · 모델의 판단 이유를 싣지 않는다 — 코드와 숫자만. 판단 이유 원문은
  감사 기록(`llm_calls.response_json`)에 있고 `run_id` 로 이어진다.
★`[2026-10-06]` 같은 기록을 **표에도** 남긴다(`activity_judge_shadow`, A안) — 앱에 로깅 설정이 없어
  `INFO` 로그는 운영에서 아무 데도 안 남았다. 표에 쓰는 함수(`sink`)는 조립이 넣는다. 쓰기에 실패해도
  판정은 그대로 가고, 실패는 `WARNING` 로 보이게 남긴다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, Protocol

from .. import failure_codes as fc
from .llm import LLMJudge
from .rule import RuleJudge, SharedCheckFacts
from .types import JudgeContext, JudgeRequest, Verdict

SHADOW_LOGGER_NAME = "acop.activity.judge_shadow"
_shadow_log = logging.getLogger(SHADOW_LOGGER_NAME)

#: LLM 모드에서 **호출 실패**면 규칙으로 답한다. 근거 검증 탈락(`llm_uncited`)은 실패가 아니라 「모름」이라
#:  규칙으로 덮지 않는다 — LLM 모드를 켠다는 것은 「LLM 이 근거를 못 대면 모른다고 말한다」를 고른 것이다.
_CALL_FAILURES = frozenset({fc.LLM_TIMEOUT, fc.LLM_SCHEMA_INVALID, fc.LLM_ERROR})


class ActivityJudge(Protocol):
    def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict: ...


class BackgroundRunner:
    """섀도 판정을 돌리는 스레드 풀. 밀린 일이 상한을 넘으면 **받지 않는다**(고객 응답을 기다리게 하지 않는다)."""

    def __init__(self, *, max_workers: int, max_pending: int) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="activity-judge-shadow")
        self._max_pending = max_pending
        self._pending = 0
        self._lock = threading.Lock()

    def submit(self, work) -> bool:
        with self._lock:
            if self._pending >= self._max_pending:
                return False
            self._pending += 1
        future = self._executor.submit(work)
        future.add_done_callback(lambda _: self._done())
        return True

    def _done(self) -> None:
        with self._lock:
            self._pending -= 1


_runner: BackgroundRunner | None = None
_runner_lock = threading.Lock()


def default_runner() -> BackgroundRunner:
    global _runner
    with _runner_lock:
        if _runner is None:
            from app.core.settings import get_guardrails

            g = get_guardrails()
            _runner = BackgroundRunner(max_workers=int(g.get("travel.activity_judge.shadow_max_workers")),
                                       max_pending=int(g.get("travel.activity_judge.shadow_max_pending")))
        return _runner


#: 종류별로 받는 값(`travel.activity_judge.kind_modes`). ★`llm` 은 아직 받지 않는다 — D-CS-015 개정 전. `[2026-10-12]`
KIND_MODES = ("rule", "shadow")


def kind_mode(kind: str, modes: Any = None) -> str:
    """그 판정 종류를 섀도로 돌리나 — `rule` · `shadow`(구현 계획 1.4). `modes` 를 안 주면 가드레일에서 읽는다.
    ★표에 없는 종류는 `rule`(부르지 않는다) — 새 종류가 설정 없이 몰래 LLM 을 부르지 않게.
    ★받지 않는 값(`llm` · 오타 · YAML 이 `off` 를 읽은 `False`)은 **멈춘다**(`ValueError`) — 조용히 끄거나 켜지 않는다."""
    if modes is None:
        from app.core.settings import get_guardrails

        modes = get_guardrails().get("travel.activity_judge.kind_modes")
    if not isinstance(modes, dict):
        raise ValueError(f"travel.activity_judge.kind_modes 는 표여야 한다: {modes!r}")
    value = modes.get(kind, "rule")
    if value not in KIND_MODES:
        raise ValueError(f"travel.activity_judge.kind_modes.{kind} = {value!r} — {list(KIND_MODES)} 중 하나여야 한다")
    return value


def _run(coro) -> Any:
    """동기 코드에서 코루틴 하나를 끝까지 돌린다. ★Team 코드는 이벤트 루프 안에서 불리므로 새 스레드에서 돈다."""
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="activity-judge") as pool:
        return pool.submit(asyncio.run, coro).result()


#: 판정 LLM 호출 예산의 줄 이름 — 웹 검색(실시간 운영)은 호출당 약 $0.032, 나머지(원문 해석)는 약 $0.0003 이라 따로 센다.
#:  ★조립이 `external_call_budget` 에 이 이름으로 줄을 만들어 `ActivityTeam.judge_budget` 에 꽂는다(코어 협의 — 협의 메모 요청 7).
BUDGET_METER_TEXT = "activity_judge"
BUDGET_METER_WEB = "activity_judge_web"


def budget_meter(kind: str) -> str:
    """판정 종류 → 예산 줄 이름. `[2026-10-12]`"""
    return BUDGET_METER_WEB if kind == "live_status" else BUDGET_METER_TEXT


def budget_caps(guard: Any = None) -> dict[str, dict[str, int]]:
    """예산 줄별 `{"day": n, "month": n}` — `travel.activity_judge.budget`. 조립이 `CallBudget(caps=…)` 에 그대로 넘긴다."""
    if guard is None:
        from app.core.settings import get_guardrails

        guard = get_guardrails()
    table = guard.get("travel.activity_judge.budget")
    return {meter: {"day": int(table[name]["day"]), "month": int(table[name]["month"])}
            for name, meter in (("text", BUDGET_METER_TEXT), ("web", BUDGET_METER_WEB))}


class ShadowJudge:
    def __init__(self, rule: RuleJudge, llm: LLMJudge, *, runner: Any | None = None,
                 sink: Any | None = None, budget: Any | None = None) -> None:
        """`budget`: 판정 종류 → 「불러도 되나」(`True`/`False`). 부르기 **전에** 한 칸을 확보하는 함수다(조립이 넣는다).
        `None` 이면 세지 않는다(지금까지와 같다)."""
        self.rule = rule
        self.llm = llm
        self._runner = runner
        self._sink = sink
        self._budget = budget

    def _within_budget(self, kind: str) -> bool:
        """★세다가 실패하면 **부르지 않는다** — 섀도는 고객 답에 쓰이지 않아 안 불러도 손해가 없고, 비용 상한이 먼저다.
        (모델 서버 넘김 장치는 반대로 부른다 — 그쪽은 고객 응답이 걸려 있다.)"""
        if self._budget is None:
            return True
        try:
            return bool(self._budget(kind))
        except Exception as exc:  # noqa: BLE001 — 세는 일이 판정을 막지 않게, 대신 부르지 않는다
            _shadow_log.warning("activity judge budget unreadable (%s) — skipping the LLM call", type(exc).__name__)
            return False

    def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:
        rule_verdict = self.rule.judge(ctx, request)
        if not self._within_budget(request.kind):
            # ★`[2026-10-12]` 예산 상한(구현 계획 4.6 · 전달사항 「비용 제한」) — 부르지 않고 건너뜀으로 남긴다
            _emit(_record(ctx, request, event="activity_judge_shadow_skipped", rule=rule_verdict,
                          error="budget_exhausted"), self._sink)
            return rule_verdict

        def work() -> None:
            try:
                llm_verdict = asyncio.run(self.llm.judge(ctx, request))
            except Exception as exc:  # LLMJudge 는 던지지 않는다 — 여기 오면 계층의 결함이다. 보이게 남긴다
                _emit(_record(ctx, request, event="activity_judge_shadow_error", rule=rule_verdict,
                              error=type(exc).__name__), self._sink)
                return
            _emit(_record(ctx, request, event="activity_judge_shadow", rule=rule_verdict, llm=llm_verdict),
                  self._sink)

        runner = self._runner or default_runner()
        if not runner.submit(work):
            _emit(_record(ctx, request, event="activity_judge_shadow_skipped", rule=rule_verdict), self._sink)
        return rule_verdict


class LLMFirstJudge:
    """LLM 모드 — LLM 판정으로 답한다. 호출이 실패하면 규칙 판정에 `llm_fallback_rule` 을 달아 돌려준다.

    ★이 브랜치는 섀도 모드로 시작한다. 이 모드는 전환 기준(계획서 §8)이 정해진 뒤에 켠다.
    ★동기로 기다린다 — 웹 판정은 최대 `reliability.activity_judge_call_timeout_seconds` 만큼 응답을 늦춘다.
    """

    def __init__(self, rule: RuleJudge, llm: LLMJudge) -> None:
        self.rule = rule
        self.llm = llm

    def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:
        verdict = _run(self.llm.judge(ctx, request))
        if verdict.failure_code in _CALL_FAILURES:
            fallback = self.rule.judge(ctx, request)
            return replace(fallback, failure_code=fc.LLM_FALLBACK_RULE,
                           dropped=[*fallback.dropped, f"llm:{verdict.failure_code}"])
        return verdict


def build_judge(mode: str, judge_llm: Any | None, *, runner: Any | None = None,
                sink: Any | None = None, facts: SharedCheckFacts | None = None) -> ActivityJudge:
    """설정 모드와 조립이 넣은 어댑터로 판정기를 고른다. 어댑터가 없으면 언제나 규칙이다.
    `facts` 는 공유 점검의 재난 유형 목록 · 낱말 — 안 주면 규칙의 재난 영향은 `unknown`(`rule.SharedCheckFacts`)."""
    rule = RuleJudge(facts)
    if judge_llm is None or mode == "rule":
        return rule
    llm = LLMJudge(judge_llm)
    if mode == "shadow":
        return ShadowJudge(rule, llm, runner=runner, sink=sink)
    if mode == "llm":
        return LLMFirstJudge(rule, llm)
    raise ValueError(f"unknown activity_judge_mode: {mode}")


def _record(ctx: JudgeContext, request: JudgeRequest, *, event: str, rule: Verdict,
            llm: Verdict | None = None, error: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "event": event, "tenant_id": ctx.tenant_id, "case_id": str(ctx.case_id) if ctx.case_id else None,
        "capability": ctx.capability, "run_id": str(ctx.run_id) if ctx.run_id else None,
        "kind": request.kind, "rule": rule.value, "rule_basis": rule.basis,
    }
    if llm is not None:
        record.update({
            "llm": llm.value, "agree": llm.value == rule.value,
            # 둘 다 아는 경우만 비교할 수 있다 — 한쪽이 모름이면 일치율의 분모에서 뺀다
            "comparable": llm.known and rule.known,
            "llm_failure_code": llm.failure_code, "llm_confidence": llm.confidence,
            # ★호출 실패면 예외 종류만 남긴다(`AuditWriteError` · `RateLimitError` …) — 실측에서 이게 없어 원인을 못 봤다.
            #   성공한 판정의 `basis` 는 모델의 판단 이유라 싣지 않는다.
            "llm_error": llm.basis if llm.failure_code in (fc.LLM_ERROR, fc.LLM_SCHEMA_INVALID) else None,
            "dropped": len(llm.dropped), "quotes": len(llm.quotes), "citations": len(llm.citations),
            **{k: llm.metrics.get(k) for k in ("latency_ms", "search_calls", "input_tokens", "output_tokens",
                                                "reasoning_tokens", "undated_citations", "model")},
        })
    if error is not None:
        record["llm_error"] = error
    return record


def _emit(record: dict[str, Any], sink: Any | None) -> None:
    """로그 한 줄 + (있으면) 표 한 행. ★표 쓰기 실패는 판정을 막지 않는다 — `WARNING` 로 보이게만 남긴다."""
    _shadow_log.info(json.dumps(record, ensure_ascii=False, default=str))
    if sink is None:
        return
    try:
        sink(record)
    except Exception as exc:
        _shadow_log.warning(json.dumps({"event": "activity_judge_shadow_sink_failed", "kind": record.get("kind"),
                                        "case_id": record.get("case_id"), "error": type(exc).__name__},
                                       ensure_ascii=False))
