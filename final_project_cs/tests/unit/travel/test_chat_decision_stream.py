# -*- coding: utf-8 -*-
"""채팅 해석(`decision_unit.decide`)도 계획 읽기처럼 답을 **조금씩 받으며** 조각 감시로 넘긴다. `[2026-10-26 사용자 승인]`

☆왜: 채팅 해석은 로컬 9초(`llm_failover_primary_timeout_seconds`) 고정 대기 뒤 유료 대체 1회였다. 학습 E4B 해석 한 건이 5.1~7.3초(x600) ·
  8.9초(로컬)라 9초 경계에서 정상으로 답을 쓰고 있던 호출도 끊겨 유료(`gpt-6-luna`)로 넘어갔다(x600 첫 턴 20초).

★지키려는 것
 ①설정은 가드레일 `travel.chat_decision_stream`(첫 조각 · 조각 사이 · 맨 위 상한) — 하드코딩 없음, 없는 키는 조용히 넘기지 않는다
 ②구조화 답 유지 — 스키마를 `format`(Ollama) · 엄격 `json_schema`(유료)로 보내고, 스키마 검사 · 근거 검사(`validator`)를 **경로 안에서** 한다
 ③넘김 계약 그대로 — 로컬이 끊기거나 모양이 틀리면 받다 만 답을 버리고 유료가 처음부터 · 유료의 틀린 답은 성공으로 돌려주지 않는다
 ④스트리밍 실패에 조용한 폴백 없음 — 고정 대기 호출(`structured_validated`)로 다시 부르지 않고 `DecisionFailed`
 ⑤설정이 없으면(다른 호출자 · 평가 스크립트) 지금 그대로 `structured_validated`
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du
from app.infrastructure import llm_failover
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, OpenAIChat, _Backend
from app.infrastructure.model_stream import StreamStalled
from app.infrastructure.ollama_chat import OllamaChat, OllamaContentError, OllamaError

KST = ZoneInfo("Asia/Seoul")
STREAM = {"first_token_seconds": 8, "stall_seconds": 5, "max_seconds": 12}
SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "enum": ["a", "b"]}}, "required": ["action"]}
RAW = {"action": "other", "target_item": "none", "target_change": "none", "fact": "none", "minutes": 0,
       "choices": [], "reads": [], "social": "", "general_requests": []}


@pytest.fixture(autouse=True)
def _clean():
    llm_failover.reset_state()
    yield
    llm_failover.reset_state()


def _stop(alias, hour, title="일정"):
    item = SimpleNamespace(item_id=uuid4(), kind="activity", title=title, place={"name": title}, seq=int(alias[1:]),
                           starts_at=datetime(2026, 11, 2, hour, 0, tzinfo=KST), ends_at=None)
    return du.Stop(alias, item)


STOPS = [_stop("i1", 9), _stop("i2", 15)]


# ── ① 가드레일 값 ─────────────────────────────────────────────
def test_the_chat_decision_stream_settings_live_in_the_guardrails():
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    first, stall, top = (float(guard.get(f"travel.chat_decision_stream.{k}"))
                         for k in ("first_token_seconds", "stall_seconds", "max_seconds"))
    assert stall == 5                                     # 사용자 승인: 답 조각이 5초 넘게 끊기면 넘긴다
    assert 0 < first <= top                               # 첫 조각은 맨 위 상한 안에서 기다린다
    assert top > 8.9                                      # 정상 로컬 해석(로컬 실측 8.9초)을 맨 위 상한이 끊지 않는다


def test_the_conversation_entry_hands_the_guardrail_stream_settings_to_decide(monkeypatch):
    from app.domains.travel_ops.components.conversation import chat_log, trip_messages

    seen = {}
    monkeypatch.setattr(du, "stops_of", lambda items: STOPS)
    monkeypatch.setattr(du, "changes_of", lambda store, conn, trip_id, items: [])
    monkeypatch.setattr(chat_log, "recent", lambda conn, **kw: [])
    monkeypatch.setattr(du, "decide", lambda chat, **kw: seen.update(kw) or "decision")
    out = trip_messages._try_decide(None, store=None, tenant="demo", trip_id=uuid4(), items=[], message="m", selected=None,
                                    chat=object())
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    assert out == ("decision", None)
    assert seen["stream"] == {k: guard.get(f"travel.chat_decision_stream.{k}")
                              for k in ("first_token_seconds", "stall_seconds", "max_seconds")}


# ── ②④⑤ decide 의 호출 ───────────────────────────────────────
class StreamChat:
    def __init__(self, fail: BaseException | None = None):
        self.fail, self.calls, self.fixed = fail, [], 0

    def structured_stream_validated(self, system, user, schema, *, validator, num_predict, on_piece=None, first_wait, stall,
                                    max_seconds):
        self.calls.append({"schema": schema, "num_predict": num_predict, "first_wait": first_wait, "stall": stall,
                           "max_seconds": max_seconds})
        if self.fail is not None:
            raise self.fail
        validator(dict(RAW))
        return dict(RAW)

    def structured_validated(self, *a, **k):              # 고정 대기 호출 — 스트리밍 설정이 있으면 부르면 안 된다
        self.fixed += 1
        return dict(RAW)

    def structured(self, *a, **k):
        self.fixed += 1
        return dict(RAW)


def test_decide_streams_with_the_given_watch_settings_and_keeps_the_schema():
    chat = StreamChat()
    decision = du.decide(chat, stops=STOPS, changes=[], history=[], selected_item_id=None, message="지금 뭐 해?",
                         num_predict=1200, stream=STREAM)
    assert decision.action == "other" and chat.fixed == 0
    call = chat.calls[0]
    assert (call["first_wait"], call["stall"], call["max_seconds"], call["num_predict"]) == (8.0, 5.0, 12.0, 1200)
    fixed = []

    class Fixed:
        def structured_validated(self, system, user, schema, *, validator, num_predict=160):
            fixed.append(schema)
            return dict(RAW)

    du.decide(Fixed(), stops=STOPS, changes=[], history=[], selected_item_id=None, message="지금 뭐 해?", num_predict=1200)
    assert call["schema"] == fixed[0]                      # 구조화 답(스키마) 그대로 — 고정 대기 호출과 같은 스키마


@pytest.mark.parametrize("fail", [StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall"),
                                  OllamaError("모든 모델 경로가 실패했다: ollama=timeout, openai=timeout")])
def test_a_streaming_failure_is_a_decision_failure_without_a_fixed_wait_retry(fail):
    chat = StreamChat(fail=fail)
    with pytest.raises(du.DecisionFailed):
        du.decide(chat, stops=STOPS, changes=[], history=[], selected_item_id=None, message="지금 뭐 해?", stream=STREAM)
    assert len(chat.calls) == 1 and chat.fixed == 0       # 조용히 고정 대기 호출로 되돌아가지 않는다


def test_without_stream_settings_decide_keeps_the_existing_validated_call():
    chat = StreamChat()
    du.decide(chat, stops=STOPS, changes=[], history=[], selected_item_id=None, message="지금 뭐 해?")
    assert chat.calls == [] and chat.fixed == 1


# ── ③ 넘김 장치 — 같은 넘김 계약 ─────────────────────────────
class Local:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, *, up=True, stall=False, answer=None):
        self.up, self.stall, self.answer, self.asked = up, stall, answer or {"action": "a"}, []

    def loaded(self, *, timeout=5.0):
        return self.up

    def structured_stream(self, system, user, schema, *, num_predict=160, on_piece=None, first_wait=15.0, stall=5.0,
                          max_seconds=180.0):
        self.asked.append({"user": user, "first_wait": first_wait, "stall": stall, "max_seconds": max_seconds})
        text = json.dumps(self.answer)
        if on_piece is not None:
            on_piece(text[:5])
        if self.stall:
            raise StreamStalled("모델 답 조각이 끊겼다(stall 5초)", which="stall")
        if on_piece is not None:
            on_piece(text)
        return dict(self.answer)

    def structured_stream_validated(self, system, user, schema, *, validator, **kw):
        # 실제 클라이언트와 같은 순서 — 받은 답을 스키마 · 근거로 검사한다(검사 자체는 아래 실제 클라이언트 시험이 본다)
        from app.infrastructure.ollama_chat import validate_content, validate_structured

        return validate_content(validate_structured(self.structured_stream(system, user, schema, **kw), schema), validator)


class Paid(Local):
    def loaded(self, *, timeout=5.0):
        return True


def chat_of(local, paid):
    clock = time.monotonic
    backends = [_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0),
                _Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock), is_api=True, timeout=8.0)]
    return FailoverChat(backends, total_seconds=15.0, sleep=lambda _s: None, clock=clock)


def _ok(value):
    return None


def _stream_call(chat, validator=_ok, pieces=None):
    return chat.structured_stream_validated("sys", "고객 문장", SCHEMA, validator=validator, num_predict=1200,
                                            on_piece=(lambda t, p: pieces.append(p)) if pieces is not None else None,
                                            first_wait=8.0, stall=5.0, max_seconds=12.0)


def test_failover_streams_locally_with_the_watch_settings_and_never_touches_paid():
    local, paid = Local(), Paid()
    assert _stream_call(chat_of(local, paid)) == {"action": "a"}
    assert paid.asked == [] and local.asked[0]["first_wait"] == 8.0 and local.asked[0]["stall"] == 5.0
    assert llm_failover.current_path()["path"] == "local" and llm_failover.current_path()["op"] == "structured_stream"


def test_a_local_stall_restarts_the_whole_answer_on_paid():
    local, paid = Local(stall=True), Paid(answer={"action": "b"})
    pieces = []
    assert _stream_call(chat_of(local, paid), pieces=pieces) == {"action": "b"}
    assert pieces[0] == "local" and pieces[-1] == "api"
    assert paid.asked[0]["user"] == "고객 문장"
    assert llm_failover.current_path()["reasons"] == [("ollama", "timeout")]


def test_a_local_answer_outside_the_schema_goes_to_paid_without_opening_the_breaker():
    local, paid = Local(answer={"action": "outside"}), Paid(answer={"action": "b"})
    chat = chat_of(local, paid)
    assert _stream_call(chat) == {"action": "b"}
    assert llm_failover.current_path()["reasons"] == [("ollama", "content")]
    assert chat._backends[0].breaker.snapshot()["failures"] == 0


def test_the_callers_evidence_check_runs_inside_each_path():
    def evidence(value):
        if value["action"] != "b":
            raise ValueError("unquoted evidence")

    local, paid = Local(answer={"action": "a"}), Paid(answer={"action": "b"})
    assert _stream_call(chat_of(local, paid), validator=evidence) == {"action": "b"}
    assert llm_failover.current_path()["reasons"] == [("ollama", "content")]


def test_a_paid_answer_outside_the_schema_is_never_returned_as_a_success():
    local, paid = Local(stall=True), Paid(answer={"action": "outside"})
    with pytest.raises(OllamaError, match="openai=content"):
        _stream_call(chat_of(local, paid))
    assert llm_failover.current_path()["path"] is None


def test_a_cold_local_model_goes_straight_to_paid():
    local, paid = Local(up=False), Paid(answer={"action": "b"})
    assert _stream_call(chat_of(local, paid)) == {"action": "b"}
    assert local.asked == [] and llm_failover.current_path()["reasons"] == [("ollama", "not_loaded")]


# ── ② 실제 클라이언트 — 스키마를 그대로 보내고 받은 답을 검사한다 ─────────
def test_ollama_streams_with_the_schema_as_format_and_rejects_an_answer_outside_it(monkeypatch):
    from app.infrastructure import ollama_chat

    sent = []

    class Response:
        status_code = 200

        def __init__(self, lines):
            self._lines = lines

        def iter_lines(self):
            yield from self._lines

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def stream_of(content):
        def fake(method, url, json=None, timeout=None):
            sent.append(json)
            pieces = [content[:4], content[4:]]
            lines = [__import__("json").dumps({"message": {"content": p}, "done": False}) for p in pieces]
            lines.append(__import__("json").dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}))
            return Response(lines)
        return fake

    chat = OllamaChat(base_url="http://ollama.test:11434", model="tripilot-pointer:e4b-ft")
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream_of('{"action": "a"}'))
    assert chat.structured_stream_validated("sys", "u", SCHEMA, validator=_ok, num_predict=1200, first_wait=1, stall=1,
                                            max_seconds=5) == {"action": "a"}
    assert sent[0]["format"] == SCHEMA and sent[0]["stream"] is True and sent[0]["options"]["num_predict"] == 1200
    monkeypatch.setattr(ollama_chat.httpx, "stream", stream_of('{"action": "zz"}'))
    with pytest.raises(OllamaContentError):
        chat.structured_stream_validated("sys", "u", SCHEMA, validator=_ok, num_predict=1200, first_wait=1, stall=1,
                                         max_seconds=5)


def test_paid_streams_with_the_strict_schema_and_rejects_an_answer_outside_it():
    calls = []

    class Stream:
        def __init__(self, content):
            self.content = content

        def __iter__(self):
            yield SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", delta=SimpleNamespace(content=self.content))])

        def close(self):
            pass

    def api(content):
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kw: calls.append(kw) or Stream(content))))

    chat = OpenAIChat(api_key="sk-test", model="gpt-6-luna", client=api('{"action": "b"}'))
    assert chat.structured_stream_validated("sys", "u", SCHEMA, validator=_ok, num_predict=1200, first_wait=1, stall=1,
                                            max_seconds=5) == {"action": "b"}
    assert calls[0]["stream"] is True and calls[0]["response_format"]["type"] == "json_schema"
    assert calls[0]["response_format"]["json_schema"]["strict"] is True
    bad = OpenAIChat(api_key="sk-test", model="gpt-6-luna", client=api('{"action": "zz"}'))
    with pytest.raises(OllamaContentError):
        bad.structured_stream_validated("sys", "u", SCHEMA, validator=_ok, num_predict=1200, first_wait=1, stall=1,
                                        max_seconds=5)
    with pytest.raises(OllamaContentError):
        chat.structured_stream_validated("sys", "u", SCHEMA, validator=lambda v: (_ for _ in ()).throw(ValueError("x")),
                                         num_predict=1200, first_wait=1, stall=1, max_seconds=5)


def test_the_failover_surface_does_not_leak_the_stream_call_to_the_first_ollama():
    """`FailoverChat.__getattr__` 는 모르는 이름을 첫 Ollama 에 넘긴다 — 이 메서드가 넘김 없이 로컬로만 가면 안 된다."""
    assert "structured_stream_validated" in FailoverChat.__dict__
    _ = httpx  # 같은 모듈에서 쓰는 전송 라이브러리(위 시험의 가짜가 바꾼다)
