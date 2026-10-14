from pathlib import Path
from datetime import datetime
import hashlib,importlib.util,json,socket,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.path.insert(0,str(CS));sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'turn-reload-state-20261010-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
from app.domains.travel_ops.instances.mobility.engine import turn_restrictions as current
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
backup=json.loads((EV/'backup-manifest-v1.json').read_text(encoding='utf8'))[0]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(ROOT/backup['backup'])==backup['sha256']
spec=importlib.util.spec_from_file_location(current.__package__+'._reload_before',ROOT/backup['backup'])
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
new_load=current.load
folder=ROOT/'datasets/mobility/processed/mobility/road_graph_v2'
sources={p.relative_to(ROOT).as_posix():sha(p) for p in folder.iterdir() if p.is_file()}
attempts=[]
def denied(*args,**kwargs):
 attempts.append(True);raise RuntimeError('오프라인 재생: 네트워크 연결 금지')
socket.socket.connect=denied;socket.create_connection=denied
router=GraphRouter(folder);router.warm(('car',))
conditions=[{'from':[126.9852,37.5845],'to':[127.0601,37.6076]},
            {'from':[126.9780,37.5665],'to':[126.9895,37.5700]}]
rows=[]
try:
 for i,condition in enumerate(conditions):
  expected=None
  for variant in ('A','B','B','A'):
   current.load=old.load if variant=='A' else new_load
   output=router.route(tuple(condition['from']),tuple(condition['to']),profile='car')
   if expected is None:expected=output
   assert output==expected,(i,variant)
   encoded=json.dumps(output,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
   path=output['paths'][0]
   rows.append({'condition':i+1,'variant':variant,'output_sha256':hashlib.sha256(encoded).hexdigest(),'distance_m':path['distance'],'applied_relations':path['turn_restrictions']['applied_relations']})
   print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
finally:current.load=new_load
assert all(sha(ROOT/p)==h for p,h in sources.items()) and not attempts
with (EV/'real-data-replay-v1.json').open('x',encoding='utf8') as f:json.dump({'created_at':datetime.now().astimezone().isoformat(),'conditions':conditions,'replays':rows,'matched':len(rows),'total':len(rows),'data_hashes':sources,'network_attempts':0,'limited_api_calls':0,'source_bytes_per_vehicle_request':(folder/current.FILE_NAME).stat().st_size,'limits':'保有道路資料の固定開発2組。実車両/新規独立web/HTTP遅延測定ではない。'.replace('保有道路資料の固定開発2組。実車両/新規独立web/HTTP遅延測定ではない。','보유 도로자료의 고정 개발 2쌍. 실제 차량·새 독립 웹·HTTP 지연 측정 아님.')},f,ensure_ascii=False,indent=2)
