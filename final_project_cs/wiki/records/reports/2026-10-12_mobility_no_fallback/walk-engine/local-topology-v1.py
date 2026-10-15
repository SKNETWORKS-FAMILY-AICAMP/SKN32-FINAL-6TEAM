"""실제 그래프 주변 533간선의 연결과 골목 경유 비용을 분리합니다. 제품 재생과 구분합니다."""
from pathlib import Path
import json,gzip,heapq,collections
W=Path(__file__).resolve().parents[3];P=Path(__file__).resolve().parent
d=json.loads((P/'diagnosis-v1.json').read_text(encoding='utf-8'))
a=json.loads((P/'pbf-audit-v1.json').read_text(encoding='utf-8'))
expected={x['edge_index']:x for x in d['nearby_edges']};edges={}
with gzip.open(W/'datasets/mobility/processed/mobility/road_graph_v2/edges.jsonl.gz','rt',encoding='utf-8') as f:
    for idx,line in enumerate(f):
        if idx in expected:
            r=json.loads(line)
            assert r['way']==expected[idx]['way'],(idx,r['way'],expected[idx]['way'])
            edges[idx]=r
assert len(edges)==len(expected)
adj=collections.defaultdict(list)
for idx,r in edges.items():
    if not r.get('foot'):continue
    adj[r['u']].append((r['v'],idx));adj[r['v']].append((r['u'],idx))
S,T=d['snaps']; sr,tr=edges[S['edge_index']],edges[T['edge_index']]
starts={sr['u']:sr['len']*S['offset_on_edge_m']/S['geometry_m'],sr['v']:sr['len']*(S['geometry_m']-S['offset_on_edge_m'])/S['geometry_m']}
goals={tr['u']:tr['len']*T['offset_on_edge_m']/T['geometry_m'],tr['v']:tr['len']*(T['geometry_m']-T['offset_on_edge_m'])/T['geometry_m']}
def solve(target=None,stairs=True):
    dist={};heap=[];parents={};best=(float('inf'),None)
    for n,c in starts.items():dist[(n,False)]=c;heapq.heappush(heap,(c,n,False));parents[(n,False)]=None
    while heap:
        c,n,used=heapq.heappop(heap);state=(n,used)
        if c!=dist[state]:continue
        if c>=best[0]:break
        if n in goals and (used or target is None):best=(c+goals[n],state)
        for v,idx in adj[n]:
            r=edges[idx];nxt=(v,used or r['way']==target);nc=c+r['len']*(1.5 if stairs and r.get('st') else 1)
            if nc<dist.get(nxt,float('inf')):dist[nxt]=nc;parents[nxt]=(state,idx);heapq.heappush(heap,(nc,*nxt))
    route=[];st=best[1]
    while st and parents[st] is not None:prev,idx=parents[st];route.append(idx);st=prev
    route.reverse()
    return {'cost_m':best[0],'ways':[edges[i]['way'] for i in route],'edge_indices':route,'kind':'주변 부분망의 진단 계산이며 제품 재실행이 아닙니다.'}
out={'matched_nearby_edge_rows':len(edges),'unconstrained':solve(),'distance_only':solve(stairs=False),'euljiro_1gil_constrained':solve(233651317),
     'snapshot_match':a['same_snapshot'],'api_calls':0,'network_calls':0}
with (P/'local-topology-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
