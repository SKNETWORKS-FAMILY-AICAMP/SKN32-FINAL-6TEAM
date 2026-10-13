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
    import socket
    calls = []
    def deny(*args, **kwargs):
        calls.append(1)
        raise RuntimeError('오프라인 시험의 통신을 차단했습니다')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    from app.domains.travel_ops.instances.mobility.engine import runtime
    original = runtime.build_verifier
    def offline(**kwargs):
        kwargs.setdefault('local_router', True)
        kwargs.setdefault('seoul_key', '')
        kwargs.setdefault('gh_url', '')
        return original(**kwargs)
    runtime.build_verifier = offline
    from app.domains.travel_ops.instances.mobility.engine import options as O
    O.mixed_fare_estimate = lambda *_args: None
    import pytest
    base = Path(__file__).parent / 'pytest-transfer-baseline-seven'
    assert not base.exists()
    code = pytest.main(['tests/unit/travel/mobility/test_plan_v1.py::test_golden',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_contract_keys',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_golden_all_modes',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_option_ids_mode_tag',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_bus_from_place_recheck',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_replan_fare_known_locked',
                                 'tests/unit/travel/mobility/test_plan_v1.py::test_bus_cap_zero_keeps_planned',
                                 '-q', '--basetemp=' + str(base),
                                 '--junitxml=' + str(ev / 'baseline-seven.xml')])
    (ev / 'baseline-seven-network.json').write_text(json.dumps({'blocked_network_attempts': len(calls)}), encoding='utf8')
    raise SystemExit(code)
sys.stdout.reconfigure(encoding='utf8')
cmd = [sys.executable, str(Path(__file__).resolve()), '--child']
p = subprocess.run(cmd, cwd=cs, env=dict(os.environ, PYTHONIOENCODING='utf8'),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8')
with (ev / 'baseline-seven.log').open('x', encoding='utf8') as f:
    f.write(p.stdout)
with (ev / 'baseline-seven-run.json').open('x', encoding='utf8') as f:
    json.dump({'command': cmd, 'exit_code': p.returncode,
               'condition': 'mixed_fare_estimate returns None in this isolated Python process'}, f, indent=2)
print(p.stdout[-3000:])
sys.exit(p.returncode)
