from datetime import datetime
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.planning.safety import SafetyRules
from app.domains.travel_ops.components.watch.receipt_impact import describe
from app.domains.travel_ops.components.watch.receipt_notice import review
from app.domains.travel_ops.ports.data_sources.disaster_msg import _covers
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
from app.domains.travel_ops.ports.data_sources.notice_area import place_area, relation

MESSAGE = {'category': 'disaster_msg', 'kind': '기타', 'step': '안전안내',
           'text': '오늘 금천구 행사장에서 불꽃 행사가 열립니다. 소음과 연기에 유의해 주세요.',
           'regions': ['서울특별시 금천구'], 'created_at': '2026-10-17T18:00:00+09:00'}
PLACE = {'name': '서초구 시험 활동장소', 'latitude': 37.48, 'longitude': 127.04}
RULES = SafetyRules(True, frozenset({'긴급재난'}), frozenset({'화재'}), frozenset({'위급재난'}),
                    frozenset({'전쟁'}), ('미사일',), 6, ('훈련',))


def impact(payload):
    return describe(category='disaster_msg', status='ok', record_type='api_check', mode='actual',
                    trip_id='trip', stage='schedule', payload=payload, rules=RULES)


def test_other_district_event_keeps_content_and_exclusion_reason_without_red_impact():
    payload = {'review_target': {**PLACE, 'basis_source': 'current_saved_place'},
               'value': {'for_region': [MESSAGE]}, 'disruptions': [MESSAGE]}
    result = review(payload)
    assert result['target']['district'] == '서초구'
    assert result['target']['basis_source'] == 'current_saved_place'
    assert result['messages'][0]['text'] == MESSAGE['text']
    assert result['messages'][0]['regions'] == ['서울특별시 금천구']
    assert result['unrelated'] == 1 and result['matched'] == 0
    assert impact(payload)['scope'] == 'none'
    assert not impact(payload)['affects_itinerary']
    assert '달라' in impact(payload)['summary']


def test_known_matching_event_keeps_its_influence_and_does_not_claim_application():
    message = {**MESSAGE, 'regions': ['서울특별시 서초구'], 'text': '서초구 시험 장소 주변 도로 통제'}
    result = impact({'target_place': place_area(PLACE), 'value': {'for_region': [message]}, 'disruptions': [message]})
    assert result['scope'] == 'item' and result['affects_itinerary']
    assert '정지 완료를 뜻하지 않습니다' in result['summary']


@pytest.mark.parametrize('target,message', [({}, MESSAGE), (PLACE, {**MESSAGE, 'regions': []}),
    ({'district': ['서초구', '금천구'], 'district_basis': 'box_ambiguous'}, MESSAGE)])
def test_missing_or_ambiguous_geography_never_becomes_green_or_red(target, message):
    result = impact({'target_place': target, 'value': {'for_region': [message]}, 'disruptions': [message]})
    assert result['scope'] == 'unassessed' and not result['affects_itinerary']


def test_address_precedes_rough_coordinates_and_all_overlap_candidates_are_retained():
    result = place_area({**PLACE, 'attributes': {'address': '서울특별시 금천구 시험로'}})
    assert result['district'] == '금천구' and result['district_basis'] == 'address'
    overlap = place_area({'latitude': 37.52, 'longitude': 126.91})
    assert isinstance(overlap['district'], list) and overlap['district_basis'] == 'box_ambiguous'


@pytest.mark.parametrize('target,regions', [('broken', [None]), ({'district': 'unknown'}, 'not-an-array')])
def test_malformed_historical_geography_is_unassessed(target, regions):
    message = {**MESSAGE, 'regions': regions}
    result = review({'review_target': target, 'value': {'for_region': [message]}})
    assert result['unassessed'] == 1 and result['matched'] == 0


@pytest.mark.parametrize('region', ['서울특별시', '서울특별시 전체', '서울특별시전체'])
def test_whole_city_alert_is_not_lost_when_district_is_known(region):
    assert _covers([region], '서울', '서초구')
    assert relation([region], place_area(PLACE)) == 'matched'


@pytest.mark.parametrize('region', ['서울특별시 금천구', '서울특별시 금천구 전체', '서울특별시금천구전체'])
def test_whole_district_alert_stays_inside_that_district(region):
    assert not _covers([region], '서울', '서초구')
    assert _covers([region], '서울', '금천구')
    assert _covers([region], '서울', ['서초구', '금천구'])
    assert relation([region], {'region': '서울', 'district': '서초구'}) == 'unrelated'
    assert relation([region], {'region': '서울', 'district': '금천구'}) == 'matched'
    assert relation([region], {'region': '서울', 'district': ['서초구', '금천구']}) == 'unassessed'
    assert relation([region], {'region': '서울', 'district': ['서초구', '강남구']}) == 'unrelated'
    assert relation([region], {'region': '서울'}) == 'unassessed'


def test_multiple_district_tokens_cover_all_ambiguous_candidates_without_becoming_citywide():
    regions = ['서울특별시 서초구 전체', '서울특별시 금천구 전체']
    assert relation(regions, {'region': '서울', 'district': ['서초구', '금천구']}) == 'matched'
    assert relation(regions, {'region': '서울', 'district': '강남구'}) == 'unrelated'


@pytest.mark.parametrize('serials', [(1, 2), (None, None), (1, 1)])
def test_identical_text_and_time_do_not_merge_distinct_receipt_regions(serials):
    outside = {**MESSAGE, 'serial': serials[0]}
    inside = {**MESSAGE, 'serial': serials[1], 'regions': ['서울특별시 서초구']}
    payload = {'target_place': place_area(PLACE), 'value': {'for_region': [outside, inside]},
               'disruptions': [outside, inside]}
    result = review(payload)
    assert len(result['messages']) == 2
    assert result['matched'] == result['unrelated'] == 1
    assert impact(payload)['scope'] == 'item'


@pytest.mark.parametrize('field', ['advisories', '_advisories'])
def test_both_stored_advisory_formats_keep_message_and_matching_region(field):
    message = {**MESSAGE, 'regions': ['서울특별시 서초구']}
    payload = {'target_place': place_area(PLACE), field: [message]}
    assert review(payload)['matched'] == 1
    assert review(payload)['messages'][0]['text'] == message['text']
    assert impact(payload)['scope'] == 'item'


def test_unrelated_severe_cause_cannot_borrow_matching_regions_from_same_text():
    outside = {**MESSAGE, 'serial': 1, 'kind': '화재', 'step': '긴급재난'}
    inside = {**MESSAGE, 'serial': 2, 'regions': ['서울특별시 서초구']}
    payload = {'target_place': place_area(PLACE), 'value': {'for_region': [outside, inside]},
               'disruptions': [outside, inside]}
    assert impact(payload)['scope'] == 'item'


def test_old_cause_without_region_only_inherits_a_uniquely_identified_receipt():
    inside = {**MESSAGE, 'serial': 1, 'regions': ['서울특별시 서초구']}
    unknown = {**inside, 'serial': None, 'regions': []}
    payload = {'target_place': place_area(PLACE), 'value': {'for_region': [inside]}, 'disruptions': [unknown]}
    assert len(review(payload)['messages']) == 1
    assert impact(payload)['scope'] == 'item'
    outside = {**inside, 'regions': ['서울특별시 금천구']}
    payload['value']['for_region'] = [outside]
    assert len(review(payload)['messages']) == 1
    assert impact(payload)['scope'] == 'none'


def test_old_cause_cannot_inherit_a_region_when_distinct_receipts_share_text_and_time():
    inside = {**MESSAGE, 'serial': 1, 'regions': ['서울특별시 서초구']}
    outside = {**MESSAGE, 'serial': 2}
    unknown = {**MESSAGE, 'regions': []}
    payload = {'target_place': place_area(PLACE), 'value': {'for_region': [inside, outside]}, 'disruptions': [unknown]}
    assert len(review(payload)['messages']) == 3
    assert review(payload)['unassessed'] == 1
    assert impact(payload)['scope'] == 'unassessed'


def test_disruption_lookup_uses_coordinates_when_explicit_district_is_missing():
    calls = []

    class Source:
        def active(self, **kwargs):
            calls.append(kwargs)
            return {'covered': True, 'source': 'synthetic', 'district': kwargs['district'], 'for_region': []}

    result = DisruptionCheck(SimpleNamespace(disaster=Source()))._disaster(
        PLACE, datetime.fromisoformat('2026-10-17T19:00:00+09:00'), '서울', True)
    assert calls[0]['district'] == '서초구'
    assert result['target_place']['district_basis'] == 'box'
    assert result['status'] == 'ok' and result['_disruptions'] == []


def test_unverified_local_message_is_held_but_confirmed_citywide_emergency_remains():
    class Source:
        messages = [MESSAGE]

        def active(self, **kwargs):
            return {'covered': True, 'source': 'synthetic', 'for_region': self.messages}

    source = Source()
    check = DisruptionCheck(SimpleNamespace(disaster=source))
    result = check._disaster({}, None, '서울', True)
    assert result['status'] == 'failed' and result['_disruptions'] == []
    city = {**MESSAGE, 'kind': '화재', 'regions': ['서울특별시 전체'], 'text': '도시 전체 긴급 경보'}
    source.messages = [MESSAGE, city]
    result = check._disaster({}, None, '서울', True)
    assert result['status'] == 'ok'
    assert [item['text'] for item in result['_disruptions']] == [city['text']]
    assert result['value']['partial_from'] == ['target_area']
