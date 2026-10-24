"""Independent F3 schedule: enqueue before API start, caller cannot consume.

The barrier observes worker completion, never requires provider entry. Both old
and new implementations execute the identical test; only the product may deny
an unnecessary dispatch. No socket, DB, SDK or production hook is replaced.
"""
import threading
from types import SimpleNamespace

import pytest

from app.infrastructure import llm_failover as lf


@pytest.mark.parametrize("iteration", range(3))
def test_enqueued_local_winner_prevents_unclaimed_paid_dispatch(monkeypatch, iteration):
    release_local = threading.Event()
    published = threading.Event()
    api_finished = threading.Event()
    paid = []
    events = []
    outcomes = []
    workers = []
    budget_callers = []
    caller = threading.get_ident()
    real_thread = threading.Thread
    real_queue = lf.queue.Queue

    class ObservedQueue(real_queue):
        def put(self, item, *args, **kwargs):
            result = super().put(item, *args, **kwargs)
            outcomes.append((item[0].is_api, item[1]))
            if not item[0].is_api:
                events.append("local-enqueued")
                published.set()
            return result

    class ScheduledThread(real_thread):
        def __init__(self, *, target, args, **kwargs):
            self.api_worker = len(workers) == 1

            def owned_target():
                try:
                    target(*args)
                finally:
                    if self.api_worker:
                        events.append("api-worker-finished")
                        api_finished.set()

            super().__init__(target=owned_target, **kwargs)
            workers.append(self)

        def start(self):
            if self.api_worker:
                # Same gap as original probe: caller's last queue read was empty.
                events.append("api-start-hook")
                release_local.set()
                assert published.wait(3)
            super().start()
            if self.api_worker:
                # Caller stays in Thread.start until the actual worker terminates.
                # Unlike paid_called.wait, this is satisfiable when dispatch is denied.
                assert api_finished.wait(3)
                events.append("caller-resumed")

    def local(*args):
        assert release_local.wait(3)
        return "local-valid"

    def api(*args):
        paid.append("avoidable")
        events.append("provider-entered")
        return "paid-valid"

    def gate():
        budget_callers.append(threading.get_ident())
        return True

    def backend(name, fn, is_api=False):
        return lf._Backend(
            name, SimpleNamespace(base_url="fake://acceptance-" + name, model="m", text=fn),
            lf.CircuitBreaker(name, threshold=3, open_seconds=60),
            is_api=is_api, budget=gate if is_api else None, timeout=.001,
        )

    monkeypatch.setattr(lf.queue, "Queue", ObservedQueue)
    monkeypatch.setattr(lf.threading, "Thread", ScheduledThread)
    chat = lf.FailoverChat([
        backend("local-" + str(iteration), local),
        backend("api-" + str(iteration), api, True),
    ], hedge_seconds=.005)
    try:
        result = chat.text("system", "Seoul")
        path = lf.current_path()
    finally:
        release_local.set()
        for worker in workers:
            worker.join(3)
            assert not worker.is_alive()
    assert result == "local-valid"
    assert path["path"] == "local" and path["backend"] == "local-" + str(iteration)
    assert events.index("api-start-hook") < events.index("local-enqueued")
    assert events.index("local-enqueued") < events.index("api-worker-finished") < events.index("caller-resumed")
    assert paid == [], "F3: paid provider dispatched after local winner enqueue before Thread.start"
    assert outcomes == [(False, (True, "local-valid")), (True, (False, "cancelled"))]
    assert budget_callers == [caller]
    assert all(value == 0 for value in lf.snapshot()["inflight"].values())
    assert all(not b.breaker._probing for b in chat._backends)
