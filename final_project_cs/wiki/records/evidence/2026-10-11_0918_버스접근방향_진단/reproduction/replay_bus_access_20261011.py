from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor,as_completed
import sys,json,socket,time
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parents[2];cs=root/'final_project_cs'
ev=cs/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단'
stage=sys.argv[1];out=ev/f'product-{stage}.json'
assert not out.exists()
sys.path.insert(0,str(cs))
attempts=[]
def deny(*args,**kw):
    attempts.append(1);raise RuntimeError('외부 통신 차단')
socket.socket.connect=deny;socket.socket.connect_ex=deny
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
rt=build_verifier(quiet=True,local_router=True,seoul_key='',gh_url='',data_dir=str(root/'datasets/mobility/processed'))
print('자료 로딩 완료',flush=True)
design=json.loads((root/'datasets/mobility/raw/kakao_golden/fresh_experiment_100_design.json').read_text(encoding='utf8'))
targets=[('N022','2026-10-08T10:30:00+09:00'),('N100','2026-10-08T10:30:00+09:00'),('N089','2026-10-08T10:30:00+09:00'),('N062','2026-10-09T01:30:00+09:00')]
def run(target):
    id,at=target;p=next(x for x in design['pairs'] if x['id']==id)
    a={'name':p['a'],'lat':p['alat'],'lon':p['alon']};b={'name':p['b'],'lat':p['blat'],'lon':p['blon']}
    planner=Planner(rt,modes=['bus']);planner.trace=[]
    begin=time.perf_counter();got,why=planner.leg(a,b,datetime.fromisoformat(at),{},True,id)
    elapsed=time.perf_counter()-begin
    return {'id':id,'from':a,'to':b,'arrive':at,'modes':['bus'],'result':got,'why':why,'trace':planner.trace,'seconds':elapsed}
rows=[]
with ThreadPoolExecutor(max_workers=2) as pool:
    for f in as_completed([pool.submit(run,t) for t in targets]):
        r=f.result();rows.append(r);print(r['id'],str(r['result'])[:700],flush=True)
with out.open('x',encoding='utf8') as f:json.dump({'stage':stage,'rows':rows,'network_attempts':len(attempts)},f,ensure_ascii=False,indent=2,default=str)
