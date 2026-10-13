from pathlib import Path
import json, os, time, tempfile
from offline_guard_socketpair_v1 import OfflineOnly

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
OUT = ROOT / '.tmp/mobility_finish_20261011/remaining-gate-v5'
OUT.mkdir(exist_ok=False)
TEMP = OUT / 'collection-temp'
TEMP.mkdir()
os.environ['TEMP'] = os.environ['TMP'] = str(TEMP)
tempfile.tempdir = str(TEMP)
import pytest
os.chdir(CS)
args = [
 'tests/unit/travel/mobility/test_walk_comparison_scope_v1.py',
 'tests/unit/travel/mobility/test_walk_comparison_values_v1.py',
 'tests/unit/travel/mobility/test_walk_duration_contract_v1.py',
 'tests/unit/travel/mobility/test_walk_routed_cap.py',
 'tests/unit/travel/mobility/test_walk_timing_replay_v1.py',
 'tests/unit/travel/test_subway_notice.py',
 'tests/unit/travel/test_subway_notice_station_lists_v1.py',
 'tests/contract', 'tests/security', '-q', '--maxfail=8',
 '--basetemp', str(OUT / 'temp'), '--junitxml', str(OUT / 'result.xml')]
start = time.monotonic()
rc = pytest.main(args, plugins=[OfflineOnly()])
(OUT / 'execution.json').write_text(json.dumps({
 'args': args, 'exit_code': int(rc), 'elapsed_s': round(time.monotonic()-start,2),
 'scope': 'v4 early-stop remaining files + notice + contract + security',
 'network': 'blocked except same-thread standard socketpair IPC'}, ensure_ascii=False, indent=2), encoding='utf8')
raise SystemExit(rc)
