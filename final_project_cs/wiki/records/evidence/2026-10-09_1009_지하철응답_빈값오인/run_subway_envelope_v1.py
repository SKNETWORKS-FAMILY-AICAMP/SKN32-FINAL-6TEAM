from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-envelope-work-v1.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
phase = sys.argv[1]
files = ['tests/unit/travel/test_subway_envelope_v1.py']
if phase.startswith('after'):
    files += ['tests/unit/travel/test_subway_identity_v1.py', 'tests/unit/travel/test_seoul_subway_arrival.py',
              'tests/unit/travel/test_subway_observation_time.py', 'tests/unit/travel/test_subway_line_identity_v1.py',
              'tests/unit/travel/test_departure_observer_notice_v1.py',
              'tests/unit/travel/mobility/test_arrival_query_clock_v1.py']
cmd = [sys.executable, '-m', 'pytest', '-q', *files, '--basetemp', str(scratch / ('pytest-subway-envelope-' + phase)),
       '--junitxml', str(ev / (phase + '.xml'))]
env = dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch))
r = subprocess.run(cmd, cwd=root / 'final_project_cs', env=env, capture_output=True, text=True, encoding='utf8')
with (ev / (phase + '.log')).open('x', encoding='utf8') as f: f.write(r.stdout + r.stderr)
with (ev / (phase + '.run.json')).open('x', encoding='utf8') as f:
    json.dump({'command': cmd, 'time': datetime.now().astimezone().isoformat(), 'exit_code': r.returncode}, f, ensure_ascii=False, indent=2)
print(r.stdout[-1400:])
print('exit_code=', r.returncode)
