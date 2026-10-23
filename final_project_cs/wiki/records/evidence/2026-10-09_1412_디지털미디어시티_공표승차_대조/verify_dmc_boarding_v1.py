from pathlib import Path
from datetime import datetime
import json,subprocess,sys,os
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'dmc-published-state-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
files=['test_published_boarding_v1.py','test_review_fixes_runtime.py','test_express_source_reload_v1.py','test_departure_publish_basis_v1.py','test_departure_express_basis_v1.py','test_regression_cases.py']
args=[sys.executable,'-m','pytest',*['tests/unit/travel/mobility/'+n for n in files],'-q','-p','no:cacheprovider',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/dmc_related_v1"}',f'--junitxml={EV/"related-v1.xml"}']
p=subprocess.run(args,cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
with (EV/'related-v1.log').open('x',encoding='utf8') as f:f.write(p.stdout+'\n'+p.stderr)
with (EV/'related-v1-run.json').open('x',encoding='utf8') as f:json.dump({'command':args,'cwd':str(CS),'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()},f,ensure_ascii=False,indent=2)
print(p.returncode,p.stdout[-1000:]);sys.exit(p.returncode)
