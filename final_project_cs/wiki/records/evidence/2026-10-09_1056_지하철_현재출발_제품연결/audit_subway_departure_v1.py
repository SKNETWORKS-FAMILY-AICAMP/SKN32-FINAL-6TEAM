from pathlib import Path
from datetime import datetime,timedelta
import json, sys, time
from copy import deepcopy
root=Path(__file__).resolve().parents[2]; cs=root/'final_project_cs';sys.path.insert(0,str(cs))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.subway_departure import boarding_services
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.ports.data_sources.seoul_subway import select_boardable_arrival
state=json.loads((Path(__file__).parent/'subway-departure-work-v7.json').read_text(encoding='utf8'));ev=cs/'wiki/records/evidence'/state['tag'];start=time.perf_counter()
rt=build_verifier(data_dir=root/'datasets/mobility/processed',gh_url='',seoul_key='',quiet=True,local_router=False)
leg={'mode':'subway','line':'05호선','from':'양평','to':'영등포구청'}
binding,services=boarding_services(rt,leg);assert binding['status']=='matched' and services
now=datetime.fromisoformat('2026-10-09T10:00:00+09:00');origin={'lat':37.5245,'lon':126.886};destination={'lat':37.5249,'lon':126.896}
context={'schema_version':1,'timing_unit':'model_minutes','from_place':origin,'to_place':destination,'basis':input_basis(rt),'party':{},'first_visit':False,'options':{'p':{'option_id':'p','legs':[leg],'subway_identity':binding,'check':{'legs':[deepcopy(leg)],'walk_place_in':4,'walk_stop_in':2,'walk_stop_out':1,'walk_place_out':1}}}}
queries=[]
def source(station,**kw):
    queries.append({'station':station,'service_count':len(kw['allowed_services'])})
    service=next(s for s in kw['allowed_services'] if s['path_station_ids'][-1]==binding['target_station_id'])
    ids=service['path_station_ids']; snapshot={'kind':'subway_arrival','source':'controlled/native-route','confirmed_at':now.isoformat(),'trains':[{'line_id':binding['line_id'],'station_id':ids[0],'next_station_id':ids[1],'terminal_station_id':ids[-1],'train_status':'일반','train_number':'0501','eta_seconds':480,'eta_status':'valid','arrival_code':'99','received_at':now.isoformat()}]}
    return select_boardable_arrival(snapshot,max_age_seconds=30,max_provider_age_seconds=90,max_provider_clock_ahead_seconds=2,**kw)
base=observe(rt,context,'p',now=now,deadline=now+timedelta(hours=1),origin=origin,destination=destination)
runs=[]
for i in range(2):
    got=observe(rt,context,'p',now=now,deadline=now+timedelta(hours=1),origin=origin,destination=destination,subway_arrival=source)
    assert got['status']=='realtime',got
    assert got['leg_results'][0]['depart_min']==608,got
    assert got['leg_results'][0]['ride_src']=='subway_path_model',got
    runs.append(got)
assert runs[0]==runs[1]
result={'created_at':datetime.now().astimezone().isoformat(),'claim':'보유 실제 노선/시간표/공식ID와 통제 도착응답의 제품 연결. 좌표 및 접근/퇴장분은 통제 입력. 새 실시간 표본·실탑승·독립 웹 정확도 아님.','binding':binding,'static_service_count':len(services),'services':services,'baseline':base,'controlled_runs':runs,'query_count':len(queries),'queries':queries,'elapsed_seconds':time.perf_counter()-start,'new_web_samples':0,'map_developer_api_calls':0,'new_live_snapshots':0,'actual_boarding_payment':0}
with (ev/'native-route-controlled-v1.json').open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({'services':len(services),'baseline':base['status'],'baseline_eta':base.get('eta_min'),'current_eta':runs[0]['eta_min'],'runs':len(runs)},ensure_ascii=False))
