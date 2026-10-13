"""같은 시험 목록을 순차 실행하되 실제 도로 런타임 시험은 별도 프로세스에 둔다."""
from pathlib import Path
import json
import subprocess
import sys

w = Path(__file__).resolve().parents[2]
p = w/'.tmp/mobility_complete_20261008'
old = json.loads((p/'car-snap-regression-command.json').read_text(encoding='utf8'))
files = sorted({arg for arg in old if arg.startswith('tests/') and arg.endswith('.py')})
files = sorted(set(files) | {'tests/unit/travel/mobility/test_car_legacy_selected_snap_v1.py'})
heavy = 'tests/unit/travel/mobility/test_taxi_fallback.py'
remaining = [file for file in files if file != heavy]
groups = [remaining[index::3] for index in range(3)] + [[heavy]]
commands, results = [], []
for index, chosen in enumerate(groups, 1):
    prefix = f'car-legacy-regression-v1-part{index}'
    command = [sys.executable, '-m', 'pytest', *chosen, '-q', '-m', 'not mobility_full and not live',
               '-o', 'faulthandler_timeout=45', f'--junitxml={p/(prefix+".xml")}',
               f'--basetemp={p/("pytest_"+prefix)}']
    commands.append(command)
    with (p/(prefix+'.log')).open('x', encoding='utf8') as f:
        done = subprocess.run(command, cwd=w/'final_project_cs', stdout=f, stderr=subprocess.STDOUT)
    results.append(dict(part=index, exit_code=done.returncode))
    print(json.dumps(results[-1]), flush=True)
with (p/'car-legacy-regression-v1-commands.json').open('x', encoding='utf8') as f:
    json.dump(dict(commands=commands, results=results, scope_files=files), f, indent=2)
sys.exit(int(any(row['exit_code'] for row in results)))
