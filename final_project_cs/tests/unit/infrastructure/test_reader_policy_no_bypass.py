"""계획 읽기 reader 차단이 role-manager 의 공용 장치로 우회되지 않는지 — 순수 대역만(HTTP · DB · 모델 없음).

reader 입구(`FailoverChat.reader_json_stream` · `reader_structured_stream` · `reader_json`)는 유료를 기본으로 건너뛰고,
채팅 해석(`structured_stream_validated` · `structured`) · 채팅 「넣기」(`trip_desk._read_plan`) · 감시 분류 계획
(`feedback._ollama_structured` → `structured_stream`)은 기존 계약(가린 글로 유료 넘김 · 일반 예산)을 그대로 쓴다.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.infrastructure import llm_failover
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, ModelCallError, OpenAIChat, _Backend
from app.infrastructure.ollama_chat import OllamaError

PHONE = "010-1234-5678"


class Recorder:
    def __init__(self) -> None:
        self.events: dict[str, list] = {"local": [], "paid": [], "global": [], "strict": [], "warm": []}


def make(rec: Recorder, *, local_up: bool = True, local_fails: bool = True, paid_fail_first: bool = False,
         strict=lambda: True, hold=None):
    class Local:
        model = "local-e4b"

        def loaded(self, timeout=5.0):
            return local_up

        def _go(self, name, user):
            rec.events["local"].append((name, user))
            if local_fails:
                raise OllamaError("synthetic local failure")
            return {"items": []}

        def json_stream(self, system, user, **kw):
            return self._go("json_stream", user)

        def structured_stream(self, system, user, schema, **kw):
            if hold is not None:
                hold()
            return self._go("structured_stream", user)

        def structured_stream_validated(self, system, user, schema, *, validator, **kw):
            return self._go("structured_stream_validated", user)

        def structured(self, system, user, schema, **kw):
            return self._go("structured", user)

        def json(self, system, user):
            return self._go("json", user)

        def text(self, system, user):
            return self._go("text", user)

    class Paid:
        model = "paid-model"

        def _go(self, name, user):
            rec.events["paid"].append((name, user))
            if paid_fail_first and len(rec.events["paid"]) == 1:
                raise ModelCallError("busy", reason="429")
            return {"items": []}

        def json_stream(self, system, user, **kw):
            return self._go("json_stream", user)

        def structured_stream(self, system, user, schema, **kw):
            return self._go("structured_stream", user)

        def structured_stream_validated(self, system, user, schema, *, validator, **kw):
            value = self._go("structured_stream_validated", user)
            validator(value)
            return value

        def structured(self, system, user, schema, **kw):
            rec.events.setdefault("paid_schema", []).append(json.dumps(schema, ensure_ascii=False))
            return self._go("structured", user)

        def json(self, system, user):
            return self._go("json", user)

        def text(self, system, user):
            return self._go("text", user)

    def global_gate():
        rec.events["global"].append(True)
        return True

    def strict_gate():
        rec.events["strict"].append(True)
        return strict()

    local = _Backend("ollama", Local(), CircuitBreaker("ollama", threshold=3, open_seconds=60), timeout=1.0)
    paid = _Backend("openai", Paid(), CircuitBreaker("openai", threshold=3, open_seconds=60), is_api=True, timeout=1.0,
                    budget=global_gate, reader_budget=strict_gate)
    return FailoverChat([local, paid], total_seconds=15.0, sleep=lambda _s: None)


@pytest.fixture(autouse=True)
def _no_warm(monkeypatch):
    llm_failover.reset_state()
    calls: list = []
    monkeypatch.setattr(llm_failover, "_warm_starter", lambda chat: calls.append(chat))
    yield calls
    llm_failover.reset_state()


READER_CALLS = {
    "reader_json_stream": lambda chat, **kw: chat.reader_json_stream("s", PHONE, first_wait=1, stall=1, max_seconds=2, **kw),
    "reader_structured_stream": lambda chat, **kw: chat.reader_structured_stream("s", PHONE, {}, first_wait=1, stall=1,
                                                                                 max_seconds=2, **kw),
    "reader_structured_stream_api_only": lambda chat, **kw: chat.reader_structured_stream("s", PHONE, {}, first_wait=1, stall=1,
                                                                                          max_seconds=2, api_only=True, **kw),
    "reader_json": lambda chat, **kw: chat.reader_json("s", PHONE, **kw),
}


@pytest.mark.parametrize("name", sorted(READER_CALLS))
def test_reader_entry_never_reaches_paid_or_any_budget_when_disabled(name):
    """`[2026-10-26]` 가드레일 기본은 켜짐(사용자 결정) — 끈 설정(`external_fallback_enabled=False`)이면 유료 · 예산 0회."""
    rec = Recorder()
    with pytest.raises(OllamaError):
        READER_CALLS[name](make(rec), external_fallback_enabled=False)
    assert rec.events["paid"] == [] and rec.events["global"] == [] and rec.events["strict"] == []
    assert ("openai", "reader_external_disabled") in llm_failover.current_path()["reasons"]


@pytest.mark.parametrize("name", sorted(READER_CALLS))
def test_reader_entry_without_the_argument_stays_blocked(name):
    """인자를 빼고 부르면(가드레일 값을 안 거친 호출) 유료 · 예산 0회 — 켜는 것은 `agent_reader_config` 가 넘길 때만."""
    rec = Recorder()
    with pytest.raises(OllamaError):
        READER_CALLS[name](make(rec))
    assert rec.events["paid"] == [] and rec.events["global"] == [] and rec.events["strict"] == []
    assert ("openai", "reader_external_disabled") in llm_failover.current_path()["reasons"]


@pytest.mark.parametrize("name", sorted(READER_CALLS))
def test_reader_entry_cold_primary_starts_warm_but_still_skips_paid(name, _no_warm):
    """rm 53dea261 의 식은 모델 갈래(`ModelNotLoaded` → 다음 경로 + 뒤 예열)도 reader 의 유료 차단을 넘지 못한다."""
    rec = Recorder()
    with pytest.raises(OllamaError):
        READER_CALLS[name](make(rec, local_up=False))
    assert rec.events["paid"] == [] and rec.events["strict"] == [] and rec.events["global"] == []


def test_reader_opt_in_uses_strict_gate_per_attempt_and_never_the_global_gate():
    rec = Recorder()
    out = READER_CALLS["reader_structured_stream"](make(rec, paid_fail_first=True), external_fallback_enabled=True)
    assert out == {"items": []}
    assert len(rec.events["paid"]) == 2 and len(rec.events["strict"]) == 2      # 다시 시도도 한 번씩 예약
    assert rec.events["global"] == []
    assert rec.events["paid"][0][1] != PHONE                                     # 유료로 갈 때는 가린 글


def test_reader_opt_in_strict_denial_on_retry_stops_paid():
    rec = Recorder()
    answers = iter([True, False])
    with pytest.raises(OllamaError):
        READER_CALLS["reader_json_stream"](make(rec, paid_fail_first=True, strict=lambda: next(answers)),
                                    external_fallback_enabled=True)
    assert len(rec.events["paid"]) == 1 and len(rec.events["strict"]) == 2


def test_chat_decision_stream_keeps_masked_paid_failover_and_global_budget():
    """채팅 해석(rm eebd9691 `structured_stream_validated`)은 기존 계약 그대로 — reader 차단 · reader 예산을 쓰지 않는다."""
    rec = Recorder()
    out = make(rec).structured_stream_validated("s", PHONE, {}, validator=lambda value: None,
                                                first_wait=1, stall=1, max_seconds=2)
    assert out == {"items": []}
    assert [name for name, _ in rec.events["paid"]] == ["structured_stream_validated"]
    assert PHONE not in rec.events["paid"][0][1]                                 # `redaction.masked`
    assert rec.events["global"] == [True] and rec.events["strict"] == []
    assert llm_failover.current_path()["path"] == "api"


def test_chat_decision_stream_cold_primary_still_goes_paid(_no_warm):
    rec = Recorder()
    make(rec, local_up=False).structured_stream_validated("s", PHONE, {}, validator=lambda value: None,
                                                          first_wait=1, stall=1, max_seconds=2)
    assert rec.events["local"] == [] and len(rec.events["paid"]) == 1
    assert llm_failover.current_path()["reasons"] == [("ollama", "not_loaded")]


@pytest.mark.parametrize("op", ["structured", "json", "structured_stream", "json_stream"])
def test_general_calls_keep_existing_failover(op):
    """일반 업무 입구(감시 분류 계획의 `structured_stream` 포함)는 reader 차단을 받지 않는다 — 가린 글 · 일반 예산."""
    rec = Recorder()
    chat = make(rec)
    if op == "structured":
        chat.structured("s", PHONE, {})
    elif op == "json":
        chat.json("s", PHONE)
    elif op == "structured_stream":
        chat.structured_stream("s", PHONE, {}, first_wait=1, stall=1, max_seconds=2)
    else:
        chat.json_stream("s", PHONE, first_wait=1, stall=1, max_seconds=2)
    assert len(rec.events["paid"]) == 1 and rec.events["global"] == [True] and rec.events["strict"] == []
    assert PHONE not in rec.events["paid"][0][1]


def test_wrapper_without_stream_policy_is_rejected_before_general_structured():
    """`structured`(일반 넘김)로 내려가는 길 — reader 정책 wrapper 에 stream 이 없으면 부르기 전에 거부."""
    from app.domains.travel_ops.components.intake import agent_read
    rec = Recorder()
    with pytest.raises(agent_read.ReaderPolicyError, match="reader_stream_required"):
        agent_read.read(PHONE, [PHONE], make(rec), today=date(2026, 10, 24))
    assert all(not value for key, value in rec.events.items() if key != "warm")



def test_direct_paid_client_is_rejected_as_reader():
    from app.domains.travel_ops.components.intake import agent_read, llm_spans
    api = OpenAIChat(api_key="unit-only", model="configured", client=object())
    with pytest.raises(agent_read.ReaderPolicyError, match="reader_unbudgeted_external"):
        agent_read.read(PHONE, [PHONE], api, today=date(2026, 10, 24), stream={"first_token_seconds": 1})
    with pytest.raises(llm_spans.ReadingFailed, match="reader_unbudgeted_external"):
        llm_spans.label_lines([PHONE], [1], api)


def test_line_reader_nonstream_uses_reader_json_not_general_json():
    from app.domains.travel_ops.components.intake import llm_spans
    rec = Recorder()
    with pytest.raises(llm_spans.ReadingFailed):
        llm_spans.label_lines([PHONE], [1], make(rec))
    assert [name for name, _ in rec.events["local"]] == ["json"]               # 로컬은 `json` 으로 불렸다(reader_json 이 부른다)
    assert rec.events["paid"] == [] and rec.events["global"] == [] and rec.events["strict"] == []
    assert llm_failover.current_path()["op"] == "reader_json"


def test_getattr_delegation_does_not_expose_paid_to_reader():
    """`FailoverChat.__getattr__` 은 첫 경로(로컬)의 것을 돌려준다 — 정의 안 된 이름으로 유료에 닿지 않는다."""
    rec = Recorder()
    chat = make(rec)
    assert chat.model == "local-e4b"
    assert getattr(type(chat), "reader_json", None) is not None


def test_line_reader_stream_uses_reader_entry_not_general_json_stream():
    from app.domains.travel_ops.components.intake import llm_spans
    rec = Recorder()
    stream = {"progress_seconds": 1, "first_token_seconds": 1, "stall_seconds": 1, "max_seconds": 2,
              "output_tokens_base": 64, "output_tokens_per_line": 10, "output_tokens_per_char": 1}
    with pytest.raises(llm_spans.ReadingFailed):
        llm_spans.label_lines([PHONE], [1], make(rec), stream=stream)
    assert rec.events["paid"] == [] and rec.events["global"] == [] and rec.events["strict"] == []
    assert llm_failover.current_path()["op"] == "reader_json_stream"


def test_agent_reader_stream_uses_reader_entry_not_general_structured_stream():
    from app.domains.travel_ops.components.intake import agent_read
    rec = Recorder()
    stream = {"progress_seconds": 1, "first_token_seconds": 1, "stall_seconds": 1, "max_seconds": 2}
    with pytest.raises(OllamaError):
        agent_read.read(PHONE, [PHONE], make(rec), today=date(2026, 10, 24), stream=stream)
    assert rec.events["paid"] == [] and rec.events["global"] == [] and rec.events["strict"] == []
    assert llm_failover.current_path()["op"] == "reader_structured_stream"


def test_policy_wrapper_without_reader_stream_entry_is_rejected():
    from app.domains.travel_ops.components.intake import agent_read

    class HalfWrapper:
        def reader_json(self, *a, **kw):
            raise AssertionError("must not be called")

        def structured_stream(self, *a, **kw):
            raise AssertionError("general stream must not be used by the reader")

        structured = structured_stream

    with pytest.raises(agent_read.ReaderPolicyError, match="reader_stream_entry_missing"):
        agent_read.read(PHONE, [PHONE], HalfWrapper(), today=date(2026, 10, 24), stream={"progress_seconds": 1})


def test_unknown_reader_purpose_is_refused():
    from app.domains.travel_ops.components.intake import agent_read
    with pytest.raises(ValueError):
        agent_read.read(PHONE, [PHONE], make(Recorder()), today=date(2026, 10, 24), purpose="other")


def test_reader_attempt_authorization_is_cleared_after_failure_then_chat_keeps_paid():
    rec = Recorder()
    chat = make(rec)
    with pytest.raises(OllamaError):
        READER_CALLS["reader_structured_stream"](chat)
    assert llm_failover._reader_attempt.get() is None
    chat.structured_stream_validated("s", PHONE, {}, validator=lambda value: None, first_wait=1, stall=1, max_seconds=2)
    assert len(rec.events["paid"]) == 1 and rec.events["strict"] == [] and rec.events["global"] == [True]


def test_concurrent_reader_and_chat_do_not_share_policy():
    """reader 호출이 로컬에서 기다리는 동안 다른 스레드의 채팅 해석은 기존대로 유료로 넘어간다(reader 차단이 새지 않는다)."""
    import threading
    inside, release = threading.Event(), threading.Event()
    rec = Recorder()

    def hold():
        if threading.current_thread().name == "reader-thread":
            inside.set()
            release.wait(2)

    chat = make(rec, hold=hold)
    errors = []

    def reader():
        try:
            READER_CALLS["reader_structured_stream"](chat)
        except OllamaError as exc:
            errors.append(exc)

    worker = threading.Thread(target=reader, name="reader-thread")
    worker.start()
    assert inside.wait(2)
    chat.structured_stream_validated("s", PHONE, {}, validator=lambda value: None, first_wait=1, stall=1, max_seconds=2)
    release.set()
    worker.join(2)
    assert errors and [name for name, _ in rec.events["paid"]] == ["structured_stream_validated"]
    assert rec.events["strict"] == []


def test_chat_add_reader_keeps_chat_contract(monkeypatch):
    """채팅 「넣기」(`TripDesk._read_plan`, D-025 「같은 입구」)는 채팅 해석 계약 — 가린 글로 일반 넘김. reader 차단으로 조용히 한 곳 넣기로 떨어지지 않는다."""
    from types import SimpleNamespace
    from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
    from app.domains.travel_ops.components.intake import pipeline
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant_id: {
        "mode": "on", "num_predict": 64, "chunk_chars": 1800, "prefill": "off", "external_fallback_enabled": False})
    rec = Recorder()
    chat = make(rec)
    desk = TripDesk(store=SimpleNamespace(tenant_id="unit"), connection_factory=lambda: None, reader=lambda: chat)
    read_plan = desk._read_plan()
    assert read_plan is not None
    got = read_plan("덕수궁 13:30 " + PHONE, date(2030, 1, 1))
    assert got.items == []
    assert [name for name, _ in rec.events["paid"]] == ["structured"]
    assert PHONE not in rec.events["paid"][0][1]
    assert all(PHONE not in schema and "덕수궁" not in schema for schema in rec.events["paid_schema"])  # 스키마로 원문이 새지 않는다
    assert rec.events["global"] == [True] and rec.events["strict"] == []


def test_watch_classification_plan_stream_keeps_paid_failover(monkeypatch):
    """rm fb291b33 감시 분류 계획(`feedback._ollama_structured` → `structured_stream`)은 고객 계획서 원문이 아니다 — 기존 넘김 그대로."""
    from app.domains.travel_ops.components.core_hooks import feedback
    from app.infrastructure import ollama_chat
    rec = Recorder()
    chat = make(rec)
    monkeypatch.setattr(ollama_chat, "from_settings", lambda settings: chat)
    out = feedback._ollama_structured("masked text", system="s", schema={"type": "object"},
                                      stream={"first_token_seconds": 1.0, "stall_seconds": 1.0, "max_seconds": 2.0}, num_predict=16)
    assert out == {"items": []}
    assert [name for name, _ in rec.events["paid"]] == ["structured_stream"]
    assert rec.events["global"] == [True] and rec.events["strict"] == []


def test_complete_stream_is_not_turned_into_a_stall_by_blocking_close():
    """Codex 검토: 답을 다 받은 뒤 응답 닫기가 막혀도 완료를 먼저 알린다(정상 답이 stall 오류가 되지 않는다)."""
    import threading
    import time as _time
    from app.infrastructure.model_stream import StreamLifetime, collect
    release, closing = threading.Event(), threading.Event()

    class Response:
        def close(self):
            closing.set()
            release.wait(2)

    lifetime = StreamLifetime()

    def pieces():
        assert lifetime.acquire(Response())
        yield '{"items": []}'

    started = _time.monotonic()
    try:
        assert collect(pieces, first_wait=1, stall=0.3, max_seconds=1, lifetime=lifetime) == '{"items": []}'
        assert _time.monotonic() - started < 0.3
    finally:
        release.set()
    assert closing.wait(1)


BARE = "01012345678 · 0212345678 · +82 2 1234 5678 · 2026-10-26 10:30"


@pytest.mark.parametrize("op", ["structured", "structured_validated", "json", "text", "structured_stream", "json_stream",
                                "structured_stream_validated", "reader_json", "reader_json_stream", "reader_structured_stream"])
def test_every_paid_send_hides_phones_without_separator(op):
    """`[2026-10-26 integ-rm9]` 모든 유료 전송 입구가 `redaction.masked_outbound` 를 쓴다 — 구분자 없는 휴대폰 · 지역번호 · +82 지역전화.
    같은 글의 날짜 · 시각은 그대로 간다."""
    rec = Recorder()
    chat = make(rec)
    stream = dict(first_wait=1, stall=1, max_seconds=2)
    if op == "structured":
        chat.structured("s", BARE, {})
    elif op == "structured_validated":
        chat.structured_validated("s", BARE, {}, validator=lambda value: None)
    elif op == "json":
        chat.json("s", BARE)
    elif op == "text":
        chat.text("s", BARE)
    elif op == "structured_stream":
        chat.structured_stream("s", BARE, {}, **stream)
    elif op == "json_stream":
        chat.json_stream("s", BARE, **stream)
    elif op == "structured_stream_validated":
        chat.structured_stream_validated("s", BARE, {}, validator=lambda value: None, **stream)
    elif op == "reader_json":
        chat.reader_json("s", BARE, external_fallback_enabled=True)
    elif op == "reader_json_stream":
        chat.reader_json_stream("s", BARE, external_fallback_enabled=True, **stream)
    else:
        chat.reader_structured_stream("s", BARE, {}, external_fallback_enabled=True, **stream)
    assert len(rec.events["paid"]) == 1, rec.events
    sent = rec.events["paid"][0][1]
    assert "12345678" not in sent and "1234 5678" not in sent and "2026-10-26 10:30" in sent, sent
    assert any(user == BARE for _, user in rec.events["local"])                   # 로컬에는 원문 그대로


def test_paid_embedding_input_uses_outbound_mask():
    """규정 검색 질문 임베딩(유료)도 같은 가림을 쓴다 — 소스 안 전송 지점이 `masked_outbound` 를 부르는지 본다(외부 호출 없이)."""
    import inspect as _inspect
    src = _inspect.getsource(llm_failover)
    assert "input=masked_outbound(text)" in src and "masked(" not in src.replace("masked_outbound(", "")
