from pathlib import Path
from datetime import datetime,timedelta
import json,hashlib,sys,logging
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.path.insert(0,str(CS))
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
logging.getLogger('app.domains.travel_ops.ports.data_sources.base').addHandler(logging.NullHandler());logging.getLogger('app.domains.travel_ops.ports.data_sources.base').propagate=False
w=json.loads((Path(__file__).parent/'subway-completeness-work-v3.json').read_text(encoding='utf8'));ev=ROOT/w['evidence'];raw=ROOT/w['raw'];key=(dotenv_values(CS/'.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').strip();assert key
rt=build_verifier(data_dir=ROOT/'datasets/mobility/processed',gh_url='',seoul_key='',quiet=True,local_router=False)
context=json.loads((CS/'wiki/records/evidence/2026-10-09_1143_지하철_실제키_승차조회/real-key-product-v1.json').read_text(encoding='utf8'))['requests'][0]['context']
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
entries=[]
for i,station in enumerate(('서울','양평'),5):
 src=SeoulSubwayArrival(service_key=key,timeout=20,cache_ttl_seconds=30);original_get=src._get;captures=[];original_arrivals=src.arrivals;snapshots=[]
 def capture(url,params):
  response=original_get(url,params);captures.append(response);return response
 def record_arrivals(*args,**kw):
  snapshot=original_arrivals(*args,**kw);snapshots.append(snapshot);return snapshot
 src._get=capture;src.arrivals=record_arrivals;start=datetime.now().astimezone();result=None
 if station=='서울':snapshot=src.arrivals(station)
 else:
  def callback(name,**kw):return src.boardable_arrival(name,max_age_seconds=30,max_provider_age_seconds=90,max_provider_clock_ahead_seconds=2,**kw)
  result=observe(rt,context,'p',now=start,deadline=start+timedelta(hours=1),origin=context['from_place'],destination=context['to_place'],subway_arrival=callback);snapshot=snapshots[0]
 finish=datetime.now().astimezone();entry={'station':station,'started_at':start.isoformat(),'finished_at':finish.isoformat(),'actual_http_responses':len(captures),'page_end':1000,'normalized_replay':False,'snapshot':snapshot,'product_result':result,'controlled_access_egress_minutes':2 if result else None,'misses':dict(src.misses)}
 if captures:
  response=captures[0];body=response.content;echoed=key.encode() in body;p=raw/f'response-{i}-v1.json';p.write_bytes(body.replace(key.encode(),b'<redacted>') if echoed else body);data=response.json();info=data.get('errorMessage',data);entry.update(http_status=response.status_code,code=info.get('code'),provider_total=info.get('total'),raw_rows=len(data.get('realtimeArrivalList',[])),raw_path=p.relative_to(ROOT).as_posix(),raw_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),key_redacted=echoed)
 entries.append(entry)
result={'created_at':datetime.now().astimezone().isoformat(),'requests':entries,'actual_http_attempts':2,'map_developer_api_calls':0,'actual_eta_error_boarding_payment':0,'claim':'수정 제품 소스1000행 실제 조회2회, 양평출발관측→실제선택과후속환승모델. 접근/퇴장/장소좌표는통제. 새ETA오차/실탑승/독립웹경로아님.'}
save(raw/'after-acquisition-v1.json',result);save(ev/'after-live-v1.json',result)
print(json.dumps({'requests':[{'station':e['station'],'code':e.get('code'),'actual_http_responses':e['actual_http_responses'],'provider_total':e.get('provider_total'),'raw_rows':e.get('raw_rows'),'normalized_rows':len(e['snapshot']['trains']) if e['snapshot'] else None,'coverage_complete':e['snapshot'].get('coverage_complete') if e['snapshot'] else None,'product_status':e['product_result'].get('status') if e['product_result'] else None,'product_eta':e['product_result'].get('eta_min') if e['product_result'] else None} for e in entries]},ensure_ascii=False))