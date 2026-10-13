"""할인 연결을 비활성화한 별도 프로세스에서 기존 실패를 대조한다."""
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
tag = '2026-10-11_0421_혼합환승_제품운임_연결'
ev = cs / 'wiki/records/evidence' / tag
if '--child' in sys.argv:
    sys.path.insert(0, str(cs))
    from app.domains.travel_ops.instances.mobility.engine import options as O
    O.mixed_fare_estimate = lambda *_args: None
    import pytest
    base = Path(__file__).parent / 'pytest-transfer-baseline-three'
    assert not base.exists()
    raise SystemExit(pytest.main(['tests/unit/travel/mobility/test_plan_v1.py::test_golden',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_contract_keys',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_golden_all_modes',
                                 '-q', '--basetemp=' + str(base),
                                 '--junitxml=' + str(ev / 'baseline-three.xml')]))
sys.stdout.reconfigure(encoding='utf8')
cmd = [sys.executable, str(Path(__file__).resolve()), '--child']
p = subprocess.run(cmd, cwd=cs, env=dict(os.environ, PYTHONIOENCODING='utf8'),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8')
with (ev / 'baseline-three.log').open('x', encoding='utf8') as f:
    f.write(p.stdout)
with (ev / 'baseline-three-run.json').open('x', encoding='utf8') as f:
    json.dump({'command': cmd, 'exit_code': p.returncode,
               'condition': 'mixed_fare_estimate returns None in this isolated Python process'}, f, indent=2)
print(p.stdout[-3000:])
sys.exit(p.returncode)
