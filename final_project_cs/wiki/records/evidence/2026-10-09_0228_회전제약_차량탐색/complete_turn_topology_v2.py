from pathlib import Path
from datetime import datetime
import json, gzip
p = Path(__file__).parent
w = p.parents[1]
result = json.loads((p/'car-turn-topology-v1.json').read_text(encoding='utf8'))
result['created_at'] = datetime.now().astimezone().isoformat()
result['correction'] = 'Raw edge u/v use OSM node IDs, not compact router array indices. v1 compared different ID spaces.'
result['graph_incident_edges'] = []
with gzip.open(w/'datasets/mobility/processed/mobility/road_graph_v2/edges.jsonl.gz', 'rt', encoding='utf8') as f:
    for index, line in enumerate(f):
        row = json.loads(line)
        if row['u'] == result['osm_via_node'] or row['v'] == result['osm_via_node']:
            result['graph_incident_edges'].append(dict(edge=index, record=row))
with (p/'car-turn-topology-v2.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=True))
