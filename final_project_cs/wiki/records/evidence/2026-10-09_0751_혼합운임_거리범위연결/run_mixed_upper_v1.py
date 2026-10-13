from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
mode = sys.argv[1]
assert mode in ('before', 'related')
scratch = Path(__file__).parent
paths = ['tests/unit/travel/mobility/test_mixed_fare_upper_v1.py']
if mode == 'related':
    paths += ['tests/unit/travel/mobility/test_subway_fare_upper.py',
              'tests/unit/travel/mobility/test_fare_est_v1.py',
              'tests/unit/travel/mobility/test_special_rail_fare.py',
              'tests/unit/travel/mobility/test_review_fixes_plan.py',
              'tests/unit/travel/mobility/test_plan_v1.py',
              'tests/unit/travel/mobility/test_transfer_fare_clock_v1.py']
prefix = scratch / f'mixed-upper-{mode}-v1'
command = [sys.executable, '-m', 'pytest', *paths, '-q',
           '--basetemp', str(prefix), '--junitxml', str(prefix) + '.xml']
env = dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch))
p = subprocess.run(command, cwd=root / 'final_project_cs', env=env,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8')
Path(str(prefix) + '.log').write_text(p.stdout, encoding='utf8')
Path(str(prefix) + '.run.json').write_text(json.dumps({'command': command, 'exit_code': p.returncode}), encoding='utf8')
print(p.stdout[-6000:])
sys.exit(p.returncode)
