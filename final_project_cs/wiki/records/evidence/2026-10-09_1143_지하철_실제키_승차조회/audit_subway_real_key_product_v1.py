from pathlib import Path
from datetime import datetime,timedelta
from copy import deepcopy
import json,sys,logging,hashlib
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.path.insert(0,str(CS))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.subway_identity import boarding_identity
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
logging.getLogger('app.domains.travel_ops.ports.data_sources.base').addHandler(logging.NullHandler());logging.getLogger('app.domains.travel_ops.ports.data_sources.base').propagate=False
work=json.loads((Path(__file__).parent/'subway-real-key-work-v1.json').read_text(encoding='utf8'));ev=ROOT/work['evidence'];rawdir=ROOT/work['raw']
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
key=(dotenv_values(CS/'.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').strip();assert key
rt=build_verifier(data_dir=ROOT/'datasets/mobility/processed',gh_url='',seoul_key='',quiet=True,local_router=False)
entries=[]
for i,legs in enumerate([[{'mode':'subway','line':'05호선','from':'양평','to':'영등포구청'},{'mode':'subway','line':'02호선','from':'영등포구청','to':'당산'}],[{'mode':'subway','line':'05호선','from':'군자','to':'아차산'}]],3):
 # 장소와 접근/퇴장분은 통제 입력. 도착응답·보유 노선·시간표·공식ID는 실제 자료다.
 origin={'lat':37.5245,'lon':126.886};destination={'lat':37.5249,'lon':126.896}
 context={'schema_version':1,'timing_unit':'model_minutes','from_place':origin,'to_place':destination,'basis':input_basis(rt),'party':{},'first_visit':False,'options':{'p':{'option_id':'p','legs':legs,'subway_identity':boarding_identity(rt,legs),'check':{'legs':deepcopy(legs),'walk_place_in':1,'walk_stop_in':1,'walk_stop_out':1,'walk_place_out':1}}}}
 src=SeoulSubwayArrival(service_key=key,timeout=20,cache_ttl_seconds=30); original_get=src._get; captures=[]
 def capture(url,params):
  response=original_get(url,params);captures.append(response);return response
 src._get=capture
 def callback(station,**kw):
  return src.boardable_arrival(station,max_age_seconds=30,max_provider_age_seconds=90,max_provider_clock_ahead_seconds=2,**kw)
 start=datetime.now().astimezone();deadline=start+timedelta(hours=1)
 got=observe(rt,context,'p',now=start,deadline=deadline,origin=origin,destination=destination,subway_arrival=callback)
 finish=datetime.now().astimezone();observation=got.get('observations',[{}])[0]
 evaluated=datetime.fromisoformat(observation['evaluated_at']) if observation.get('evaluated_at') else start
 baseline=observe(rt,context,'p',now=evaluated,deadline=deadline,origin=origin,destination=destination)
 entry={'legs':legs,'context':context,'started_at':start.isoformat(),'finished_at':finish.isoformat(),'baseline_clock':evaluated.isoformat(),'baseline':baseline,'product_result':got,'misses':dict(src.misses),'actual_http_responses':len(captures),'normalized_replay':False,'controlled_access_minutes':2,'controlled_egress_minutes':2}
 if captures:
  response=captures[0];body=response.content;echoed=key.encode() in body;raw=rawdir/f'response-{i}-v1.json';raw.write_bytes(body.replace(key.encode(),b'<redacted>') if echoed else body)
  info=response.json().get('errorMessage',response.json());entry.update(http_status=response.status_code,response_code=info.get('code'),provider_total=info.get('total'),raw_path=raw.relative_to(ROOT).as_posix(),raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),response_key_redacted=echoed)
 entries.append(entry)
result={'created_at':datetime.now().astimezone().isoformat(),'requests':entries,'actual_http_attempts':len(entries),'map_developer_api_calls':0,'actual_boarding_payment_samples':0,'claim':'제품 observe→실제 인증키 boardable_arrival→현재 첫 승차·후속환승 모델 계산. 장소 좌표·접근/퇴장분 통제. 실제 ETA 오차·탑승 검증이나 독립 웹 정확도 아님.'}
save(rawdir/'product-acquisition-v1.json',result);save(ev/'real-key-product-v1.json',result)
print(json.dumps({'requests':[{'legs':x['legs'],'response_code':x.get('response_code'),'status':x['product_result']['status'],'observation_status':x['product_result'].get('observations',[{}])[0].get('status'),'baseline_eta':x['baseline'].get('eta_min'),'current_eta':x['product_result'].get('eta_min'),'leg_results':x['product_result'].get('leg_results')} for x in entries]},ensure_ascii=False))