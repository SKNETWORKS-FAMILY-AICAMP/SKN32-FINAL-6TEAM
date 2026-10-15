from pathlib import Path
from datetime import datetime, timedelta
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import hashlib, json, socket, sys

ROOT=Path(__file__).resolve().parents[2]
CS=ROOT/'final_project_cs'
sys.path.insert(0,str(CS))
sys.stdout.reconfigure(encoding='utf8')
EV=CS/'wiki/records/evidence/2026-10-10_2120_출발안내_탑승환승시각_연결'
RAW=ROOT/'datasets/mobility/raw/2026-10-09_1248_지하철_방면과_인접역ID_대조'
body=json.loads((RAW/'response-1-v1.json').read_text(encoding='utf8'))
acq=json.loads((RAW/'acquisition-v1.json').read_text(encoding='utf8'))
now=datetime.fromisoformat(acq['requests'][0]['started_at'])
fetched=datetime.fromisoformat(acq['requests'][0]['finished_at'])
connections=[]
def denied(*args,**kwargs):
    connections.append(True)
    raise RuntimeError('보유 자료 재생: 네트워크 연결 금지')
socket.socket.connect=denied
socket.create_connection=denied
from app.domains.travel_ops.instances.mobility.engine import runtime
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.subway_identity import boarding_identity
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.components.watch.trip_reminders import build_departure,notice_fields
from app.domains.travel_ops.components.itinerary.itinerary import Item

rt=runtime.build_verifier(quiet=True,local_router=True,seoul_key='',gh_url='',data_dir=str(ROOT/'datasets/mobility/processed'))
class ReplaySource(SeoulSubwayArrival):
    # 원문은 그대로 두고 실제 이전 수신 시각/조회 시각으로 정상화한다. 현재 조회 아님.
    def _fetch_json(self,url,params):
        self._fetch_state.fetched_at=fetched
        self._fetch_state.from_cache=True
        return deepcopy(body)
source=ReplaySource(service_key='offline-replay',now=lambda:fetched)
legs=[{'mode':'subway','line':'05호선','from':'공덕','to':'종로3가'},
      {'mode':'subway','line':'03호선','from':'종로3가','to':'안국'}]
origin={'lat':37.544005,'lon':126.951058}
destination={'lat':37.576562,'lon':126.98547}
context={'schema_version':1,'timing_unit':'model_minutes','from_place':origin,'to_place':destination,
         'basis':input_basis(rt),'party':{},'first_visit':False,'options':{'p':{'option_id':'p','legs':legs,
         'subway_identity':boarding_identity(rt,legs),'check':{'legs':deepcopy(legs),
         'walk_place_in':1,'walk_stop_in':1,'walk_stop_out':1,'walk_place_out':1}}}}
queries=[]
def arrival(station,**kwargs):
    queries.append(station)
    return source.boardable_arrival(station,max_age_seconds=30,max_provider_age_seconds=90,max_provider_clock_ahead_seconds=2,**kwargs)
deadline=now+timedelta(hours=1)
original=deepcopy(context)
got=observe(rt,context,'p',now=now,deadline=deadline,origin=origin,destination=destination,subway_arrival=arrival)
model=observe(rt,context,'p',now=now,deadline=deadline,origin=origin,destination=destination,subway_arrival=lambda *a,**k:{'status':'unavailable','reason':'offline_failure_control'})
move=Item(item_id=uuid4(),seq=1,kind='mobility',title='공덕 → 안국',place_id=None,starts_at=now,ends_at=deadline,
          detail={'route_def':{'planned':'p','options':[{'id':'p','label':'05호선 → 03호선','uses':['05호선','03호선'],'eta_min':30}]}})
next_item=Item(item_id=uuid4(),seq=2,kind='activity',title='안국 방문',place_id=None,starts_at=deadline,ends_at=deadline+timedelta(hours=1),detail={})
events=SimpleNamespace(affecting=lambda targets:{})
status,phrase=build_departure(move,[move,next_item],route_events=events,routes=None,now=now,departure_observer=lambda *a,**k:got)
out={'replay_clock':now.isoformat(),'original_fetched_at':fetched.isoformat(),
     'scope':'보유 서울 도로/시간표와 이전 공개 응답의 고정 구간 개발 재생. 계획기가 고른 새 경로·현재 실시간 조회·실탑승 검증 아님.',
     'input_context':context,'observation':got,'model_control':model,'notice_status':status,
     'notice':notice_fields(phrase) if phrase else None,'queried_stations':queries,
     'blocked_connections':len(connections),'limited_api_calls':0,
     'source_hashes':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (RAW/'response-1-v1.json',RAW/'acquisition-v1.json')}}
with (EV/'stored-seoul-replay-v3.json').open('x',encoding='utf8') as f:
    json.dump(out,f,ensure_ascii=False,indent=2,default=str)
assert context==original and not connections
assert got['status']=='realtime' and status=='ok',got
assert len(got['boarding_steps'])==2 and queries==['공덕']
assert got['boarding_steps'][1]['boarding_basis']=='timetable_model'
assert model['status']=='model_revalidated'
print(json.dumps({'status':status,'source_status':got['status'],'steps':got['boarding_steps'],'notice':out['notice']['text'],'network_connections':len(connections)},ensure_ascii=False,indent=2))
