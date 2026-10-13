from pathlib import Path
from datetime import datetime
import json,subprocess,sys,os
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs'
state=json.loads((Path(__file__).parent/'published-boarding-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
prior=json.loads((CS/'wiki/records/evidence/2026-10-09_1248_지하철_방면과_인접역ID_대조/after-run-v3.json').read_text(encoding='utf8'))
files=[v for v in prior['command'] if v.endswith('.py')]+['tests/unit/travel/mobility/test_published_boarding_v1.py','tests/unit/travel/mobility/test_review_fixes_runtime.py','tests/unit/travel/mobility/test_express_source_reload_v1.py','tests/unit/travel/mobility/test_departure_publish_basis_v1.py','tests/unit/travel/mobility/test_departure_express_basis_v1.py','tests/unit/travel/mobility/test_regression_cases.py']
def run(name,args):
 env=dict(os.environ,PYTHONIOENCODING='utf-8')
 p=subprocess.run(args,cwd=CS,env=env,capture_output=True,text=True,encoding='utf8',errors='replace')
 with (EV/f'{name}.log').open('x',encoding='utf8') as f:f.write(p.stdout+'\n'+p.stderr)
 with (EV/f'{name}-run.json').open('x',encoding='utf8') as f:json.dump({'command':args,'cwd':str(CS),'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()},f,ensure_ascii=False,indent=2)
 print(name,p.returncode,p.stdout[-650:],flush=True)
 return p.returncode
args=[sys.executable,'-m','pytest',*files,'-q','-p','no:cacheprovider',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/published_related_v1"}',f'--junitxml={EV/"related-v1.xml"}']
status=run('related-v1',args)
codefiles=['app/domains/travel_ops/instances/mobility/engine/'+n for n in ('runtime.py','verify_time.py','published_boarding.py','datacheck.py')]+['tests/unit/travel/mobility/test_published_boarding_v1.py']
status|=run('ruff-v1',[sys.executable,'-m','ruff','check',*codefiles])
sys.exit(status)
