"""휴리스틱 수정 뒤 실제 도보 한 쌍만 네트워크 차단 상태로 재생합니다."""
from pathlib import Path
import json,hashlib,socket,sys,time
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'final_project_cs'))
attempts=[]
def blocked(*args,**kwargs):attempts.append(1);raise RuntimeError('network_disabled')
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
source=W/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/graph_router.py'
before=hashlib.sha256(source.read_bytes()).hexdigest();t=time.monotonic()
router=GraphRouter(W/'datasets/mobility/processed/mobility/road_graph_v2')
path=router.route((126.978,37.5665),(126.98222,37.56948),'foot')['paths'][0]
old=json.loads((P/'diagnosis-v1.json').read_text(encoding='utf-8'))['astar']
out={'path':path,'before_distance_m':old['distance'],'after_distance_m':path['distance'],
     'same_distance':path['distance']==old['distance'],'same_geometry':path['points']==old['points'],
     'elapsed_seconds':time.monotonic()-t,'source_before':before,'source_after':hashlib.sha256(source.read_bytes()).hexdigest(),
     'network_attempts':len(attempts),'developer_api_calls':0,'scope':'실제 도보1OD 재생. 카카오 거리 차이는 해소됐다고 판정하지 않습니다.'}
with (P/'postfix-w01-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in out.items() if k!='path'},ensure_ascii=False,indent=2))
