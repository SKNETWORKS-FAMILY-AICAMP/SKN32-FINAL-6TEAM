"""현재 재탐색은 오래된 출발 시각·인원·저장 후보를 다시 쓰지 않는다."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, NoChange
from app.domains.travel_ops.instances.mobility.team import plan_mobility_trigger
from .test_route_reroute_engine import _scene, T


@pytest.mark.parametrize('batch', [False, True])
@pytest.mark.parametrize('result_kind', ['fresh', 'no_path', 'no_data', 'old_time', 'no_context'])
def test_single_and_batch_replan_with_current_time_and_party(monkeypatch, batch, result_kind):
    before, move, after, _ = _scene()
    # 안내 전 대상이지만 처리 지연으로 감시 시각보다 2분 늦었다.
    current = T('10:52')
    trip = {'party_size': 6, 'constraints': {'survey': {'walking': 'limited'}}}
    seen = {}
    move.detail['route_def']['options'][0]['uses'] = []
    fresh_route = {'from': before.title, 'to': after.title, 'planned': 'fresh',
        'options': [{'id': 'fresh', 'label': '현재 계산 경로', 'eta_min': 5, 'uses': []}]}

    def planner(size, constraints, **kwargs):
        seen.update(party_size=size, constraints=deepcopy(constraints))
        def leg(a, b, deadline, start_floor):
            seen.update(start_floor=start_floor, origin=a, destination=b)
            if result_kind in ('no_path', 'no_data'):
                return None, {'code': result_kind}
            got = {'route': fresh_route, 'starts_at': current, 'ends_at': current+timedelta(minutes=5),
                   'eta_min': 5, 'departure_context': {'schema_version': 1, 'timing_unit': 'model_minutes',
                                                      'selected_option_id': 'fresh'}}
            if result_kind == 'old_time':
                got['starts_at'] = T('10:50')
            if result_kind == 'no_context':
                got.pop('departure_context')
            return got, None
        return leg
    monkeypatch.setattr(legs, 'leg_planner', planner)
    entry = {'item_id': str(move.item_id), 'categories': ['departure_revalidation'], 'detected': 'departure'}
    trigger = {'batch': [entry], 'detected': 'batch'} if batch else entry
    task = SimpleNamespace(context=SimpleNamespace(current_state={'trigger': trigger}))
    work = SimpleNamespace(_moment=lambda value: current,
        _read=lambda *a: pytest.fail('확인할 사건 대상 없는 경로는 사건 소스를 요구하지 않습니다'),
        _evidence=lambda *a, value, base, **k: [*base, value],
        _escalate=lambda *a, **k: 'fatal_source_failure')
    ctx = {'items': [before, move, after], 'at': T('10:50'), 'trip': trip, 'seen': set(), 'evidence': []}
    got = plan_mobility_trigger(work, task, ctx, move)
    assert seen['start_floor'] == current and seen['party_size'] == 6 and seen['constraints'] == trip['constraints']
    if result_kind == 'fresh':
        assert isinstance(got, ItineraryChange)
        new = next(iter(got.replacements.values()))
        assert new.starts_at == current and new.detail['departure_context']['selected_option_id'] == 'fresh'
        assert new.detail['route_def'] == fresh_route and new.item_id != move.item_id
    elif result_kind == 'no_path':
        assert isinstance(got, NoChange) and got.status == 'unresolved'
        assert ctx['evidence'] == [{'code': 'no_path'}]
    else:
        assert got == 'fatal_source_failure'
