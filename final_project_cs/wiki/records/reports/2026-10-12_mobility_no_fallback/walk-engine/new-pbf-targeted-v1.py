"""새 공개 OSM에서 기존 주변 way 및 동일 도로명 연결을 표적 대조합니다."""
from pathlib import Path
import json,sys,hashlib,time
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'.tmp/mobility_complete_20261008/deps'))
import osmium
old=json.loads((P/'way-tags-v1.json').read_text(encoding='utf-8'))['ways'];ids=set(map(int,old));new={}
pbf=W/'datasets/mobility/raw/osm_20261012_v1/south-korea-261011.osm.pbf'
class Ways(osmium.SimpleHandler):
    def way(self,w):new[w.id]={'tags':dict(w.tags),'nodes':[n.ref for n in w.nodes]}
t=time.monotonic();Ways().apply_file(str(pbf),filters=[osmium.filter.IdFilter(ids)])
named={}
class Named(osmium.SimpleHandler):
    def way(self,w):named[w.id]={'tags':dict(w.tags),'nodes':[n.ref for n in w.nodes]}
Named().apply_file(str(pbf),filters=[osmium.filter.TagFilter(('name','을지로1길'),('name','무교로'),('name','청계천로'))])
nodeids={n for w in new.values() for n in w['nodes']};coords={}
class Nodes(osmium.SimpleHandler):
    def node(self,n):coords[n.id]=(n.location.lon,n.location.lat)
Nodes().apply_file(str(pbf),filters=[osmium.filter.IdFilter(nodeids)])
a=json.loads((P/'pbf-audit-v1.json').read_text(encoding='utf-8'))
oldcoords={n:pt for w in a['ways'] for n,pt in zip(w['nodes'],w['coordinates']) if pt}
changed=[{'id':wid,'old':old[str(wid)],'new':new.get(wid)} for wid in ids if old[str(wid)]!=new.get(wid)]
coordchanges=[{'node':n,'old':pt,'new':coords.get(n)} for n,pt in oldcoords.items() if n in nodeids and coords.get(n)!=tuple(pt)]
h=hashlib.md5()
with pbf.open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
out={'new_pbf':str(pbf.relative_to(W)),'new_md5':h.hexdigest(),'old_way_count':len(ids),'new_matched_way_count':len(new),
     'changed_ways':changed,'changed_node_coordinates':coordchanges,'same_name_ways':named,'new_node_coordinates':coords,
     'elapsed_seconds':time.monotonic()-t,'api_calls':0,'scope':'기존 주변 way와 같은 도로명의 표적 대조입니다. 새 무명 도로 전체를 조사한 결과가 아닙니다.'}
with (P/'new-pbf-targeted-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'matched':f'{len(new)}/{len(ids)}','changed_way_count':len(changed),'changed_coordinate_count':len(coordchanges),
 'changed_ways':changed,'md5':h.hexdigest(),'elapsed_seconds':out['elapsed_seconds']},ensure_ascii=False,indent=2))
