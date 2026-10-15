"""출발 좌표를 실제 선택 도로 위로 옮기는 개발 계산. 웹 정확도 검증이 아니다."""
from datetime import datetime
from pathlib import Path
import json
import sys

p = Path(__file__).parent
w = p.parents[1]
sys.path.insert(0, str(w/'final_project_cs'))
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter

prior = json.loads((p/'turn-web-public-probe-v1.json').read_text(encoding='utf8'))
original, end = prior['start'], prior['end']
shifted = prior['observations'][1]['repeats'][0]['points']['coordinates'][0]
router = GraphRouter(w/'datasets/mobility/processed/mobility/road_graph_v2')
router.warm(('car',))
rows = []
for repeat in range(3):
    for label, start in [('original', original), ('on_selected_road', shifted)]:
        path = router.route(start, end, profile='car')['paths'][0]
        rows.append(dict(repeat=repeat+1, label=label, requested_start=start, requested_end=end,
                         distance_m=path['distance'], model_seconds=path['time']/1000,
                         snap_m=path['snap_m'], quality=path['quality'], turns=path['turn_restrictions']))
data = dict(created_at=datetime.now().astimezone().isoformat(), queries=2, repetitions=3,
            calls=6, api_calls=0, independent_holdout=False, observations=rows,
            scope='기존 좌표·도로 위로 옮긴 좌표 교대; 정적 모델; 웹 신규 결과 미확보; 합법 진입 미확인')
with (p/'legacy-snap-real-probe-v1.json').open('x', encoding='utf8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(json.dumps(data, ensure_ascii=True))
