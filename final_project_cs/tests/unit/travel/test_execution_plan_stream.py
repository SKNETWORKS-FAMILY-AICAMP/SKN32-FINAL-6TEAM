"""라우팅 감사 12c — 분류 계획 호출의 답 조각 감시(사용자 결정: 조각이 오는 동안 기다리고, 조각 사이 stall 동안 없으면 실패).

실제 `OllamaChat.structured_stream_validated` → `model_stream.collect` 를 지나게 하고, 연결(`httpx.stream`)만 가짜 조각으로 바꾼다.
시간 값은 시험용으로 줄인다(`feedback.plan_stream`). 실제 값과 근거는 가드레일 `travel.watch.plan_stream`.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager

import pytest

from app.domains.travel_ops.components.core_hooks import feedback
from app.domains.travel_ops.components.planning import execution_plan as ep
from tests.unit.travel.activity.test_watch_batch_unit import _item, _place

TEAMS = {"activity": {"tools": ["read.itinerary", "read.disruptions"], "max_calls": 12}}
WATCH = {"first_token_seconds": 0.6, "stall_seconds": 0.3, "max_seconds": 3.0}


def _answer_text(item_id: str) -> str:
    return json.dumps({"schema_version": "1.0", "base_version": 3, "assignments": {item_id: {
        "team_id": "activity", "order": 1, "priority": 1, "depends_on": [], "reason": "통제 구간"}}}, ensure_ascii=False)


def _fake_stream(pieces, gaps, hang_after=None):
    """`gaps[i]` 초 쉬고 `pieces[i]` 를 보낸다. `hang_after` 조각 뒤로는 아무것도 안 보내고 닫힐 때까지 멈춘다."""
    closed = {"value": False}

    class Response:
        status_code = 200

        def iter_lines(self):
            for index, (piece, gap) in enumerate(zip(pieces, gaps)):
                time.sleep(gap)
                yield json.dumps({"message": {"content": piece}, "done": False})
                if hang_after is not None and index + 1 >= hang_after:
                    while not closed["value"]:
                        time.sleep(0.02)
                    return
            yield json.dumps({"message": {"content": ""}, "done": True})

        def close(self):
            closed["value"] = True

        def read(self):
            return b""

    @contextmanager
    def stream(*_a, **_k):
        yield Response()
    return stream, closed


def _run(monkeypatch, stream):
    from app.infrastructure import ollama_chat

    real = feedback.get_settings()
    monkeypatch.setattr(feedback, "get_settings", lambda: real.model_copy(update={
        "ollama_base_url": "http://127.0.0.1:9", "llm_failover_enabled": False}))
    monkeypatch.setattr(feedback, "plan_stream", lambda: dict(WATCH))
    monkeypatch.setattr(ollama_chat.OllamaChat, "loaded", lambda self, **_: True)
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream)
    item = _item(1, "activity", "관람", 10, _place("서울 전시관"))
    issue = {"item_id": str(item.item_id), "categories": ["traffic_control"]}
    return item, lambda: ep.classify_plan(query="[감시] 관람", trip={"version": 3}, items=[item], issues=[issue], teams=TEAMS)


def test_a_slow_answer_that_keeps_sending_pieces_is_waited_for(monkeypatch):
    """조각 사이 간격(0.2초) < stall(0.3초)이면, 전체가 stall 의 몇 배(약 1.4초)여도 기다려 받는다 — 고정 한도로 끊지 않는다."""
    item, plan = _run(monkeypatch, None)
    text = _answer_text(str(item.item_id))
    size = -(-len(text) // 7)
    pieces = [text[i:i + size] for i in range(0, len(text), size)]
    gaps = [0.1] + [0.2] * (len(pieces) - 1)
    stream, _ = _fake_stream(pieces, gaps)
    from app.infrastructure import ollama_chat
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream)
    started = time.monotonic()
    result = plan()
    assert time.monotonic() - started > 3 * WATCH["stall_seconds"]
    assert [s.item_id for s in result.steps] == [str(item.item_id)]


def test_pieces_that_stop_coming_fail_the_plan_after_the_stall_window(monkeypatch):
    item, plan = _run(monkeypatch, None)
    text = _answer_text(str(item.item_id))
    stream, closed = _fake_stream([text[:10], text[10:20]], [0.05, 0.05], hang_after=2)
    from app.infrastructure import ollama_chat
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream)
    started = time.monotonic()
    with pytest.raises(ep.PlanFailed, match="plan_provider_failed") as caught:
        plan()
    elapsed = time.monotonic() - started
    assert WATCH["stall_seconds"] <= elapsed < WATCH["max_seconds"]
    assert closed["value"] is True                                        # 받는 연결을 닫았다
    cause = caught.value.__cause__
    while cause is not None and type(cause).__name__ != "StreamStalled":
        cause = cause.__cause__
    assert cause is not None and cause.which == "stall"


def test_no_first_piece_fails_after_the_first_token_window(monkeypatch):
    item, plan = _run(monkeypatch, None)
    stream, _ = _fake_stream(["{"], [WATCH["first_token_seconds"] + 0.5])
    from app.infrastructure import ollama_chat
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream)
    with pytest.raises(ep.PlanFailed, match="plan_provider_failed") as caught:
        plan()
    cause = caught.value.__cause__
    while cause is not None and type(cause).__name__ != "StreamStalled":
        cause = cause.__cause__
    assert cause is not None and cause.which == "first"


def test_a_cold_model_is_not_waited_for_with_a_fixed_call(monkeypatch):
    """Codex 검토: 모델이 안 올라와 있어도 고정 대기 호출(`structured_validated`)로 바꾸지 않는다 — 같은 조각 감시로 끝난다."""
    from app.infrastructure import ollama_chat

    item, plan = _run(monkeypatch, None)
    monkeypatch.setattr(ollama_chat.OllamaChat, "loaded", lambda self, **_: False)

    def fixed(*_a, **_k):
        raise AssertionError("fixed-wait call used")
    monkeypatch.setattr(ollama_chat.OllamaChat, "structured_validated", fixed)
    monkeypatch.setattr(ollama_chat.OllamaChat, "structured", fixed)
    stream, _ = _fake_stream(["{"], [WATCH["first_token_seconds"] + 0.5])          # 적재 중 — 첫 조각이 늦다
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream)
    with pytest.raises(ep.PlanFailed, match="plan_provider_failed"):
        plan()
