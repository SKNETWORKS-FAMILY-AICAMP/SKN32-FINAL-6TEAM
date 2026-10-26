"""계획 읽기(reader) 입구의 시간 나눔 — 로컬이 조각 감시로 멈춘 뒤 유료가 돌 시간이 남아야 한다.

근거: x600 74b2b232 실서버(2026-10-26 10:29 · 10:31 · 10:46 KST) 계획 담기 16건 중 3건 `reading_model_failed`,
로그 「ollama=timeout, openai=deadline_exhausted」, 접수 → 실패 15.3 · 16.7 · 16.4초. reader 시한이 채팅 SLA
`llm_failover_total_seconds`(15)로 잘렸고 로컬이 그 15초를 다 받아 유료는 0초였다.
계약(가드레일 `travel.intake_reading`): reader 호출 하나의 절대 시한은 `max_seconds`(reader 자신의 상한)이고,
뒤에 쓸 수 있는 유료 경로가 있으면 로컬 시도는 `api_reserve_seconds` 를 남긴 만큼만 쓴다.
시계 · 대역만 쓴다(모델 · HTTP · DB 없음).
"""
from __future__ import annotations

import pytest

from app.infrastructure import llm_failover
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, _Backend
from app.infrastructure.model_stream import StreamStalled


@pytest.fixture(autouse=True)
def _clean():
    llm_failover.reset_state()
    yield
    llm_failover.reset_state()


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Local:
    """x600 재현 — 받은 `max_seconds`(또는 첫 조각 시한)를 다 쓰고 멈춘다."""
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, clock, *, stall=True, which="max"):
        self.clock, self.stall, self.which, self.seen = clock, stall, which, []

    def loaded(self, *, timeout=5.0):
        return True

    def _run(self, kw):
        self.seen.append({k: kw[k] for k in ("first_wait", "stall", "max_seconds")})
        if self.stall:
            self.clock.now += kw["first_wait"] if self.which == "first" else kw["max_seconds"]
            raise StreamStalled(f"model stream deadline: {self.which}", which=self.which)
        self.clock.now += 1.0
        return {"items": [], "spans": []}

    def structured_stream(self, system, user, schema, **kw):
        return self._run(kw)

    def json_stream(self, system, user, **kw):
        return self._run(kw)


class Paid(Local):
    model = "paid-double"

    def __init__(self, clock):
        super().__init__(clock, stall=False)


def chat_of(clock, local, paid=None, *, total_seconds=15.0):
    backends = [_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0)]
    if paid is not None:
        backends.append(_Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock),
                                 is_api=True, timeout=8.0, reader_budget=lambda: True))
    return FailoverChat(backends, total_seconds=total_seconds, sleep=lambda s: None, clock=clock)


STREAM = dict(first_wait=15.0, stall=5.0, max_seconds=120.0)


@pytest.mark.parametrize("entry", ["reader_structured_stream", "reader_json_stream"])
def test_x600_local_timeout_still_leaves_the_paid_reserve(entry):
    clock = Clock()
    local, paid = Local(clock), Paid(clock)
    chat = chat_of(clock, local, paid)
    args = ("sys", "1: 09:30~11:00 국립중앙박물관 관람") + (({},) if entry == "reader_structured_stream" else ())
    out = getattr(chat, entry)(*args, **STREAM, api_reserve_seconds=30.0, external_fallback_enabled=True)
    assert out == {"items": [], "spans": []}
    # 로컬은 reader 상한(120)에서 유료 몫(30)을 뺀 90초까지만 — 채팅 SLA(15)로 자르지 않는다
    assert local.seen == [{"first_wait": 15.0, "stall": 5.0, "max_seconds": 90.0}]
    # 유료는 남은 시간 전부(≥ 30초)를 받고 실제로 불렸다(deadline_exhausted 아님)
    assert paid.seen == [{"first_wait": 15.0, "stall": 5.0, "max_seconds": 30.0}]
    path = llm_failover.current_path()
    assert path["path"] == "api" and path["reasons"] == [("ollama", "timeout")]


def test_first_piece_stall_hands_over_at_once_and_paid_gets_the_rest():
    clock = Clock()
    local, paid = Local(clock, which="first"), Paid(clock)
    chat_of(clock, local, paid).reader_structured_stream("sys", "u", {}, **STREAM, api_reserve_seconds=30.0,
                                                         external_fallback_enabled=True)
    assert clock.now == pytest.approx(15.0 + 1.0)                 # 첫 조각 15초 규칙으로 멈춘 즉시 유료 1초
    assert paid.seen[0]["max_seconds"] == pytest.approx(105.0)    # 120 − 15


def test_no_reserve_when_external_fallback_is_off():
    clock = Clock()
    local, paid = Local(clock), Paid(clock)
    from app.infrastructure.ollama_chat import OllamaError
    with pytest.raises(OllamaError):
        chat_of(clock, local, paid).reader_structured_stream("sys", "u", {}, **STREAM, api_reserve_seconds=30.0,
                                                             external_fallback_enabled=False)
    assert local.seen[0]["max_seconds"] == 120.0 and paid.seen == []


def test_no_reserve_without_a_paid_backend():
    clock = Clock()
    local = Local(clock, stall=False)
    chat_of(clock, local).reader_structured_stream("sys", "u", {}, **STREAM, api_reserve_seconds=30.0,
                                                   external_fallback_enabled=True)
    assert local.seen[0]["max_seconds"] == 120.0


def test_api_only_chunk_gives_paid_the_whole_deadline():
    clock = Clock()
    local, paid = Local(clock, stall=False), Paid(clock)
    chat_of(clock, local, paid).reader_structured_stream("sys", "u", {}, **STREAM, api_only=True, api_reserve_seconds=30.0,
                                                         external_fallback_enabled=True)
    assert local.seen == [] and paid.seen[0]["max_seconds"] == 120.0


def test_local_is_skipped_when_only_the_reserve_is_left():
    clock = Clock()
    local, paid = Local(clock, stall=False), Paid(clock)
    chat_of(clock, local, paid).reader_structured_stream("sys", "u", {}, first_wait=15.0, stall=5.0, max_seconds=20.0,
                                                         api_reserve_seconds=30.0, external_fallback_enabled=True)
    assert local.seen == [] and paid.seen[0]["max_seconds"] == 20.0


def test_reserve_comes_from_the_guardrails():
    from app.domains.travel_ops.components.intake import pipeline
    from app.core.settings import get_guardrails

    value = get_guardrails().get("travel.intake_reading.api_reserve_seconds")
    assert isinstance(value, (int, float)) and 0 < value < get_guardrails().get("travel.intake_reading.max_seconds")
    assert pipeline._reading_stream(None)["api_reserve_seconds"] == value


def test_agent_reader_passes_the_reserve_to_the_reader_entry():
    from datetime import date
    from app.domains.travel_ops.components.intake import agent_read

    seen = {}

    class Wrapper:
        model = "w"

        def reader_json(self, *a, **k):
            raise AssertionError("not used")

        def reader_structured_stream(self, system, user, schema, **kw):
            seen.update(kw)
            return {"items": []}

    stream = {"first_token_seconds": 15, "stall_seconds": 5, "max_seconds": 120, "progress_seconds": 5, "api_reserve_seconds": 30}
    agent_read.read("2030-01-02\n10:00 경복궁", ["2030-01-02", "10:00 경복궁"], Wrapper(), today=date(2029, 12, 20),
                    stream=stream, external_fallback_enabled=True)
    assert seen["api_reserve_seconds"] == 30.0 and seen["max_seconds"] == 120.0


def test_reader_deadline_is_the_reader_ceiling_not_the_chat_sla():
    """x600 재현(새 인자 없이) — 옛 판은 로컬에 15초(채팅 SLA)만 주고 유료를 `deadline_exhausted` 로 건너뛰었다."""
    clock = Clock()
    local, paid = Local(clock, which="first"), Paid(clock)
    chat_of(clock, local, paid, total_seconds=15.0).reader_structured_stream("sys", "u", {}, **STREAM,
                                                                             external_fallback_enabled=True)
    assert local.seen[0]["max_seconds"] == 120.0 and paid.seen and paid.seen[0]["max_seconds"] == pytest.approx(105.0)
