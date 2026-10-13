# -*- coding: utf-8 -*-
"""판정 LLM 장애 주입 — 구현 계획 1.6 · 5.4. `[2026-10-12]`

★실시간 운영(웹 검색)이 성립 판정 맨 앞에서 고객 응답을 기다리게 하면서 넣은 것: 동시 호출 상한 · 응답 대기 상한 · 429 만 다시 부르기.
★어떤 장애도 「모름」이다 — 판정을 지어내지 않고, 예외를 밖으로 던지지 않는다.
"""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domains.travel_ops.instances.activity import failure_codes as fc
from app.domains.travel_ops.instances.activity.judge import JudgeContext, LLMJudge, requests
from app.domains.travel_ops.instances.activity.judge.modes import rule_first
from app.domains.travel_ops.instances.activity.judge.types import Verdict

from ._judge_fakes import out

KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
CTX = JudgeContext()
NOTICE = "https://www.example.go.kr/notice?id=1"
CLOSED = out("closed", citations=[{"url": NOTICE, "quote": "임시 휴관", "published_at": "2026-11-01"}])
ODD = "평일 (학생 안전강화로 인해 주말에만 개방)"
RELIABILITY = {"web_max_concurrent": 2, "web_wait_seconds": 0, "web_answer_timeout_seconds": 5,
               "rate_limit_retries": 1, "rate_limit_backoff_seconds": 0}


class RateLimitError(Exception):
    status_code = 429


class ScriptedLLM:
    """부를 때마다 차례로 — 예외면 던지고, 숫자면 그만큼 (스레드에서) 늦게 답한다."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = 0

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None,
                    instructions=None, run_id=None):
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, (int, float)):
            await asyncio.to_thread(time.sleep, step)
            step = CLOSED
        return SimpleNamespace(output=step, sources=[NOTICE], search_calls=1, latency_ms=5,
                               input_tokens=1, output_tokens=1, reasoning_tokens=0, model="fake")


def _judge(llm, *, kind="live_status", slots=None, **reliability):
    sleeps: list[float] = []

    async def sleep(seconds):
        sleeps.append(seconds)

    judge = LLMJudge(llm, today=TUESDAY.date(), reliability={**RELIABILITY, **reliability}, slots=slots, sleep=sleep)
    request = (requests.live_status("경복궁", "activity", None, TUESDAY) if kind == "live_status"
               else requests.closure(ODD, TUESDAY))
    return asyncio.run(judge.judge(CTX, request)), sleeps


def test_a_429_is_retried_once_after_a_pause():
    llm = ScriptedLLM(RateLimitError("slow down"), CLOSED)
    verdict, sleeps = _judge(llm)
    assert verdict.value == "closed" and llm.calls == 2 and sleeps == [0]


def test_a_second_429_gives_up_as_unknown():
    llm = ScriptedLLM(RateLimitError("slow down"))
    verdict, _ = _judge(llm)
    assert verdict.value == "unknown" and verdict.failure_code == fc.LLM_ERROR and verdict.basis == "RateLimitError"
    assert llm.calls == 2


def test_other_errors_and_timeouts_are_not_retried():
    for error, code in ((RuntimeError("no key"), fc.LLM_ERROR), (TimeoutError("45s"), fc.LLM_TIMEOUT),
                        (ValueError("not json"), fc.LLM_SCHEMA_INVALID)):
        llm = ScriptedLLM(error, CLOSED)
        verdict, sleeps = _judge(llm)
        assert (verdict.value, verdict.failure_code, llm.calls, sleeps) == ("unknown", code, 1, [])


def test_an_answer_outside_the_schema_is_unknown():
    verdict, _ = _judge(ScriptedLLM({"verdict": "maybe", "confidence": 2}))
    assert verdict.value == "unknown" and verdict.failure_code == fc.LLM_SCHEMA_INVALID


def test_full_web_slots_skip_the_call():
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    llm = ScriptedLLM(CLOSED)
    verdict, _ = _judge(llm, slots=slots)
    assert verdict.failure_code == fc.LLM_BUSY and llm.calls == 0
    # ★원문 해석 판정은 웹 자리를 쓰지 않는다
    text_llm = ScriptedLLM(out("closed", quotes=[ODD]))
    verdict, _ = _judge(text_llm, kind="closure", slots=slots)
    assert verdict.value == "closed" and text_llm.calls == 1


def test_the_slot_is_given_back_after_each_call():
    slots = threading.BoundedSemaphore(1)
    for _ in range(3):
        verdict, _ = _judge(ScriptedLLM(CLOSED), slots=slots)
        assert verdict.value == "closed"


def test_the_customer_waits_no_longer_than_the_answer_timeout():
    """웹 검색이 늦으면 상한에서 「모름」으로 답한다 — 호출 자체는 뒤에서 끝난다."""
    judge = LLMJudge(ScriptedLLM(1.5), today=TUESDAY.date(),
                     reliability={**RELIABILITY, "web_answer_timeout_seconds": 0.2},
                     slots=threading.BoundedSemaphore(1))
    rule = Verdict("live_status", "unknown", "rule", basis="develop_does_not_read_web_notices")
    started = time.monotonic()
    verdict = rule_first(CTX, requests.live_status("경복궁", "activity", None, TUESDAY), rule, judge)
    assert time.monotonic() - started < 1.0
    assert verdict.value == "unknown" and "llm:llm_timeout" in verdict.dropped
