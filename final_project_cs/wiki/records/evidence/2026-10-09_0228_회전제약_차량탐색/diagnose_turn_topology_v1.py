from pathlib import Path
from datetime import datetime
import gzip, json, osmium
p = Path(__file__).parent
w = p.parents[1]
g = w/'datasets/mobility/processed/mobility/road_graph_v2'
class Reader(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []
    def way(self, way):
        ids = [n.ref for n in way.nodes]
        if 4604019409 in ids:
            self.rows.append(dict(id=way.id, tags=dict(way.tags), nodes=ids))
r = Reader()
r.apply_file(str(w/'datasets/mobility/raw/osm/south-korea-latest.osm.pbf'))
edges = []
with gzip.open(g/'edges.jsonl.gz', 'rt', encoding='utf8') as f:
    for index, line in enumerate(f):
        row = json.loads(line)
        if row['u'] == 126485 or row['v'] == 126485:
            edges.append(dict(edge=index, record=row))
result = dict(created_at=datetime.now().astimezone().isoformat(), osm_via_node=4604019409,
    graph_node=126485, pbf_incident_ways=r.rows, graph_incident_edges=edges,
    scope='current local PBF and graph records only; present-day physical road not observed')
with (p/'car-turn-topology-v1.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result))
