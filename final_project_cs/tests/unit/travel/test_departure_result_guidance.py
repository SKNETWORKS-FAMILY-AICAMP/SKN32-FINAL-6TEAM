"""자료 누락·조회 불가를 실제 경로 부재로 안내하지 않는다. 외부 호출·일정 변경은 없다."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.itinerary.itinerary_changes import (
    DepartureReplanUnavailable,
    NoChange,
    plan_departure_adjustment,
)
from app.domains.travel_ops.components.planning.pending import _cause_text, unresolved_notice
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.instances.mobility.team import plan_mobility_trigger
from .test_route_reroute_engine import T, _scene


@pytest.mark.parametrize('code', ['arrive_late', 'before_first', 'service_gap', 'after_last', 'no_path', 'no_walk_path'])
def test_infeasible_route_keeps_original_reason_without_changing_schedule(monkeypatch, code):
    before, move, after, _ = _scene()
    original = deepcopy(move.detail)
    why = {'code': code, 'reason': '현재 시각 이후 출발로는 목표 도착에 맞지 않음',
           'left_out': [{'code': 'before_prev_end', 'reason': '후보 시간 불성립'}]}
    monkeypatch.setattr(legs, 'leg_planner', lambda *a, **k: lambda *a: (None, why))
    got = plan_departure_adjustment(item=move, previous=before, following=after, events={}, now=T('10:52'), trip={})
    assert isinstance(got, NoChange) and got.status == 'unresolved'
    assert got.detail['departure_replan'] == why
    why['left_out'][0]['reason'] = '호출자 변경'
    assert got.detail['departure_replan']['left_out'][0]['reason'] == '후보 시간 불성립'
    assert move.detail == original


@pytest.mark.parametrize('why', [
    {'code': 'no_data', 'reason': '자료 부족'},
    {'code': 'walk_source_unavailable', 'reason': '보행망 조회 실패'},
    {'code': 'earliest_unconfirmed', 'reason': '탐색 한도로 확인 불가'},
    {'code': 'unrecognized_failure', 'reason': '새 오류'},
    None,
])
def test_unavailable_or_unknown_result_is_not_no_alternate(monkeypatch, why):
    before, move, after, _ = _scene()
    monkeypatch.setattr(legs, 'leg_planner', lambda *a, **k: lambda *a: (None, why))
    with pytest.raises(DepartureReplanUnavailable) as found:
        plan_departure_adjustment(item=move, previous=before, following=after, events={}, now=T('10:52'), trip={})
    assert found.value.report == (why if isinstance(why, dict) else {'code': 'invalid_replan_result'})


@pytest.mark.parametrize('missing', ['previous', 'following', 'coordinates'])
def test_missing_route_input_is_unavailable_before_engine_query(monkeypatch, missing):
    before, move, after, _ = _scene()
    if missing == 'coordinates':
        before.place = None
    monkeypatch.setattr(legs, 'leg_planner', lambda *a, **k: pytest.fail('입력이 없는 경로를 조회하면 안 됩니다'))
    with pytest.raises(DepartureReplanUnavailable) as found:
        plan_departure_adjustment(item=move, previous=None if missing == 'previous' else before,
            following=None if missing == 'following' else after, events={}, now=T('10:52'), trip={})
    assert found.value.report['code'] == ('current_place_missing' if missing == 'coordinates' else 'adjacent_visit_missing')


@pytest.mark.parametrize('batch', [False, True])
@pytest.mark.parametrize('code', ['arrive_late', 'walk_source_unavailable'])
def test_single_and_batch_keep_replan_reason_in_case_evidence(monkeypatch, batch, code):
    before, move, after, _ = _scene()
    move.detail['route_def']['options'][0]['uses'] = []
    why = {'code': code, 'reason': '계산 원문 사유', 'left_out': [{'code': 'failed', 'reason': '후보 확인 사유'}]}
    monkeypatch.setattr(legs, 'leg_planner', lambda *a, **k: lambda *a: (None, why))
    entry = {'item_id': str(move.item_id), 'categories': ['departure_revalidation']}
    trigger = {'batch': [entry]} if batch else entry
    task = SimpleNamespace(context=SimpleNamespace(current_state={'trigger': trigger}))
    work = SimpleNamespace(_moment=lambda value: T('10:52'),
        _read=lambda *a: pytest.fail('조회 대상 없는 운행 사건은 읽지 않습니다'),
        _evidence=lambda *a, value, base, **k: [*base, {'value': value}],
        _escalate=lambda *a, **k: 'fatal_source_failure')
    ctx = {'items': [before, move, after], 'at': T('10:50'), 'trip': {}, 'seen': set(), 'evidence': []}
    got = plan_mobility_trigger(work, task, ctx, move)
    assert ctx['evidence'][-1]['value'] == why
    assert (isinstance(got, NoChange) and got.status == 'unresolved') if code == 'arrive_late' else got == 'fatal_source_failure'


def test_missing_context_and_confirmed_road_fact_are_both_reported():
    causes = [{'category': 'departure_revalidation', 'kind': 'context_missing_or_version'},
              {'category': 'traffic_control', 'message': '확인된 도로 전면 통제'}]
    text = _cause_text(causes)
    assert '저장 자료가 없거나 형식이 맞지 않아요' in text
    assert '확인된 도로 전면 통제' in text
    assert 'context_missing_or_version' not in text


@pytest.mark.parametrize('recheck', [False, True])
def test_departure_notice_uses_route_words_without_claiming_no_place_or_road_event(recheck):
    _, move, _, _ = _scene()
    notice = unresolved_notice(item=move,
        causes=[{'category': 'departure_revalidation', 'kind': 'context_missing_or_version'}], recheck_failed=recheck)
    assert '이동 경로' in notice['text'] and '저장 자료' in notice['text']
    assert '대신 갈 수 있는 곳' not in notice['text']
    assert '도로가 통제' not in notice['text']
    assert notice['kind'] == ('recheck_failed' if recheck else 'no_alternate')
    assert notice['type'] == 'guidance'
