# -*- coding: utf-8 -*-
"""유료 경로 실패는 이유와 함께 `app.llm_failover` 로그 줄로 남는다. `[2026-10-26 x600 40231a56]`

☆왜: x600 Case 72e29b8c 「오후 5시 30분으로 옮겨줘」(17항목)가 `ollama=timeout, openai=content` 로 escalated 됐는데
  `llm_failover` 로그 줄이 하나도 없었다. 경로 전환 로그(`_record`)는 **성공한** 넘김만 적고, 모든 경로가 실패하면
  예외만 올라가 원인(`evidence_validation:inconsistent_temporal_scope`)은 Case 기록에만 남았다.

★지키려는 것
 ①유료 경로가 실패하면 그때마다 `llm_failover op=… backend=openai failed reason=… detail=…` 한 줄(정해 둔 코드만 — 고객 문장 · 모델 답 · 키 없음)
 ②모든 경로가 실패하면 `llm_failover op=… path=none reasons=…` 한 줄
 ③근거 검사 실패의 코드는 정해 둔 모양(`[a-z0-9_:]`)일 때만 적는다 — 아니면 `unspecified`
"""
from __future__ import annotations

import logging
import time

import pytest

from app.infrastructure import llm_failover as lf
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, _Backend
from app.infrastructure.model_stream import StreamStalled
from app.infrastructure.ollama_chat import OllamaContentError, OllamaError, validate_content

SECRET_TEXT = "합성고객문장-오후 5시 30분으로 옮겨줘"


@pytest.fixture(autouse=True)
def _clean():
    lf.reset_state()
    yield
    lf.reset_state()


class Local:
    model = "tripilot-pointer:e4b-ft"

    def loaded(self, *, timeout=5.0):
        return True

    def json(self, system, user):
        raise StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall")

    def structured_stream_validated(self, system, user, schema, *, validator, **_kw):
        raise StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall")


class Paid:
    model = "gpt-6-luna"

    def __init__(self, error=None, answer=None):
        self.error, self.answer = error, answer

    def json(self, system, user):
        raise self.error

    def structured_stream_validated(self, system, user, schema, *, validator, **_kw):
        return validate_content(dict(self.answer), validator)


def chat_of(local, paid):
    clock = time.monotonic
    return FailoverChat([_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                         _Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock),
                                  is_api=True, timeout=8.0)],
                        total_seconds=15.0, sleep=lambda _s: None, clock=clock)


def _lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.llm_failover"]


def test_a_paid_content_failure_and_the_all_paths_failure_are_both_logged_with_reasons(caplog):
    caplog.set_level(logging.WARNING, logger="app.llm_failover")
    chat = chat_of(Local(), Paid(error=OllamaContentError("JSON 이 아니다: " + SECRET_TEXT)))
    with pytest.raises(OllamaError):
        chat.json("sys", SECRET_TEXT)
    lines = _lines(caplog)
    assert any("op=json backend=openai failed reason=content" in line for line in lines), lines
    assert any("op=json path=none" in line and "ollama:timeout,openai:content" in line for line in lines), lines
    assert all(SECRET_TEXT not in line and "옮겨줘" not in line for line in lines)


def test_an_evidence_failure_code_from_the_caller_reaches_the_log_line(caplog):
    caplog.set_level(logging.WARNING, logger="app.llm_failover")

    def validator(_value):
        error = ValueError("inconsistent temporal scope")
        error.log_code = "inconsistent_temporal_scope"
        raise error

    chat = chat_of(Local(), Paid(answer={"action": "change_time"}))
    with pytest.raises(OllamaError):
        chat.structured_stream_validated("sys", SECRET_TEXT, {"type": "object"}, validator=validator)
    lines = _lines(caplog)
    assert any("backend=openai failed reason=content detail=evidence_validation:inconsistent_temporal_scope" in line
               for line in lines), lines
    assert all(SECRET_TEXT not in line for line in lines)


def test_a_code_that_is_not_a_plain_token_is_not_logged(caplog):
    caplog.set_level(logging.WARNING, logger="app.llm_failover")

    def validator(_value):
        error = ValueError("x")
        error.log_code = SECRET_TEXT                     # 정해 둔 모양이 아니다 — 그대로 적지 않는다
        raise error

    chat = chat_of(Local(), Paid(answer={"action": "change_time"}))
    with pytest.raises(OllamaError):
        chat.structured_stream_validated("sys", "hi", {"type": "object"}, validator=validator)
    lines = _lines(caplog)
    assert any("detail=evidence_validation:unspecified" in line for line in lines), lines
    assert all(SECRET_TEXT not in line for line in lines)


def test_a_local_success_writes_no_failure_line(caplog):
    caplog.set_level(logging.WARNING, logger="app.llm_failover")

    class Fine(Local):
        def json(self, system, user):
            return {"ok": True}

    assert chat_of(Fine(), Paid(error=OllamaContentError("x"))).json("sys", "hi") == {"ok": True}
    assert _lines(caplog) == []
