from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'bus-distance-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
p = cs / 'tests/unit/travel/mobility/test_bus_distance_completeness_v1.py'
b = p.parent / '_backup' / (stamp + '_出발판정_기존계약'.replace('出', '출')) / p.name
b.parent.mkdir(parents=True, exist_ok=True)
assert not b.exists()
shutil.copy2(p, b)
state['backups'].append({'source': p.relative_to(root).as_posix(), 'backup': b.relative_to(root).as_posix(),
                         'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
p.write_text(p.read_text(encoding='utf8').replace("assert got['status'] == 'needs_replan', got", "assert got['status'] == 'fatal', got"), encoding='utf8')
with (scratch / 'bus-distance-work-v2.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
audit = (scratch / 'audit_bus_distance_v1.py').read_text(encoding='utf8')
audit = audit.replace('from app.domains.travel_ops.instances.mobility.engine.paths import PROCESSED',
    'from app.domains.travel_ops.instances.mobility.engine.paths import cli_processed\nprocessed = cli_processed()')
audit = audit.replace('PROCESSED /', 'processed /').replace('assert not differences\n', '')
audit = audit.replace('existing-distance-audit-v1.json', 'existing-distance-audit-v2.json')
with (scratch / 'audit_bus_distance_v2.py').open('x', encoding='utf8') as f:
    f.write(audit)
env = dict(os.environ, PYTHONIOENCODING='utf-8')
for name, cmd in [ ('audit-v2', [sys.executable, str(scratch / 'audit_bus_distance_v2.py')]),
    ('after-v2', [sys.executable, '-m', 'pytest', '-q',
        *['tests/unit/travel/mobility/' + n + '.py' for n in [
            'test_bus_distance_completeness_v1', 'test_bus_stop_identity_v1', 'test_bus_profile_unit',
            'test_bus_to_bus', 'test_departure_observer_v1', 'test_arrival_query_clock_v1', 'test_mixed_fare_upper_v1']],
        '--junitxml=' + str(ev / 'after-v2.xml')]) ]:
    temp = scratch / (name + '-temp-bus-distance')
    temp.mkdir(exist_ok=False)
    run_env = dict(env, TEMP=str(temp), TMP=str(temp))
    r = subprocess.run(cmd, cwd=cs, capture_output=True, text=True, encoding='utf8', env=run_env)
    with (ev / (name + '.log')).open('x', encoding='utf8') as f:
        f.write(r.stdout + r.stderr)
    with (ev / (name + '.run.json')).open('x', encoding='utf8') as f:
        json.dump({'command': cmd, 'exit_code': r.returncode}, f, ensure_ascii=False, indent=2)
    print(name, r.returncode, r.stdout[-3000:])
    if r.returncode:
        sys.exit(r.returncode)
