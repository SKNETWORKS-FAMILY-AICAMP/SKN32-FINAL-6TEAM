"""부분 순환선이 없는 간선을 만들거나 단방향을 거꾸로 타지 않게 한다."""
from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder


def fixture_order():
    # A→B→C→A 고리에 A↔D↔E 꼬리가 붙는다. 번호순 C→D는 없다.
    pairs = [('A', 'B', 'D', None), ('B', 'C', 'D', None),
             ('C', 'A', 'D', None), ('A', 'D', 'D', 'U'), ('D', 'E', 'D', 'U')]
    edges = [dict(a=a, b=b, dir_a_to_b=fwd, dir_b_to_a=rev,
                  grade='확정', travel_min=2) for a, b, fwd, rev in pairs]
    return LineOrder({'built_at': 'test', 'lines': {'L': {
        'is_loop': True, 'dir_label': {'reliable': True},
        'direction': {'D': {'fr_order': 'asc', 'grade': '확정'}},
        'stations': [dict(station_nm=n, fr_order=i) for i, n in enumerate('ABCDE')],
        'edges': edges}}})


def test_partial_loop_includes_actual_join_and_ride_time():
    lo = fixture_order()
    verdict = lo.passes('L', 'B', 'E', 'D', dir='D')
    assert verdict.value is True
    assert verdict.path == ['B', 'C', 'A', 'D', 'E']
    assert lo.travel_min_on_path('L', verdict.path, 'D') == 6


def test_partial_loop_does_not_invent_reverse_connection():
    lo = fixture_order()
    assert lo.passes('L', 'C', 'E', 'B', dir='D').value is False


def test_partial_loop_requires_direction_evidence():
    lo = fixture_order()
    assert lo.passes('L', 'B', 'E', 'D').value is None
    assert lo.passes('L', 'B', 'E', 'D', dir='U').value is None


def test_complete_loop_keeps_directional_wrap():
    lo = fixture_order()
    doc = lo.doc['lines']['L']
    doc['stations'] = doc['stations'][:3]
    doc['edges'] = doc['edges'][:3]
    lo = LineOrder(lo.doc)
    verdict = lo.passes('L', 'C', 'B', 'A', dir='D')
    assert verdict.value is True
    assert verdict.path == ['C', 'A', 'B']


def test_unknown_direction_after_alighting_does_not_discard_known_prefix():
    lo = fixture_order()
    lo.doc['lines']['L']['edges'][-1]['dir_a_to_b'] = None
    verdict = lo.passes('L', 'A', 'E', 'D', dir='D')
    # A→D는 확인됨. D에서 내리므로 그 뒤 D→E 시간은 더하지 않는다.
    assert verdict.value is True
    assert verdict.path == ['A', 'D']
    assert lo.travel_min_on_path('L', verdict.path, 'D') == 2
