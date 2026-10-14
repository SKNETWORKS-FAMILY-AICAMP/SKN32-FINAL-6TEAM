"""규정 검색용 임베딩 모델 예열(`retriever.warm_embedding`).

x600 서버 웹 채팅 시험(2026-10-13)에서 규정·날씨 질문 17건이 모두 「규정을 찾다가 오류」였다. 식은 임베딩 모델이
짧은 대기(6초) 안에 못 올라갔고, 대체 경로(1536 칸)는 여행 규정에 비어 있었다. 예열은 모델을 올리는 시간만큼 기다린다.
"""
import io
import json
from types import SimpleNamespace

import pytest

from app.infrastructure.rag import retriever


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def server(monkeypatch):
    calls = []
    state = {"loaded": []}

    def urlopen(request, timeout):
        url = request if isinstance(request, str) else request.full_url
        calls.append((url.rsplit("/", 1)[-1], timeout))
        if url.endswith("/api/ps"):
            return _Response(json.dumps({"models": [{"name": m} for m in state["loaded"]]}).encode())
        return _Response(json.dumps({"embeddings": [[0.0] * 3]}).encode())

    settings = SimpleNamespace(embedding_provider="ollama", ollama_base_url="http://ollama.test:11434",
                               ollama_embedding_model="bge-m3:latest", ollama_timeout_seconds=150.0)
    monkeypatch.setattr(retriever, "get_settings", lambda: settings)
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    retriever._WARM_STARTED[0] = 0.0
    return calls, state


def test_a_cold_embedding_model_is_loaded_with_the_load_timeout(server):
    calls, _ = server
    got = retriever.warm_embedding()
    assert got["status"] == "warmed" and calls == [("ps", 5), ("embed", 150.0)]


def test_an_already_loaded_model_is_left_alone(server):
    calls, state = server
    state["loaded"] = ["bge-m3:latest"]
    assert retriever.warm_embedding()["status"] == "warm" and calls == [("ps", 5)]


def test_a_second_call_right_after_does_not_load_again(server):
    calls, _ = server
    retriever.warm_embedding()
    assert retriever.warm_embedding()["status"] == "warming"
    assert [c for c in calls if c[0] == "embed"] == [("embed", 150.0)]


def test_a_non_ollama_provider_is_skipped(server, monkeypatch):
    calls, _ = server
    monkeypatch.setattr(retriever, "get_settings", lambda: SimpleNamespace(embedding_provider="openai", ollama_base_url="x",
                                                                           ollama_embedding_model="m", ollama_timeout_seconds=1))
    assert retriever.warm_embedding()["status"] == "skipped" and calls == []
