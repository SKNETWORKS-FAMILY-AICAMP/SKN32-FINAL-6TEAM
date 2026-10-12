from pathlib import Path
import json, subprocess, sys, os
from datetime import datetime

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'
state=json.loads((Path(__file__).parent/'collection-integrity-state-v1.json').read_text(encoding='utf8')); EV=ROOT/state['evidence']
prior=json.loads((CS/'wiki/records/evidence/2026-10-09_1343_공항철도_공표승차시간_대조/related-v1-run.json').read_text(encoding='utf8'))
files=list(dict.fromkeys([v for v in prior['command'] if v.endswith('.py')]+['tests/unit/travel/mobility/test_tago_collection_integrity_v1.py']))
def run(name,args,cwd=CS):
    p=subprocess.run(args,cwd=cwd,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
    (EV/f'{name}.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf8')
    (EV/f'{name}-run.json').write_text(json.dumps({'command':args,'cwd':str(cwd),'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()},ensure_ascii=False,indent=2),encoding='utf8')
    print(name,p.returncode,p.stdout[-1200:],flush=True)
    return p.returncode
code=run('related-v2',[sys.executable,'-m','pytest',*files,'-q','-p','no:cacheprovider',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/collector_related_v2"}',f'--junitxml={EV/"related-v2.xml"}'])
code|=run('ruff-v2',[sys.executable,'-m','ruff','check',str(ROOT/'datasets/mobility/scripts/_tago_checked.py'),'tests/unit/travel/mobility/test_tago_collection_integrity_v1.py'])
for n in ['tago_subway_collect.py','tago_retry_empty.py','_tago_checked.py']:
    p=ROOT/'datasets/mobility/scripts'/n
    compile(p.read_text(encoding='utf8'),str(p),'exec')
(EV/'syntax-v1.json').write_text(json.dumps({'compiled':3,'files':['tago_subway_collect.py','tago_retry_empty.py','_tago_checked.py']}),encoding='utf8')
sys.exit(code)
