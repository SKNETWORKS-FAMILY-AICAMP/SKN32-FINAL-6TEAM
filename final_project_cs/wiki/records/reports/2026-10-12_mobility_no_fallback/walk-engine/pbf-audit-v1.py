"""동일 OSM 원자료의 주변 도보 연결·붙임을 네트워크 없이 확인합니다."""
from pathlib import Path
import hashlib,json,sys,math,time
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'.tmp/mobility_complete_20261008/deps'))
import osmium
d=json.loads((P/'diagnosis-v1.json').read_text(encoding='utf-8'))
pbf=W/'datasets/mobility/raw/osm/south-korea-latest.osm.pbf'
nodes={};ways=[]
class Handler(osmium.SimpleHandler):
    def node(self,n):
        if 37.565<=n.location.lat<=37.571 and 126.976<=n.location.lon<=126.984:
            nodes[n.id]=(n.location.lon,n.location.lat)
    def way(self,w):
        refs=[n.ref for n in w.nodes]
        if any(n in nodes for n in refs):
            tags={t.k:t.v for t in w.tags}
            if 'highway' in tags:
                ways.append({'id':w.id,'tags':tags,'nodes':refs,'coordinates':[nodes.get(n) for n in refs]})
t=time.monotonic();Handler().apply_file(str(pbf),locations=False)
h=hashlib.md5()
with pbf.open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
manifest=json.loads((W/'datasets/mobility/processed/mobility/road_graph_v2/MANIFEST.json').read_text(encoding='utf-8'))
tags={x['id']:x['tags'] for x in ways}
def projection(p,coords):
    kx=math.cos(math.radians(p[1]))*111320;ky=110540
    best=(float('inf'),None)
    for a,b in zip(coords,coords[1:]):
        if a is None or b is None:continue
        ax=(a[0]-p[0])*kx;ay=(a[1]-p[1])*ky
        bx=(b[0]-p[0])*kx;by=(b[1]-p[1])*ky
        dx=bx-ax;dy=by-ay;t=max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
        dist=math.hypot(ax+t*dx,ay+t*dy)
        if dist<best[0]:best=(dist,(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
    return best
near={}
for sn in d['snaps']:
    rows=[]
    for e in d['nearby_edges']:
        dist,pt=projection(sn['input'],e['coordinates'])
        rows.append({k:e[k] for k in ['edge_index','way','road_class','foot','fmain']}|{'distance_m':dist,'snap':pt,'tags':tags.get(e['way'],{})})
    near[sn['name']]=sorted(rows,key=lambda x:x['distance_m'])[:25]
graphways={e['way'] for e in d['nearby_edges']}
missing=[w for w in ways if w['id'] not in graphways]
out={'pbf_md5':h.hexdigest(),'graph_source_md5':manifest['src_md5'],'same_snapshot':h.hexdigest()==manifest['src_md5'],
     'nodes_in_bbox':len(nodes),'ways_in_bbox':len(ways),'elapsed_seconds':time.monotonic()-t,
     'ways':ways,'nearest_edges':near,'ways_not_in_graph_bbox':missing,'api_calls':0,'network_calls':0}
with (P/'pbf-audit-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'same_snapshot':out['same_snapshot'],'nodes':len(nodes),'ways':len(ways),'missing':len(missing),'elapsed':out['elapsed_seconds'],
 'nearest':{k:[{z:r[z] for z in ['way','distance_m','foot','fmain','tags']} for r in v[:10]] for k,v in near.items()}},ensure_ascii=False,indent=2))
