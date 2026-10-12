from pathlib import Path
import json, subprocess, sys, os
from datetime import datetime

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'
state=json.loads((Path(__file__).parent/'collection-integrity-state-v1.json').read_text(encoding='utf8')); EV=ROOT/state['evidence']
def run(name,args,cwd=CS):
    p=subprocess.run(args,cwd=cwd,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
    (EV/f'{name}.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf8')
    (EV/f'{name}-run.json').write_text(json.dumps({'command':args,'cwd':str(cwd),'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()},ensure_ascii=False,indent=2),encoding='utf8')
    print(name,p.returncode,p.stdout[-1800:])
    return p.returncode
test='tests/unit/travel/mobility/test_tago_collection_integrity_v1.py'
code=run('collector-tests-v1',[sys.executable,'-m','pytest',test,'-q','-p','no:cacheprovider',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/collector_tests_v1"}',f'--junitxml={EV/"collector-tests-v1.xml"}'])
code|=run('ruff-v1',[sys.executable,'-m','ruff','check',str(ROOT/'datasets/mobility/scripts/_tago_checked.py'),test])
sys.exit(code)
