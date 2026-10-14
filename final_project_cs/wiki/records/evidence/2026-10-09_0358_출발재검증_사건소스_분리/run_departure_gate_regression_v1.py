from pathlib import Path
import json
import os
import subprocess
import sys

w = Path(__file__).resolve().parents[2]
p = Path(__file__).parent
prior = json.loads((p/'car-legacy-regression-v1-commands.json').read_text(encoding='utf8'))
files = sorted(set(prior['scope_files']) | {
    'tests/unit/travel/test_departure_source_gate_v1.py',
    'tests/scenario/test_departure_source_gate_db_v1.py'})
heavy = 'tests/unit/travel/mobility/test_taxi_fallback.py'
others = [name for name in files if name != heavy]
groups = [others[index::3] for index in range(3)] + [[heavy]]
commands, results = [], []
env = dict(os.environ, PYTHONIOENCODING='utf-8')
for index, chosen in enumerate(groups, 1):
    prefix = f'departure-gate-regression-v1-part{index}'
    command = [sys.executable, '-m', 'pytest', *chosen, '-q', '-m', 'not mobility_full and not live',
               '-o', 'faulthandler_timeout=45', f'--junitxml={p/(prefix+".xml")}',
               f'--basetemp={p/("pytest_"+prefix)}']
    commands.append(command)
    with (p/(prefix+'.log')).open('xb') as f:
        done = subprocess.run(command, cwd=w/'final_project_cs', stdout=f, stderr=subprocess.STDOUT, env=env)
    results.append(dict(part=index, exit_code=done.returncode))
    print(json.dumps(results[-1]), flush=True)
with (p/'departure-gate-regression-v1-commands.json').open('x', encoding='utf8') as f:
    json.dump(dict(commands=commands, results=results, scope_files=files), f, indent=2)
sys.exit(int(any(row['exit_code'] for row in results)))
