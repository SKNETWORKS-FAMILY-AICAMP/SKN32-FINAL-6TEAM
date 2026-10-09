"""모드별 판정기 — 섀도는 규칙으로 답하고 LLM 은 백그라운드에서 차이만 남긴다. LLM 모드는 호출 실패 때만 규칙으로."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime

import pytest

from app.domains.travel_ops.instances.activity import failure_codes as fc
from app.domains.travel_ops.instances.activity.judge import (
    SHADOW_LOGGER_NAME,
    BackgroundRunner,
    JudgeContext,
    LLMFirstJudge,
    RuleJudge,
    ShadowJudge,
    build_judge,
    requests,
)

from ._judge_fakes import FakeJudgeLLM, out

MONDAY = datetime(2026, 10, 12, 10, 0)
CTX = JudgeContext(case_id="case-1", capability="activity.check_feasible")


class InlineRunner:
    """시험용 — 받은 일을 그 자리에서 돌린다."""

    def __init__(self, accept=True):
        self.accept = accept

    def submit(self, work):
        if not self.accept:
            return False
        work()
        return True


def _shadow_lines(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == SHADOW_LOGGER_NAME]


@pytest.mark.parametrize("mode, llm, expected", [
    ("shadow", None, RuleJudge),          # 어댑터가 없으면 언제나 규칙
    ("rule", object(), RuleJudge),
    ("shadow", object(), ShadowJudge),
    ("llm", object(), LLMFirstJudge),
])
def test_build_judge_picks_by_mode(mode, llm, expected):
    assert isinstance(build_judge(mode, llm), expected)


def test_build_judge_rejects_unknown_mode():
    with pytest.raises(ValueError):
        build_judge("both", object())


def test_shadow_answers_with_rule_and_logs_difference(caplog):
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)
    text = "[종로구] 율곡로 일부 구간 교통통제 — 우회 바랍니다"
    llm = FakeJudgeLLM(out("no_effect", quotes=[text]))
    judge = build_judge("shadow", llm, runner=InlineRunner())
    # 규칙은 유형(교통통제 — 장소형)으로 막는다, LLM 은 이 장소와 무관하다고 본다
    # ★`[2026-10-09]` 규칙이 develop 판 기준이 됐다(D-CS-015) — 전의 「위급재난 호우」는 실내외를 모르면 규칙이 「모름」이다.
    messages = [{"step": "안전안내", "kind": "교통통제", "text": text, "regions": ["서울특별시 종로구"], "created_at": "t"}]
    verdict = judge.judge(CTX, requests.disaster_effect("경복궁", "activity", messages, MONDAY))
    assert (verdict.value, verdict.source) == ("blocks", "rule")   # ★고객 쪽은 규칙 결과 그대로
    [line] = _shadow_lines(caplog)
    assert line["event"] == "activity_judge_shadow"
    assert (line["rule"], line["llm"], line["agree"], line["comparable"]) == ("blocks", "no_effect", False, True)
    assert line["case_id"] == "case-1" and line["kind"] == "disaster_effect" and line["model"] == "fake-nano"


def test_shadow_log_has_no_place_or_reason_text(caplog):
    """★로그에는 장소명 · 원문 · 모델의 판단 이유를 싣지 않는다 — 코드와 숫자만."""
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)
    llm = FakeJudgeLLM(out("unknown", reason="경복궁은 비밀스러운 이유로"))
    build_judge("shadow", llm, runner=InlineRunner()).judge(
        CTX, requests.live_status("경복궁", "activity", "서울 종로구 사직로 161", MONDAY))
    text = caplog.records[-1].getMessage()
    assert "경복궁" not in text and "사직로" not in text and "비밀" not in text


def test_shadow_skips_when_runner_is_full(caplog):
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)
    llm = FakeJudgeLLM(out("closed"))
    verdict = build_judge("shadow", llm, runner=InlineRunner(accept=False)).judge(
        CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert verdict.value == "closed" and llm.calls == []
    assert _shadow_lines(caplog)[0]["event"] == "activity_judge_shadow_skipped"


def test_shadow_llm_failure_does_not_touch_the_answer(caplog):
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)
    verdict = build_judge("shadow", FakeJudgeLLM(exc=TimeoutError()), runner=InlineRunner()).judge(
        CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert verdict.value == "closed" and verdict.failure_code is None
    assert _shadow_lines(caplog)[0]["llm_failure_code"] == fc.LLM_TIMEOUT


def test_background_runner_refuses_beyond_pending_limit():
    release = threading.Event()
    started = threading.Event()
    runner = BackgroundRunner(max_workers=1, max_pending=1)

    def blocked():
        started.set()
        release.wait(5)
    assert runner.submit(blocked) is True
    started.wait(5)
    assert runner.submit(lambda: None) is False      # ★넘치면 받지 않는다 — 기다리게 하지 않는다
    release.set()
    for _ in range(100):
        if runner.submit(lambda: None):
            break
        threading.Event().wait(0.01)
    else:
        pytest.fail("runner did not free its slot")


def test_shadow_really_runs_in_background():
    """기본 실행기에서도 규칙 판정이 LLM 을 기다리지 않는다."""
    gate = threading.Event()

    class SlowLLM(FakeJudgeLLM):
        async def judge(self, *args, **kwargs):
            await asyncio.to_thread(gate.wait, 5)
            return await super().judge(*args, **kwargs)
    llm = SlowLLM(out("closed", quotes=["매주 월요일 휴무"]))
    judge = ShadowJudge(RuleJudge(), __import__("app.domains.travel_ops.instances.activity.judge", fromlist=["x"])
                        .LLMJudge(llm, citation_max_age_days=180),
                        runner=BackgroundRunner(max_workers=1, max_pending=2))
    verdict = judge.judge(CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert verdict.value == "closed" and llm.calls == []   # 아직 LLM 이 끝나지 않았는데 답이 나왔다
    gate.set()


# ── LLM 모드 ─────────────────────────────────────────────────

def test_llm_mode_falls_back_to_rule_on_call_failure():
    verdict = build_judge("llm", FakeJudgeLLM(exc=TimeoutError())).judge(
        CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert (verdict.value, verdict.source, verdict.failure_code) == ("closed", "rule", fc.LLM_FALLBACK_RULE)
    assert f"llm:{fc.LLM_TIMEOUT}" in verdict.dropped


def test_llm_mode_keeps_uncited_unknown():
    """★근거 검증 탈락은 호출 실패가 아니다 — 규칙으로 덮지 않고 「모름」으로 둔다."""
    verdict = build_judge("llm", FakeJudgeLLM(out("closed", quotes=["지어낸 구절"]))).judge(
        CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert (verdict.value, verdict.source, verdict.failure_code) == ("unknown", "llm", fc.LLM_UNCITED)


@pytest.mark.asyncio
async def test_llm_mode_works_inside_a_running_event_loop():
    """Team 코드는 이벤트 루프 안(`async execute`)에서 동기로 판정을 부른다."""
    verdict = build_judge("llm", FakeJudgeLLM(out("closed", quotes=["매주 월요일 휴무"]))).judge(
        CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert verdict.value == "closed" and verdict.source == "llm"


def test_shadow_log_names_the_exception_type_on_call_failure(caplog):
    """★2026-10-06 실호출에서 다섯 판정이 모두 `llm_error` 였는데 로그만으로는 원인(감사 기록 외래 키)을 몰랐다."""
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)

    class AuditWriteError(RuntimeError):
        pass
    build_judge("shadow", FakeJudgeLLM(exc=AuditWriteError("fk")), runner=InlineRunner()).judge(
        CTX, requests.closure("매주 월요일 휴무", MONDAY))
    line = _shadow_lines(caplog)[0]
    assert (line["llm_failure_code"], line["llm_error"]) == (fc.LLM_ERROR, "AuditWriteError")


def test_shadow_log_does_not_carry_reason_of_a_successful_verdict(caplog):
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)
    build_judge("shadow", FakeJudgeLLM(out("closed", quotes=["매주 월요일 휴무"], reason="비밀 이유")),
                runner=InlineRunner()).judge(CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert _shadow_lines(caplog)[0]["llm_error"] is None


# ── 표 기록(A안, 2026-10-06) ────────────────────────────────────

def test_shadow_record_goes_to_the_sink():
    records = []
    ctx = JudgeContext(case_id="case-1", capability="activity.check_feasible", tenant_id="t-1")
    build_judge("shadow", FakeJudgeLLM(out("closed", quotes=["매주 월요일 휴무"])), runner=InlineRunner(),
                sink=records.append).judge(ctx, requests.closure("매주 월요일 휴무", MONDAY))
    [record] = records
    assert record["event"] == "activity_judge_shadow" and record["tenant_id"] == "t-1"
    assert (record["rule"], record["llm"], record["agree"]) == ("closed", "closed", True)


def test_skipped_shadow_is_recorded_too():
    records = []
    build_judge("shadow", FakeJudgeLLM(out("closed")), runner=InlineRunner(accept=False),
                sink=records.append).judge(CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert [r["event"] for r in records] == ["activity_judge_shadow_skipped"]


def test_sink_failure_does_not_touch_the_verdict(caplog):
    """★표 쓰기가 실패해도 판정은 그대로 간다 — 실패는 WARNING 으로 보이게만."""
    caplog.set_level(logging.INFO, logger=SHADOW_LOGGER_NAME)

    def broken(_):
        raise OSError("db down")
    verdict = build_judge("shadow", FakeJudgeLLM(out("closed", quotes=["매주 월요일 휴무"])),
                          runner=InlineRunner(), sink=broken).judge(CTX, requests.closure("매주 월요일 휴무", MONDAY))
    assert verdict.value == "closed"
    failed = [json.loads(r.getMessage()) for r in caplog.records
              if r.levelno == logging.WARNING and r.name == SHADOW_LOGGER_NAME]
    assert failed and failed[0]["event"] == "activity_judge_shadow_sink_failed" and failed[0]["error"] == "OSError"


def test_record_carries_no_place_text():
    records = []
    build_judge("shadow", FakeJudgeLLM(out("unknown", reason="경복궁 이유")), runner=InlineRunner(),
                sink=records.append).judge(CTX, requests.live_status("경복궁", "activity", "사직로 161", MONDAY))
    text = json.dumps(records, ensure_ascii=False)
    assert "경복궁" not in text and "사직로" not in text
