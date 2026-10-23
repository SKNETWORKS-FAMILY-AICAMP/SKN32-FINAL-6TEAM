from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-identity-work-v1.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
phase = sys.argv[1]
files = ['tests/unit/travel/test_subway_identity_v1.py']
if phase.startswith('after'):
    files += ['tests/unit/travel/test_seoul_subway_arrival.py',
              'tests/unit/travel/test_subway_observation_time.py',
              'tests/unit/travel/test_departure_observer_notice_v1.py',
              'tests/unit/travel/mobility/test_arrival_query_clock_v1.py']
env = dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch))
cmd = [sys.executable, '-m', 'pytest', '-q', *files, '-m', 'not live and not mobility_fulldata',
       '--basetemp', str(scratch / ('pytest-subway-identity-' + phase)), '--junitxml', str(ev / (phase + '.xml'))]
result = subprocess.run(cmd, cwd=root / 'final_project_cs', env=env, capture_output=True, text=True, encoding='utf8')
with (ev / (phase + '.log')).open('x', encoding='utf8') as f:
    f.write(result.stdout + result.stderr)
with (ev / (phase + '.run.json')).open('x', encoding='utf8') as f:
    json.dump({'command': cmd, 'time': datetime.now().astimezone().isoformat(), 'exit_code': result.returncode,
               'network': 'injected transport only; no external provider requested'}, f, ensure_ascii=False, indent=2)
print(result.stdout[-1200:])
print('exit_code=', result.returncode)
