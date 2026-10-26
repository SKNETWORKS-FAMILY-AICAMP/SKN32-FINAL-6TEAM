"""Reader-only safety regressions. Event/clock doubles; no HTTP or database."""


from contextlib import contextmanager


import threading


import time


from types import SimpleNamespace as N


import pytest


from app.infrastructure.model_stream import collect, StreamStalled


from app.infrastructure.ollama_chat import OllamaChat


from app.infrastructure.llm_failover import OpenAIChat


@pytest.mark.parametrize('provider', ['ollama', 'openai'])
def test_late_response_is_closed_without_any_read(monkeypatch, provider):
    entered, release, closed, exited = (threading.Event() for _ in range(4))
    reads, workers = [], []
    class Response:
        status_code = 200
        def iter_lines(self):
            reads.append('iter_lines')
            return iter([])
        def __iter__(self):
            reads.append('sdk_iter')
            return iter([])
        def close(self):
            closed.set()
    response = Response()
    def acquire(**kw):
        workers.append(threading.current_thread())
        entered.set()
        release.wait()
        return response
    @contextmanager
    def stream(*a, **kw):
        try:
            yield acquire()
        finally:
            response.close()
            exited.set()
    if provider == 'ollama':
        monkeypatch.setattr('httpx.stream', stream)
        chat = OllamaChat(base_url='http://never.invalid', model='configured')
    else:
        def create(**kw):
            try:
                return acquire()
            finally:
                exited.set()
        chat = OpenAIChat(api_key='unit-only', model='configured', client=N(chat=N(completions=N(create=create))))
    try:
        with pytest.raises(StreamStalled):
            chat.structured_stream('s', 'u', {}, num_predict=1, first_wait=.02, stall=1, max_seconds=1)
        assert entered.is_set()
    finally:
        release.set()
    assert closed.wait(1), 'late response leaked after caller timeout'
    assert exited.wait(1)
    workers[0].join(1)
    assert not workers[0].is_alive(), 'released producer did not terminate'
    assert reads == [], 'timed-out producer started reading the late response'


def test_blocking_close_cannot_extend_caller_deadline():
    release, closing, done = (threading.Event() for _ in range(3))
    def pieces():
        try:
            release.wait()
            yield 'too late'
        finally:
            done.set()
    def close():
        closing.set()
        release.wait()
    start = time.monotonic()
    # Release from a separate watchdog even on the broken implementation.
    watchdog = threading.Timer(.4, release.set)
    watchdog.start()
    try:
        with pytest.raises(StreamStalled):
            collect(pieces, first_wait=.02, stall=1, max_seconds=1, close=close)
        assert time.monotonic() - start < .2, 'synchronous close blocked deadline'
    finally:
        release.set()
        watchdog.cancel()
    assert closing.wait(1) and done.wait(1)


def test_failover_stream_passes_only_remaining_shared_deadline():
    from app.infrastructure.llm_failover import FailoverChat, CircuitBreaker, _Backend
    from app.infrastructure.ollama_chat import OllamaError
    now, seen = [0.0], []
    class Chat:
        def __init__(self, cost, fail):
            self.cost, self.fail = cost, fail
        def structured_stream(self, *a, **kw):
            seen.append(kw['max_seconds'])
            now[0] += self.cost
            if self.fail:
                raise OllamaError('local failed')
            return {'items': []}
    def backend(name, cost, fail):
        return _Backend(name, Chat(cost, fail), CircuitBreaker(name, threshold=1, open_seconds=1), timeout=1)
    # contract_correction [2026-10-26 x600 74b2b232]: reader 시한은 reader 자신의 max_seconds 다(채팅 SLA total_seconds 로 자르지 않는다).
    #   옛 입력 total_seconds=3 · max_seconds=10 은 시한 3을 total 로 만들었다 — 같은 시한 3을 max_seconds 로 주고 기대([3, 1])는 그대로 둔다.
    chat = FailoverChat([backend('one', 2, True), backend('two', 1, False)],
                        total_seconds=15, clock=lambda: now[0])
    assert chat.reader_structured_stream('s', 'u', {}, num_predict=1, first_wait=1, stall=1, max_seconds=3) == {'items': []}
    assert seen == [3, 1], 'backend received a renewed total instead of remaining time'


def test_failover_does_not_start_backend_after_shared_deadline():
    from app.infrastructure.llm_failover import FailoverChat, CircuitBreaker, _Backend
    from app.infrastructure.ollama_chat import OllamaError
    now, seen = [0.0], []
    class Chat:
        def structured_stream(self, *a, **kw):
            seen.append(kw['max_seconds'])
            now[0] += 3
            raise OllamaError('failed')
    backends = [_Backend(n, Chat(), CircuitBreaker(n, threshold=1, open_seconds=1)) for n in ('one','two')]
    with pytest.raises(OllamaError):
        # contract_correction [2026-10-26 x600 74b2b232]: 시한 2를 total_seconds 대신 reader 의 max_seconds 로 준다(기대 [2] 그대로)
        FailoverChat(backends, total_seconds=15, clock=lambda: now[0]).reader_structured_stream(
            's', 'u', {}, num_predict=1, first_wait=1, stall=1, max_seconds=2)
    assert seen == [2], 'expired caller budget still started a second backend'


def paid_chat(gate, *, fail_first=False):
    from app.infrastructure.llm_failover import FailoverChat, CircuitBreaker, _Backend, ModelCallError
    calls, reserves, now = [], [], [0.0]
    class API:
        model = 'actual-api-model'
        def structured_stream(self, *args, **kwargs):
            calls.append(kwargs)
            if fail_first and len(calls) == 1:
                raise ModelCallError('busy', reason='429')
            return {'items': []}
    def reserve():
        reserves.append(True)
        return gate()
    backend = _Backend('paid', API(), CircuitBreaker('paid', threshold=1, open_seconds=1),
                       is_api=True, timeout=.1, budget=lambda: True)
    backend.reader_budget = reserve if gate is not None else None
    chat = FailoverChat([backend], total_seconds=5, clock=lambda: now[0],
                        sleep=lambda seconds: now.__setitem__(0, now[0] + seconds), backoff_seconds=.1)
    return chat, calls, reserves


def test_direct_local_reader_provenance_identifies_configured_model():
    chat = OllamaChat(base_url='http://never.invalid', model='configured-local')
    assert chat.reader_provenance == {'path': 'local', 'backend': 'ollama', 'model': 'configured-local'}


def test_legacy_reader_json_cannot_bypass_external_policy():
    from app.infrastructure.llm_failover import FailoverChat, CircuitBreaker, _Backend
    from app.infrastructure.ollama_chat import OllamaError
    calls = []
    class API:
        def json(self, *a, **kw):
            calls.append('paid')
            return {}
    backend = _Backend('api', API(), CircuitBreaker('line', threshold=1, open_seconds=1), is_api=True,
                       budget=lambda: True, reader_budget=lambda: True)
    chat = FailoverChat([backend])
    assert callable(getattr(type(chat), 'reader_json', None)), 'reader needs policy-scoped compatibility entry'
    with pytest.raises(OllamaError):
        chat.reader_json('s', '김여행')
    assert calls == []


def test_json_stream_reader_policy_blocks_external_before_budget():
    from app.infrastructure.llm_failover import FailoverChat, CircuitBreaker, _Backend
    from app.infrastructure.ollama_chat import OllamaError
    calls = []
    class API:
        def json_stream(self, *a, **kw):
            calls.append('paid')
            return {}
    backend = _Backend('api', API(), CircuitBreaker('json', threshold=1, open_seconds=1),
                       is_api=True, budget=lambda: calls.append('global') or True,
                       reader_budget=lambda: calls.append('strict') or True)
    with pytest.raises(OllamaError):
        FailoverChat([backend]).reader_json_stream('s', '김여행', first_wait=1, stall=1, max_seconds=2)
    assert calls == []


def test_sdk_parse_retry_reserves_each_paid_attempt_and_denial_stops_retry():
    from app.infrastructure.llm_failover import FailoverChat, CircuitBreaker
    from app.infrastructure.ollama_chat import OllamaError
    calls, reserves = [], []
    class Chunks:
        def __iter__(self):
            yield N(choices=[N(delta=N(content='not-json'), finish_reason='stop')])
        def close(self):
            pass
    def create(**kw):
        calls.append(kw)
        return Chunks()
    def reserve():
        reserves.append(True)
        return len(reserves) == 1
    api = OpenAIChat(api_key='unit', model='configured', client=N(chat=N(completions=N(create=create))))
    backend = __import__('app.infrastructure.llm_failover', fromlist=['_Backend'])._Backend(
        'api', api, CircuitBreaker('sdk', threshold=1, open_seconds=1), is_api=True,
        reader_budget=reserve)
    with pytest.raises(OllamaError):
        FailoverChat([backend]).reader_structured_stream('s', 'u', {}, num_predict=1,
            first_wait=1, stall=1, max_seconds=2, external_fallback_enabled=True)
    assert len(reserves) == 2
    assert len(calls) == 1


def test_reader_reports_actual_success_backend_and_model():
    from app.infrastructure.llm_failover import current_path
    chat, calls, reserves = paid_chat(lambda: True)
    chat.model = 'wrong-primary'
    chat.reader_structured_stream('s', 'u', {}, num_predict=1, first_wait=1, stall=1,
                           max_seconds=5, external_fallback_enabled=True)
    assert current_path()['model'] == 'actual-api-model'
    assert current_path()['backend'] == 'paid'


def test_reader_reserves_each_paid_retry():
    chat, calls, reserves = paid_chat(lambda: True, fail_first=True)
    chat.reader_structured_stream('s', 'u', {}, num_predict=1, first_wait=1, stall=1, max_seconds=5, external_fallback_enabled=True)
    assert len(calls) == len(reserves) == 2


@pytest.mark.parametrize('gate', [None, lambda: (_ for _ in ()).throw(RuntimeError('budget DB unavailable'))])
def test_reader_missing_or_broken_strict_gate_never_calls_api(gate):
    from app.infrastructure.ollama_chat import OllamaError
    chat, calls, reserves = paid_chat(gate)
    with pytest.raises(OllamaError):
        chat.reader_structured_stream('s', 'u', {}, num_predict=1, first_wait=1, stall=1, max_seconds=5, external_fallback_enabled=True)
    assert calls == []


def test_composed_reader_budget_fails_closed_without_changing_global_policy(monkeypatch):
    from app import composition
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
    strict = getattr(composition, '_llm_reader_budget', None)
    assert callable(strict), 'reader needs a separately composed strict reserve gate'
    def fail(*a, **kw):
        raise RuntimeError('synthetic budget database failure')
    monkeypatch.setattr(CallBudget, 'try_reserve', fail)
    settings = N(llm_failover_daily_cap=1, llm_failover_monthly_cap=2)
    assert strict(settings)() is False
    assert composition._llm_failover_budget(settings)() is True


def test_composed_reader_budget_without_cap_settings_denies_at_call_not_at_assembly(monkeypatch):
    from app import composition
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
    reserves = []
    monkeypatch.setattr(CallBudget, 'try_reserve', lambda *a, **kw: reserves.append(1) or True)
    gate = composition._llm_reader_budget(N())          # no cap settings: building the gate must not raise
    assert gate() is False
    assert reserves == []


@pytest.mark.parametrize('sentinel', ['김여행', '예약번호 ABCD-1234', '01012345678'])
def test_reader_default_external_policy_denies_pii_before_any_api_or_reserve(sentinel):
    from app.infrastructure.ollama_chat import OllamaError
    chat, calls, reserves = paid_chat(lambda: True)
    with pytest.raises(OllamaError):
        chat.reader_structured_stream('previous customer state: ' + sentinel, sentinel, {}, num_predict=1,
                               first_wait=1, stall=1, max_seconds=5)
    assert calls == reserves == []


def test_inflight_read_finishes_without_another_read_and_worker_exits():
    from app.infrastructure.model_stream import StreamLifetime
    lifetime = StreamLifetime()
    entered, release, closed, finalized = (threading.Event() for _ in range(4))
    reads, workers = [], []
    class Response:
        def __iter__(self):
            try:
                while True:
                    reads.append(True)
                    entered.set()
                    release.wait()
                    yield 'late'
            finally:
                finalized.set()
        def close(self):
            closed.set()
            release.set()
    def pieces():
        workers.append(threading.current_thread())
        response = Response()
        assert lifetime.acquire(response)
        yield from lifetime.iterate(response)
    try:
        with pytest.raises(StreamStalled):
            collect(pieces, first_wait=.02, stall=1, max_seconds=1, lifetime=lifetime)
    finally:
        release.set()
    assert entered.is_set() and closed.wait(1) and finalized.wait(1)
    workers[0].join(1)
    assert not workers[0].is_alive() and reads == [True]


def test_budget_denial_on_second_attempt_prevents_paid_retry():
    from app.infrastructure.ollama_chat import OllamaError
    decisions = iter([True, False])
    chat, calls, reserves = paid_chat(lambda: next(decisions), fail_first=True)
    with pytest.raises(OllamaError):
        chat.reader_structured_stream('s', 'u', {}, num_predict=1, first_wait=1, stall=1, max_seconds=5,
                               external_fallback_enabled=True)
    assert len(calls) == 1 and len(reserves) == 2
