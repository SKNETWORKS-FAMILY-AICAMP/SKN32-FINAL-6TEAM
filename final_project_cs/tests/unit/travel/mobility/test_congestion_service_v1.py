"""9호선 일반·급행 30분 평균을 같은 수치로 바꾸지 않는다. 실제 혼잡 실측 아님."""
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.congestion import Congestion

LEVELS = {'보통': {'gte': 60, 'lt': 80}, '극심': {'gte': 130}}


def fixture_rows():
    return [dict(line='09호선', station_nm='여의도', dir='U', day_type='weekday',
                 slot='08:00', service=service, congestion=value, source_id='controlled')
            for service, value in [('local', 77.1), ('express', 162.5)]]


def controlled(tmp_path):
    path = tmp_path / 'crowd.jsonl'
    path.write_text('\n'.join(json.dumps(r) for r in fixture_rows()), encoding='utf-8')
    return Congestion.load([path])


def test_loader_keeps_both_services_without_key_collision(tmp_path):
    cg = controlled(tmp_path)
    assert len(cg.by_key) == 2


@pytest.mark.parametrize('service,expected', [('local', 77.1), ('express', 162.5), (None, None), ('unknown', None)])
def test_lookup_requires_the_selected_service_for_line9(tmp_path, service, expected):
    cg = controlled(tmp_path)
    hit = cg.lookup('09호선', '여의도', 'U', 'weekday', date(2026, 10, 9), 480,
                    LEVELS, service=service)
    assert (hit[0] if hit else None) == expected


def test_existing_public_line9_rows_all_remain_loaded():
    path = Path(__file__).resolve().parents[5] / 'datasets/mobility/processed/mobility/congestion_line9_v1.jsonl'
    if not path.exists():
        pytest.skip('보유 공개 혼잡도 자료가 없는 환경')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    cg = Congestion.load([path])
    assert cg.rows == len(rows)
    assert {r['service'] for r in cg.by_key.values()} == {'local', 'express'}
    for service, value in [('local', 77.1), ('express', 162.5)]:
        hit = cg.lookup('09호선', '여의도', 'U', 'weekday', date(2026, 10, 9), 480,
                        LEVELS, service=service)
        assert hit[0] == value and hit[2]['service'] == service


def test_verifier_passes_selected_service_into_crowding_lookup():
    from app.domains.travel_ops.instances.mobility.engine.verify_time import Verifier
    received = []
    def lookup(*args, **kwargs):
        received.append(kwargs)
        return None
    verifier = SimpleNamespace(cg_data=SimpleNamespace(lookup=lookup),
                               R={'congestion': {'levels': LEVELS}},
                               _case_date=date(2026, 10, 9), holidays=set())
    assert Verifier._congestion_hit(verifier, '09호선', '여의도', 'U', 'weekday', 480,
                                    {}, 'express') is None
    assert received == [{'is_holiday': False, 'service': 'express'}]


@pytest.mark.parametrize('services,expected', [([True], 'express'), ([False], 'local'),
                                            ([None], None), ([True, False], None), ([True, None], None)])
def test_product_coverage_never_calls_local_data_for_unknown_or_mixed_services(services, expected):
    from app.domains.travel_ops.instances.mobility.engine.options import congestion_checked
    from .test_plan_v1 import _D, _FakeV, _LR
    deps = []
    for express in services:
        dep = _D(480, 'U')
        if express is not None:
            dep.run = SimpleNamespace(express=express, ride_min=lambda a, b: 4)
        deps.append((dep, ['A', 'B', 'C']))
    v = _FakeV(deps)
    seen = []
    def lookup(*args, **kwargs):
        seen.append(kwargs.get('service'))
        return 55, '보통', {}
    v.cg_data = SimpleNamespace(lookup=lookup)
    v.R, v.holidays = {'congestion': {'levels': {}}}, set()
    got = congestion_checked(v, [{'line': '09호선', 'from': 'A', 'to': 'C'}],
                             [_LR('09호선 A→C', 480, 484)], date(2026, 10, 9), 'weekday')
    assert got is (expected is not None)
    assert seen == ([expected] if expected else [])


@pytest.mark.parametrize('services,expected', [([True], ('U', 'express')), ([False], ('U', 'local')),
                                            ([None], ('U', None)), ([True, False], None)])
def test_estimator_matches_service_as_well_as_direction(services, expected):
    from app.domains.travel_ops.instances.mobility.engine.plan_estimate import Estimator
    from .test_plan_v1 import _D, _FakeV
    deps = []
    for express in services:
        dep = _D(480, 'U')
        if express is not None:
            dep.run = SimpleNamespace(express=express, ride_min=lambda a, b: 4)
        deps.append((dep, ['A', 'B', 'C']))
    est = object.__new__(Estimator)
    est.v = _FakeV(deps)
    assert est._dir_of('09호선', 'A', 'C', 'weekday', 480, 484, include_service=True) == expected
