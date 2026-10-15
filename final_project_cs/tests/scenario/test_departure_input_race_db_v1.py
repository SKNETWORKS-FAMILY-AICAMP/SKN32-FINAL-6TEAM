"""출발 계산 후 일정 판은 유지한 채 인원/조건만 바뀌는 순서를 재현한다."""
from copy import deepcopy
import json

import pytest

from app.infrastructure.db.session import get_connection
from .test_trip_reminders import world, _at, _NoEvents, _reminders, _notices  # noqa: F401


@pytest.mark.parametrize('field', ['size', 'constraints'])
def test_inputs_changed_after_calculation_discard_notice_without_version_change(world, monkeypatch, field):
    world['clock'].now = _at('10:50')
    reminders = _reminders(world, route_events=_NoEvents())
    original = reminders._payload

    def calculate_then_change(*args, **kwargs):
        payload = original(*args, **kwargs)
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            trip, _ = world['store'].latest(conn, world['trip_id'])
            if field == 'size':
                cur.execute('UPDATE trips SET party_size=party_size+1 WHERE tenant_id=%s AND trip_id=%s',
                            (world['tenant'], world['trip_id']))
            else:
                constraints = {**trip['constraints'], 'mobility_ease': 'needs_rest'}
                cur.execute('UPDATE trips SET constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s',
                            (json.dumps(constraints), world['tenant'], world['trip_id']))
        return payload

    monkeypatch.setattr(reminders, '_payload', calculate_then_change)
    outcome = reminders.tick()
    assert not outcome.sent and len(outcome.stale) == 1 and outcome.already == 0, outcome
    assert outcome.stale[0]['reason'] == 'departure trip inputs changed'
    assert _notices(world) == []
    with get_connection() as conn:
        trip, _ = world['store'].latest(conn, world['trip_id'])
    assert trip['version'] == 1
    # 여기서는 모델 재계산의 정확도가 아니라 저장 순서만 검증합니다.
    again = _reminders(world, route_events=_NoEvents()).tick()
    assert len(again.sent) == 1 and not again.stale
    notice = _notices(world)[0][1]
    assert 'expected_departure_inputs' not in notice


def test_snapshot_is_copied_before_observer_mutates_input(world, monkeypatch):
    world['clock'].now = _at('10:50')
    reminders = _reminders(world, route_events=_NoEvents())
    original = reminders._payload

    def calculate_and_mutate_local_input(trip_id, trip, *args, **kwargs):
        payload = original(trip_id, trip, *args, **kwargs)
        trip['constraints']['unrelated_budget_note'] = 'changed only in memory'
        return payload

    monkeypatch.setattr(reminders, '_payload', calculate_and_mutate_local_input)
    result = reminders.tick()
    assert len(result.sent) == 1 and not result.stale


def test_equal_json_with_reordered_keys_is_not_stale(world):
    world['clock'].now = _at('10:50')
    with get_connection() as conn, conn.transaction():
        trip, items = world['store'].latest(conn, world['trip_id'])
        move = next(i for i in items if i.seq == 3)
        inputs = {'party_size': trip['party_size'],
                  'constraints': dict(reversed(list(deepcopy(trip['constraints']).items())))}
        assert world['store'].enqueue_message(conn, trip_id=world['trip_id'],
            key=f'departure:{move.item_id}', payload={'version':trip['version'], 'text':'출발 안내'},
            expected_departure_inputs=inputs)
    assert len(_notices(world)) == 1
