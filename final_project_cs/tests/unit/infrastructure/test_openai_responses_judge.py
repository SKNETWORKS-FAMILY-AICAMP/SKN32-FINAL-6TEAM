"""활동 판정 LLM 어댑터(`openai_responses.py`, D-CS-008) — 네트워크 없이 요청 모양과 응답 읽기를 본다.

★스파이크 실측(2026-10-06)에서 정한 것을 시험이 지킨다:
  - `temperature`·`seed` 를 넘기지 않는다(nano 가 400 으로 거절했다)
  - 웹 검색을 켜면 `include` 로 출처 목록을 받는다(json_schema 에서는 `url_citation` 이 0건이었다)
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.llm import openai_responses as mod
from app.infrastructure.llm.openai_responses import (
    WEB_SOURCES_INCLUDE,
    JudgeResponseError,
    OpenAIResponsesJudgeLLM,
)

SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"verdict": {"type": "string"}}, "required": ["verdict"]}


def _settings(**overrides):
    base = dict(openai_api_key="test", activity_judge_model="gpt-5.4-nano",
                activity_judge_reasoning_effort="low", activity_judge_web_search=True)
    base.update(overrides)
    return SimpleNamespace(**base)


def _response(text='{"verdict": "open"}', *, status="completed", output=None):
    return SimpleNamespace(
        status=status, output_text=text, output=output or [],
        usage=SimpleNamespace(input_tokens=11, output_tokens=7,
                              output_tokens_details=SimpleNamespace(reasoning_tokens=3)))


def _search(action_type, *urls):
    return SimpleNamespace(type="web_search_call", action=SimpleNamespace(
        type=action_type, sources=[SimpleNamespace(url=u) for u in urls]))


class _Client:
    def __init__(self, response):
        self.requests = []
        self._response = response
        outer = self

        class responses:
            @staticmethod
            def create(**request):
                outer.requests.append(request)
                return outer._response
        self.responses = responses


def _adapter(monkeypatch, response, *, settings=None, connection_factory=None):
    monkeypatch.setattr(mod, "get_settings", lambda: settings or _settings())
    client = _Client(response)
    adapter = OpenAIResponsesJudgeLLM(connection_factory=connection_factory, timeout=5,
                                      client_factory=lambda **_: client)
    return adapter, client


def _judge(adapter, **kwargs):
    kwargs.setdefault("instructions", "판정하라")
    return asyncio.run(adapter.judge("activity_judge.test", {"place": "x"}, schema=SCHEMA,
                                     schema_name="t", **kwargs))


def test_request_shape_with_web_search(monkeypatch):
    adapter, client = _adapter(monkeypatch, _response())
    _judge(adapter)
    request = client.requests[0]
    assert request["model"] == "gpt-5.4-nano"
    assert request["reasoning"] == {"effort": "low"}
    assert request["tools"] == [{"type": "web_search"}]
    assert request["include"] == [WEB_SOURCES_INCLUDE]
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"] == SCHEMA
    # ★nano 가 거절한 파라미터를 보내지 않는다
    assert "temperature" not in request and "seed" not in request


def test_web_search_off_sends_no_tools(monkeypatch):
    adapter, client = _adapter(monkeypatch, _response())
    _judge(adapter, web_search=False)
    assert "tools" not in client.requests[0] and "include" not in client.requests[0]


def test_web_search_default_follows_settings(monkeypatch):
    adapter, client = _adapter(monkeypatch, _response(), settings=_settings(activity_judge_web_search=False))
    _judge(adapter)
    assert "tools" not in client.requests[0]


def test_reads_output_sources_and_usage(monkeypatch):
    output = [_search("search", "https://a.example/1", "https://b.example/2"),
              _search("open_page", "https://a.example/1"),
              SimpleNamespace(type="message")]
    adapter, _ = _adapter(monkeypatch, _response(output=output))
    call = _judge(adapter)
    assert call.output == {"verdict": "open"}
    # 중복 없이, 처음 나온 순서로
    assert call.sources == ["https://a.example/1", "https://b.example/2"]
    assert call.search_calls == 2 and call.search_actions == ["search", "open_page"]
    assert (call.input_tokens, call.output_tokens, call.reasoning_tokens) == (11, 7, 3)


@pytest.mark.parametrize("response, message", [
    (_response(""), "empty"),
    (_response("not json"), "not JSON"),
    (_response("[1, 2]"), "not an object"),
    (_response('{"verdict": "op', status="incomplete"), "not completed"),
])
def test_unreadable_response_raises(monkeypatch, response, message):
    """★어댑터는 「모름」으로 바꾸지 않는다 — 판정 계층이 실패 코드를 남기도록 예외로 말한다."""
    adapter, _ = _adapter(monkeypatch, response)
    with pytest.raises(JudgeResponseError, match=message):
        _judge(adapter)


def test_missing_key_fails_before_call(monkeypatch):
    adapter, client = _adapter(monkeypatch, _response(), settings=_settings(openai_api_key=" "))
    with pytest.raises(RuntimeError, match="API key"):
        _judge(adapter)
    assert client.requests == []


def test_no_instructions_fails_before_call(monkeypatch):
    adapter, client = _adapter(monkeypatch, _response())
    with pytest.raises(RuntimeError, match="no instructions"):
        _judge(adapter, instructions=None)
    assert client.requests == []


# ── 등록된 프롬프트 · 감사 기록 ────────────────────────────────

class _Cursor:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params=()): pass
    def fetchall(self): return self.rows


class _Conn:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def transaction(self): return self
    def cursor(self): return _Cursor(self.rows)


def test_registered_prompt_is_used_and_audited(monkeypatch):
    prompt_id, run_id = uuid4(), uuid4()
    connections = iter([_Conn([(prompt_id, "등록된 지시문")]), _Conn([])])
    output = [_search("search", "https://a.example/1")]
    adapter, client = _adapter(monkeypatch, _response(output=output),
                               connection_factory=lambda: next(connections))
    recorded = {}
    monkeypatch.setattr(mod, "record_llm_call", lambda conn, **kwargs: recorded.update(kwargs))
    asyncio.run(adapter.judge("activity_judge.test", {}, schema=SCHEMA, schema_name="t",
                              instructions="무시된다", run_id=run_id))
    # ★등록된 지시문이 이긴다 — 넘긴 문장으로 감사 밖 경로를 열지 않는다
    assert client.requests[0]["instructions"] == "등록된 지시문"
    assert recorded["prompt_id"] == prompt_id and recorded["run_id"] == run_id
    assert recorded["provider"] == "openai_responses" and recorded["model"] == "gpt-5.4-nano"
    assert recorded["response_json"]["sources"] == ["https://a.example/1"]
    assert recorded["input_tokens"] == 11 and recorded["output_tokens"] == 7


def test_missing_registered_prompt_fails_before_call(monkeypatch):
    adapter, client = _adapter(monkeypatch, _response(), connection_factory=lambda: _Conn([]))
    with pytest.raises(RuntimeError, match="no active prompt"):
        _judge(adapter)
    assert client.requests == []


def test_audit_failure_is_not_hidden(monkeypatch):
    from app.infrastructure.llm._registry import AuditWriteError

    connections = iter([_Conn([(uuid4(), "지시문")]), _Conn([])])
    adapter, _ = _adapter(monkeypatch, _response(), connection_factory=lambda: next(connections))

    def broken(conn, **_):
        raise OSError("db down")
    monkeypatch.setattr(mod, "record_llm_call", broken)
    with pytest.raises(AuditWriteError):
        _judge(adapter)


def test_timeout_is_raised_as_timeout_error(monkeypatch):
    """★판정 계층은 `openai` 를 import 하지 못한다 — SDK 의 시간 초과를 표준 `TimeoutError` 로 바꿔 낸다."""
    import httpx
    from openai import APITimeoutError

    adapter, client = _adapter(monkeypatch, _response())

    def slow(**_):
        raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    client.responses.create = staticmethod(slow)
    with pytest.raises(TimeoutError):
        _judge(adapter)


def test_unreadable_response_is_a_value_error():
    assert issubclass(JudgeResponseError, ValueError)
