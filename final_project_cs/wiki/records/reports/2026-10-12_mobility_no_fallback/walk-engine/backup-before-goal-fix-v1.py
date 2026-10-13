from pathlib import Path
import datetime,hashlib,json,shutil
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
source=W/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/graph_router.py'
test=W/'final_project_cs/tests/unit/travel/mobility/test_graph_router_goal_heuristic_v1.py'
stamp=datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
b=P/'_backup'/f'{stamp}_goal_heuristic_fix';b.mkdir(parents=True,exist_ok=False)
paths=[source,test,P/'local-topology-v1.py',P/'local-topology-v1.json',P/'new-pbf-targeted-v1.py',P/'new-pbf-targeted-v1.json']
hashes={str(p.relative_to(W)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
for p in paths:shutil.copy2(p,b/p.name)
out={'backup':str(b.relative_to(W)),'source_sha256':hashes[str(source.relative_to(W))],'files_before':hashes}
with (P/'backup-before-goal-fix-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
for p in paths[1:]:
    s=p.read_text(encoding='utf-8')
    s=s.replace('複数の降車候補は互いに12m以内とは限らないことの回帰試験。','여러 하차 후보 사이 거리가 12m 이내라는 가정의 회귀 시험입니다.')
    s=s.replace('周辺切出しグラフの診断計算、製品再実行ではない','주변 부분망의 진단 계산이며 제품 재실행이 아닙니다.')
    s=s.replace('既知周辺wayと同道路名の標的照合。新設無名way全域の不在証明ではありません。','기존 주변 way와 같은 도로명의 표적 대조입니다. 새 무명 도로 전체를 조사한 결과가 아닙니다.')
    p.write_text(s,encoding='utf-8')
assert hashlib.sha256(source.read_bytes()).hexdigest()==out['source_sha256']
print(json.dumps(out,ensure_ascii=False,indent=2))
