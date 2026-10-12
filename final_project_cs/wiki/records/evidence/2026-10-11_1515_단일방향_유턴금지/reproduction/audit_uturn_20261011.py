from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib, json, sys, socket, shutil, time
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parents[2]; repo=root/'final_project_cs'
sys.path.insert(0,str(repo))
out=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
calls=[]
def denied(*a,**kw): calls.append('blocked'); raise RuntimeError('offline validation')
socket.socket.connect=socket.socket.connect_ex=denied
from scripts.mobility.build_car_turn_policy_v1 import build, unique_same_way_uturn
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from app.domains.travel_ops.instances.mobility.engine.turn_restrictions import tables, permitted, load
graph=root/'datasets/mobility/processed/mobility/road_graph_v2'
audit=root/'datasets/mobility/processed/mobility/turn_restrictions_20261008_v1'
candidate=out/'turn_restrictions_extended_v1.json'
data=build(audit,graph,candidate,include_same_way_uturn=True)
old=json.loads((graph/'turn_restrictions_v1.json').read_text(encoding='utf8'))
old_ids={r['relation_id'] for r in old['rules']}
assert all(r in data['rules'] for r in old['rules'])
extra=[r for r in data['rules'] if r['relation_id'] not in old_ids]
rt=GraphRouter(graph); rt._load()
before=tables(old,rt); after=tables(data,rt)
source={r['relation_id']:r for r in map(json.loads,(audit/'restrictions-graph-audit.jsonl').read_text(encoding='utf8').splitlines())}
checked=[]
for r in extra:
    row=source[r['relation_id']]; roles={m['role']:m for m in row['members']}
    arc=r['incoming']; edge=arc>>1
    via=rt.eu[edge] if arc&1 else rt.ev[edge]
    assert rt.eway[edge]==roles['from']['ref']==roles['to']['ref']
    assert rt.nid[roles['via']['ref']]==via
    assert r['outgoing']==arc^1 and rt._allowed('car',edge)==(True,True)
    assert not permitted(after,arc,r['outgoing'])
    checked.append({'relation_id':r['relation_id'],'incoming':arc,'outgoing':r['outgoing'],
                    'previously_permitted':permitted(before,arc,r['outgoing'])})
all_same=[r for r in source.values() if r['graph_audit']['effective_motorcar_value_candidate']=='no_u_turn'
          and r['graph_audit']['unsupported_or_unresolved_reasons']==['same_way_turn_requires_arc_geometry_semantics']]
diagnosis={'created_at':datetime.now().astimezone().isoformat(),'source_relations':len(source),
           'same_way_without_other_reasons':len(all_same),'added':len(extra),'old':len(old_ids),'new':len(data['rules']),
           'previously_permitted':sum(r['previously_permitted'] for r in checked),
           'excluded_same_way_ids':[r['relation_id'] for r in all_same if not unique_same_way_uturn(r)],
           'graph_identity_checked':len(checked),'all_added_reverse_forbidden':len(checked),
           'network_attempts':len(calls)}
with (out/'diagnosis.json').open('x',encoding='utf8') as f:json.dump(diagnosis,f,ensure_ascii=False,indent=2)
with (out/'added-relations-validation.json').open('x',encoding='utf8') as f:json.dump(checked,f,indent=2)
print(json.dumps(diagnosis,ensure_ascii=False),flush=True)
design=json.loads((root/'datasets/mobility/raw/kakao_golden/fresh_experiment_100_design.json').read_text(encoding='utf8'))
new_pairs={(r['incoming'],r['outgoing']) for r in extra}
def replay(stage):
    rows=[]
    for idx,p in enumerate(design['pairs']):
        start=time.perf_counter()
        try:
            result=rt.route((p['alon'],p['alat']),(p['blon'],p['blat']),profile='car')['paths'][0]
            arcs=result['turn_restrictions']['arc_codes']
            violations=[list(pair) for pair in zip(arcs,arcs[1:]) if pair in new_pairs]
            record={'id':p['id'],'a':p['a'],'b':p['b'],'distance_m':result['distance'],
                'model_seconds':result['time']/1000,'new_uturn_occurrences':violations,
                'applied_relations':result['turn_restrictions']['applied_relations']}
        except Exception as e:record={'id':p['id'],'error':type(e).__name__,'detail':str(e)}
        record['elapsed_seconds']=time.perf_counter()-start;rows.append(record)
        if (idx+1)%10==0: print(f'{stage} {idx+1}/{len(design["pairs"])}',flush=True)
    with (out/f'car-{stage}.json').open('x',encoding='utf8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
    return rows
before_rows=replay('before')
# 백업과 시작 해시가 확인된 로컬 자료만 교체한다. 운영 배포는 하지 않는다.
target=graph/'turn_restrictions_v1.json'
backup=graph/'_backup/2026-10-11_1515_単一方向ユータン/turn_restrictions_v1.json'
assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(backup.read_bytes()).digest()
temp=graph/'turn_restrictions_v1.uturn-20261011.tmp'
with temp.open('xb') as f:f.write(candidate.read_bytes())
temp.replace(target)
assert load(rt)[2]['applied_relations']==len(data['rules'])
after_rows=replay('after')
summary={'total':len(before_rows),'before_success':sum('error' not in r for r in before_rows),
         'after_success':sum('error' not in r for r in after_rows),
         'before_routes_with_new_uturn':sum(bool(r.get('new_uturn_occurrences')) for r in before_rows),
         'after_routes_with_new_uturn':sum(bool(r.get('new_uturn_occurrences')) for r in after_rows),
         'changed':[{'before':b,'after':a} for b,a in zip(before_rows,after_rows) if b.get('distance_m')!=a.get('distance_m')],
         'network_attempts':len(calls),'limited_api_calls':0,'actual_driving':0}
with (out/'car-comparison.json').open('x',encoding='utf8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in summary.items() if k!='changed'},ensure_ascii=False),flush=True)
