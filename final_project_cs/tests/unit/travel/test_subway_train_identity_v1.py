"""문자 포함 열차번호의 통제 시험. 실탑승·ETA 정확도 측정이 아니다."""
from copy import deepcopy
from datetime import datetime, timedelta

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from .test_subway_boardable_v1 import NOW, policy, select, snapshot, train
from .mobility.test_subway_departure_v1 import scene, call, source


def row(number):
    return dict(train(), train_number=number)


@pytest.mark.parametrize('number', ['A2099', 'X2099', 'a2099', '12A', '001A02', '0005010'])
def test_valid_literal_number_is_preserved_without_operator_or_type_guess(number):
    got = select(snapshot([row(number)]))
    assert got['status'] == 'predicted', got
    assert got['train_number'] == number
    assert got['arrival_at'] == (NOW + timedelta(seconds=180)).isoformat()


@pytest.mark.parametrize('number', [None, True, 2099, 2.5, [], {}, '', ' ', ' A2099',
                                  'A2099 ', 'A 2099', 'A-2099', 'Ａ2099', 'A２０９９', '0000'])
def test_bad_identity_stays_excluded_without_crashing(number):
    got = select(snapshot([row(number)]))
    assert got['status'] == 'no_boardable_prediction'
    assert got['excluded'][0]['reason'] == 'train_identity_missing'


def test_duplicate_literal_number_does_not_invent_a_vehicle():
    got = select(snapshot([row('A2099'), row('A2099')]))
    assert got['status'] == 'no_boardable_prediction'
    assert [x['reason'] for x in got['excluded']] == ['duplicate_train_identity'] * 2


def test_prefix_is_not_removed_to_merge_different_trains():
    first = row('A2099')
    second = dict(row('2099'), eta_seconds=240)
    got = select(snapshot([first, second]))
    assert got['status'] == 'predicted' and got['train_number'] == 'A2099'
    assert got['excluded'] == []


def test_letter_number_does_not_relax_station_ids_or_allow_express():
    assert select(snapshot([row('A2099')]), station_id='A2099')['reason'] == 'boarding_identity_invalid'
    got = select(snapshot([dict(row('A2099'), train_status='급행')]))
    assert got['excluded'][0]['reason'] == 'service_path_mismatch'


@pytest.mark.parametrize('number', ['A2099', 'X2099'])
def test_departure_callback_recheck_accepts_literal_number_and_keeps_path_model(number):
    rt, context = scene()
    before = deepcopy(context)
    def observation(*a, **kw):
        return dict(source(*a, **kw), train_number=number)
    got = call(rt, context, subway_arrival=observation)
    assert got['status'] == 'realtime', got
    assert got['eta_min'] == 13 and got['leg_results'][0]['depart_min'] == 608
    assert got['leg_results'][0]['ride_src'] == 'subway_path_model'
    assert got['observations'][0]['train_number'] == number
    assert context == before


def test_actual_source_normalizer_and_selector_accept_letter_without_extra_http_calls():
    now = datetime.now(NOW.tzinfo)
    calls = []
    path = policy()['allowed_services'][0]['path_station_ids']
    def transport(url, params):
        calls.append(True)
        raw = {'subwayId': policy()['line_id'], 'statnId': path[0], 'statnTid': path[1],
               'bstatnId': path[-1], 'btrainSttus': '일반', 'btrainNo': 'A2099',
               'barvlDt': '200', 'arvlCd': '99', 'recptnDt': now.isoformat()}
        return httpx.Response(200, json={'errorMessage': {'code': 'INFO-000', 'total': 1},
                                        'realtimeArrivalList': [raw]}, request=httpx.Request('GET', url))
    src = SeoulSubwayArrival(service_key='controlled-test-key', transport=transport,
                             now=lambda: now + timedelta(seconds=2))
    got = src.boardable_arrival('양평', **policy(now=now, ready_at=now + timedelta(seconds=100)))
    assert len(calls) == 1 and got['status'] == 'predicted', got
    assert got['train_number'] == 'A2099'


def test_letter_number_reaches_departure_notice_with_new_eta():
    from app.domains.travel_ops.components.watch.trip_reminders import build_departure
    from .test_departure_observer_notice_v1 import NoEvents, scene as notice_scene
    rt, context = scene()
    def observation(*a, **kw):
        return dict(source(*a, **kw), train_number='A2099')
    result = call(rt, context, subway_arrival=observation)
    move, items = notice_scene()
    move.detail['route_def']['options'][0].update(label='지하철', uses=['05호선'])
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None, now=NOW,
                                     departure_observer=lambda *a, **kw: result)
    assert status == 'ok', (status, result)
    assert '약 13분' in phrase.render() and '현재 지하철 대기 반영' in phrase.render()
