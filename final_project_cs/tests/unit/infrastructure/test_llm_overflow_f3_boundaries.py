"""Atomic dispatch ordering through the real nonstream caller, with fake providers."""
import threading
from types import SimpleNamespace
import pytest
from app.infrastructure import llm_failover as lf


@pytest.mark.parametrize('publication_first', [True, False])
def test_publication_and_dispatch_claim_have_explicit_order(monkeypatch, publication_first):
    release = threading.Event()
    published = threading.Event()
    paid = []
    claims = []
    workers = []
    real_queue = lf.queue.Queue
    real_thread = threading.Thread
    real_attempt = lf.FailoverChat._attempt

    class ObservedQueue(real_queue):
        def put(self, item, *args, **kwargs):
            result = super().put(item, *args, **kwargs)
            if not item[0].is_api and item[1][0]:
                published.set()
            return result

    class OwnedThread(real_thread):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            workers.append(self)

    def attempt(self, backend, *args, **kwargs):
        if backend.is_api:
            actual_claim = kwargs['dispatch_claim']

            def ordered_claim():
                if publication_first:
                    release.set()
                    assert published.wait(3)
                accepted = actual_claim()
                claims.append(accepted)
                if not publication_first:
                    # Provider invocation has not happened yet, but dispatch has
                    # committed. Publication must not revoke an existing claim.
                    release.set()
                    assert published.wait(3)
                return accepted

            kwargs['dispatch_claim'] = ordered_claim
        return real_attempt(self, backend, *args, **kwargs)

    def backend(name, fn, api=False):
        return lf._Backend(name, SimpleNamespace(base_url='fake://order-' + name, model='m', text=fn),
                           lf.CircuitBreaker(name, threshold=3, open_seconds=60),
                           is_api=api, budget=(lambda: True) if api else None, timeout=.001)

    def local(*args):
        assert release.wait(3)
        return 'local'

    monkeypatch.setattr(lf.queue, 'Queue', ObservedQueue)
    monkeypatch.setattr(lf.threading, 'Thread', OwnedThread)
    monkeypatch.setattr(lf.FailoverChat, '_attempt', attempt)
    chat = lf.FailoverChat([backend('order-local', local),
                            backend('order-api', lambda *args: paid.append(1) or 'paid', True)],
                           hedge_seconds=.005)
    try:
        assert chat.text('s', 'Seoul') == 'local'
    finally:
        release.set()
        for worker in workers:
            worker.join(3)
            assert not worker.is_alive()
    assert claims == [not publication_first]
    assert paid == ([] if publication_first else [1])
    assert all(value == 0 for value in lf.snapshot()['inflight'].values())
