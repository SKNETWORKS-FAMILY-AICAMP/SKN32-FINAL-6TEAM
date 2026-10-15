"""실제 판정 호출에서 필수 승차 경로 누락을 조회 전에 보류한다."""
from copy import deepcopy
import json

import pytest

from .test_departure_observer_v1 import scene as bus_scene, call as bus_call, prediction
from .test_subway_departure_v1 import scene as rail_scene, call as rail_call, source as rail_source


@pytest.mark.parametrize('mode,key', [
    ('bus', 'route'), ('bus', 'from'), ('bus', 'to'),
    ('subway', 'line'), ('subway', 'from'), ('subway', 'to'),
])
def test_required_route_field_missing_is_rejected_before_live_lookup(mode, key):
    runtime, context = bus_scene() if mode == 'bus' else rail_scene()
    option = context['options']['p']
    option.pop('subway_identity', None)  # 이전 저장본도 현재 역 색인으로 판정하는 실제 경로
    del option['legs'][0][key]
    del option['check']['legs'][0][key]
    queried = []
    def source(*a, **kw):
        queried.append(1)
        return (prediction if mode == 'bus' else rail_source)(*a, **kw)
    call = bus_call if mode == 'bus' else rail_call
    got = call(runtime, context, **{mode+'_arrival': source})
    assert got['status'] == 'needs_replan'
    assert got['reason'] == 'route_check_missing_or_changed'
    assert queried == []


def test_empty_subway_mapping_is_not_forwarded_to_actual_verifier():
    runtime, context = rail_scene()
    option = context['options']['p']
    option.pop('subway_identity', None)
    option['legs'] = [{}]
    option['check']['legs'] = [{}]
    got = rail_call(runtime, context, subway_arrival=rail_source)
    assert got['status'] == 'needs_replan'
    assert got['reason'] == 'route_check_missing_or_changed'


@pytest.mark.parametrize('field,value', [('line', None), ('line', ''), ('from', []), ('to', True)])
def test_non_text_subway_identity_is_held(field, value):
    runtime, context = rail_scene()
    option = context['options']['p']
    option.pop('subway_identity', None)
    option['legs'][0][field] = value
    option['check']['legs'][0][field] = value
    got = rail_call(runtime, context,
                    subway_arrival=lambda *a, **kw: pytest.fail('손상 역 식별정보 조회 금지'))
    assert got['status'] == 'needs_replan'
    assert got['reason'] == 'route_check_missing_or_changed'


@pytest.mark.parametrize('mode', ['bus', 'subway'])
def test_empty_later_leg_does_not_query_the_valid_first_vehicle(mode):
    runtime, context = bus_scene() if mode == 'bus' else rail_scene()
    option = context['options']['p']
    option['legs'].append({})
    option['check']['legs'].append({})
    call = bus_call if mode == 'bus' else rail_call
    got = call(runtime, context,
               **{mode+'_arrival': lambda *a, **kw: pytest.fail('후속 구간 손상 경로 조회 금지')})
    assert got['status'] == 'needs_replan'
    assert got['reason'] == 'route_check_missing_or_changed'


@pytest.mark.parametrize('mode', ['bus', 'subway'])
def test_shared_json_round_trip_preserves_both_saved_leg_lists(mode):
    runtime, context = bus_scene() if mode == 'bus' else rail_scene()
    # 두 경로 목록은 같은 저장 detail 안에 함께 직렬화된다.
    restored = json.loads(json.dumps(context))
    assert restored['options']['p']['legs'] == restored['options']['p']['check']['legs']
    before = deepcopy(restored)
    call = bus_call if mode == 'bus' else rail_call
    got = call(runtime, restored, **{mode+'_arrival': prediction if mode == 'bus' else rail_source})
    assert got['status'] == 'realtime'
    assert restored == before


def test_legacy_subway_mode_omission_still_uses_the_valid_subway_path():
    runtime, context = rail_scene()
    option = context['options']['p']
    del option['legs'][0]['mode']
    del option['check']['legs'][0]['mode']
    got = rail_call(runtime, context, subway_arrival=rail_source)
    assert got['status'] == 'realtime'
    assert got['boarding_steps'][0]['service'] == '05호선'
