from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'fare-discount-upper-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
mode = sys.argv[1]
assert mode in ('before-v1', 'after-v1')
tests = ['test_fare_discount_upper_v1']
if mode == 'after-v1':
    tests += ['test_fare_est_v1', 'test_subway_fare_upper', 'test_special_rail_fare',
              'test_review_fixes_plan', 'test_transfer_fare_clock_v1', 'test_mixed_fare_upper_v1']
temp = scratch / ('fare-discount-' + mode + '-temp')
temp.mkdir(exist_ok=False)
cmd = [sys.executable, '-m', 'pytest', '-q', *['tests/unit/travel/mobility/' + t + '.py' for t in tests],
       '--basetemp', str(temp), '--junitxml', str(ev / (mode + '.xml'))]
result = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8',
                        env=dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(temp), TMP=str(temp)))
with (ev / (mode + '.log')).open('x', encoding='utf8') as f:
    f.write(result.stdout + result.stderr)
with (ev / (mode + '.run.json')).open('x', encoding='utf8') as f:
    json.dump({'command': cmd, 'exit_code': result.returncode}, f, ensure_ascii=False, indent=2)
print(result.stdout[-2000:])
sys.exit(result.returncode)
