from pathlib import Path
from datetime import datetime,date
import copy,dataclasses,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.path.insert(0,str(CS));sys.stdout.reconfigure(encoding='utf8')
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.verify_time import Timetable
from app.domains.travel_ops.instances.mobility.engine.published_boarding import file_sha256
from app.domains.travel_ops.instances.mobility.engine.timeutil import day_type_of
from app.domains.travel_ops.instances.mobility.engine import datacheck
state=json.loads((Path(__file__).parent/'published-boarding-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
runtime=build_verifier(data_dir=ROOT/'datasets/mobility/processed',gh_url='',seoul_key='',quiet=True,local_router=False)
new=runtime._v;old=copy.copy(new)
old.tt=Timetable.load(ROOT/'datasets/mobility/processed/mobility/timetable_v1.jsonl.gz',express=True)
def digest(rows):
 vals=[(d.min,d.dir,d.dest,d.inferred,getattr(d.run,'tno',None),getattr(d.run,'express',None)) for d in rows]
 return hashlib.sha256(json.dumps(vals,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
same=[];different=[]
for key in set(old.tt.by_key)|set(new.tt.by_key):
 (same if digest(old.tt.by_key.get(key,[]))==digest(new.tt.by_key.get(key,[])) else different).append(key)
assert sorted(different)==sorted([('공항철도','홍대입구',day) for day in ('weekday','holiday')])
replays=[]
for day,direction,target,ready,expected in [('weekday','U','공덕',809,813),('holiday','U','공덕',809,813),('weekday','D','디지털미디어시티',815,819),('holiday','D','디지털미디어시티',815,822)]:
 for variant in ('A','B','B','A'):
  v=old if variant=='A' else new
  result=v.verify_leg(0,{'line':'공항철도','from':'홍대입구','to':target},ready,day,False)
  if variant=='B':assert result.depart_min==expected
  else:assert result.depart_min==(810 if direction=='U' else 815)
  replays.append({'variant':variant,'day_type':day,'direction':direction,'ready_minute':ready,'expected_published_departure':expected,'result':dataclasses.asdict(result)})
check=datacheck.check(verify_hash=True);assert check['ok'],check
summary=runtime.stats['published_boarding'];assert sum(x['matched'] for x in summary)==682 and sum(x['excluded'] for x in summary)==104
doc={'created_at':datetime.now().astimezone().isoformat(),'day_type_today':day_type_of(date(2026,10,9),new.holidays),'summary':summary,
 'same_group_count':len(same),'changed_groups':different,'all_other_groups_unchanged':True,'replays':replays,
 'base_files':{name:file_sha256(ROOT/'datasets/mobility/processed/mobility'/name) for name in ('timetable_v1.jsonl.gz','timetable_v1.jsonl','timetable_v1_meta.json')},
 'datacheck':check,'timetable_built_at':runtime.timetable_built_at,'stats':runtime.stats,
 'limits':'실제 보유 원자료+공표 표의 통제 시각 재생16회이며 독립 새 경로/실제 ETA오차/실탑승/결제 표본이 아니다. API 호출0. 104행의 원래 열차 종류 미확정·다른 역 공표 대조 남음.'}
with (EV/'product-replay-v1.json').open('x',encoding='utf8') as f:json.dump(doc,f,ensure_ascii=False,indent=2,default=str)
print(json.dumps({'matched':682,'excluded':104,'same_groups':len(same),'changed_groups':different,'ABBA_runs':len(replays),'datacheck_ok':check['ok']},ensure_ascii=False))
