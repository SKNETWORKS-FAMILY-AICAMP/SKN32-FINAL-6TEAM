"""v10 정적 관찰 두 건을 DB·외부 API 없이 실제 함수와 실제 리듀서로 좁게 확인한다."""
from pathlib import Path
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import json
import sys
import pytest

root=Path(__file__).resolve().parents[4]
candidate=root/"legacy/deployment_candidates/2026-10-12_001736_plugin_v9"
sys.path.insert(0,str(candidate))
sys.stdout.reconfigure(encoding="utf-8")
from app.application import classification
from app.core.case_lifecycle.case import CaseProjection, apply_event
from app.core.contracts import CaseStatus, StateConflict
from app.core import transition, settings
from app.infrastructure.db import repository
from app.domains.travel_ops.components.conversation import trip_messages, case_dispatch, chat_log
from app.domains.travel_ops.components.conversation.decision_unit import Decision

class ProcessStopped(BaseException):
    pass
class Conn:
    def __init__(self):
        self.committed=None
        self.stop_on_commit=False
        self.rows=[]
        self.commits=0
    def transaction(self): return nullcontext()
    def cursor(self): return nullcontext(self)
    def execute(self,*a,**kw): pass
    def fetchall(self): return self.rows
    def fetchone(self): return None
    def commit(self):
        self.commits+=1
        if self.stop_on_commit:
            self.committed=deepcopy(case)
            raise ProcessStopped("injected process stop immediately after CLASSIFIED commit")

trip_id=uuid4(); case_id=uuid4(); customer_id=uuid4()
case=dict(case_id=case_id,tenant_id="synthetic-travel",customer_id=customer_id,
          subject="경복궁 주소 알려줘",status=CaseStatus.CLASSIFYING,version=1,
          intent=None,issue_code=None,sentiment=None,owner_team_id=None,
          state_json={"trip_message":{"trip_id":str(trip_id),"request_id":"fact-crash"}})
events=[]
def actual_reducer(connection,*,expected_version,event_type,payload,**kw):
    assert case["version"]==expected_version
    keys=("status","version","state_json","intent","issue_code","sentiment","owner_team_id")
    case.update(asdict(apply_event(CaseProjection(**{k:case[k] for k in keys}),event_type,payload)))
    events.append(event_type.value)
    return deepcopy(case)
now=datetime(2030,1,1,tzinfo=timezone.utc)
item=SimpleNamespace(item_id=uuid4(),kind="activity",title="경복궁",place={"name":"경복궁"},starts_at=now,ends_at=None,detail={})
trip={"trip_id":trip_id,"customer_id":customer_id,"version":1}
store=SimpleNamespace(latest=lambda *a:(trip,[item]))
with pytest.MonkeyPatch.context() as mp:
    mp.setattr(classification,"transition_case",actual_reducer)
    mp.setattr(transition,"transition_case",actual_reducer)
    mp.setattr(repository,"get_case",lambda *a,**kw:deepcopy(case))
    mp.setattr(settings,"get_guardrails",lambda:SimpleNamespace(get=lambda key:1800))
    mp.setattr(chat_log,"recent",lambda *a,**kw:[])
    conn=Conn(); conn.stop_on_commit=True
    try:
        trip_messages._run_decision(conn,tenant="synthetic-travel",trip_id=trip_id,case_id=case_id,
            message=case["subject"],request_id="fact-crash",at=now,desk=None,store=store,items=[item],
            decision=Decision(action="answer_fact",item=item,change=None,fact="address",minutes=None,question=""),
            failure=None,actor_id="synthetic",policy_search=None,place_source=None,selected=None,controller=None)
        raise AssertionError("injected stop was not reached")
    except ProcessStopped:
        pass
    assert conn.committed and conn.committed["status"]==CaseStatus.ROUTING
    case.clear(); case.update(conn.committed)
    conn.stop_on_commit=False
    observed=[]
    for attempt in range(3):
        try:
            case_dispatch.retry_initial(conn,controller=None,tenant="synthetic-travel",trip=trip,
                case_id=case_id,items=[item],actor_id="synthetic")
            raise AssertionError("same fact request unexpectedly recovered")
        except StateConflict as exc:
            observed.append(str(exc))
    assert all("저장된 실행 계획" in msg for msg in observed)
    a={"reproduced":True,"actual_functions":["_run_decision","classify_case","apply_event","retry_initial"],
       "committed_status":str(case["status"]),"events":events,
       "conversation_dispatch_present":"conversation_dispatch" in case["state_json"],
       "same_request_retries":len(observed),"conflict_messages":observed,
       "db_io":False,"http":False,"limitation":"commit durability is a memory seam, not a DB process-kill test"}

old_id=uuid4()
old_state={"trip_message":{"trip_id":str(trip_id)},"wait_reason":"customer_input",
    "required_input_schema":{"required":["message"],"choices":[{"label":"점심 식당을 바꿔 줘","message":"점심 식당을 바꿔 줘","action":"apply_change"}],
                             "x-conversation":{"request":{"action":"clarify"}}}}
old_case=dict(case_id=old_id,tenant_id="synthetic-travel",customer_id=customer_id,
              status="waiting_input",owner_team_id="dining",state_json=old_state)
resumes=[]
def resume_customer_input(**kw):
    resumes.append(kw)
    return {"status":"synthetic-return"}
with pytest.MonkeyPatch.context() as mp:
    mp.setattr(repository,"get_case",lambda *a,**kw:deepcopy(old_case))
    mp.setattr(case_dispatch,"response",lambda **kw:{"selected_case":str(kw["case_id"])})
    conn=Conn(); conn.rows=[(old_id,False)]
    controller=SimpleNamespace(resume_customer_input=resume_customer_input)
    result=case_dispatch.resume_pending(conn,controller=controller,tenant="synthetic-travel",trip=trip,
        request_id="new-fact-number-reply",message="1번",actor_id="synthetic",case_id=None,token=None,expected_version=None)
    assert len(resumes)==1 and resumes[0]["case_id"]==old_id
    b={"reproduced_old_wait_selection":True,"actual_functions":["_matches_implicit_reply","resume_pending"],
       "message":"1번","selected_old_case":result["selected_case"],"resume_calls":len(resumes),
       "db_io":False,"http":False,"limitation":"most recent fact choices are not consulted by resume_pending; schema permits numeric reply"}
print(json.dumps({"A_fact_crash_retry":a,"B_numeric_reply_selection":b},ensure_ascii=False,indent=2))
