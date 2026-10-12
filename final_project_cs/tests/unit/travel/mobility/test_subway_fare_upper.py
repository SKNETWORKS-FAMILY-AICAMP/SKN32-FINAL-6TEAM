"""확정되지 않은 요금과 알려진 거리 범위의 예산 상단을 구분한다."""
from types import SimpleNamespace
from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.verify_time import leg_txt
from tests.unit.travel.mobility.test_fare_est_v1 import _lo, _v, _legs, FARE


def _rides(legs, minute=700):
    return [SimpleNamespace(label=leg_txt(l), depart_min=minute) for l in legs]


def test_distance_crossing_band_keeps_exact_unknown_but_provides_estimated_upper():
    v = _v(_lo(est={('09호선', 'A', 'B'): 4000, ('09호선', 'B', 'C'): 6000}))
    legs = _legs()
    assert O.subway_fare(v, legs, _rides(legs)) is None
    assert O.subway_fare_upper(v, legs, _rides(legs)) == 1650


def test_missing_distance_does_not_turn_into_base_fare():
    v = _v(_lo(est={('09호선', 'A', 'B'): 4000}))
    assert O.subway_fare_upper(v, _legs(), _rides(_legs())) is None


def test_early_bird_boundary_uses_full_base_for_budget():
    v = _v(_lo(est={('09호선', 'A', 'B'): 2000, ('09호선', 'B', 'C'): 3000}))
    legs = _legs()
    assert O.subway_fare(v, legs, _rides(legs, 395)) is None
    assert O.subway_fare_upper(v, legs, _rides(legs, 395)) == 1550
    assert O.subway_fare_upper(v, legs, _rides(legs, 380)) == 1240


def test_unapproved_line_cannot_borrow_estimated_distance_fare():
    v = _v(_lo(est={('09호선', 'A', 'B'): 4000, ('09호선', 'B', 'C'): 6000}))
    v.R = {'fare': {'subway': dict(FARE['subway'], distance_estimate={'value': {'lines': ['02호선'], 'tolerance': .3}})}}
    assert O.subway_fare_upper(v, _legs(), _rides(_legs())) is None
