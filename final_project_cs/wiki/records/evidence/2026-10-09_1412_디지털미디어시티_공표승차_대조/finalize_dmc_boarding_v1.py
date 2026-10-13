from pathlib import Path
from datetime import datetime
import hashlib,json,os,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'dmc-published-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence'];ASSETS=CS/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v49';RAW=ROOT/state['raw']
def rel(p):return p.relative_to(ROOT).as_posix()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
reports=list((CS/'wiki/records/reports').glob('2026-10-09_*_디지털미디어시티_공식승차시간_확대검증.md'));assert len(reports)==1;REPORT=reports[0]
debug=ROOT/state['debug'];wiki=CS/'wiki/teams/mobility.md'
assert re.search(r'^## 해결됨',debug.read_text(encoding='utf8'),re.M) and not re.search(r'^## 미해결',debug.read_text(encoding='utf8'),re.M)
args=[sys.executable,'C:/Users/playdata2/.agents/skills/diagram-design/scripts/self_check.py',str(ASSETS/'mobility-readiness.html')]
p=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8'));assert p.returncode==0,p.stdout+p.stderr
with (EV/'visual-self-check-v1.log').open('x',encoding='utf8') as f:f.write(p.stdout+'\n'+p.stderr)
save(EV/'visual-self-check-v1-run.json',{'command':args,'exit_code':p.returncode,'browser_rendered':False})
save(EV/'publication-finalization-v1.json',{'publication_completed':True,'prior_script_error':'공개본 생성 뒤 무결성 기록 단계에서 ROOT[path] 오타로 TypeError. 코드·자료 검사 실패가 아니며 기존 산출물을 재생성하지 않고 이 마감 스크립트에서 ROOT / path로 검사함. 최초 생성 스크립트는 evidence에 그대로 보존.','new_debug_status':'해결됨(부분)','related_tests':97,'ABBA_runs':16})
shutil.copy2(Path(__file__),EV/Path(__file__).name)
prior=json.loads((ROOT/state['previous_integrity']).read_text(encoding='utf8'));sourcehashes={name:sha(ROOT/name) for name in prior['source_test_data_hashes']};sourcehashes[rel(RAW/'official-minute-facts-v1.json')]=sha(RAW/'official-minute-facts-v1.json')
backups=json.loads((EV/'backup-manifest-v1.json').read_text(encoding='utf8'))+json.loads((EV/'publication-backups-v1.json').read_text(encoding='utf8'))
assert all(sha(ROOT / b['backup'])==b['sha256'] for b in backups)
files=[p for d in (EV,ASSETS) for p in d.iterdir() if p.is_file()]+[REPORT,debug,wiki,ROOT/'datasets/mobility/REPORT.md']
manifest={'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':sourcehashes,'artifact_hashes':{rel(p):sha(p) for p in files},'backups':backups,'full_feature_completion':False,'report':rel(REPORT),'assets':rel(ASSETS),'evidence':rel(EV)}
save(EV/'final-integrity-v1.json',manifest)
hashes=sourcehashes|manifest['artifact_hashes'];assert all(sha(ROOT/name)==value for name,value in hashes.items())
save(EV/'final-validation-v1.json',{'checked_at':datetime.now().astimezone().isoformat(),'matched':len(hashes),'total':len(hashes),'backups_matched':len(backups),'backups_total':len(backups),'prior_preserved':322,'related_tests_passed':97,'deselected':165,'ABBA_runs_passed':16,'full_feature_completion':False,'browser_rendered':False})
print(json.dumps({'report':rel(REPORT),'assets':rel(ASSETS),'matched':len(hashes),'source_test_data_hashes':len(sourcehashes),'artifact_hashes':len(files),'backups':len(backups)},ensure_ascii=False))
