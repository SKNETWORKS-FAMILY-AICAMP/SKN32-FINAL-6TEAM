"""Request-scope closure before a delayed worker's first provider call."""
import threading
from types import SimpleNamespace
import pytest
from app.infrastructure import llm_failover as lf


def test_budget_exception_closes_scope_before_delayed_local_worker_dispatch(monkeypatch):
    release = threading.Event()
    done = threading.Event()
    calls = []
    real_thread = threading.Thread

    class DelayedThread(real_thread):
        def __init__(self, *, target, args, **kwargs):
            def delayed():
                try:
                    assert release.wait(2)
                    target(*args)
                finally:
                    done.set()
            super().__init__(target=delayed, **kwargs)

    def backend(name, fn, *, api=False, budget=None):
        return lf._Backend(name, SimpleNamespace(base_url='fake://' + name, model='m', text=fn),
                           lf.CircuitBreaker(name, threshold=3, open_seconds=60),
                           is_api=api, budget=budget, timeout=.01)

    def gate():
        raise RuntimeError('controlled admission failure')

    monkeypatch.setattr(lf.threading, 'Thread', DelayedThread)
    chat = lf.FailoverChat([
        backend('delayed-local', lambda *args: calls.append('local') or 'local'),
        backend('delayed-api', lambda *args: calls.append('paid') or 'paid', api=True, budget=gate),
    ], hedge_seconds=.005)
    try:
        with pytest.raises(RuntimeError, match='controlled admission failure'):
            chat.text('system', 'Seoul')
    finally:
        release.set()
        assert done.wait(2)
    assert calls == [], 'Provider started after the caller had already failed'
    assert all(value == 0 for value in lf.snapshot()['inflight'].values())
