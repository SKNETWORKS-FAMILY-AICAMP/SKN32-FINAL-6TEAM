# -*- coding: utf-8 -*-
"""규정 검색의 질문 임베딩 — Ollama 임베딩이 안 되면 서버용 OpenAI 키로 1536 칸을 검색한다. `[2026-10-07 사용자 지시]`

★전부 mock 서버(가짜 임베딩 함수 · 가짜 커서 · 가짜 OpenAI 클라이언트)다 — 실제 Ollama · 실제 유료 API 는 부르지 않는다.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure import llm_failover as lf
from app.infrastructure.rag import retriever

KEY = "sk-test-NOT-A-REAL-KEY-0123456789"
_REAL_EMBED = lf.embed_with_api


def settings(**over):
    base = dict(ollama_base_url="http://ollama.test:11434", ollama_timeout_seconds=60.0, embedding_model="text-embedding-3-small",
                llm_failover_enabled=True, openai_api_key_server=KEY, llm_failover_primary_timeout_seconds=6.0,
                llm_failover_api_timeout_seconds=8.0, llm_failover_failures=3, llm_failover_open_seconds=60.0,
                llm_failover_daily_cap=2000, llm_failover_monthly_cap=30000)
    base.update(over)
    return SimpleNamespace(**base)


class Cursor:
    def __init__(self, has_1536: bool) -> None:
        self.has, self.sql = has_1536, []

    def execute(self, sql, params=None):
        self.sql.append(sql)

    def fetchone(self):
        return (1,) if self.has else None


class Client:
    def __init__(self) -> None:
        self.calls = []
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 1536)])


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    lf.reset_state()
    monkeypatch.setattr(lf, "_budget_provider", None)
    yield
    lf.reset_state()


def run(monkeypatch, *, embed, cursor, cfg=None, client=None, budget=None):
    monkeypatch.setattr(retriever, "get_settings", lambda: cfg or settings())
    monkeypatch.setattr(retriever, "_embed_query", embed)
    if client is not None or budget is not None:
        monkeypatch.setattr(lf, "embed_with_api", lambda s, text: _REAL_EMBED(s, text, client=client, budget=budget))
    return retriever._query_vector(cursor, "demo", ["travel_dining"], "ollama", "embedding_1024", "취소하면 위약금 있어요?")


def test_when_ollama_embeds_nothing_changes(monkeypatch):
    column, vector = run(monkeypatch, embed=lambda q: [0.5] * 1024, cursor=Cursor(True))
    assert column == "embedding_1024" and len(vector) == 1024


def test_when_the_switch_is_off_an_ollama_failure_is_raised_as_before(monkeypatch):
    def boom(q):
        raise OSError("connection refused")
    with pytest.raises(OSError):
        run(monkeypatch, embed=boom, cursor=Cursor(True), cfg=settings(llm_failover_enabled=False))


def test_an_ollama_failure_goes_to_the_api_and_searches_the_1536_column(monkeypatch):
    def boom(q):
        raise OSError("connection refused")
    client = Client()
    column, vector = run(monkeypatch, embed=boom, cursor=Cursor(True), client=client, budget=lambda: True)
    assert column == "embedding" and len(vector) == 1536
    assert client.calls[0]["model"] == "text-embedding-3-small"
    assert lf.snapshot()["counters"]["ok:embed:openai"] == 1


def test_if_the_1536_column_is_empty_it_does_not_fall_over_it_raises_with_the_fix(monkeypatch):
    def boom(q):
        raise OSError("connection refused")
    client = Client()
    with pytest.raises(RuntimeError, match="embed_chunks_openai"):
        run(monkeypatch, embed=boom, cursor=Cursor(False), client=client, budget=lambda: True)
    assert client.calls == []


def test_after_three_failures_the_breaker_skips_ollama_and_goes_straight_to_the_api(monkeypatch):
    calls = []

    def boom(q):
        calls.append(q)
        raise OSError("connection refused")
    client = Client()
    for _ in range(4):
        run(monkeypatch, embed=boom, cursor=Cursor(True), client=client, budget=lambda: True)
    assert len(calls) == 3 and len(client.calls) == 4
    assert lf.snapshot()["counters"]["ok:embed:openai"] == 4


def test_the_call_budget_stops_the_embedding_api(monkeypatch):
    def boom(q):
        raise OSError("connection refused")
    client = Client()
    with pytest.raises(lf.ModelCallError) as caught:
        run(monkeypatch, embed=boom, cursor=Cursor(True), client=client, budget=lambda: False)
    assert "상한" in str(caught.value) and client.calls == [] and KEY not in str(caught.value)


def test_the_openai_provider_is_untouched(monkeypatch):
    monkeypatch.setattr(retriever, "get_settings", lambda: settings())
    monkeypatch.setattr(retriever, "_embed_query", lambda q: [0.2] * 1536)
    column, vector = retriever._query_vector(Cursor(True), "demo", ["s"], "openai", "embedding", "q")
    assert column == "embedding" and len(vector) == 1536
