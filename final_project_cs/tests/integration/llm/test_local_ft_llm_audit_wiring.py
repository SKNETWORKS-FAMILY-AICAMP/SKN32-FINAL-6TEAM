from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from app.infrastructure.llm.local_ft import LocalFTTeamLLM

_RealAsyncClient = httpx.AsyncClient


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

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/complete"
        body = json.loads(request.content)
        assert '"prompt_key": "response.generate"' in body["prompt"]
        return httpx.Response(200, json={"text": '{"final_response_text":"ok"}', "input_tokens": 5, "output_tokens": 2})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")))
    recorded = {}
    monkeypatch.setattr("app.infrastructure.llm.local_ft.record_llm_call", lambda conn, **kwargs: recorded.update(kwargs))

    result = await LocalFTTeamLLM(base_url="http://x600:8100", connection_factory=lambda: next(connections)).complete(
        "response.generate", "draft text", {}, run_id=run_id)

    assert result == {"final_response_text": "ok"}
    assert recorded["prompt_id"] == prompt_id
    assert recorded["run_id"] == run_id
    assert recorded["provider"] == "local_ft"
    assert recorded["input_tokens"] == 5 and recorded["output_tokens"] == 2


@pytest.mark.asyncio
async def test_missing_active_prompt_fails_before_http_call(monkeypatch):
    conn = Connection([])
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"text": "{}"})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")))
    with pytest.raises(RuntimeError, match="no active prompt"):
        await LocalFTTeamLLM(base_url="http://x600:8100", connection_factory=lambda: conn).complete("missing", "", {})
    assert not called


@pytest.mark.asyncio
async def test_unparseable_server_output_raises(monkeypatch):
    prompt_id = uuid4()
    conn = Connection([(prompt_id, "instructions")])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "not json"})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")))
    with pytest.raises(RuntimeError, match="unparseable"):
        await LocalFTTeamLLM(base_url="http://x600:8100", connection_factory=lambda: conn).complete("response.generate", "", {})


@pytest.mark.asyncio
async def test_none_connection_factory_skips_audit(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": '{"ok": true}'})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")))
    result = await LocalFTTeamLLM(base_url="http://x600:8100").complete("legacy", "", {})
    assert result == {"ok": True}
