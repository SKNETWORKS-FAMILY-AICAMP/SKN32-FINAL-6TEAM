from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.llm.openai import OpenAITeamLLM


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params=()): self.executed.append((sql, params))
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0]


class Connection:
    def __init__(self, prompt_rows):
        self.prompt_rows = prompt_rows
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def transaction(self): return self
    def cursor(self): return Cursor(self.prompt_rows)


@pytest.mark.asyncio
async def test_complete_records_prompt_and_run(monkeypatch):
    prompt_id, run_id = uuid4(), uuid4()
    read_conn = Connection([(prompt_id, "instructions from registry")])
    write_conn = Connection([])
    connections = iter([read_conn, write_conn])
    monkeypatch.setattr("app.infrastructure.llm.openai.get_settings", lambda: SimpleNamespace(
        openai_api_key="test", llm_model="test-model", llm_temperature=0, llm_seed=7))

    class FakeClient:
        def __init__(self, **_): pass
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    return SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content='{"answer":"ok"}'))],
                        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4),
                    )
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeClient))
    recorded = {}
    monkeypatch.setattr("app.infrastructure.llm.openai.record_llm_call", lambda conn, **kwargs: recorded.update(kwargs))

    result = await OpenAITeamLLM(connection_factory=lambda: next(connections)).complete(
        "activity.answer", "hello", {}, run_id=run_id)
    assert result == {"answer": "ok"}
    assert recorded["prompt_id"] == prompt_id
    assert recorded["run_id"] == run_id
    assert recorded["input_tokens"] == 3 and recorded["output_tokens"] == 4


@pytest.mark.asyncio
async def test_missing_active_prompt_fails_before_external_call(monkeypatch):
    conn = Connection([])
    called = False
    monkeypatch.setattr("app.infrastructure.llm.openai.get_settings", lambda: SimpleNamespace(
        openai_api_key="test", llm_model="test-model", llm_temperature=0, llm_seed=7))
    async def forbidden(*_):
        nonlocal called
        called = True
    monkeypatch.setattr(asyncio, "to_thread", forbidden)
    with pytest.raises(RuntimeError, match="no active prompt"):
        await OpenAITeamLLM(connection_factory=lambda: conn).complete("missing", "", {})
    assert not called


@pytest.mark.asyncio
async def test_none_connection_factory_keeps_inline_compatibility(monkeypatch):
    monkeypatch.setattr("app.infrastructure.llm.openai.get_settings", lambda: SimpleNamespace(
        openai_api_key="test", llm_model="test-model", llm_temperature=0, llm_seed=7))
    monkeypatch.setattr(asyncio, "to_thread", lambda fn: asyncio.sleep(0, result=({"ok": True}, None, None)))
    assert await OpenAITeamLLM().complete("legacy", "", {}) == {"ok": True}
