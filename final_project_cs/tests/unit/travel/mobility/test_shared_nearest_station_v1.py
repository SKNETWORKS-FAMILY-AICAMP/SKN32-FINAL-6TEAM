"""최근접역이 같아도 다른 역 조합을 실제 구간 판정에 넘깁니다."""
import pytest

from .test_station_fallback_v1 import _pair_planner, _opt, A_, B_, ARR, NB


COMMON = ('공통역', 100.0, frozenset({'01호선'}))
LEFT = ('출발보조역', 300.0, frozenset({'01호선'}))
RIGHT = ('도착보조역', 400.0, frozenset({'01호선'}))


def planner_with_lists(a, b, options=None):
    planner, seen = _pair_planner(options or {})
    planner._near_stations = lambda place, limit, k=None: a if place['key'] == 'a' else b
    return planner, seen


@pytest.mark.parametrize('a,b,expected', [
    ([COMMON,LEFT], [COMMON,RIGHT], [(1,0),(0,1),(1,1)]),
    ([COMMON], [COMMON,RIGHT], [(0,1)]),
    ([COMMON,LEFT], [COMMON], [(1,0)]),
    ([COMMON], [COMMON], []),
    ([], [COMMON,RIGHT], []),
    ([COMMON,LEFT], [], []),
])
def test_only_same_physical_station_pairs_are_excluded(a,b,expected):
    planner,_ = planner_with_lists(a,b)
    _sa,_sb,pairs = planner._station_pairs(A_,B_,1200)
    assert [(x[0],x[1]) for x in pairs] == expected


def test_same_name_other_physical_station_keeps_line_identity():
    a = [('양평',100.0,frozenset({'05호선'}))]
    b = [('양평',100.0,frozenset({'경의선'}))]
    planner,_ = planner_with_lists(a,b)
    assert len(planner._station_pairs(A_,B_,1200)[2]) == 1


@pytest.mark.parametrize('success_at', [0,1,2])
def test_public_leg_uses_first_feasible_other_station_pair(success_at):
    planner,seen = planner_with_lists([COMMON,LEFT],[COMMON,RIGHT],
                                      {success_at:[_opt(success_at,650)]})
    got,why = planner.leg(A_,B_,ARR,{},True,'shared-station',not_before_dt=NB)
    assert got is not None,why
    assert seen == list(range(success_at+1))
    assert got[1] == 650


def test_failure_names_reviewed_pairs_instead_of_nearest_only_policy():
    planner,seen = planner_with_lists([COMMON,LEFT],[COMMON,RIGHT])
    got,why = planner.leg(A_,B_,ARR,{},True,'shared-station',not_before_dt=NB)
    assert got is None and seen == [0,1,2]
    assert why['reason'].startswith('검토한 역 짝 3개')
    assert '도보만 본다' not in why['reason']


def test_single_shared_station_has_no_zero_ride_candidate():
    planner,seen = planner_with_lists([COMMON],[COMMON])
    got,why = planner.leg(A_,B_,ARR,{},True,'shared-only')
    assert got is None and not seen
    assert '다른 물리적 역 조합' in why['reason']
