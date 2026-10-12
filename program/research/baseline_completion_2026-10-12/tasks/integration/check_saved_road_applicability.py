"""기존 실제 사건 행을 현재 파서와 조정기에 재생한다. 실제 고객 경로 검증은 아니다."""
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4
import hashlib, json, socket, sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
sys.path.insert(0,str(CS))
import httpx
from app.domains.travel_ops.ports.data_sources.utic import UticIncidents, UticRouteEvents
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange, plan_route_adjustment

source=CS/'var/alert-snapshots/analysis/2026-10-12-seoul28-replay-v1/runs/2026-10-12_032148_8f5b54d1/cases.json'
cases=json.loads(source.read_text(encoding='utf-8'))['cases']
def blocked(*args,**kwargs): raise RuntimeError('이 검사는 외부 연결을 허용하지 않는다')
socket.socket.connect=blocked
results=[]
for case in cases:
    moment=datetime.fromisoformat(case['replay_clock'])
    record=case['record']
    xml=ET.Element('result'); row=ET.SubElement(xml,'record')
    for key,value in record.items(): ET.SubElement(row,key).text=str(value) if value is not None else ''
    body=ET.tostring(xml,encoding='unicode')
    provider=UticIncidents(service_key='offline-unused',now=lambda:moment,
        transport=lambda url,params:httpx.Response(200,text=body,request=httpx.Request('GET',url)))
    target='도로:'+record['roadName']
    events=UticRouteEvents(provider).affecting([target],at=moment)
    route={'from':'시험 출발지','to':'시험 도착지','planned':'road','options':[
        {'id':'road','label':'선언 도로','eta_min':20,'eta_min_if_controlled':60,'walk_m':0,'fare_krw':1500,'uses':[target]},
        {'id':'alternate','label':'별도 시험 대안','eta_min':25,'walk_m':100,'fare_krw':1500,'uses':[]}]}
    item=Item(item_id=uuid4(),seq=1,kind='mobility',title='선언 구간',place_id=None,
        starts_at=moment,ends_at=moment+timedelta(minutes=20),detail={'route_def':route})
    plan=plan_route_adjustment(item=item,following=None,route=route,events=events,now=moment)
    wanted='unresolved' if case['expected_source_level']=='disruption' else 'clear'
    good=isinstance(plan,NoChange) and plan.status==wanted
    if wanted=='unresolved': good=good and plan.detail.get('reason')=='route_applicability_unverified'
    results.append({'incident_id':case['incident_id'],'expected':wanted,'actual':getattr(plan,'status','change'),
                    'passed':good,'actual_customer_trip':False})
output=HERE/'checks/saved-road-applicability-2026-10-12.json'
assert not output.exists()
output.write_text(json.dumps({'input':source.relative_to(ROOT).as_posix(),'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'passed':sum(r['passed'] for r in results),'total':len(results),'cases':results,
    'scope':'실제 사건 행 + 명시적 시험 경로. 영향 미확인20건 보류·주의8건 정상 유지. 방향 정확도 시험은 기존2/20 그대로이며 실제 경로의 영향·무영향 판정 완료 아님.',
    'network':'socket connect blocked; in-memory XML response only'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(r['passed'] for r in results)
print('saved_road_applicability',len(results),'/',len(results))
