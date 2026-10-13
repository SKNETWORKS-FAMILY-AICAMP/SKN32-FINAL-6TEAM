from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-selection-work-v1.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
stage = sys.argv[1]
tests = ['tests/unit/travel/test_subway_boardable_v1.py']
if stage == 'after':
    tests += ['tests/unit/travel/test_seoul_subway_arrival.py', 'tests/unit/travel/test_subway_identity_v1.py',
              'tests/unit/travel/test_subway_envelope_v1.py', 'tests/unit/travel/test_subway_observation_time.py',
              'tests/unit/travel/test_subway_line_identity_v1.py']
command = [sys.executable, '-m', 'pytest', *tests, '-q', '--basetemp=' + str(scratch / ('pytest-subway-select-' + stage)),
           '--junitxml=' + str(ev / (stage + '-v1.xml'))]
env = dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch))
result = subprocess.run(command, cwd=root / 'final_project_cs', env=env, capture_output=True, text=True, encoding='utf8')
with (ev / (stage + '-v1.log')).open('x', encoding='utf8') as f: f.write(result.stdout + result.stderr)
with (ev / (stage + '-v1.run.json')).open('x', encoding='utf8') as f:
    json.dump({'command': command, 'exit_code': result.returncode}, f, indent=2)
print(result.stdout[-1300:])
print('exit_code', result.returncode)
