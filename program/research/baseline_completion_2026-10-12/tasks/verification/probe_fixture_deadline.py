"""모듈 import 때 고정된 시험 마감의 영향만 교대로 직접 측정한다."""
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
CS=HERE.parents[4]/'final_project_cs'
os.environ.update(ACOP_MOBILITY_DATA_DIR='',ACOP_OLLAMA_BASE_URL='',ACOP_LOCAL_FT_BASE_URL='',
                  ACOP_OPENAI_API_KEY='verification-unused',ACOP_LLM_FAILOVER_ENABLED='false')
def blocked(*args,**kwargs):
    raise RuntimeError('verification probe: network/DB blocked')
original_bind,original_connect=socket.socket.bind,socket.socket.connect
own_ports=set()
def own_bind(sock,address):
    result=original_bind(sock,address)
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1','localhost'):
        own_ports.add(sock.getsockname()[1])
    return result
def own_connect(sock,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1','localhost') and address[1] in own_ports:
        return original_connect(sock,address)
    return blocked()
socket.socket.bind=own_bind
socket.socket.connect=own_connect
import psycopg
psycopg.connect=blocked
sys.path.insert(0,str(CS))
from app.composition import wire_domain_teams
from app.core.service_bindings import standalone_services
from tests.unit.travel import helpers
from tests.unit.travel.activity import test_watch_batch_unit as fixture
previous_path=CS/'_backup/2026-10-12_052358_api_surface_deadline_integration/helpers.py'
spec=importlib.util.spec_from_file_location('verification_old_helpers',previous_path)
previous=importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)

async def measure():
    rows=[]
    original=helpers.NOW
    original_task=fixture.task
    try:
        for attempt in range(3):
            for condition in ('previous_fresh','previous_expired','current_after_old_import'):
                previous.NOW=datetime.now(UTC)-timedelta(seconds=120 if condition!='previous_fresh' else 0)
                helpers.NOW=previous.NOW
                fixture.task=previous.task if condition.startswith('previous_') else helpers.task
                a,b=fixture._place('가나다 전망대',0),fixture._place('마바사 정원',1)
                items=[fixture._item(1,'activity','전망대 관람',10,a),fixture._item(2,'activity','정원 산책',13,b)]
                candidates=[fixture._place('아자 박물관',2),fixture._place('차카 갤러리',3),fixture._place('타파 공원',4)]
                reports={a['place_id']:fixture.ROAD,b['place_id']:fixture.ROAD}
                _,task=fixture._world(items,candidates,reports)
                remaining=(task.deadline_at-datetime.now(UTC)).total_seconds()
                wire_domain_teams()
                with standalone_services():
                    result,_=await fixture._run(items,candidates,reports)
                rows.append({'attempt':attempt+1,'condition':condition,'seconds_to_deadline':remaining,
                             'outcome':result.outcome,'failure_code':result.failure_code,
                             'proposals':len(result.action_proposals),'warnings':result.warnings})
    finally:
        helpers.NOW=original
        fixture.task=original_task
    return rows

rows=asyncio.run(measure())
paths=('tests/unit/travel/helpers.py','app/domains/travel_ops/components/watch/trip_watch_batch.py',
       'app/domains/travel_ops/components/watch/batch_executor.py','app/composition.py')
result={'at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
        'scope':'실제 묶음 계산기·합성 시험 도구. 보존된 수정 전 helper 함수의 import 시각만 현재/120초 전으로 교대하고 현재 helper와 비교. 이 검증 세션은 제품·시험 본문을 수정하지 않음. 외부 통신·DB 차단, 자체 event loop 루프백만 허용.',
        'previous_helper':str(previous_path),'previous_helper_sha256':hashlib.sha256(previous_path.read_bytes()).hexdigest(),
        'rows':rows,'sha256':{p:hashlib.sha256((CS/p).read_bytes()).hexdigest() for p in paths}}
output=HERE/'runs/2026-10-12_final_hash_1/fixture-deadline-comparison.json'
if output.exists():
    raise SystemExit('기존 증거가 있습니다.')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
