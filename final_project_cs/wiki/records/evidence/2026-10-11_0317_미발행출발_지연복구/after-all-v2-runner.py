import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(errors='replace')
REPO = ROOT / 'final_project_cs'
EV = REPO / 'wiki/records/evidence/2026-10-11_0317_미발행출발_지연복구'
stage = sys.argv[1]
test = 'tests/unit/travel/test_late_departure_notice_v1.py'
files = [test]
if stage.startswith('after-all'):
    files += sorted(str(p.relative_to(REPO)) for p in (REPO / 'tests/unit/travel').glob('test_departure*.py'))
    files += sorted(str(p.relative_to(REPO)) for p in (REPO / 'tests/unit/travel/mobility').glob('test_*departure*.py'))
temp = ROOT / '.tmp/mobility_complete_20261008' / ('pytest_late_' + stage)
assert not temp.exists(), temp
cmd = [sys.executable, '-m', 'pytest', '-q', *files, '--junitxml=' + str(EV / (stage + '.xml')),
       '--basetemp=' + str(temp)]
start = time.time()
r = subprocess.run(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'})
with (EV / (stage + '.log')).open('xb') as f:
    f.write(r.stdout)
with (EV / (stage + '-run.json')).open('x', encoding='utf-8') as f:
    json.dump({'command': cmd, 'returncode': r.returncode, 'elapsed_seconds': time.time()-start, 'files': files}, f, indent=2)
shutil.copy2(__file__, EV / (stage + '-runner.py'))
print(r.stdout.decode('utf-8', errors='replace')[-2500:])
print('returncode', r.returncode)
raise SystemExit(r.returncode)
