from pathlib import Path
from datetime import datetime
from collections import Counter
import dataclasses,gzip,hashlib,json,socket,sys,time
ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'
sys.path.insert(0,str(CS));sys.stdout.reconfigure(encoding='utf8')
BASE=ROOT/'datasets/mobility/processed/mobility'
state=json.loads((Path(__file__).parent/'gimpo-published-state-v1.json').read_text(encoding='utf8'))
EV=ROOT/state['evidence']; RAW=ROOT/state['raw']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def save(name,obj):
 with (EV/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=str)
def now():return datetime.now().astimezone().isoformat()
prior=read(ROOT/state['previous_integrity']); prior_hashes=prior['source_test_data_hashes']|prior['artifact_hashes']
baseline={p:sha(ROOT/p) for p in prior_hashes}
changes=[p for p,h in prior_hashes.items() if baseline[p]!=h]
expected_changes={
 'final_project_cs/app/domains/travel_ops/components/watch/notice_routing.py',
 'final_project_cs/app/domains/travel_ops/instances/mobility/wiring.py',
 'final_project_cs/config/guardrails.yaml',
 'datasets/mobility/processed/mobility/published_boarding_timetable_v1.json',
 'datasets/mobility/processed/mobility/MANIFEST_git_v1.json',
 'final_project_cs/wiki/teams/mobility.md'}
assert set(changes)==expected_changes,changes
save('resume-baseline-v1.json',{'created_at':now(),'hashes':baseline,'previous_changes':changes,'previous_matches':len(baseline)-len(changes),'previous_total':len(baseline),'policy':'처음 3개 코드·설정의 다른 작업 변경을 현재 기준으로 보존. 이 스크립트는 제품 코드·자료를 쓰지 않음.'})
backups=read(EV/'backup-manifest-v1.json')
assert all(sha(ROOT/b['backup'])==b['sha256'] for b in backups)
oldfile=ROOT/backups[0]['backup']; olddoc=read(oldfile);newdoc=read(BASE/'published_boarding_timetable_v1.json')
assert sha(BASE/'published_boarding_timetable_v1.json')=='7ce5ed25c9bb83aa2eb8b8d1ca0da519dafdd8a3a54d0cac52ac7408ea751cf8'
assert sha(BASE/'MANIFEST_git_v1.json')=='3fa2f58ee5cb58deba795a33bff57cb2bd1ea30545b3db33ca51ea2347494be7'
assert len(olddoc['groups'])==8 and len(newdoc['groups'])==12 and newdoc['groups'][:8]==olddoc['groups']
entry=[e for e in read(ROOT/backups[1]['backup'])['files'] if e['path']==oldfile.name];assert len(entry)==1
assert entry[0]['bytes']==oldfile.stat().st_size and entry[0]['sha256']==sha(oldfile)
fresh=read(RAW/'official-minute-facts-rechecked-v1.json');stored=read(RAW/'official-minute-facts-v1.json')
def minutes(g):return sorted(int(h)*60+m for h,ms in g['hours'].items() for m in ms)
freshgroups={(g['day_type'],g['dir']):minutes(g) for g in fresh['groups']}
assert freshgroups=={(g['day_type'],g['dir']):minutes(g) for g in stored['groups']}
assert freshgroups=={(g['day_type'],g['dir']):g['minutes'] for g in newdoc['groups'][8:]}
assert sum(map(len,freshgroups.values()))==680
audit=[];rows=[];allrows=0
with gzip.open(BASE/'timetable_v1.jsonl.gz','rt',encoding='utf8') as f:
 for line in f:
  r=json.loads(line);allrows+=1
  if r.get('line')=='공항철도' and r.get('station_nm')=='김포공항':rows.append(r)
for (day,direction),official in freshgroups.items():
 selected=[r for r in rows if r['day_type']==day and r['dir']==direction]
 def minute(r):
  h,m,*_=map(int,r['dep_time'].split(':'));return h*60+m
 counts=Counter(minute(r) for r in selected)
 missing=sorted(set(official)-counts.keys());duplicates=sorted(m for m in official if counts[m]>1)
 excluded=[r for r in selected if minute(r) not in official]
 assert not missing and not duplicates and len(excluded)==26
 audit.append({'day_type':day,'direction':direction,'stored':len(selected),'official':len(official),'missing':missing,'duplicates':duplicates,'excluded':excluded})
save('official-recheck-v1.json',{'checked_at':now(),'source_url':fresh['source_url'],'fresh_fact_sha256':sha(RAW/'official-minute-facts-rechecked-v1.json'),'tables_matched':4,'tables_total':4,'minutes_matched':680,'minutes_total':680,'original_facts_match':True,'published_data_match':True,'web_method':'공식 URL 직접 열기는 실패했고 검색 참조로 같은 공식 페이지를 열어 4개 표 전체 숫자를 재확인함.','limited_api_calls':0,'quota_usage':'공유 누적 사용량을 확인하지 않았으므로 제한 있는 API를 호출하지 않음.'})
save('resume-data-audit-v1.json',{'created_at':now(),'gzip_rows':allrows,'groups':audit,'backups_verified':len(backups),'old_eight_groups_preserved':True})
attempts=[]
def denied(*args,**kwargs):
 attempts.append(str(args[0] if args else kwargs));raise RuntimeError('offline replay: network disabled')
socket.socket.connect=denied;socket.create_connection=denied
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine import datacheck
print('변경 전 백업으로 계산기 구성 시작',flush=True)
oldrt=build_verifier(data_dir=BASE.parent,paths={'published_boarding':oldfile},gh_url='',seoul_key='',quiet=True,local_router=False);old=oldrt._v
print('현재 자료로 계산기 구성 시작',flush=True)
newrt=build_verifier(data_dir=BASE.parent,gh_url='',seoul_key='',quiet=True,local_router=False);new=newrt._v
def digest(rows):return hashlib.sha256(json.dumps([(d.min,d.dir,d.dest,d.inferred,getattr(d.run,'tno',None),getattr(d.run,'express',None)) for d in rows],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
same=[];different=[]
for key in set(old.tt.by_key)|set(new.tt.by_key):
 (same if digest(old.tt.by_key.get(key,[]))==digest(new.tt.by_key.get(key,[])) else different).append(key)
assert sorted(different)==sorted([('공항철도','김포공항',day) for day in ('weekday','holiday')]),different
conditions=[(day,direction,'마곡나루' if direction=='U' else '계양',798 if direction=='U' else 785,804 if direction=='U' else (789 if day=='weekday' else 790)) for day in ('weekday','holiday') for direction in ('U','D')]
replays=[]
for day,direction,target,ready,expected in conditions:
 for variant in ('A','B','B','A'):
  r=(old if variant=='A' else new).verify_leg(0,{'line':'공항철도','from':'김포공항','to':target},ready,day,False)
  assert r.depart_min==(expected if variant=='B' else (799 if direction=='U' else 786)),r
  replays.append({'variant':variant,'day_type':day,'direction':direction,'ready_minute':ready,'result':dataclasses.asdict(r)})
check=datacheck.check(verify_hash=True);assert check['ok'],check
summary=newrt.stats['published_boarding'];assert sum(r['matched'] for r in summary)==2044 and sum(r['excluded'] for r in summary)==312
assert oldrt.timetable_built_at!=newrt.timetable_built_at and not attempts
assert all(sha(ROOT/p)==h for p,h in baseline.items()),'다른 작업 변경 감지'
save('product-replay-v1.json',{'created_at':now(),'summary':summary,'same_group_count':len(same),'changed_groups':sorted(different),'replays':replays,'datacheck':check,'base_files':{n:sha(BASE/n) for n in ('timetable_v1.jsonl.gz','timetable_v1.jsonl','timetable_v1_meta.json')},'old_input_basis':oldrt.timetable_built_at,'new_input_basis':newrt.timetable_built_at,'old_eight_groups_preserved':True,'network_attempts':attempts,'baseline_hashes_preserved':len(baseline),'backup_source_note':'A는 published_boarding 경로만 검증된 8그룹 백업으로 지정. 경로 지정은 기본 manifest 검사 우회하므로 백업 manifest의 SHA256·bytes를 별도 확인함. B는 현재 기본 자료와 전체 hash 검사.','limits':'통제 시각 재생이며 독립 경로·실제 ETA·탑승·결제 검증 아님. 계양 목적지는 계산기 내부 검사이며 서울 상품 지원 확대 근거 아님.'})
print(json.dumps({'ABBA_runs':len(replays),'same_groups':len(same),'changed_groups':different,'matched':2044,'excluded':312,'preserved_hashes':len(baseline),'network_attempts':len(attempts)},ensure_ascii=False),flush=True)
