from pathlib import Path
import json,sys,time
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'.tmp/mobility_complete_20261008/deps'))
import osmium
d=json.loads((P/'diagnosis-v1.json').read_text(encoding='utf-8'));ids={e['way'] for e in d['nearby_edges']};ways={}
class Handler(osmium.SimpleHandler):
    def way(self,w):ways[w.id]={'tags':dict(w.tags),'nodes':[n.ref for n in w.nodes]}
print('선택 way 원문 읽기 시작',flush=True)
t=time.monotonic();Handler().apply_file(str(W/'datasets/mobility/raw/osm/south-korea-latest.osm.pbf'),filters=[osmium.filter.IdFilter(ids)])
out={'requested':len(ids),'found':len(ways),'elapsed_seconds':time.monotonic()-t,'ways':ways,'api_calls':0}
with (P/'way-tags-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'requested':len(ids),'found':len(ways),'elapsed':out['elapsed_seconds'],'route':{str(x['way']):ways.get(x['way']) for x in d['segments']}},ensure_ascii=False,indent=2))
