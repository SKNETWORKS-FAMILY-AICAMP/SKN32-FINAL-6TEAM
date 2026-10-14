from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
cs = root/'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch/'shared-nearest-station-work-v1.json').read_text(encoding='utf8'))
ev = cs/'wiki/records/evidence'/state['tag']
mode = sys.argv[1]
assert mode=='after-v2'
tests = ['test_shared_nearest_station_v1']
if mode=='after-v2':
    tests += ['test_station_fallback_v1','test_review_fixes_plan','test_plan_access_walk',
              'test_walk_routed_cap','test_estimate_walk_network_v1',
              'test_earliest_v1','test_verify55_v1']
temp = scratch/('shared-nearest-'+mode+'-temp')
temp.mkdir(exist_ok=False)
cmd = [sys.executable,'-m','pytest','-q',*['tests/unit/travel/mobility/'+x+'.py' for x in tests],
       '--basetemp',str(temp),'--junitxml',str(ev/(mode+'.xml'))]
r = subprocess.run(cmd,cwd=cs,capture_output=True,text=True,encoding='utf8',
                   env=dict(os.environ,PYTHONIOENCODING='utf-8',TEMP=str(temp),TMP=str(temp)))
with (ev/(mode+'.log')).open('x',encoding='utf8') as f:
    f.write(r.stdout+r.stderr)
with (ev/(mode+'.run.json')).open('x',encoding='utf8') as f:
    json.dump({'command':cmd,'exit_code':r.returncode},f,indent=2)
print(r.stdout[-2300:])
sys.exit(r.returncode)
