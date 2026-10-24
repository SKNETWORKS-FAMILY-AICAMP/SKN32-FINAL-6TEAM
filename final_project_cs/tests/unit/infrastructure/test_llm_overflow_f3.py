"""Fresh independent event-controlled probes, no real providers or sockets."""
import contextvars
import threading
import queue
from types import SimpleNamespace
import pytest
from app.infrastructure import llm_failover as lf
from app.infrastructure.ollama_chat import OllamaError


def backend(name, fn, api=False, budget=None, cap=0):
    return lf._Backend(name, SimpleNamespace(base_url='fake://fresh-'+name,model='m',text=fn),
                      lf.CircuitBreaker(name,threshold=3,open_seconds=60),is_api=api,budget=budget,max_inflight=cap,timeout=.001)


def observe_queue(monkeypatch):
    published=threading.Event();real=queue.Queue
    class Observed(real):
        def put(self,item,*a,**kw):
            result=super().put(item,*a,**kw)
            if not item[0].is_api:published.set()
            return result
    monkeypatch.setattr(lf.queue,'Queue',Observed)
    return published


def test_bool_unused_reservation_exhausts_next_fallback_characterization(monkeypatch):
    published=observe_queue(monkeypatch);release=threading.Event();paid=[];reservations=[]
    def local(*a):
        if len(reservations)==0:
            assert release.wait(3);return 'local'
        raise OllamaError('cannot connect')
    def gate():
        if reservations:return False
        release.set();assert published.wait(3);reservations.append('unused');return True
    chat=lf.FailoverChat([backend('quota-local',local),backend('quota-api',lambda *a:paid.append(1) or 'paid',True,gate)],hedge_seconds=.005)
    assert chat.text('s','Seoul')=='local'
    with pytest.raises(OllamaError,match='budget_exhausted'):chat.text('s','Seoul again')
    assert reservations==['unused'] and paid==[]
    assert all(v==0 for v in lf.snapshot()['inflight'].values())


def test_delayed_api_first_dispatch_is_cancelled_after_local_winner(monkeypatch):
    local_release=threading.Event();api_release=threading.Event();api_done=threading.Event();paid=[]
    real=threading.Thread;count=[]
    class Delayed(real):
        def __init__(self,*,target,args,**kw):
            count.append(1);is_api=len(count)==2
            def run():
                try:
                    if is_api:assert api_release.wait(3)
                    target(*args)
                finally:
                    if is_api:api_done.set()
            super().__init__(target=run,**kw)
        def start(self):
            super().start()
            if len(count)==2:local_release.set()
    monkeypatch.setattr(lf.threading,'Thread',Delayed)
    def local(*a):assert local_release.wait(3);return 'local'
    chat=lf.FailoverChat([backend('delayed-local',local),backend('delayed-api',lambda *a:paid.append(1) or 'paid',True,lambda:True)],hedge_seconds=.005)
    try:assert chat.text('s','Seoul')=='local'
    finally:api_release.set();assert api_done.wait(3)
    assert paid==[]
    assert all(v==0 for v in lf.snapshot()['inflight'].values())


@pytest.mark.parametrize('iteration',range(3))
def test_no_paid_dispatch_if_local_is_queued_between_recheck_and_thread_start(monkeypatch,iteration):
    published=observe_queue(monkeypatch);release=threading.Event();paid_called=threading.Event();paid=[]
    real=threading.Thread;count=[];workers=[]
    class SchedulingGap(real):
        def __init__(self,*,target,args,**kw):
            count.append(1);self.second=len(count)==2
            super().__init__(target=target,args=args,**kw);workers.append(self)
        def start(self):
            if self.second:
                # Caller is descheduled after get_nowait() returned empty.
                release.set();assert published.wait(3)
            super().start()
            if self.second:assert paid_called.wait(3)
    monkeypatch.setattr(lf.threading,'Thread',SchedulingGap)
    def local(*a):assert release.wait(3);return 'local-valid'
    def api(*a):paid.append('avoidable');paid_called.set();return 'paid-valid'
    chat=lf.FailoverChat([backend('gap-local-'+str(iteration),local),backend('gap-api-'+str(iteration),api,True,lambda:True)],hedge_seconds=.005)
    try:assert chat.text('s','Seoul')=='local-valid'
    finally:
        release.set()
        for worker in workers:worker.join(3)
    assert paid==[], 'paid provider dispatched after a validated local winner was already enqueued before Thread.start'


def test_concurrent_callers_keep_context_budget_and_path_separate():
    marker=contextvars.ContextVar('fresh-caller',default='missing');barrier=threading.Barrier(2);release=threading.Event()
    gates=[];calls=[];answers={};errors=[];lock=threading.Lock();done=threading.Event();finished=[]
    def local(*a):
        with lock:calls.append(('local',marker.get()))
        assert release.wait(3)
        raise OllamaError('HTTP 503')
    def api(*a):
        value=marker.get()
        with lock:calls.append(('api',value))
        marker.set('worker-mutated');return value
    def gate():
        with lock:gates.append((marker.get(),threading.get_ident()))
        barrier.wait(3);return True
    chat=lf.FailoverChat([backend('parallel-local',local),backend('parallel-api',api,True,gate)],hedge_seconds=.005,backoff_seconds=.001,total_seconds=1)
    def caller(name):
        marker.set(name)
        try:
            result=chat.text('s','Seoul');answers[name]=(result,marker.get(),lf.current_path(),threading.get_ident())
        except BaseException as e:errors.append(repr(e))
        finally:
            with lock:
                finished.append(name)
                if len(finished)==2:done.set()
    threads=[threading.Thread(target=caller,args=(name,)) for name in ('A','B')]
    try:
        for t in threads:t.start()
        assert done.wait(3)
    finally:
        release.set()
        for t in threads:t.join(3)
    # Workers are daemon threads; join those exact owned workers, not unrelated threads.
    for t in threading.enumerate():
        if t.name=='llm-overflow':t.join(3)
    assert not errors and set(answers)=={'A','B'}
    assert sorted(calls)==[('api','A'),('api','B'),('local','A'),('local','B')]
    for name,(result,context,path,ident) in answers.items():
        assert result==context==name and path['path']=='api'
        assert (name,ident) in gates
    assert len(gates)==2 and all(v==0 for v in lf.snapshot()['inflight'].values())


def test_nonstream_busy_primary_uses_api_once_on_second_caller():
    entered=threading.Event();release=threading.Event();answers=[];paid=[];gates=[];errors=[]
    def local(*a):entered.set();assert release.wait(3);return 'first-local'
    def gate():gates.append(threading.get_ident());return True
    chat=lf.FailoverChat([backend('busy-local',local,cap=1),backend('busy-api',lambda *a:paid.append(1) or 'second-api',True,gate)])
    def first():
        try:answers.append(chat.text('s','first'))
        except BaseException as e:errors.append(repr(e))
    t=threading.Thread(target=first);t.start();assert entered.wait(3)
    try:
        assert chat.text('s','second')=='second-api'
        assert ('busy-local','busy') in lf.current_path()['reasons']
        assert paid==[1] and gates==[threading.get_ident()]
    finally:release.set();t.join(3)
    assert answers==['first-local'] and errors==[]
    assert all(v==0 for v in lf.snapshot()['inflight'].values())


def test_api_start_failure_returns_permit_and_ends_local_retry(monkeypatch):
    release=threading.Event();finished=threading.Event();calls=[];count=[];real=threading.Thread
    class Rejected(real):
        def start(self):
            count.append(1)
            if len(count)==2:raise RuntimeError('controlled scheduler rejection')
            return super().start()
    monkeypatch.setattr(lf.threading,'Thread',Rejected)
    def local(*a):
        calls.append(1)
        try:assert release.wait(3);raise OllamaError('HTTP 503')
        finally:finished.set()
    api=backend('rejected-api',lambda *a:pytest.fail('API dispatched'),True,lambda:True)
    api.breaker.state='half_open'
    chat=lf.FailoverChat([backend('rejected-local',local),api],hedge_seconds=.005,backoff_seconds=.001,total_seconds=1)
    try:
        with pytest.raises(RuntimeError,match='scheduler rejection'):chat.text('s','Seoul')
    finally:
        release.set();assert finished.wait(3)
        for t in threading.enumerate():
            if t.name=='llm-overflow':t.join(3)
    assert calls==[1] and not api.breaker._probing
    assert all(v==0 for v in lf.snapshot()['inflight'].values())
