# -*- coding: utf-8 -*-
"""로컬 runner 앞 줄서기는 회로 실패가 아니다. `[2026-10-28 x600 05:26:35]`

근거: x600 Ollama runner 는 `-np 1`(한 번에 1건)이다. 모델이 다시 올라온 직후 같은 api 프로세스에서 `structured` 3건이 동시에 들어와
runner 안에서 줄을 섰고, 기다린 시간까지 로컬 제한시간에 들어가 셋 다 `timeout` 으로 세어졌다 → 로컬 회로 open 60초 → 그동안 모든 호출 유료.
계약(`wiki/external/llm-failover.md` 4-1): 넘김 장치는 로컬 runner 마다 동시 호출 자리(`llm_failover_local_concurrency`)를 둔다.
자리를 못 얻은 호출은 회로를 건드리지 않고(`local_busy`) 다음 경로로 간다. 자리 대기는 호출의 첫 조각 · 제한시간 바깥이고,
대기 상한은 `llm_failover_local_queue_seconds` 와 뒤 유료 몫(비-reader: 기존 SLA 식, reader: `api_reserve_seconds`) 중 작은 쪽이다.
대역만 쓴다(모델 · HTTP · DB 없음).
"""
from __future__ import annotations

import json
import math
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

from app.infrastructure import llm_failover as lf
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, _Backend
from app.infrastructure.ollama_chat import OllamaChat

URL = "http://ollama.test:11434"
KEY = "sk-test-not-a-key"
SCHEMA = {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    from app.infrastructure import ollama_chat

    monkeypatch.setattr(ollama_chat, "_route_provider", None)
    lf.reset_state()
    yield
    lf.reset_state()


def settings(**over):
    base = dict(ollama_base_url=URL, ollama_model="gemma4:12b", ollama_timeout_seconds=60.0, ollama_keep_alive="",
                llm_failover_enabled=True, openai_api_key_server=KEY, llm_model="gpt-4o-mini", llm_failover_model="",
                llm_failover_primary_timeout_seconds=6.0, llm_failover_api_timeout_seconds=8.0, llm_failover_total_seconds=15.0,
                llm_failover_failures=3, llm_failover_open_seconds=60.0, llm_failover_daily_cap=2000, llm_failover_monthly_cap=30000,
                llm_failover_vision=False, ollama_fallback_base_urls="")
    base.update(over)
    return SimpleNamespace(**base)


class Api:
    """OpenAI 클라이언트 흉내 — 여러 스레드가 불러도 된다."""

    def __init__(self, content='{"action": "paid"}') -> None:
        self.content, self.calls, self._lock = content, [], threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def answer(url, content='{"action": "local"}'):
    return httpx.Response(200, json={"message": {"content": content}}, request=httpx.Request("POST", url))


class OneSlotRunner:
    """`-np 1` runner 흉내 — 한 번에 한 건만 처리하고(`service` 초), 클라이언트 제한시간(`client_timeout`)은 **요청을 보낸 때부터** 센다.
    그래서 runner 안에서 줄을 선 시간도 제한시간에 들어간다(x600 그대로)."""

    def __init__(self, *, service: float, client_timeout: float) -> None:
        self.service, self.client_timeout = service, client_timeout
        self._runner, self._lock = threading.Lock(), threading.Lock()
        self.calls = self.active = self.peak = 0

    def __call__(self, url, payload):
        sent = time.monotonic()
        with self._lock:
            self.calls += 1
        with self._runner:
            with self._lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(self.service)
            with self._lock:
                self.active -= 1
        if time.monotonic() - sent > self.client_timeout:
            raise httpx.ReadTimeout("client read timeout")
        return answer(url)


class HeldRunner:
    """`-np 1` runner 흉내(시간에 기대지 않는 판) — 첫 요청은 시험이 `release` 할 때까지 붙잡고,
    뒤 요청은 runner 안에서 줄을 서다 클라이언트 제한시간(`client_timeout`, 요청을 보낸 때부터)에 끊긴다."""

    def __init__(self, *, client_timeout: float) -> None:
        self.client_timeout = client_timeout
        self._runner, self._lock, self.release = threading.Lock(), threading.Lock(), threading.Event()
        self.calls = self.active = self.peak = 0

    def __call__(self, url, payload):
        with self._lock:
            self.calls += 1
        if not self._runner.acquire(timeout=self.client_timeout):
            raise httpx.ReadTimeout("client read timeout while queued in the runner")
        try:
            with self._lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            assert self.release.wait(10), "the test never released the first request"
        finally:
            with self._lock:
                self.active -= 1
            self._runner.release()
        return answer(url)


class Script:
    """호출마다 다음 동작(예외 · 응답)을 한다. 다 쓰면 마지막 동작을 되풀이한다."""

    def __init__(self, *steps) -> None:
        self.steps, self.calls = list(steps), 0

    def __call__(self, url, payload):
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        if isinstance(step, BaseException):
            raise step
        return answer(url, step)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def build(transport, api=None, *, clock=None, sleep=None, **over):
    primary = OllamaChat(base_url=URL, model="gemma4:12b", transport=transport)
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    if sleep is not None:
        kwargs["sleep"] = sleep
    return lf.wrap_from_settings(primary, settings(**over), budget=lambda: True, api_client=api or Api(), **kwargs)


def local_breaker():
    return lf.breaker_for(f"ollama@{URL}", threshold=3, open_seconds=60.0)


def run_together(chat, count):
    barrier, out, errors = threading.Barrier(count), [None] * count, []

    def one(i):
        barrier.wait()
        try:
            out[i] = (chat.structured("sys", "synthetic request", SCHEMA), lf.current_path())
        except BaseException as exc:                              # noqa: BLE001 — 시험이 모아서 본다
            errors.append(exc)

    threads = [threading.Thread(target=one, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not any(t.is_alive() for t in threads)
    assert not errors, errors
    return out


# ───────────── x600 재현 ─────────────
def test_x600_four_concurrent_structured_calls_behind_a_one_slot_runner_do_not_open_the_local_breaker():
    """runner 가 첫 요청을 처리하는 동안 3건이 더 오면, 예전에는 3건이 runner 안에서 줄만 서다 timeout 으로 세어져 회로가 열렸다."""
    runner, api = HeldRunner(client_timeout=0.5), Api()
    chat = build(runner, api, llm_failover_local_concurrency=1)
    results, finished, lock = [], [], threading.Lock()

    def one():
        out = (chat.structured("sys", "synthetic request", SCHEMA), lf.current_path())
        with lock:
            results.append(out)
            finished.append(1)

    threads = [threading.Thread(target=one) for _ in range(4)]
    for t in threads:
        t.start()
    limit = time.monotonic() + 5.0
    while len(finished) < 3 and time.monotonic() < limit:     # 붙잡힌 첫 요청 말고 3건이 끝날 때까지
        time.sleep(0.01)
    runner.release.set()
    for t in threads:
        t.join(10)
    assert not any(t.is_alive() for t in threads) and len(results) == 4
    paths = sorted(path["path"] for _, path in results)
    assert paths == ["api", "api", "api", "local"]
    assert sorted(tuple(map(tuple, path["reasons"])) for _, path in results if path["path"] == "api") == [(("ollama", "local_busy"),)] * 3
    assert runner.calls == 1 and runner.peak == 1                  # runner 에는 한 건만 갔다 — 줄을 runner 안에 세우지 않는다
    assert local_breaker().snapshot() == {"state": "closed", "failures": 0}
    counters = lf.snapshot()["counters"]
    assert counters["skip:ollama:local_busy"] == 3 and "fail:ollama:timeout" not in counters
    assert len(api.calls) == 3


def test_genuine_local_timeouts_still_open_the_breaker_and_busy_skips_do_not_reset_the_count():
    clock = Clock()
    server = Script(httpx.ReadTimeout("slow"))
    chat = build(server, clock=clock, sleep=clock.sleep, llm_failover_local_concurrency=1)
    chat.structured("sys", "u", SCHEMA)
    assert local_breaker().snapshot() == {"state": "closed", "failures": 1}
    gate = chat._backends[0].slots
    assert gate.acquire(0.0)                                       # 다른 호출이 runner 를 쓰는 중
    try:
        chat.structured("sys", "u", SCHEMA)
        assert lf.current_path()["reasons"] == [("ollama", "local_busy")]
        assert local_breaker().snapshot() == {"state": "closed", "failures": 1}   # 성공도 실패도 아니다
    finally:
        gate.release()
    chat.structured("sys", "u", SCHEMA)
    chat.structured("sys", "u", SCHEMA)
    assert local_breaker().snapshot()["state"] == "open" and server.calls == 3   # 진짜 고장 3번이면 그대로 열린다
    chat.structured("sys", "u", SCHEMA)
    assert lf.current_path()["reasons"] == [("ollama", "circuit_open")] and server.calls == 3


def test_a_free_slot_still_calls_local_even_when_the_sla_leaves_no_queue_time():
    """15 - 9(로컬) - 8(유료) < 0 이라 기다릴 시간은 0 이지만, 빈 자리면 예전처럼 로컬을 부른다. 바쁘면 기다리지 않고 바로 넘긴다."""
    server, api = Script('{"action": "local"}'), Api()
    chat = build(server, api, llm_failover_local_concurrency=1, llm_failover_local_queue_seconds=30.0,
                 llm_failover_primary_timeout_seconds=9.0)
    assert chat.structured("sys", "u", SCHEMA) == {"action": "local"} and lf.current_path()["path"] == "local"
    gate = chat._backends[0].slots
    assert gate.acquire(0.0)
    try:
        started = time.monotonic()
        assert chat.structured("sys", "u", SCHEMA) == {"action": "paid"}
        assert time.monotonic() - started < 1.0
    finally:
        gate.release()
    assert server.calls == 1 and len(api.calls) == 1


def test_a_configured_queue_wait_lets_queued_calls_run_locally_with_their_own_timer():
    """자리 대기는 로컬 제한시간 바깥이다 — 기다린 뒤 보낸 요청은 제 처리 시간만 제한시간에 든다."""
    runner, api = OneSlotRunner(service=0.2, client_timeout=0.35), Api()
    chat = build(runner, api, llm_failover_local_concurrency=1, llm_failover_local_queue_seconds=5.0,
                 llm_failover_total_seconds=60.0)
    results = run_together(chat, 3)
    assert [path["path"] for _, path in results] == ["local"] * 3
    assert runner.calls == 3 and runner.peak == 1 and api.calls == []
    assert local_breaker().snapshot() == {"state": "closed", "failures": 0}


class FakeGate:
    """자리 대역 — 요청받은 대기 상한을 적고, 시계를 `wait` 만큼 옮긴 뒤 `grant` 를 돌려준다."""

    def __init__(self, clock, *, grant: bool, wait: float | None = None) -> None:
        self.clock, self.grant, self.wait, self.asked, self.held = clock, grant, wait, [], 0

    def acquire(self, timeout: float) -> bool:
        self.asked.append(timeout)
        self.clock.now += timeout if self.wait is None else self.wait
        if self.grant:
            self.held += 1
        return self.grant

    def release(self) -> None:
        self.held -= 1


def test_the_queue_wait_outside_reader_never_eats_the_paid_share():
    clock = Clock()
    server, api = Script('{"action": "local"}'), Api()
    chat = build(server, api, clock=clock, sleep=clock.sleep, llm_failover_local_concurrency=1, llm_failover_local_queue_seconds=10.0)
    gate = chat._backends[0].slots = FakeGate(clock, grant=False)
    assert chat.structured("sys", "u", SCHEMA) == {"action": "paid"}
    assert gate.asked == [pytest.approx(1.0)]                       # 15 - 6(로컬) - 8(유료) = 1 < 10
    assert server.calls == 0 and local_breaker().snapshot() == {"state": "closed", "failures": 0}


class StreamLocal:
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, clock) -> None:
        self.clock, self.seen = clock, []

    def loaded(self, *, timeout=5.0):
        return True

    def structured_stream(self, system, user, schema, **kw):
        self.seen.append({"at": self.clock.now, **{k: kw[k] for k in ("first_wait", "stall", "max_seconds")}})
        self.clock.now += 1.0
        return {"action": "local"}


class StreamPaid(StreamLocal):
    model = "paid-double"

    def structured_stream(self, system, user, schema, **kw):
        self.seen.append({"at": self.clock.now, **{k: kw[k] for k in ("first_wait", "stall", "max_seconds")}})
        self.clock.now += 1.0
        return {"action": "paid"}


def reader_chat(clock, gate, *, queue_seconds):
    local, paid = StreamLocal(clock), StreamPaid(clock)
    backends = [_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60, clock=clock), timeout=9.0, slots=gate),
                _Backend("openai", paid, CircuitBreaker("openai", threshold=3, open_seconds=60, clock=clock), is_api=True, timeout=8.0,
                         reader_budget=lambda: True)]
    return FailoverChat(backends, total_seconds=15.0, sleep=lambda s: None, clock=clock, local_queue_seconds=queue_seconds), local, paid


def test_reader_queue_wait_keeps_the_paid_reserve_and_the_first_piece_timer_starts_after_the_slot():
    clock = Clock()
    gate = FakeGate(clock, grant=True, wait=4.0)
    chat, local, paid = reader_chat(clock, gate, queue_seconds=100.0)
    out = chat.reader_structured_stream("sys", "plan", SCHEMA, first_wait=5.0, stall=5.0, max_seconds=60.0,
                                        external_fallback_enabled=True, api_reserve_seconds=30.0)
    assert out == {"action": "local"}
    assert gate.asked == [pytest.approx(30.0)]                      # 60 - 30(유료 몫)
    assert local.seen == [{"at": 1004.0, "first_wait": 5.0, "stall": 5.0, "max_seconds": pytest.approx(26.0)}]
    assert gate.held == 0 and paid.seen == []


def test_reader_busy_after_the_full_wait_still_leaves_the_whole_reserve_to_the_paid_model():
    clock = Clock()
    gate = FakeGate(clock, grant=False)
    chat, local, paid = reader_chat(clock, gate, queue_seconds=100.0)
    out = chat.reader_structured_stream("sys", "plan", SCHEMA, first_wait=5.0, stall=5.0, max_seconds=60.0,
                                        external_fallback_enabled=True, api_reserve_seconds=30.0)
    assert out == {"action": "paid"} and local.seen == []
    assert paid.seen[0]["max_seconds"] == pytest.approx(30.0)       # 유료 몫은 고스란히 남는다
    assert lf.current_path()["reasons"] == [("ollama", "local_busy")]
    assert chat._backends[0].breaker.snapshot() == {"state": "closed", "failures": 0}


def test_reader_without_a_usable_paid_path_may_wait_up_to_its_whole_deadline():
    clock = Clock()
    gate = FakeGate(clock, grant=True, wait=0.0)
    chat, local, _ = reader_chat(clock, gate, queue_seconds=100.0)
    chat.reader_structured_stream("sys", "plan", SCHEMA, first_wait=5.0, stall=5.0, max_seconds=60.0,
                                  external_fallback_enabled=False, api_reserve_seconds=30.0)
    assert gate.asked == [pytest.approx(60.0)] and len(local.seen) == 1


# ───────────── 반쪽 시험 · 자리 반납 ─────────────
def test_a_busy_call_does_not_take_or_spend_the_half_open_probe():
    clock = Clock()
    server = Script(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), '{"action": "local"}')
    chat = build(server, clock=clock, sleep=clock.sleep, llm_failover_local_concurrency=1)
    for _ in range(3):
        chat.structured("sys", "u", SCHEMA)
    breaker = local_breaker()
    assert breaker.snapshot()["state"] == "open"
    clock.now += 61.0
    gate = chat._backends[0].slots
    assert gate.acquire(0.0)
    try:
        chat.structured("sys", "u", SCHEMA)
        assert lf.current_path()["reasons"] == [("ollama", "local_busy")]
        assert breaker.snapshot()["state"] == "open" and breaker._probing is False
    finally:
        gate.release()
    assert chat.structured("sys", "u", SCHEMA) == {"action": "local"}   # 자리가 나면 시험 한 건이 로컬로 가 닫는다
    assert breaker.snapshot() == {"state": "closed", "failures": 0} and server.calls == 4


def test_the_slot_is_returned_after_an_unexpected_exception():
    chat = build(Script(RuntimeError("boom")), llm_failover_local_concurrency=1)
    with pytest.raises(RuntimeError):
        chat.structured("sys", "u", SCHEMA)
    gate = chat._backends[0].slots
    assert gate.snapshot()["active"] == 0 and gate.acquire(0.0)
    gate.release()


def test_the_retry_backoff_does_not_hold_the_slot():
    clock, held_during_sleep = Clock(), []
    server = SimpleNamespace(calls=0)

    def transport(url, payload):                                    # 첫 번은 503(다시 시도 대상), 다음은 답
        server.calls += 1
        if server.calls == 1:
            return httpx.Response(503, json={}, request=httpx.Request("POST", url))
        return answer(url)

    holder = {}

    def sleep(seconds):
        held_during_sleep.append(holder["chat"]._backends[0].slots.snapshot()["active"])
        clock.sleep(seconds)

    chat = holder["chat"] = build(transport, clock=clock, sleep=sleep, llm_failover_local_concurrency=1)
    assert chat.structured("sys", "u", SCHEMA) == {"action": "local"}
    assert held_during_sleep == [0] and server.calls == 2
    assert chat._backends[0].slots.snapshot()["active"] == 0


def test_a_retry_is_not_sent_when_the_runner_breaker_opened_during_the_backoff():
    clock, api = Clock(), Api()
    server = SimpleNamespace(calls=0)

    def transport(url, payload):
        server.calls += 1
        return httpx.Response(503, json={}, request=httpx.Request("POST", url))

    holder = {}

    def sleep(seconds):
        clock.sleep(seconds)
        breaker = holder["chat"]._backends[0].breaker
        for _ in range(3):                                          # 쉬는 동안 다른 호출들이 진짜로 실패해 회로를 열었다
            breaker.failure()

    chat = holder["chat"] = build(transport, api, clock=clock, sleep=sleep, llm_failover_local_concurrency=1)
    assert chat.structured("sys", "u", SCHEMA) == {"action": "paid"}
    assert server.calls == 1 and lf.current_path()["reasons"] == [("ollama", "circuit_open")]
    assert chat._backends[0].slots.snapshot()["active"] == 0


# ───────────── 5초 규칙 — 실제 조각 감시(`model_stream.collect`) ─────────────
class CollectLocal:
    """실제 조각 감시로 받는 로컬 대역 — 첫 조각을 `first_after` 초 뒤에 낸다."""
    model = "tripilot-pointer:e4b-ft"

    def __init__(self, first_after: float) -> None:
        self.first_after, self.sent_at = first_after, []

    def loaded(self, *, timeout=5.0):
        return True

    def structured_stream(self, system, user, schema, *, num_predict=160, on_piece=None, first_wait, stall, max_seconds):
        from app.infrastructure.model_stream import collect

        self.sent_at.append(time.monotonic())

        def pieces():
            time.sleep(self.first_after)
            yield '{"action": '
            yield '"local"}'

        return json.loads(collect(pieces, first_wait=first_wait, stall=stall, max_seconds=max_seconds, on_piece=on_piece))


class CollectPaid(CollectLocal):
    model = "paid-double"

    def structured_stream(self, system, user, schema, **kw):
        return {"action": "paid"}


def stream_chat(local, slots, *, queue_seconds):
    backends = [_Backend("ollama", local, CircuitBreaker("ollama", threshold=3, open_seconds=60), timeout=1.0, slots=slots),
                _Backend("openai", CollectPaid(0.0), CircuitBreaker("openai", threshold=3, open_seconds=60), is_api=True, timeout=1.0)]
    return FailoverChat(backends, total_seconds=60.0, sleep=lambda s: None, local_queue_seconds=queue_seconds)


def test_the_slot_wait_is_outside_the_first_piece_watch_and_the_watch_still_bites_after_it():
    slots = lf.LocalSlots("runner-under-test", 1)
    local = CollectLocal(first_after=0.1)
    chat = stream_chat(local, slots, queue_seconds=3.0)
    assert slots.acquire(0.0)
    threading.Timer(0.6, slots.release).start()                   # 다른 호출이 0.6초 동안 runner 를 쓴다
    started = time.monotonic()
    assert chat.structured_stream("sys", "u", SCHEMA, first_wait=0.4, stall=0.4, max_seconds=5.0) == {"action": "local"}
    waited = local.sent_at[0] - started
    assert waited >= 0.5 and time.monotonic() - started > 0.4      # 첫 조각 시한(0.4)보다 오래 기다렸지만 끊기지 않았다
    assert lf.current_path()["path"] == "local" and chat._backends[0].breaker.snapshot() == {"state": "closed", "failures": 0}

    slow = CollectLocal(first_after=0.8)                           # 자리를 얻은 뒤 첫 조각이 시한보다 늦으면 예전처럼 끊고 센다
    chat = stream_chat(slow, slots, queue_seconds=3.0)
    assert chat.structured_stream("sys", "u", SCHEMA, first_wait=0.4, stall=0.4, max_seconds=5.0) == {"action": "paid"}
    assert lf.current_path()["reasons"] == [("ollama", "timeout")]
    assert chat._backends[0].breaker.snapshot() == {"state": "closed", "failures": 1}
    assert slots.snapshot()["active"] == 0


# ───────────── 설정 ─────────────
def test_without_the_setting_the_old_unlimited_behaviour_stays():
    chat = build(Script('{"action": "local"}'))
    assert chat._backends[0].slots is None and chat.local_queue_seconds == 0.0


@pytest.mark.parametrize("over", [{"llm_failover_local_concurrency": -1}, {"llm_failover_local_queue_seconds": -0.5},
                                  {"llm_failover_local_queue_seconds": math.inf}, {"llm_failover_local_queue_seconds": math.nan}])
def test_invalid_slot_settings_are_refused(over):
    with pytest.raises(ValueError):
        build(Script('{"action": "local"}'), **{"llm_failover_local_concurrency": 1, **over})


@pytest.mark.parametrize("first,second", [(1, 2), (1, 0), (0, 1)])
def test_two_sizes_for_the_same_runner_are_refused_instead_of_silently_taking_the_first(first, second):
    """0(상한 없음)도 크기다 — 한 wrapper 가 상한 없이 불러 다른 wrapper 의 자리를 우회하지 않게."""
    build(Script('{"action": "local"}'), llm_failover_local_concurrency=first)
    with pytest.raises(ValueError):
        build(Script('{"action": "local"}'), llm_failover_local_concurrency=second)


def test_the_runner_key_folds_scheme_host_case_and_a_trailing_slash_only():
    assert lf._runner_key("HTTP://Ollama.Test:11434/") == lf._runner_key(URL)
    assert lf._runner_key("http://ollama.test:11434/A") != lf._runner_key("http://ollama.test:11434/a")


def test_the_same_runner_shares_one_gate_across_wrappers():
    first = build(Script('{"action": "local"}'), llm_failover_local_concurrency=1)
    second = build(Script('{"action": "local"}'), llm_failover_local_concurrency=1)
    assert first._backends[0].slots is second._backends[0].slots


def test_settings_defaults_match_the_one_slot_runner():
    from app.core.settings import Settings

    fields = Settings.model_fields
    assert fields["llm_failover_local_concurrency"].default == 1
    assert fields["llm_failover_local_queue_seconds"].default == 0.0
    meta = {type(m).__name__: m for m in fields["llm_failover_local_concurrency"].metadata}
    assert meta["Ge"].ge == 0
    assert json.dumps(lf.snapshot()["local_slots"]) == "{}"
