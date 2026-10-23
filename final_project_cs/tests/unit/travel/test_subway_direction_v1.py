"""공식 방면 이름과 원문 인접ID의 통제 대조. 실탑승·ETA 정확도 자료 아님."""
from copy import deepcopy

import pytest

from .test_subway_boardable_v1 import NEXT, PATH, STATION, TERMINAL, select, snapshot, train

PREVIOUS = '1005000521'


def service():
    return dict(deepcopy(PATH), next_station_names=['영등포구청'],
                terminal_station_names=['하남검단산'], boarding_neighbor_ids=[PREVIOUS, NEXT])


def observed(**changes):
    row = train()
    row.update(next_station_id=PREVIOUS, previous_station_id=NEXT,
               route_label='하남검단산행 - 영등포구청방면')
    row.update(changes)
    return row


def test_swapped_source_neighbors_use_exact_route_names_and_preserve_raw_ids():
    data = snapshot([observed()]); original = deepcopy(data)
    got = select(data, allowed_services=[service()])
    assert got['status'] == 'predicted', got
    assert got['next_station_id'] == NEXT
    assert got['provider_next_station_id'] == PREVIOUS
    assert got['provider_previous_station_id'] == NEXT
    assert got['direction_basis'] == 'route_label_and_neighbor_ids'
    assert data == original


@pytest.mark.parametrize('changes', [
    {'route_label': '하남검단산행 - 당산방면'},
    {'route_label': '마천행 - 영등포구청방면'},
    {'route_label': None}, {'route_label': '하남검단산행 - 영등포구청방면 '},
    {'route_label': '하남검단산행 - 영등포구청방면 (급행)'},
    {'route_label': '영등포구청'},
    {'previous_station_id': STATION}, {'next_station_id': STATION},
    {'previous_station_id': []}, {'next_station_id': '999999'},
    {'terminal_station_id': '99999'}, {'train_status': '급행'},
])
def test_label_neighbor_terminal_or_kind_conflict_is_not_corrected(changes):
    got = select(snapshot([observed(**changes)]), allowed_services=[service()])
    assert got['status'] == 'no_boardable_prediction', got
    assert got['excluded'][0]['reason'] == 'service_path_mismatch'


def test_already_departed_is_not_boardable_after_route_correction():
    got = select(snapshot([observed(arrival_code='2', eta_seconds=0)]), allowed_services=[service()])
    assert got['status'] == 'no_boardable_prediction'
    assert got['excluded'][0]['reason'] == 'departed_or_unknown_state'


def test_old_generation_is_not_fresh_after_route_correction():
    got = select(snapshot([observed(received_at='2026-10-09 09:50:00')]), allowed_services=[service()])
    assert got['excluded'][0]['reason'] == 'provider_refresh_required'


def test_opposite_neighbor_pair_without_official_names_keeps_old_strict_rule():
    got = select(snapshot([observed()]))
    assert got['status'] == 'no_boardable_prediction'


def test_direct_neighbor_with_contradicting_route_label_is_excluded():
    got = select(snapshot([observed(next_station_id=NEXT, previous_station_id=PREVIOUS,
                                    route_label='마천행 - 당산방면')]), allowed_services=[service()])
    assert got['status'] == 'no_boardable_prediction'


@pytest.mark.parametrize('field,value', [('next_station_names', []),
    ('terminal_station_names', '하남검단산'), ('boarding_neighbor_ids', [NEXT, NEXT]),
    ('boarding_neighbor_ids', [STATION, NEXT])])
def test_invalid_new_service_metadata_is_rejected(field, value):
    path = service();path[field] = value
    assert select(snapshot([observed()]), allowed_services=[path])['reason'] == 'service_path_invalid'


def test_callback_rechecks_raw_direction_evidence():
    from app.domains.travel_ops.instances.mobility.engine.subway_departure import matched_service
    got = select(snapshot([observed()]), allowed_services=[service()])
    identity = {k: got[k] for k in ('line_id', 'station_id', 'target_station_id')}
    assert matched_service(got, identity, [service()]) == service()
    for changes in ({'provider_previous_station_id': TERMINAL},
                    {'route_label': '마천행 - 당산방면'},
                    {'direction_basis': None},
                    {'provider_next_station_id': '999999'}):
        assert matched_service(dict(got, **changes), identity, [service()]) is None
    without_label = dict(got)
    without_label.pop('route_label')
    assert matched_service(without_label, identity, [service()]) is None


def test_product_service_generation_and_departure_use_corrected_neighbor():
    from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
    from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder
    from app.domains.travel_ops.instances.mobility.engine.subway_identity import SubwayStationIndex
    from .mobility.test_subway_departure_v1 import call, scene

    rt, context = scene()
    doc = deepcopy(rt._v.lo.doc)
    line = doc['lines']['05호선']
    line['stations'].append({'station_nm': '오목교'})
    line['edges'].append({'a': '오목교', 'b': '양평', 'grade': '확정', 'travel_min': 3,
                          'travel_min_grade': '추정', 'dir_a_to_b': 'U', 'dir_b_to_a': 'D'})
    rt._v.lo = LineOrder(doc)
    stations = [rt.subway_stations.lookup('05호선', name) for name in ('양평', '영등포구청', '영등포시장')]
    stations.append({'line_id': '1005', 'station_id': PREVIOUS, 'line': '5호선',
                     'station': '오목교', 'query_station': '오목교'})
    rt.subway_stations = SubwayStationIndex({'schema_version': '1.0', 'station_count': 4,
                                              'line_count': 1, 'stations': stations}, content_sha256='b' * 64)
    context['basis'] = input_basis(rt)
    seen = []

    def arrival(station, **kw):
        path = max(kw['allowed_services'], key=lambda s: len(s['path_station_ids']))
        assert set(path['boarding_neighbor_ids']) == {PREVIOUS, NEXT}
        row = observed(terminal_station_id=path['path_station_ids'][-1], eta_seconds=480,
                       received_at=kw['now'].isoformat(),
                       route_label=path['terminal_station_names'][0] + '행 - 영등포구청방면')
        got = select(snapshot([row]), **kw)
        seen.append(got)
        return got

    got = call(rt, context, subway_arrival=arrival)
    assert got['status'] == 'realtime', got
    assert got['eta_min'] == 13 and got['leg_results'][0]['depart_min'] == 608
    assert seen[0]['next_station_id'] == NEXT and seen[0]['provider_next_station_id'] == PREVIOUS
