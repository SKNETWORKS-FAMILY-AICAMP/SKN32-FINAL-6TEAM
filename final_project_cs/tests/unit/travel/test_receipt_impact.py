import pytest

from app.domains.travel_ops.components.planning.safety import SafetyRules
from app.domains.travel_ops.components.watch.receipt_impact import describe


@pytest.fixture
def rules():
    return SafetyRules(True, frozenset({'긴급재난'}), frozenset({'화재'}), frozenset({'위급재난'}),
                       frozenset({'전쟁'}), ('미사일',), 6, ('훈련',))


def record(rules, **changes):
    args = dict(category='earthquake', status='ok', record_type='api_check', mode='actual',
                trip_id='trip', stage='safety', payload={}, rules=rules)
    args.update(changes)
    return describe(**args)


@pytest.mark.parametrize('magnitude,scope', [(7, 'trip'), (4.5, 'day')])
def test_reuses_existing_safety_scope(rules, magnitude, scope):
    result = record(rules, payload={'disruptions': [{'category': 'earthquake', 'magnitude': magnitude}]})
    assert result['scope'] == scope
    assert result['affects_itinerary'] is True
    assert '실제 적용 여부는 별도' in result['summary']


@pytest.mark.parametrize('changes', [{'mode': 'simulation'}, {'stage': 'simulation_full'},
                                  {'payload': {'simulation_target': True}}])
def test_test_context_is_not_coloured_as_a_real_itinerary_effect(rules, changes):
    args = {'payload': {'disruptions': [{'category': 'earthquake', 'magnitude': 7}]}}
    if 'payload' in changes:
        args['payload'].update(changes['payload'])
    else:
        args.update(changes)
    result = record(rules, **args)
    assert result['scope'] == 'trip'
    assert result['target_mode'] == 'simulation'
    assert result['affects_itinerary'] is False


@pytest.mark.parametrize('kind', ['disaster_message', 'api_receipt'])
def test_receiving_a_message_does_not_prove_it_affects_a_trip(rules, kind):
    result = record(rules, record_type=kind, trip_id=None,
                    payload={'kind': '전쟁', 'text': '위급 상황', 'step': '위급재난'})
    assert result['scope'] == 'unassessed'
    assert result['affects_itinerary'] is False


@pytest.mark.parametrize('status,payload', [('failed', {}), ('not_connected', {}),
    ('ok', {'value': {'partial_from': ['utic']}}), ('ok', {'verdict': 'fatal'})])
def test_unverified_is_never_no_impact(rules, status, payload):
    assert record(rules, status=status, payload=payload)['scope'] == 'unassessed'


def test_another_source_cannot_colour_this_source(rules):
    payload = {'disruptions': [{'category': 'earthquake', 'magnitude': 7}]}
    assert record(rules, category='forecast', payload=payload)['scope'] == 'none'


def test_item_changes_and_forecast_attention_are_not_claimed_as_applied_stops(rules):
    closure = record(rules, category='traffic_control', payload={'disruptions': [{'category': 'traffic_control', 'kind': '전면 통제'}]})
    advisory = record(rules, category='forecast', record_type='mock_input', mode='simulation',
                      payload={'_advisories': [{'category': 'forecast', 'field': 'wind_speed_kmh', 'value': 100}]})
    assert closure['scope'] == advisory['scope'] == 'item'
    assert '정지 완료를 뜻하지 않습니다' in closure['summary']
    assert '주의 안내' in advisory['summary']


def test_non_applicable_and_successful_clear_checks_are_no_impact(rules):
    assert record(rules, status='not_applicable')['scope'] == 'none'
    assert record(rules)['scope'] == 'none'
    assert record(rules, trip_id=None)['scope'] == 'unassessed'
