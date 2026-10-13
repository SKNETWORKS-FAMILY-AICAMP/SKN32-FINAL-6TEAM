"""생성한 택시 계획을 현재 시각 모델 재계산과 출발 안내까지 잇는다. 실탑승 아님."""
from copy import deepcopy
from datetime import timedelta

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from app.domains.travel_ops.instances.mobility.engine.car import RouterDown
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from uuid import uuid4

from .test_departure_observer_v1 import NOW
from .test_review_fixes_plan import _rt, PLACES
from ..test_departure_observer_notice_v1 import NoEvents


class TaxiModel:
    def __init__(self):
        self.calls = []
        self.seconds = 600
        self.fare = 12000
        self.distance = 4000
        self.broken = False

    def leg(self, start, end, depart, **kwargs):
        self.calls.append((start, end, depart, kwargs))
        if self.broken:
            raise RouterDown('시험용 도로 경로 조회 실패')
        return {'topis_time_s': self.seconds, 'fare_won': self.fare,
                'distance_m': self.distance, 'grade': '추정', 'source_id': ['test_model']}


def scene():
    runtime = _rt()
    runtime._v.car = TaxiModel()
    planner = Planner(runtime, modes={'taxi'})
    deadline = NOW+timedelta(hours=1)
    got, why = planner.leg(PLACES[0], PLACES[1], deadline, {}, False, 'taxi')
    assert got, why
    runtime._v.car.calls.clear()
    return runtime, planner.departure_context, got[0], deadline


def call(runtime, context, deadline, **kw):
    args = dict(now=NOW, deadline=deadline, origin=PLACES[0], destination=PLACES[1])
    args.update(kw)
    return observe(runtime, context, 'taxi', **args)


def test_generated_taxi_context_is_revalidated_at_current_departure():
    runtime, context, _, deadline = scene()
    before = deepcopy(context)
    assert context['options']['taxi']['path_kind'] == 'direct_taxi'
    runtime._v.car.seconds = 1201
    runtime._v.car.fare = 19000
    result = call(runtime, context, deadline, now=NOW+timedelta(seconds=1))
    assert result['status'] == 'model_revalidated', result
    assert result['departure_at'].endswith('10:01:00+09:00')
    assert result['arrival_at'].endswith('10:22:00+09:00')
    assert result['eta_min'] == 22 and result['fare_krw'] == 19000
    assert len(runtime._v.car.calls) == 1
    assert runtime._v.car.calls[0][2].isoformat() == result['departure_at']
    assert runtime._v.car.calls[0][3] == {'taxi': True}
    assert result['observations'][0]['source_id'] == ['test_model']
    assert context == before


def test_current_taxi_duration_and_fare_reach_notice_without_changing_stored_plan():
    runtime, context, route, deadline = scene()
    runtime._v.car.seconds = 1200
    runtime._v.car.fare = 19000
    result = call(runtime, context, deadline)
    move = Item(item_id=uuid4(), seq=1, kind='mobility', title='택시 이동', place_id=None,
                starts_at=NOW, ends_at=NOW+timedelta(minutes=10), detail={'route_def': route})
    following = Item(item_id=uuid4(), seq=2, kind='activity', title='서울 관람', place_id=None,
                     starts_at=deadline, ends_at=deadline+timedelta(hours=1), detail={})
    before = deepcopy(move)
    status, phrase = build_departure(move, [move, following], route_events=NoEvents(), routes=None,
        now=NOW, departure_observer=lambda *a, **kw: result)
    assert status == 'ok'
    text = phrase.render()
    assert '약 20분' in text and '19,000원' in text and '12,000원' not in text
    assert '현재 시각 기준 예상' in text and '실시간' not in text
    assert move == before


def test_current_taxi_must_meet_operating_margin():
    runtime, context, _, deadline = scene()
    result = call(runtime, context, deadline)
    edge = NOW+timedelta(minutes=result['eta_min']+result['margin_min'])
    assert call(runtime, context, edge)['status'] == 'model_revalidated'
    assert call(runtime, context, edge-timedelta(seconds=1))['reason'] == 'taxi_arrive_late_or_margin'


@pytest.mark.parametrize('marker', [None, 'vehicle', 'unknown'])
def test_legacy_empty_vehicle_is_never_inferred_to_be_taxi(marker):
    runtime, context, _, deadline = scene()
    context['options']['taxi']['path_kind'] = marker
    assert call(runtime, context, deadline)['reason'] == 'route_check_missing_or_changed'
    assert not runtime._v.car.calls


@pytest.mark.parametrize('field', ['check', 'legs'])
def test_inconsistent_taxi_context_is_held(field):
    runtime, context, _, deadline = scene()
    context['options']['taxi'][field] = {} if field == 'check' else [{'mode': 'bus'}]
    assert call(runtime, context, deadline)['reason'] == 'taxi_context_changed'


@pytest.mark.parametrize('fault', ['missing', 'router'])
def test_unavailable_current_taxi_source_never_publishes_saved_estimate(fault):
    runtime, context, _, deadline = scene()
    if fault == 'missing':
        runtime._v.car = None
    else:
        runtime._v.car.broken = True
    assert call(runtime, context, deadline)['status'] == 'fatal'


@pytest.mark.parametrize('field,value', [
    ('seconds', -1), ('seconds', float('nan')), ('seconds', float('inf')), ('seconds', True),
    ('seconds', 1e30), ('fare', None), ('fare', -1), ('fare', True), ('fare', 1.5), ('distance', float('nan')),
])
def test_invalid_current_taxi_model_is_not_published(field, value):
    runtime, context, _, deadline = scene()
    setattr(runtime._v.car, field, value)
    assert call(runtime, context, deadline)['status'] == 'fatal'


def test_changed_party_is_replanned_before_querying_taxi_model():
    runtime, context, _, deadline = scene()
    result = call(runtime, context, deadline, current_party={'size': 4}, current_first_visit=False)
    assert result['reason'] == 'party_changed' and not runtime._v.car.calls


@pytest.mark.parametrize('label', [None, ''])
def test_invalid_current_route_label_is_not_published(label):
    runtime, context, route, deadline = scene()
    result = call(runtime, context, deadline)
    result['route_label'] = label
    move = Item(item_id=uuid4(), seq=1, kind='mobility', title='택시 이동', place_id=None,
                starts_at=NOW, ends_at=NOW+timedelta(minutes=10), detail={'route_def': route})
    following = Item(item_id=uuid4(), seq=2, kind='activity', title='서울 관람', place_id=None,
                     starts_at=deadline, ends_at=deadline+timedelta(hours=1), detail={})
    status, phrase = build_departure(move, [move, following], route_events=NoEvents(), routes=None,
        now=NOW, departure_observer=lambda *a, **kw: result)
    assert status == 'fatal' and phrase is None
