"""백업한 수정 전 코드와 현재 코드의 같은 반례를 수치로 보존합니다."""
from pathlib import Path
import importlib.util,json,sys,hashlib
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'final_project_cs'))
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
backup=json.loads((P/'backup-before-goal-fix-v1.json').read_text(encoding='utf-8'))
before_path=W/backup['backup']/'graph_router.py'
spec=importlib.util.spec_from_file_location('app.domains.travel_ops.instances.mobility.engine.graph_router_before_goal_fix',before_path)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
testpath=W/'final_project_cs/tests/unit/travel/mobility/test_graph_router_goal_heuristic_v1.py'
spec=importlib.util.spec_from_file_location('goal_regression',testpath);test=importlib.util.module_from_spec(spec);spec.loader.exec_module(test)
paths={}
for name,cls,reference in [('before',old.GraphRouter,False),('after',GraphRouter,False),('dijkstra',GraphRouter,True)]:
    router=cls(records=test._records());router.force_dijkstra=reference
    paths[name]=router.route((127.,37.5),(127.002,37.5),'car')['paths'][0]
assert paths['before']['time']>paths['dijkstra']['time']
assert paths['after']['time']==paths['dijkstra']['time']
out={'synthetic_only':True,'actual_trip_measurement':False,'paths':paths,
     'before_seconds':paths['before']['time']/1000,'after_seconds':paths['after']['time']/1000,
     'dijkstra_seconds':paths['dijkstra']['time']/1000,'source_before_sha256':hashlib.sha256(before_path.read_bytes()).hexdigest(),
     'source_after_sha256':hashlib.sha256((W/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/graph_router.py').read_bytes()).hexdigest(),
     'api_calls':0}
with (P/'paired-counterexample-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in out.items() if k!='paths'},ensure_ascii=False,indent=2))
