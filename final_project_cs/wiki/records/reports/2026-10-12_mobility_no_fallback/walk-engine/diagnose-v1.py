"""보유 OSM 그래프의 실제 도보 형상·구간·붙임을 진단합니다. 제품은 변경하지 않습니다."""
from pathlib import Path
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import socket
import sys
import time
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
CS=W/'final_project_cs';sys.path.insert(0,str(CS))
network=[]
def blocked(*a,**kw):
    network.append(True)
    raise RuntimeError('network_disabled')
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from app.domains.travel_ops.instances.mobility.engine.car import hav
G=W/'datasets/mobility/processed/mobility/road_graph_v2'
router=GraphRouter(G)
s=(126.978,37.5665);e=(126.98222,37.56948)
source=CS/'app/domains/travel_ops/instances/mobility/engine/graph_router.py'
before=hashlib.sha256(source.read_bytes()).hexdigest()
started=time.monotonic();captured=[]
original=router._response
def record(parts,profile,a,b):
    captured.append([(ed,pts) for ed,pts in parts])
    return original(parts,profile,a,b)
router._response=record
astar=router.route(s,e,'foot')['paths'][0]
router.force_dijkstra=True
dijkstra=router.route(s,e,'foot')['paths'][0]
snaps=[]
for name,pt in [('origin',s),('destination',e)]:
    sn=router._snap_many('foot',*pt)[0]
    snaps.append({'name':name,'input':pt,'edge_index':sn.e,'way':int(router.eway[sn.e]),'snap':sn.pt,
                  'access_m':sn.dist,'offset_on_edge_m':sn.d_u,'geometry_m':router._geom(sn.e)[1][-1],
                  'road_class':router.hw_name[router.ehw[sn.e]],'allowed':router._allowed('foot',sn.e)})
segments=[]
for i,(ed,pts) in enumerate(captured[0]):
    length=sum(hav(a,b) for a,b in zip(pts,pts[1:]))
    segments.append({'sequence':i,'edge_index':ed,'way':int(router.eway[ed]),'road_class':router.hw_name[router.ehw[ed]],
                     'stored_edge_length_m':float(router.elen[ed]),'used_length_m':length,'coordinates':pts,
                     'steps':bool(router.eflag[ed]&64)})
targetways={x['way'] for x in segments}
rawedges=[]
with gzip.open(G/'edges.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        r=json.loads(line)
        if r['way'] in targetways:rawedges.append(r)
near=[]
for ed in range(len(router.eu)):
    if router.bb[2][ed]>=37.5655 and router.bb[0][ed]<=37.5705 and router.bb[3][ed]>=126.9765 and router.bb[1][ed]<=126.9832:
        near.append({'edge_index':ed,'way':int(router.eway[ed]),'road_class':router.hw_name[router.ehw[ed]],
                     'foot':router._allowed('foot',ed)[0],'fmain':router._snappable('foot',ed),'length_m':float(router.elen[ed]),
                     'coordinates':router._geom(ed)[0]})
targetways.update(x['way'] for x in near)
tags={};pbf=W/'datasets/mobility/raw/osm/south-korea-latest.osm.pbf'
pbf_status={'exists':pbf.exists(),'osmium_available':importlib.util.find_spec('osmium') is not None}
if pbf_status['exists'] and pbf_status['osmium_available']:
    import osmium
    class Handler(osmium.SimpleHandler):
        def way(self,w):
            if w.id in targetways:tags[str(w.id)]={t.k:t.v for t in w.tags}
    Handler().apply_file(str(pbf),locations=False)
    pbf_status.update(bytes=pbf.stat().st_size,modified_ns=pbf.stat().st_mtime_ns,matched_ways=len(tags))
network_m=sum(x['used_length_m'] for x in segments)
body={'started_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),'input':{'s_lnglat':s,'e_lnglat':e},
      'graph_info':router.info(),'load_seconds':router.load_seconds,'elapsed_seconds':round(time.monotonic()-started,3),
      'astar':astar,'dijkstra':dijkstra,'same_astar_dijkstra_distance':astar['distance']==dijkstra['distance'],
      'snaps':snaps,'network_geometry_m':network_m,'straight_access_m':sum(x['access_m'] for x in snaps),
      'segments':segments,'nearby_edges':near,'raw_route_way_edges':rawedges,'osm_way_tags':tags,'pbf_status':pbf_status,
      'source_sha256_before':before,'source_sha256_after':hashlib.sha256(source.read_bytes()).hexdigest(),
      'graph_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [G/'MANIFEST.json',G/'nodes.jsonl.gz',G/'edges.jsonl.gz']},
      'developer_api_calls':0,'network_attempts':len(network),'private_data_access':0,
      'scope':'같은요청좌표1OD,실제GraphRouter foot만 재생. 제품보정·폴백·허용오차변경없음. OSM태그는보유PBF에서읽었으며snapshot동일성별도확인.'}
with (P/'diagnosis-v1.json').open('x',encoding='utf-8') as f:json.dump(body,f,ensure_ascii=False,indent=2)
print(json.dumps({'distance':astar['distance'],'network_geometry_m':network_m,'access_m':body['straight_access_m'],
                  'same_dijkstra':body['same_astar_dijkstra_distance'],'snaps':snaps,
                  'segments':[{'seq':x['sequence'],'way':x['way'],'m':round(x['used_length_m'],2),'class':x['road_class'],'name':tags.get(str(x['way']),{}).get('name')} for x in segments],
                  'nearby_edges':len(near),'pbf_status':pbf_status,'api':0,'network':len(network)},ensure_ascii=False,indent=2))
