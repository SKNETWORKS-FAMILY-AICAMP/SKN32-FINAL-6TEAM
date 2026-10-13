from pathlib import Path
from dataclasses import asdict
import json, socket, sys
root=Path(__file__).resolve().parents[2]; repo=root/'final_project_cs'
sys.path.insert(0,str(repo));sys.stdout.reconfigure(encoding='utf8')
out=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
calls=[]
def deny(*a,**kw):calls.append('blocked');raise RuntimeError('offline validation')
socket.socket.connect=socket.socket.connect_ex=deny
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
rt=build_verifier(quiet=True,local_router=True,seoul_key='',gh_url='',data_dir=str(root/'datasets/mobility/processed'))
print('실제 저장 자료로 이동 계산기 조립 완료',flush=True)
design=json.loads((root/'datasets/mobility/raw/kakao_golden/fresh_experiment_100_design.json').read_text(encoding='utf8'))
rows=[]
for pid in ('N091','N094'):
    p=next(r for r in design['pairs'] if r['id']==pid)
    for mode in ('car','taxi'):
        case={'id':f'uturn/{pid}/{mode}','date':'2026-10-11','stage':'pre_departure',
              'depart_at':'10:00','arrive_by':'11:00','party':{},'first_visit':False,'no_alternatives':True,
              'legs':[{'mode':mode,'from':f"{p['alat']},{p['alon']}",'to':f"{p['blat']},{p['blon']}"}]}
        result=asdict(rt.verify_case(case));car=result['legs'][0]['car']
        assert car['routing_evidence']['turn_restrictions']['applied_relations']==4706
        assert result['verdict']=='feasible',result
        assert all(k not in car for k in ('points','geometry','arc_codes'))
        rows.append({'id':pid,'a':p['a'],'b':p['b'],'mode':mode,'case':case,'result':result})
        print(pid,mode,result['verdict'],car['distance_m'],flush=True)
with (out/'product-replay.json').open('x',encoding='utf8') as f:json.dump({'rows':rows,'network_attempts':len(calls),'limited_api_calls':0},f,ensure_ascii=False,indent=2,default=str)
