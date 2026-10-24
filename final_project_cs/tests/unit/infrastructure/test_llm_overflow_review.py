"""Independent negative probes; no sockets/providers/subprocess model calls."""
import threading,time,contextvars
from types import SimpleNamespace
import pytest
from app.infrastructure import llm_failover as lf
from app.infrastructure.ollama_chat import OllamaError

def backend(name,fn,api=False,budget=None,cap=0):
 chat=SimpleNamespace(base_url='fake://'+name,model='m',text=fn)
 return lf._Backend(name,chat,lf.CircuitBreaker(name,threshold=3,open_seconds=60),is_api=api,budget=budget,max_inflight=cap,timeout=.01)
def drain():
 until=time.monotonic()+2
 while any(lf.snapshot()['inflight'].values()) and time.monotonic()<until:time.sleep(.002)
 assert all(n==0 for n in lf.snapshot()['inflight'].values())

def test_no_paid_call_when_local_completes_during_caller_budget_reservation():
 release=threading.Event();finished=threading.Event();paid=[]
 def local(*a):
  assert release.wait(2);finished.set();return 'valid local'
 def gate():
  release.set();assert finished.wait(1)
  # Wait until result has been enqueued, not just until model function returned.
  until=time.monotonic()+1
  while any(lf.snapshot()['inflight'].values()) and time.monotonic()<until:time.sleep(.002)
  return True
 chat=lf.FailoverChat([backend('reservation-race',local),backend('paid-race',lambda *a:paid.append(1) or 'paid',True,gate)],hedge_seconds=.005)
 try:
  assert chat.text('s','Seoul')=='valid local'
 finally:release.set();drain()
 until=time.monotonic()+.2
 while not paid and time.monotonic()<until:time.sleep(.002)
 assert paid==[], 'API launched despite completed validated local response already queued during budget gate'

def test_budget_gate_exception_stops_local_retry_after_request_has_failed():
 release=threading.Event();ended=threading.Event();calls=[]
 def local(*a):
  calls.append(1);assert release.wait(2)
  if len(calls)>1:ended.set()
  raise OllamaError('HTTP 503')
 def gate():raise RuntimeError('controlled budget provider failure')
 chat=lf.FailoverChat([backend('gate-exception',local),backend('gate-exception-api',lambda *a:'paid',True,gate)],hedge_seconds=.005,backoff_seconds=.005,total_seconds=1)
 try:
  with pytest.raises(RuntimeError,match='budget provider failure'):chat.text('s','Seoul')
 finally:release.set();drain()
 assert calls==[1], 'Local loser retried after caller had already returned budget failure'

def test_copied_context_and_caller_only_budget_with_late_loser_health():
 marker=contextvars.ContextVar('independent_request',default='absent');marker.set('request-A');caller=threading.get_ident()
 release=threading.Event();seen=[];gates=[]
 def local(*a):
  seen.append(('local',marker.get()));marker.set('worker-local');assert release.wait(2);raise OllamaError('HTTP 503')
 def api(*a):seen.append(('api',marker.get()));marker.set('worker-api');return 'api-result'
 def gate():gates.append((threading.get_ident(),marker.get()));return True
 a=backend('context-local',local);b=backend('context-api',api,True,gate)
 chat=lf.FailoverChat([a,b],hedge_seconds=.005,backoff_seconds=.005,total_seconds=1)
 try:
  assert chat.text('s','Seoul')=='api-result';path=lf.current_path();assert marker.get()=='request-A'
 finally:release.set();drain()
 assert gates==[(caller,'request-A')];assert sorted(seen)==[('api','request-A'),('local','request-A')]
 assert a.breaker.snapshot()['failures']==1;assert lf.current_path()==path

def test_denied_budget_waits_local_and_reclaims_inflight():
 release=threading.Event();paid=[]
 def local(*a):assert release.wait(2);return 'local'
 def gate():release.set();return False
 chat=lf.FailoverChat([backend('deny-local',local),backend('deny-api',lambda *a:paid.append(1),True,gate)],hedge_seconds=.005)
 assert chat.text('s','Seoul')=='local';drain();assert paid==[]
 assert ('deny-api','budget_exhausted') in lf.current_path()['reasons']

def test_cap_is_explicit_busy_threshold_with_last_local_recovery_not_hard_cap():
 release=threading.Event();entered=threading.Event();calls=[];answers=[]
 def local(*a):calls.append(1);entered.set();assert release.wait(2);return 'local'
 a=backend('soft-cap-local',local,cap=1);b=backend('soft-cap-api',lambda *a:'paid',True,lambda:False)
 chat=lf.FailoverChat([a,b]);first=threading.Thread(target=lambda:answers.append(chat.text('s','one')));first.start();assert entered.wait(1)
 second=threading.Thread(target=lambda:answers.append(chat.text('s','two')));second.start()
 try:
  until=time.monotonic()+1
  while len(calls)<2 and time.monotonic()<until:time.sleep(.002)
  assert len(calls)==2;assert lf.snapshot()['inflight']['fake://soft-cap-local|m']==2
 finally:release.set();first.join(2);second.join(2);drain()
 assert answers==['local','local']

def test_zero_hedge_defaults_no_worker_no_paid_and_exception_slot_reclaimed():
 caller=threading.get_ident();seen=[];paid=[]
 chat=lf.FailoverChat([backend('zero-local',lambda *a:seen.append(threading.get_ident()) or 'local'),backend('zero-api',lambda *a:paid.append(1),True)])
 assert chat.text('s','Seoul')=='local';assert seen==[caller] and paid==[];drain()
 def fail(*a):raise RuntimeError('controlled transport bug')
 chat=lf.FailoverChat([backend('unexpected',fail)])
 with pytest.raises(RuntimeError,match='transport bug'):chat.text('s','Seoul')
 drain()

def test_hedge_does_not_reach_images_or_both_stream_operations():
 calls=[]
 class Local:
  base_url='fake://stream';model='m'
  def loaded(self,**kw):return True
  def json_stream(self,*a,**kw):calls.append('json_stream');return {'ok':1}
  def structured_stream(self,*a,**kw):calls.append('structured_stream');return {'ok':1}
  def see(self,*a,**kw):calls.append('see');return 'image'
 a=backend('plain-exclusions',lambda *a:None,cap=1);a.chat=Local()
 b=backend('plain-api',lambda *a:pytest.fail('plain call hedged'),True,lambda:pytest.fail('plain call reserved budget'))
 chat=lf.FailoverChat([a,b],hedge_seconds=.001)
 assert chat.json_stream('s','Seoul')=={'ok':1};assert chat.structured_stream('s','Seoul',{})=={'ok':1};assert chat.see('s',b'image')=='image'
 assert calls==['json_stream','structured_stream','see'];drain()
