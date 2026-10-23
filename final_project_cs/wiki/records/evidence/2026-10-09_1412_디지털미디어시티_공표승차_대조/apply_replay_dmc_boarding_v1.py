from pathlib import Path
from datetime import datetime
import copy,dataclasses,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.path.insert(0,str(CS));sys.stdout.reconfigure(encoding='utf8')
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine import datacheck
BASE=ROOT/'datasets/mobility/processed/mobility'
state=json.loads((Path(__file__).parent/'dmc-published-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str)
oldrt=build_verifier(data_dir=BASE.parent,gh_url='',seoul_key='',quiet=True,local_router=False);old=oldrt._v
conditions=[(day,direction,'홍대입구' if direction=='U' else '마곡나루',806 if direction=='U' else 817,809 if direction=='U' else 819) for day in ('weekday','holiday') for direction in ('U','D')]
before=[]
for day,direction,target,ready,expected in conditions:
 r=old.verify_leg(0,{'line':'공항철도','from':'디지털미디어시티','to':target},ready,day,False)
 assert r.depart_min==(807 if direction=='U' else 818),r
 before.append({'day_type':day,'direction':direction,'result':dataclasses.asdict(r)})
save(EV/'before-product-replay-v1.json',before)
backups=json.loads((EV/'backup-manifest-v1.json').read_text(encoding='utf8'))
for item in backups[:2]:assert sha(ROOT/item['path'])==item['sha256'],'concurrent data change'
facts=json.loads((ROOT/state['raw']/'official-minute-facts-v1.json').read_text(encoding='utf8'))
stamp=datetime.strptime(facts['observed_at'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=__import__('datetime').timezone.utc).isoformat()
p=BASE/'published_boarding_timetable_v1.json';doc=json.loads(p.read_text(encoding='utf8'));original=copy.deepcopy(doc['groups']);assert len(original)==4
for g in facts['groups']:
 assert set(map(int,g['hours']))==set(range(5,25))
 minutes=sorted(int(h)*60+m for h,ms in g['hours'].items() for m in ms)
 assert len(minutes)==len(set(minutes))
 doc['groups'].append({'line':'공항철도','station_nm':'디지털미디어시티','day_type':g['day_type'],'dir':g['dir'],'minutes':minutes,'complete':True,'source_url':facts['source_url'],'observed_at':stamp})
assert sum(len(g['minutes']) for g in doc['groups'][4:])==682
p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
mp=BASE/'MANIFEST_git_v1.json';manifest=json.loads(mp.read_text(encoding='utf8'));entries=[r for r in manifest['files'] if r['path']==p.name];assert len(entries)==1
entry=entries[0];oldbytes=entry['bytes'];entry.update(bytes=p.stat().st_size,sha256=sha(p),source_urls=sorted({g['source_url'] for g in doc['groups']}),source_checked_at=stamp,scope='홍대입구·디지털미디어시티 일반열차 평일·휴일 양방향8그룹1364분; 실제 ETA 자료 아님')
manifest['totals']['dst_bytes']+=entry['bytes']-oldbytes;manifest['published_boarding_extended_at']=datetime.now().astimezone().isoformat()
mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
newrt=build_verifier(data_dir=BASE.parent,gh_url='',seoul_key='',quiet=True,local_router=False);new=newrt._v
def digest(rows):return hashlib.sha256(json.dumps([(d.min,d.dir,d.dest,d.inferred,getattr(d.run,'tno',None),getattr(d.run,'express',None)) for d in rows],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
same=[];different=[]
for key in set(old.tt.by_key)|set(new.tt.by_key):
 (same if digest(old.tt.by_key.get(key,[]))==digest(new.tt.by_key.get(key,[])) else different).append(key)
assert sorted(different)==sorted([('공항철도','디지털미디어시티',day) for day in ('weekday','holiday')]),different
replays=[]
for day,direction,target,ready,expected in conditions:
 for variant in ('A','B','B','A'):
  r=(old if variant=='A' else new).verify_leg(0,{'line':'공항철도','from':'디지털미디어시티','to':target},ready,day,False)
  assert r.depart_min==(expected if variant=='B' else (807 if direction=='U' else 818)),r
  replays.append({'variant':variant,'day_type':day,'direction':direction,'ready_minute':ready,'result':dataclasses.asdict(r)})
check=datacheck.check(verify_hash=True);assert check['ok'],check
summary=newrt.stats['published_boarding'];assert sum(r['matched'] for r in summary)==1364 and sum(r['excluded'] for r in summary)==208
assert oldrt.timetable_built_at!=newrt.timetable_built_at
assert json.loads(p.read_text(encoding='utf8'))['groups'][:4]==original
save(EV/'product-replay-v1.json',{'created_at':datetime.now().astimezone().isoformat(),'summary':summary,'same_group_count':len(same),'changed_groups':different,'replays':replays,'datacheck':check,'base_files':{n:sha(BASE/n) for n in ('timetable_v1.jsonl.gz','timetable_v1.jsonl','timetable_v1_meta.json')},'old_input_basis':oldrt.timetable_built_at,'new_input_basis':newrt.timetable_built_at,'old_hongik_groups_preserved':True,'limits':'실제 보유 자료와 새 공식 표의 통제 시각 재생. 독립 경로/실제 ETA·탑승·결제 검증 아님. 지도개발자API·TAGO API 호출0.'})
print(json.dumps({'groups':len(summary),'matched':1364,'excluded':208,'changed_groups':different,'same_groups':len(same),'ABBA_runs':len(replays),'datacheck_ok':check['ok']},ensure_ascii=False))
