"""동일 미완료 사실 요청의 실제 handle fastpath를 세 보존판에서 비교한다. DB I/O 없음."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timezone
import sys,json,pytest
root=Path(__file__).resolve().parents[4]
paths={
 "newbase":"legacy/deployment_baselines/2026-10-12_012805_drift",
 "v9":"legacy/deployment_candidates/2026-10-12_001736_plugin_v9",
 "v10":"legacy/deployment_candidates/2026-10-12_012943_plugin_v10"}
label=sys.argv[1]; sys.path.insert(0,str(root/paths[label]));sys.stdout.reconfigure(encoding="utf-8")
from app.domains.travel_ops.components.conversation import trip_messages
from app.infrastructure.db import repository
from app.core.contracts import StateConflict
trip_id=uuid4();case_id=uuid4();customer_id=uuid4();message="경복궁 주소 알려줘"
trip={"trip_id":trip_id,"customer_id":customer_id,"version":1}
class Conn:
 def cursor(self):return nullcontext(self)
 def execute(self,sql,*a,**kw):self.sql=sql
 def fetchone(self):return (case_id,)
 def commit(self):pass
conn=Conn()
store=SimpleNamespace(latest=lambda *a:(trip,[]))
rows=[]
for status,answer in [("routing",None),("classifying","경복궁 주소 합성 답변")]:
 case=dict(case_id=case_id,customer_id=customer_id,tenant_id="synthetic",subject=message,status=status,version=2,
           state_json={"trip_message":{"trip_id":str(trip_id),"request_id":"fact-request"},**({"answer":answer} if answer else {})})
 with pytest.MonkeyPatch.context() as mp:
  mp.setattr(trip_messages,"TripStore",lambda *a:store)
  mp.setattr(trip_messages,"get_connection",lambda:nullcontext(conn))
  mp.setattr(repository,"get_case",lambda *a,**k:case)
  try:
   result=trip_messages.handle_trip_message(tenant="synthetic",trip_id=trip_id,message=message,request_id="fact-request",
       at=datetime(2030,1,1,tzinfo=timezone.utc),desk=None,classifier=None,chat=None,actor_id="synthetic")
   rows.append({"status":status,"stored_answer":answer is not None,"result":result,"recovery_executed":False})
  except StateConflict as exc:
   rows.append({"status":status,"stored_answer":answer is not None,"exception":"StateConflict","message":str(exc),"recovery_executed":False})
print(json.dumps({"source":label,"source_path":paths[label],"actual_function":"handle_trip_message","db_io":False,"http":False,"rows":rows},ensure_ascii=False,indent=2))
