from pathlib import Path
from datetime import datetime
import hashlib, json, math, socket, sys

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
sys.path.insert(0, str(CS))
sys.stdout.reconfigure(encoding='utf8')
TAG = '2026-10-10_1521_동일요청좌표_도보웹대조'
EV = CS / 'wiki/records/evidence' / TAG
RAW = ROOT / 'datasets/mobility/raw' / TAG
EV.mkdir(exist_ok=False)
RAW.mkdir(exist_ok=False)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, d):
    with p.open('x', encoding='utf8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2, default=str)

old = json.loads((CS/'wiki/records/evidence/2026-10-10_0913_도로자료_원자교체_감지/final-integrity-v1.json').read_text(encoding='utf8'))
baseline = dict(old['source_test_data_hashes'], **old['artifact_hashes'])
changed = [k for k, v in baseline.items() if sha(ROOT/k) != v]
assert not changed, changed
save(EV/'baseline-v1.json', {'checked': len(baseline), 'changed': changed, 'hashes': baseline})

facts = {
 'sample_id': 'walk-web-20261010-01', 'captured_at': '2026-10-10T15:16:01.796+09:00',
 'origin': {'key':'walk10-origin', 'name':'시청쪽 기준점', 'lat':37.5665, 'lon':126.9780},
 'destination': {'key':'walk10-dest', 'name':'청계천쪽 기준점', 'lat':37.56948, 'lon':126.98222},
 'requested_url':'https://map.kakao.com/link/by/walk/출발,37.5665,126.9780/도착,37.56948,126.98222',
 'redirect_url':'https://map.kakao.com/?map_type=TYPE_MAP&target=walk&rt=495141%2C1129713%2C496073%2C1130539&rt1=%EC%B6%9C%EB%B0%9C&rt2=%EB%8F%84%EC%B0%A9&rtIds=%2C&rtTypes=%2C',
 'routes':[{'label':'큰길우선', 'm':711, 'min':12, 'default':True}, {'label':'최단거리', 'm':672, 'min':11}, {'label':'편안한길','m':711,'min':12}],
 'reference_selected_before_product':'최단거리',
 'display_assumption':'성인 도보 시속 4km',
 'alignment':{'requested_coordinates':True, 'actual_snap_and_entrance':False, 'same_geometry':False, 'departure_time_selector':False, 'physical_measurement':False},
 'link_contract_source':'https://apis.map.kakao.com/web/guide/',
 'data_scope':'공개 화면의 수치 사실만 보존; 사용자 위치 아님; 개발 비교이며 독립 정확도 검증 아님',
 'excluded':[{'provider':'Google Maps','reason':'요청 좌표 도보 서비스 범위 밖'}, {'provider':'Naver Maps','captured_at':'2026-10-10T15:13:35.677+09:00','reference_names':['서울특별시청','청계광장'],'recommended_m':407,'recommended_min':5,'reason':'POI 경로로 전환되어 동일 요청 좌표/출입점 정렬 미확인'}]
}
save(RAW/'web-facts-v1.json', facts)
save(RAW/'arex-assessment-v1.json', {
 'source':'https://www.airportrailroad.com/train/normal/live', 'captured_at':'2026-10-10T15:09:12.678+09:00',
 'station_selected':'공덕', 'station_value':'020', 'visible_rows':10,
 'ui_fields':['formType','waitingTime','planDptrTime','startStnNm','waitingStn'],
 'refresh_interval_ms':5000,
 'example':{'direction':'서울역방면','waitingTime_display':'0분','planDptrTime_display':'15:09 출발','startStnNm_display':'검암','waitingStn_display':'1개 역 전'},
 'dom_audit':{'rows_checked':10,'train_id_rendered':False,'prediction_generation_time_rendered':False,'unrendered_backend_fields_inspected':False},
 'source_analysis':'fnRealTimeStation(start)는 await 응답 뒤 현재 선택 역/요청 세대 확인 없이 서울역방면·공항방면 목록을 갱신한다. 응답 역전 시 다른 역 목록이 남을 가능성이 있다. 이번 회차에서 응답 역전 횟수를 계측한 것은 아니다.',
 'semantic_limits':['0분 표시를 역 도착 증거로 해석할 수 없음','planDptrTime의 기준 역 의미 미확인','열차 식별자·예측 생성시각은 렌더링/공개 inline 코드 범위에서 확보하지 못함; 원 응답에 없다고 단정하지 않음'],
 'integration_decision':'실시간 대체 소스로 아직 연결하지 않음; 동시 열차 일치 대조 0쌍',
 'limited_api_calls':0, 'quota_usage_before':'미확인','quota_usage_after':'미확인','remaining':'미확인','reset_at':'미확인',
 'official_web_tab_closed':True
})
attempts = []
def denied(*args, **kwargs):
    attempts.append(True)
    raise RuntimeError('오프라인 검증: 외부 연결 금지')
socket.socket.connect = denied
socket.create_connection = denied
from app.domains.travel_ops.instances.mobility.engine import runtime
from scripts.mobility.compare_kakao_golden import _planner_leg, _product_walk
started = datetime.now().astimezone().isoformat()
rt = runtime.build_verifier(quiet=True, local_router=True, seoul_key='', gh_url='', data_dir=str(ROOT/'datasets/mobility/processed/mobility'))
arrive = datetime.fromisoformat('2026-10-10T16:00:00+09:00')
result, why = _planner_leg(rt, ['walk'])(facts['origin'], facts['destination'], arrive)
product = _product_walk(result, why)
a, b = facts['origin'], facts['destination']
lat1, lat2 = map(math.radians, (a['lat'], b['lat']))
delta_lat = lat2-lat1
delta_lon = math.radians(b['lon']-a['lon'])
straight = 6371000*2*math.asin(math.sqrt(math.sin(delta_lat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(delta_lon/2)**2))
assert straight <= 1200
comparison = []
if product['status'] == 'available':
    for reference in facts['routes'][:2]:
        dm = product['m']-reference['m']
        dt = product['min']-reference['min']
        comparison.append({'reference':reference['label'], 'distance_delta_m':dm,'distance_delta_percent':dm/reference['m']*100,'time_delta_min':dt,'distance_within_10_percent':abs(dm)/reference['m']<=.10,'time_within_5_min':abs(dt)<=5})
save(EV/'product-replay-v1.json', {'started_at':started,'finished_at':datetime.now().astimezone().isoformat(),'arrive':arrive.isoformat(),'party':'party_of(None,{}) 기본 성인·초행','modes':['walk'],'straight_m':straight,'walk_policy_straight_m':1200,'product':product,'result':result,'why':why,'comparison':comparison,'blocked_network_attempts':len(attempts),'limited_api_calls':0,'same_geometry_verified':False})
assert not attempts
print(json.dumps({'tag':TAG, 'baseline':len(baseline), 'straight_m':straight,'product':product, 'comparison':comparison,'network_attempts':len(attempts)}, ensure_ascii=False, indent=2))
