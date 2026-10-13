from pathlib import Path
from datetime import datetime, timedelta
import hashlib,json,sys,logging
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'; sys.path.insert(0,str(CS))
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.subway_departure import boarding_services
from app.domains.travel_ops.ports.data_sources.subway_boarding import select_boardable_arrival
logging.getLogger('app.domains.travel_ops.ports.data_sources.base').addHandler(logging.NullHandler())
logging.getLogger('app.domains.travel_ops.ports.data_sources.base').propagate=False
now=datetime.now().astimezone(); tag=now.strftime('%Y-%m-%d_%H%M')+'_지하철_실제키_승차조회'
ev=CS/'wiki/records/evidence'/tag; ev.mkdir(parents=True,exist_ok=False)
rawdir=ROOT/'datasets/mobility/raw'/tag; rawdir.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
key=(dotenv_values(CS/'.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').strip()
if not key:raise RuntimeError('metro key not configured')
rt=build_verifier(data_dir=ROOT/'datasets/mobility/processed',gh_url='',seoul_key='',quiet=True,local_router=False)
entries=[]
for i,leg in enumerate([{'mode':'subway','line':'05호선','from':'양평','to':'영등포구청'},{'mode':'subway','line':'05호선','from':'군자','to':'아차산'}],1):
 binding,services=boarding_services(rt,leg)
 src=SeoulSubwayArrival(service_key=key,timeout=20,cache_ttl_seconds=30)
 original_get=src._get; captures=[]
 def capture(url,params):
  response=original_get(url,params); captures.append(response); return response
 src._get=capture
 start=datetime.now().astimezone(); snapshot=src.arrivals(binding['query_station']); finish=datetime.now().astimezone()
 entry={'leg':leg,'query_station':binding['query_station'],'binding':binding,'services_count':len(services),'started_at':start.isoformat(),'finished_at':finish.isoformat(),'real_key_configured':True,'page_start':0,'page_end':20,'normalized_replay':False,'misses':dict(src.misses),'normalized_rows':len(snapshot['trains']) if snapshot else None,'captured_http_responses':len(captures)}
 if captures:
  response=captures[0]; body=response.content
  # 인증키가 응답에 반사되면 원문을 저장하지 않고 가린 사본과 원문 해시를 남긴다.
  echoed=key.encode() in body; output=body.replace(key.encode(),b'<redacted>') if echoed else body
  raw=rawdir/f'response-{i}-v1.json'; raw.write_bytes(output)
  entry.update(http_status=response.status_code,raw_path=raw.relative_to(ROOT).as_posix(),raw_sha256=sha(raw),response_sha256=hashlib.sha256(body).hexdigest(),response_key_redacted=echoed)
  try:
   data=response.json(); info=data.get('errorMessage',data);entry.update(response_code=info.get('code'),provider_total=info.get('total'))
  except (ValueError,AttributeError):entry['response_code']=None
 if snapshot:
  save(rawdir/f'normalized-{i}-v1.json',snapshot)
  choices=[]
  for access in (0,2,6):
   choices.append({'controlled_access_minutes':access,'selection':select_boardable_arrival(snapshot,line_id=binding['line_id'],station_id=binding['station_id'],target_station_id=binding['target_station_id'],allowed_services=[{'train_status':s['train_status'],'path_station_ids':s['path_station_ids']} for s in services],now=finish,ready_at=finish+timedelta(minutes=access),max_age_seconds=30,max_provider_age_seconds=90,max_provider_clock_ahead_seconds=2)})
  entry['controlled_access_selections']=choices
 entries.append(entry)
result={'created_at':datetime.now().astimezone().isoformat(),'tag':tag,'source':'서울특별시 실시간 지하철 도착정보 OA-12764','license':'공공누리 제1유형·출처 서울특별시','official_docs':'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A','key_in_provenance':False,'requests':entries,'actual_http_attempts':len(entries),'map_developer_api_calls':0,'actual_boarding_payment_samples':0,'new_independent_web_route_pairs':0,'claim':'실제 인증키를 사용하는 제품 도착 소스의 실제 HTTP 조회. 접근0/2/6분은 통제 입력이고 실제 ETA 정확도·탑승 검증은 아님.'}
save(rawdir/'acquisition-v1.json',result);save(ev/'real-key-acquisition-v1.json',result)
work={'tag':tag,'evidence':ev.relative_to(ROOT).as_posix(),'raw':rawdir.relative_to(ROOT).as_posix()};save(Path(__file__).parent/'subway-real-key-work-v1.json',work)
print(json.dumps({'tag':tag,'requests':[{k:x.get(k) for k in ('query_station','captured_http_responses','http_status','response_code','provider_total','normalized_rows','misses','controlled_access_selections')} for x in entries]},ensure_ascii=False))