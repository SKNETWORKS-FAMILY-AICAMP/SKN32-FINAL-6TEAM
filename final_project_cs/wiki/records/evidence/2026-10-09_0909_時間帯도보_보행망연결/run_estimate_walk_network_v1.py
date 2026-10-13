from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'estimate-walk-network-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
mode = sys.argv[1]
assert mode in ('before-v1', 'before-v2', 'after-v1')
tests = ['test_estimate_walk_network_v1']
if mode == 'after-v1':
    tests += ['test_walk_duration_contract_v1', 'test_plan_estimate_v1', 'test_review_fixes_plan',
              'test_plan_access_walk', 'test_walk_routed_cap']
temp = scratch / ('estimate-walk-' + mode + '-temp')
temp.mkdir(exist_ok=False)
cmd = [sys.executable, '-m', 'pytest', '-q', *['tests/unit/travel/mobility/' + t + '.py' for t in tests],
       '--basetemp', str(temp), '--junitxml', str(ev / (mode + '.xml'))]
r = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8',
                   env=dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(temp), TMP=str(temp)))
(ev / (mode + '.log')).write_text(r.stdout + r.stderr, encoding='utf8')
(ev / (mode + '.run.json')).write_text(json.dumps({'command': cmd, 'exit_code': r.returncode}, indent=2), encoding='utf8')
print(r.stdout[-2500:])
sys.exit(r.returncode)
