from pathlib import Path
import json, sys, socket
root=Path(__file__).resolve().parents[2];repo=root/'final_project_cs';sys.path.insert(0,str(repo))
out=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
calls=[]
def deny(*a,**k):calls.append(1);raise RuntimeError('offline scope check')
socket.socket.connect=socket.socket.connect_ex=deny
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from app.domains.travel_ops.instances.mobility.engine.turn_restrictions import tables, permitted
graph=root/'datasets/mobility/processed/mobility/road_graph_v2'
old=json.loads((graph/'_backup/2026-10-11_1515_単一方向ユータン/turn_restrictions_v1.json').read_text(encoding='utf8'))
new=json.loads((graph/'turn_restrictions_v1.json').read_text(encoding='utf8'))
rt=GraphRouter(graph);rt.warm(('car',))
before,after=tables(old,rt),tables(new,rt)
old_ids={r['relation_id'] for r in old['rules']}; extra=[r for r in new['rules'] if r['relation_id'] not in old_ids]
deg,to,arcs,weights=rt._adjacency('car');same=0;changed=0
for r in extra:
    inc=r['incoming'];edge=inc>>1;via=rt.eu[edge] if inc&1 else rt.ev[edge]
    for i in range(deg[via],deg[via+1]):
        outgoing=arcs[i]
        if outgoing==r['outgoing']:
            assert not permitted(after,inc,outgoing);changed+=1
        else:
            assert permitted(before,inc,outgoing)==permitted(after,inc,outgoing)
            same+=1
design=json.loads((root/'datasets/mobility/raw/kakao_golden/fresh_experiment_100_design.json').read_text(encoding='utf8'))
matched=[]
for pid in ('N091','N094'):
    p=next(r for r in design['pairs'] if r['id']==pid); paths=[]
    for mode in (False,True):
        rt.force_dijkstra=mode
        paths.append(rt.route((p['alon'],p['alat']),(p['blon'],p['blat']))['paths'][0])
    assert abs(paths[0]['time']-paths[1]['time'])<=2
    assert abs(paths[0]['distance']-paths[1]['distance'])<=0.1
    matched.append({'id':pid,'astar_ms':paths[0]['time'],'dijkstra_ms':paths[1]['time'],
                    'astar_m':paths[0]['distance'],'dijkstra_m':paths[1]['distance']})
with (out/'scope-validation.json').open('x',encoding='utf8') as f:json.dump({'checked_reverse_pairs':changed,
    'unchanged_other_outgoing_pairs':same,'search_comparison':matched,'network_attempts':len(calls)},f,indent=2)
print(same,changed,len(matched),len(calls))
