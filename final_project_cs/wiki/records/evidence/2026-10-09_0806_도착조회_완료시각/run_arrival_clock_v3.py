from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
prior = json.loads((scratch / 'arrival-clock-related-v2.run.json').read_text(encoding='utf8'))['command']
paths = prior[3:prior.index('-q')]
paths += ['tests/unit/travel/mobility/test_arrival_query_assembly_v1.py']
prefix = scratch / 'arrival-clock-related-v3'
assert not Path(str(prefix) + '.log').exists()
cmd = [sys.executable, '-m', 'pytest', *paths, '-q', '--basetemp', str(prefix), '--junitxml', str(prefix) + '.xml']
p = subprocess.run(cmd, cwd=root / 'final_project_cs',
    env=dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch)),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8')
Path(str(prefix) + '.log').write_text(p.stdout, encoding='utf8')
Path(str(prefix) + '.run.json').write_text(json.dumps({'command': cmd, 'exit_code': p.returncode}), encoding='utf8')
print(p.stdout[-6000:])
sys.exit(p.returncode)
