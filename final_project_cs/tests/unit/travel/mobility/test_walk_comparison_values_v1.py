"""잘못된 도보 입력이 제공률과 개발 오차 분모를 오염시키지 않는다."""
from types import SimpleNamespace

import pytest

from scripts.mobility import compare_kakao_golden as comparison


BAD = [True, float('nan'), float('inf'), -1, 0, '5', None]


def row():
    return {'ours_walk_product': {'m': 300, 'min': 5},
            'kakao': {'walk': {'shortest': {'km': .3, 'min': 5}}}}


@pytest.mark.parametrize('value', BAD)
def test_invalid_public_duration_is_an_error_not_an_offered_walk(value):
    result = {'route': {'options': [{'id': 'walk', 'walk_m': 300, 'eta_min': value}]}}
    got = comparison._product_walk(result, None)
    assert got['status'] == 'error' and got['reason'] == 'invalid_walk_values'


@pytest.mark.parametrize('value', BAD)
def test_invalid_product_values_do_not_enter_coverage_or_error_statistics(value):
    item = row()
    item['ours_walk_product']['m'] = value
    got = comparison.summarise([item])
    assert got['coverage']['walk_product_offered'] == 0
    assert got['coverage']['walk_product_invalid'] == 1
    assert got['walk_minutes_vs_kakao_shortest']['n'] == 0


@pytest.mark.parametrize('value', BAD)
def test_invalid_reference_duration_is_counted_and_excluded(value):
    item = row()
    item['kakao']['walk']['shortest']['min'] = value
    got = comparison.summarise([item])
    assert got['coverage']['walk_reference_invalid'] == 1
    assert got['coverage']['walk_product_offered'] == 1
    assert got['coverage']['walk_reference_rows'] == 0
    assert got['walk_distance_percent_vs_kakao_shortest']['n'] == 0


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), -1])
def test_diagnostic_invalid_duration_returns_a_visible_error(value):
    planner = SimpleNamespace(_walk_path=lambda *a, **kw: (300, value, False))
    got = comparison._walk_diagnostic(planner, {}, {}, 280)
    assert got['status'] == 'error' and got['reason'] == 'invalid_walk_values'


def test_error_status_with_numeric_payload_is_not_counted_as_available():
    item = row()
    item['ours_walk_product']['status'] = 'error'
    got = comparison.summarise([item])
    assert got['coverage']['walk_product_offered'] == 0
    assert got['coverage']['walk_product_invalid'] == 1
    assert got['coverage']['walk_product_comparisons'] == 0


def test_one_good_row_survives_invalid_product_and_reference_without_mutation():
    from copy import deepcopy
    good, bad_product, bad_reference = row(), row(), row()
    bad_product['ours_walk_product']['min'] = -1
    bad_reference['kakao']['walk']['shortest']['km'] = '0.3'
    inputs = [good, bad_product, bad_reference]
    old = deepcopy(inputs)
    got = comparison.summarise(inputs)
    assert got['coverage']['pairs'] == 3
    assert got['coverage']['walk_product_offered'] == 2
    assert got['coverage']['walk_product_invalid'] == 1
    assert got['coverage']['walk_reference_invalid'] == 1
    assert got['coverage']['walk_product_comparisons'] == 1
    assert got['walk_minutes_vs_kakao_shortest']['median'] == 0
    assert inputs == old
