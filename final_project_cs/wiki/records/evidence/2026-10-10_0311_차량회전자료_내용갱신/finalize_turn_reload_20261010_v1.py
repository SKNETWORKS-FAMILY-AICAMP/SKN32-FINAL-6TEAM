from pathlib import Path
from datetime import datetime
import difflib,hashlib,json,re,shutil,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'turn-reload-state-20261010-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def save(p,obj):
 with p.open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
prior=read(ROOT/state['previous_integrity']);baseline=read(EV/'baseline-v1.json');pub=read(EV/'publication-state-v1.json')
backups=read(EV/'backup-manifest-v1.json')+read(EV/'publication-backups-v1.json')
assert len(backups)==4 and all(sha(ROOT/b['backup'])==b['sha256'] for b in backups)
code=ROOT/backups[0]['path'];old=ROOT/backups[0]['backup'];wiki=CS/'wiki/teams/mobility.md'
allowed={rel(code),rel(wiki)};preserved={p:sha(ROOT/p)==h for p,h in baseline['hashes'].items() if p not in allowed}
assert all(preserved.values()),[p for p,ok in preserved.items() if not ok]
delta=''.join(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),code.read_text(encoding='utf8').splitlines(True),fromfile='before/'+code.name,tofile='after/'+code.name))
with (EV/'code-change-v1.patch').open('x',encoding='utf8') as f:f.write(delta)
for name in ('report','debug','plan','history'):
 p=ROOT/pub[name]
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
  if not target.startswith('http'):assert (p.parent/target).resolve().exists(),(name,target)
assert '## 해결됨' in (ROOT/pub['debug']).read_text(encoding='utf8')
save(EV/'publication-finalization-v1.json',{'checked_at':datetime.now().astimezone().isoformat(),'prior_files_preserved':sum(preserved.values()),'preservation_total':len(preserved),'code_before_sha256':sha(old),'code_after_sha256':sha(code),'limited_api_calls':0,'new_tests_passed':5,'related_tests_passed':41,'replays_passed':8,'full_feature_completion':False,'browser_rendered':False})
shutil.copy2(Path(__file__),EV/Path(__file__).name)
sources=set(prior['source_test_data_hashes'])
sources.add(rel(CS/'tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py'))
sourcehashes={p:sha(ROOT/p) for p in sorted(sources)}
assets=ROOT/pub['assets'];files=[p for d in (EV,assets) for p in d.iterdir() if p.is_file()]+[ROOT/pub[k] for k in ('report','debug','plan','history')]+[wiki]
manifest={'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':sourcehashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':backups,'report':pub['report'],'assets':pub['assets'],'evidence':state['evidence'],'full_feature_completion':False}
target=EV/'final-integrity-v1.json';save(target,manifest)
hashes=sourcehashes|manifest['artifact_hashes'];assert all(sha(ROOT/p)==h for p,h in hashes.items())
save(EV/'final-validation-v1.json',{'checked_at':datetime.now().astimezone().isoformat(),'matched':len(hashes),'total':len(hashes),'source_test_data_count':len(sourcehashes),'artifact_count':len(manifest['artifact_hashes']),'backups_matched':4,'backups_total':4,'final_integrity_sha256':sha(target),'full_feature_completion':False,'browser_rendered':False})
print(json.dumps({'matched':len(hashes),'total':len(hashes),'backups':len(backups),'preserved':len(preserved),'report':pub['report']},ensure_ascii=False))
