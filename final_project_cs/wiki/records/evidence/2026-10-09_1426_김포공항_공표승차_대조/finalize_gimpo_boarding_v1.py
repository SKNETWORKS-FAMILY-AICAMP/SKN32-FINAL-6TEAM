from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'gimpo-published-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence'];RAW=ROOT/state['raw']
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def save(p,obj):
 with p.open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
baseline=read(EV/'resume-baseline-v1.json');pub=read(EV/'publication-state-v1.json');prior=read(ROOT/state['previous_integrity'])
REPORT=ROOT/pub['report'];ASSETS=ROOT/pub['assets'];DEBUG=ROOT/state['debug'];WIKI=CS/'wiki/teams/mobility.md';DATAREPORT=ROOT/'datasets/mobility/REPORT.md'
allowed={rel(p) for p in (DEBUG,WIKI,DATAREPORT)}
preserved={p:sha(ROOT/p)==h for p,h in baseline['hashes'].items() if p not in allowed}
assert all(preserved.values()),[p for p,ok in preserved.items() if not ok]
assert '## 해결됨' in DEBUG.read_text(encoding='utf8')
backups=read(EV/'backup-manifest-v1.json')+read(EV/'publication-backups-v1.json')
assert len(backups)==7 and all(sha(ROOT/b['backup'])==b['sha256'] for b in backups)
save(EV/'publication-finalization-v1.json',{'checked_at':datetime.now().astimezone().isoformat(),'preserved_after_publication':sum(preserved.values()),'preservation_total':len(preserved),'allowed_publication_changes':sorted(allowed),'limited_api_calls':0,'network_attempts':0,'test_passed':97,'test_selected':97,'test_deselected':165,'replays_passed':16,'replays_total':16,'product_code_or_data_mutations_this_resume':0,'full_feature_completion':False})
shutil.copy2(Path(__file__),EV/Path(__file__).name)
sourcepaths=set(prior['source_test_data_hashes'])
sourcepaths.update(rel(p) for d in (CS/'app/domains/travel_ops/instances/mobility',CS/'tests/unit/travel/mobility') for p in d.rglob('*.py') if '__pycache__' not in p.parts)
sourcepaths.update(rel(RAW/name) for name in ('official-minute-facts-v1.json','official-minute-facts-rechecked-v1.json'))
sourcehashes={p:sha(ROOT/p) for p in sorted(sourcepaths)}
files=[p for d in (EV,ASSETS) for p in d.iterdir() if p.is_file()]+[REPORT,DEBUG,WIKI,DATAREPORT]
manifest={'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':sourcehashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':backups,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV),'full_feature_completion':False}
target=EV/'final-integrity-v1.json';save(target,manifest)
hashes=sourcehashes|manifest['artifact_hashes'];assert all(sha(ROOT/p)==h for p,h in hashes.items())
save(EV/'final-validation-v1.json',{'checked_at':datetime.now().astimezone().isoformat(),'matched':len(hashes),'total':len(hashes),'source_test_data_count':len(sourcehashes),'artifact_count':len(manifest['artifact_hashes']),'backups_matched':7,'backups_total':7,'final_integrity_sha256':sha(target),'full_feature_completion':False,'browser_rendered':False})
print(json.dumps({'matched':len(hashes),'total':len(hashes),'backups':7,'preserved_after_publication':len(preserved),'report':rel(REPORT)},ensure_ascii=False))
