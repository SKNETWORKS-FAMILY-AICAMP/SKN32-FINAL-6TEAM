"""정확 도착 시각을 쓴 승차편이 후속 안내에서도 같은 편성으로 식별되는지 확인한다."""
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.train_precision import TrainPrecision
from app.domains.travel_ops.instances.mobility.engine.verify_time import Dep, Verifier


def candidate(arrival, code='A'):
    doc = {'schema_version': 1, 'runs': [
        {'line': '02호선', 'day_type': 'weekday', 'dir': 'U', 'train_code': code,
         'stops': [['강남', 39090, 39120], ['교대', arrival, 39290], ['성수', 43200, None]]}]}
    row = {'line': '02호선', 'station_nm': '강남', 'day_type': 'weekday',
           'dir': 'U', 'dep_time': '10:52:00', 'dest_nm': '성수'}
    return Dep(652, 'U', '성수', precision=TrainPrecision(doc).match(row), departure_sec=39120)


def verifier(departures):
    v = Verifier.__new__(Verifier)
    v.lo = SimpleNamespace(travel_min_on_path=lambda *args: 2.2)
    path = SimpleNamespace(path=['강남', '교대', '성수'])
    v.candidates = lambda *args: ([(d, path, False) for d in departures], {}, False)
    return v


LEG = {'line': '02호선', 'from': '강남', 'to': '교대'}


def test_official_arrival_keeps_selected_train_when_legacy_model_disagrees():
    d = candidate(39210)
    result = SimpleNamespace(verdict='feasible', depart_min=652, arrive_min=654, arrival_sec=39210)
    assert [x[0] for x in O.chosen_departures(verifier([d]), LEG, result, 'weekday')] == [d]


def test_same_display_minute_does_not_merge_distinct_exact_arrivals():
    correct, other = candidate(39210), candidate(39220, 'B')
    result = SimpleNamespace(verdict='feasible', depart_min=652, arrive_min=654, arrival_sec=39210)
    assert [x[0] for x in O.chosen_departures(verifier([other, correct]), LEG, result, 'weekday')] == [correct]


def test_legacy_without_exact_arrival_keeps_conservative_selection():
    d = Dep(652, 'U', '성수')
    result = SimpleNamespace(verdict='feasible', depart_min=652, arrive_min=655)
    assert [x[0] for x in O.chosen_departures(verifier([d]), LEG, result, 'weekday')] == [d]


def test_estimator_crowding_direction_uses_the_same_exact_arrival():
    from app.domains.travel_ops.instances.mobility.engine.plan_estimate import Estimator
    correct, other = candidate(39210), candidate(39220, 'B')
    other.dir = 'D'
    est = Estimator.__new__(Estimator)
    est.v = verifier([other, correct])
    assert est._dir_of('02호선', '강남', '교대', 'weekday', 652, 654,
                       arrival_sec=39210) == 'U'
    # 정확초가 없는 옛 결과에서는 같은 표시분의 양방향을 임의로 고르지 않는다.
    assert est._dir_of('02호선', '강남', '교대', 'weekday', 652, 654) is None
