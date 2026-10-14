"""수정 후 실제 그래프를 하나만 적재해 선택 도로 근거를 재확인한다."""
from pathlib import Path
from datetime import datetime
import json
import sys

p = Path(__file__).parent
w = p.parents[1]
sys.path.insert(0, str(w/'final_project_cs'))
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter

obs = json.loads((p/'car-turn-pinned-v2.json').read_text(encoding='utf8'))['observations'][-1]
router = GraphRouter(w/'datasets/mobility/processed/mobility/road_graph_v2')
router.warm(('car',))
rows = []
for repeat in range(3):
    path = router.route(obs['start'], obs['end'], profile='car')['paths'][0]
    rows.append(dict(distance_m=path['distance'], model_seconds=path['time']/1000,
                     snap_m=path.get('snap_m'), quality=path.get('quality'),
                     turns=path.get('turn_restrictions')))
result = dict(created_at=datetime.now().astimezone().isoformat(),
              start=obs['start'], end=obs['end'], repeats=rows, api_calls=0,
              scope='수정 후 실제 그래프 단독 적재; 동일 개발 좌표쌍 3회; 웹 도로·시각 정렬 안 됨')
with (p/'turn-web-public-probe-v3.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=True))
