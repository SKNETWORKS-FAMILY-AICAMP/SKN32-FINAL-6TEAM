from pathlib import Path
from datetime import datetime,timedelta,UTC
from copy import deepcopy
import importlib.util,json,hashlib,sys,httpx
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.path.insert(0,str(CS))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.subway_departure import boarding_services
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival,select_boardable_arrival
work=json.loads((Path(__file__).parent/'subway-real-key-work-v1.json').read_text(encoding='utf8'));ev=ROOT/work['evidence'];rawdir=ROOT/work['raw']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
oldproof=CS/'wiki/records/evidence/2026-10-09_1125_공식병기역명_종착경로복구';pre=[]
for f,k in [('verification-proof-v1.json','source_test_data_hashes'),('publication-validation-v1.json','artifact_hashes')]:
 hashes=json.loads((oldproof/f).read_text(encoding='utf8'))[k];bad=[p for p,h in hashes.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h];assert not bad,bad;pre.append({'scope':k,'checked':len(hashes),'matches':len(hashes),'mismatches':bad})
save(ev/'preflight-v1.json',{'created_at':datetime.now().astimezone().isoformat(),'checks':pre})
a=json.loads((ev/'real-key-acquisition-v1.json').read_text(encoding='utf8'));p=json.loads((ev/'real-key-product-v1.json').read_text(encoding='utf8'))
requests=a['requests']+p['requests'];assert len(requests)==4
rows=0
for entry in requests:
 body=ROOT/entry['raw_path'];assert sha(body)==entry['raw_sha256'];assert entry['http_status']==200 and entry['response_code']=='INFO-000';actual=json.loads(body.read_text(encoding='utf8'));n=len(actual['realtimeArrivalList']);assert n==entry['provider_total'];rows+=n
rt=build_verifier(data_dir=ROOT/'datasets/mobility/processed',gh_url='',seoul_key='',quiet=True,local_router=False)
replays=[]
for entry in p['requests']:
 context=entry['context'];origin=context['from_place'];destination=context['to_place'];start=datetime.fromisoformat(entry['started_at']);saved=entry['product_result'];observation=saved['observations'][0];runs=[]
 def callback(station,**kw):
  assert station==observation.get('query_station',context['options']['p']['subway_identity']['query_station'])
  return deepcopy(observation)
 for _ in range(2):
  got=observe(rt,context,'p',now=start,deadline=start+timedelta(hours=1),origin=origin,destination=destination,subway_arrival=callback)
  assert got==saved;assert got['status']=='realtime';assert got['leg_results'][0]['ride_src']=='subway_path_model';runs.append(got)
 replays.append({'legs':entry['legs'],'same_saved_response_replays':len(runs),'matches':len(runs),'baseline_eta':entry['baseline'].get('eta_min'),'current_eta':saved.get('eta_min'),'current_first_departure_min':saved['leg_results'][0]['depart_min'],'provider_train_number':observation['train_number'],'provider_terminal_station_id':observation['terminal_station_id'],'future_legs_model_only':len(entry['legs'])-1})
oldpath=CS/'app/domains/travel_ops/instances/mobility/engine/_backup/2026-10-09_1125_공식병기역명_종착경로복구/subway_identity.py';spec=importlib.util.spec_from_file_location('pre_primary_identity',oldpath);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
identity=ROOT/'datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json';old=module.SubwayStationIndex(json.loads(identity.read_text(encoding='utf8')),content_sha256=sha(identity));current=rt.subway_stations;coverage=[]
for entry in a['requests']:
 leg=entry['leg'];rt.subway_stations=old;before_binding,before=boarding_services(rt,leg);rt.subway_stations=current;binding,after=boarding_services(rt,leg);snapshot=json.loads((rawdir/f"normalized-{len(coverage)+1}-v1.json").read_text(encoding='utf8'));after_keys={(s['path_station_ids'][1],s['path_station_ids'][-1],s['train_status']) for s in after};before_keys={(s['path_station_ids'][1],s['path_station_ids'][-1],s['train_status']) for s in before}
 matched=[t for t in snapshot['trains'] if t['line_id']==binding['line_id'] and t['station_id']==binding['station_id'] and (t['next_station_id'],t['terminal_station_id'],t['train_status']) in after_keys];old_matched=[t for t in matched if (t['next_station_id'],t['terminal_station_id'],t['train_status']) in before_keys]
 coverage.append({'leg':leg,'old_binding_status':before_binding['status'],'old_service_count':len(before),'new_service_count':len(after),'same_real_snapshot_direction_rows':len(matched),'old_covered_rows':len(old_matched),'new_covered_rows':len(matched),'matched_actual_terminals':sorted({t['terminal_station_id'] for t in matched}),'claim':'동일 실응답의 식별 연결 전후 대조. 독립 도착 정확도 표본 아님.'})
result={'created_at':datetime.now().astimezone().isoformat(),'real_http_normal_responses':len(requests),'real_http_attempts':len(requests),'raw_hash_matches':len(requests),'raw_rows':rows,'raw_rows_equal_provider_total':len(requests),'product_routes':len(replays),'product_replay_matches':sum(x['matches'] for x in replays),'product_replay_attempts':sum(x['same_saved_response_replays'] for x in replays),'product_replays':replays,'identity_coverage_same_snapshots':coverage,'controlled_access_note':'접근0/2/6분·퇴장2분·장소 좌표는 통제 입력. 2개 역의 4스냅샷이며 실제 탑승/ETA오차/독립 웹 경로 표본0.','source_test_data_hashes':json.loads((oldproof/'verification-proof-v1.json').read_text(encoding='utf8'))['source_test_data_hashes'],'full_feature_completion':False}
save(ev/'real-key-verification-v1.json',result)
print(json.dumps({k:result[k] for k in ('real_http_normal_responses','real_http_attempts','raw_hash_matches','raw_rows','product_routes','product_replay_matches','product_replay_attempts','identity_coverage_same_snapshots')},ensure_ascii=False))