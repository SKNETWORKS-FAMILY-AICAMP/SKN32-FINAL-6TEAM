from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
paths = ['tests/unit/travel/mobility/test_arrival_query_clock_v1.py',
         'tests/unit/travel/mobility/test_departure_observer_v1.py',
         'tests/unit/travel/mobility/test_departure_source_to_notice_v1.py',
         'tests/unit/travel/test_bus_boardable_arrival_v1.py',
         'tests/unit/travel/test_bus_boardable_source_v1.py',
         'tests/unit/travel/test_seoul_bus_arrival.py',
         'tests/unit/travel/test_seoul_bus_shared_cache_v1.py',
         'tests/unit/travel/test_departure_observer_notice_v1.py',
         'tests/unit/travel/mobility/test_departure_walk_v1.py',
         'tests/unit/travel/test_departure_assembly_v1.py']
prefix = scratch / 'arrival-clock-related-v2'
assert not Path(str(prefix) + '.log').exists()
cmd = [sys.executable, '-m', 'pytest', *paths, '-q', '--basetemp', str(prefix), '--junitxml', str(prefix) + '.xml']
p = subprocess.run(cmd, cwd=root / 'final_project_cs',
    env=dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch)),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8')
Path(str(prefix) + '.log').write_text(p.stdout, encoding='utf8')
Path(str(prefix) + '.run.json').write_text(json.dumps({'command': cmd, 'exit_code': p.returncode}), encoding='utf8')
print(p.stdout[-5000:])
sys.exit(p.returncode)
