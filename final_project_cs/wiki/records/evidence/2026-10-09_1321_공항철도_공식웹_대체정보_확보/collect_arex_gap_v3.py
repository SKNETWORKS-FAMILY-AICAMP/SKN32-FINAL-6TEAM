from pathlib import Path
from datetime import datetime, timedelta
from dotenv import dotenv_values
import hashlib, json, logging, sys

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
sys.path.insert(0, str(CS))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.subway_departure import boarding_services
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.ports.data_sources.subway_boarding import select_boardable_arrival

def save(p, data):
    with p.open('x', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)

now = datetime.now().astimezone()
folder = ROOT / 'datasets/mobility/raw' / (now.strftime('%Y-%m-%d_%H%M') + '_공항철도_공식웹_대체조사_retry_v3')
folder.mkdir(exist_ok=False)
logging.getLogger('app.domains.travel_ops.ports.data_sources.base').addHandler(logging.NullHandler())
logging.getLogger('app.domains.travel_ops.ports.data_sources.base').propagate = False
key = (dotenv_values(CS / '.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').strip()
assert key
rt = build_verifier(data_dir=ROOT / 'datasets/mobility/processed', gh_url='', seoul_key='', quiet=True, local_router=False)
identity, services = boarding_services(rt, {'mode':'subway','line':'공항철도','from':'공덕','to':'홍대입구'})
src = SeoulSubwayArrival(service_key=key, timeout=20)
responses = []
original = src._get
def capture(url, params):
    response = original(url, params)
    responses.append(response)
    return response
src._get = capture
started = datetime.now().astimezone()
snapshot = src.arrivals('공덕', line='공항철도')
finished = datetime.now().astimezone()
if len(responses) != 1 or snapshot is None:
    save(folder / 'failure-v1.json', {'finished_at':finished.isoformat(), 'http_responses':len(responses), 'misses':dict(src.misses), 'normalized_snapshot':snapshot})
    print(json.dumps({'http_responses':len(responses), 'misses':dict(src.misses)}, ensure_ascii=False))
    raise SystemExit(1)
body = responses[0].content
assert key.encode() not in body
with (folder / 'response-v1.json').open('xb') as f:
    f.write(body)
selection = select_boardable_arrival(snapshot, line_id=identity['line_id'], station_id=identity['station_id'],
    target_station_id=identity['target_station_id'], allowed_services=services, now=finished,
    ready_at=finished + timedelta(minutes=2), max_age_seconds=30, max_provider_age_seconds=90,
    max_provider_clock_ahead_seconds=2)
airport_rows = [r for r in snapshot['trains'] if r['line_id'] == identity['line_id']]
result = {'created_at':finished.isoformat(),'started_at':started.isoformat(), 'finished_at':finished.isoformat(),
    'actual_http_requests':1,'http_status':responses[0].status_code,'sha256':hashlib.sha256(body).hexdigest(),
    'snapshot':snapshot,'airport_rows':airport_rows,'identity':identity,'services':services,'selection':selection,
    'controlled_access_minutes':2,'map_developer_api_calls':0,'actual_eta_error_samples':0,
    'actual_boardings':0,'product_http_checked':False,'source':'서울특별시 OA-12764',
    'claim':'실제 무료 도착 소스1조회와 현재 제품 선택기를 대조. 접근2분은 통제; 웹과 동일 열차 대조나 실제 탑승 아님.'}
save(folder / 'acquisition-v1.json', result)
save(Path(__file__).parent / 'arex-gap-state-v1.json', {'raw':str(folder.relative_to(ROOT)), 'created_at':finished.isoformat()})
print(json.dumps({'raw':str(folder.relative_to(ROOT)),'started_at':started.isoformat(),'finished_at':finished.isoformat(),
    'http_requests':1,'rows':len(snapshot['trains']),'airport_rows':len(airport_rows),'selection':selection},ensure_ascii=False))
