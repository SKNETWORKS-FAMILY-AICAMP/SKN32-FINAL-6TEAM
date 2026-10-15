from pathlib import Path
from datetime import datetime
import json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'turn-reload-state-20261010-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
files=['test_turn_policy_content_reload_v1.py','test_car_turn_restrictions_v1.py','test_graph_router.py','test_snap_selection_v1.py','test_car_evidence_v1.py']
files=[n for n in files if (CS/'tests/unit/travel/mobility'/n).exists()]
args=[sys.executable,'-m','pytest',*['tests/unit/travel/mobility/'+n for n in files],'-q','-p','no:cacheprovider',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/turn_reload_after_v1"}',f'--junitxml={EV/"after-v1.xml"}']
p=subprocess.run(args,cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
with (EV/'after-v1.log').open('x',encoding='utf8') as f:f.write(p.stdout+'\n'+p.stderr)
with (EV/'after-v1-run.json').open('x',encoding='utf8') as f:json.dump({'command':args,'cwd':'final_project_cs','files':files,'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()},f,ensure_ascii=False,indent=2)
print(p.stdout[-1800:]);sys.exit(p.returncode)
