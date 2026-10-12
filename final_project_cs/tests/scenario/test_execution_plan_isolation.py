"""실제 조립·적용 경계의 장애 격리·재시도·경합. 자료와 모델은 명시적 시험 대역이다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from app.core.actions import ActionConflict, ActionRejected
from app.core.service_bindings import bind_services
from app.domains.travel_ops.components.actions.itinerary_actions import ItineraryApply
from app.domains.travel_ops.components.itinerary.itinerary import item_to_dict
from app.domains.travel_ops.components.planning import guardian
from app.domains.travel_ops.components.planning.safety import classify
from app.domains.travel_ops.components.watch.safety_pause import SafetyPauses
from app.infrastructure.db.session import get_connection
from tests.unit.travel.execution_plan_fixture import fixture_plan
from .test_case_version_day import case_world  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_watch_batch import (SKY, LUNCH, ROAD, FATAL, _engine, _tick, _outbox,
                               _latest, _versions, guardrails)  # noqa: F401 — guardrails 는 픽스처


def _arguments(world):
    trip, items = _latest(world)
    item = next(i for i in items if i.kind == 'activity')
    new = item.replaced_by(place=item.place, title=item.title + ' (확인됨)')
    return item, {'trip_id':str(world['trip_id']), 'base_version':trip['version'],
                  'reason':'auto_adjusted', 'causes':[], 'notice':{'text':'일정 확인 결과를 반영했어요.'},
                  'replacements':[{'item_id':str(item.item_id), 'item':item_to_dict(new)}]}


def _apply(world, arguments):
    with bind_services(world['engine'].controller.service_bindings), get_connection() as conn, conn.transaction():
        return ItineraryApply().apply(conn, tenant_id=world['tenant'], customer_id=world['customer'],
                                      case_id=None, arguments=arguments)


def test_discovery_failure_keeps_only_affected_item_and_recovers_next_tick(case_world):
    world = case_world
    first = _tick(_engine(world, {SKY:FATAL, LUNCH:ROAD}))
    assert len(first.fatal) == 1 and len(first.opened) == 1
    assert [v[0] for v in _versions(world)] == [1,2]
    assert SKY in {i.place['name'] for i in _latest(world)[1] if i.place}
    deferred = [p for _,p in _outbox(world) if p.get('deferred')]
    assert len(deferred) == 1 and '기존 일정을 유지' in deferred[0]['text']
    second = _tick(_engine(world, {SKY:FATAL}))
    assert second.fatal and not second.notified
    recovered = _tick(_engine(world, {SKY:ROAD}))
    assert len(recovered.opened) == 1
    assert SKY not in {i.place['name'] for i in _latest(world)[1] if i.place}
    assert [v[0] for v in _versions(world)] == [1,2,3]


def test_discovery_exception_does_not_abort_independent_item(case_world):
    def broken():
        raise TimeoutError('private upstream response')
    result = _tick(_engine(case_world, {SKY:broken, LUNCH:ROAD}))
    assert result.fatal and len(result.opened) == 1
    deferred = [p for _,p in _outbox(case_world) if p.get('deferred')]
    assert len(deferred) == 1 and 'TimeoutError' in deferred[0]['text']
    assert 'private upstream' not in deferred[0]['text']


def test_classification_failure_has_no_fixed_order_fallback_and_recovers(case_world, guardrails):
    guardrails.update({'travel.watch.retry_cooldown_seconds':0, 'travel.watch.retry_max':3})
    engine = _engine(case_world, {SKY:ROAD, LUNCH:ROAD})
    def broken(**kwargs):
        raise TimeoutError('model unavailable')
    engine.controller.team_executor.planner = broken
    first = _tick(engine)
    assert first.ran[0]['status'] == 'escalated'
    assert [v[0] for v in _versions(case_world)] == [1]
    notices = _outbox(case_world)
    assert len(notices) == 1 and len(notices[0][1]['deferred']) == 2
    engine.controller.team_executor.planner = fixture_plan
    second = _tick(engine)
    assert second.retried and second.ran[0]['status'] == 'resolved'
    assert [v[0] for v in _versions(case_world)] == [1,2]
    third = _tick(engine)
    assert not third.opened and len(_versions(case_world)) == 2


def test_concurrent_proposals_from_same_version_write_only_once(case_world):
    _, arguments = _arguments(case_world)
    barrier = Barrier(2)
    def contender():
        barrier.wait(timeout=10)
        try:
            _apply(case_world, arguments)
            return 'applied'
        except ActionConflict:
            return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:contender(), range(2)))
    assert sorted(results) == ['applied','stale']
    assert [v[0] for v in _versions(case_world)] == [1,2]


def test_setting_changed_during_calculation_rejects_old_batch_notice(case_world):
    item, arguments = _arguments(case_world)
    arguments['batch'] = {'applied':[str(item.item_id)], 'causes':{}}
    with get_connection() as conn, conn.transaction():
        guardian.set_enabled(conn, tenant_id=case_world['tenant'], trip_id=case_world['trip_id'],
                             customer_id=case_world['customer'], enabled=False, via='settings')
    with pytest.raises(ActionConflict, match='guardian or protection'):
        _apply(case_world, arguments)
    assert len(_versions(case_world)) == 1 and not _outbox(case_world)


def test_expired_legacy_safety_pause_stays_active_until_manual_resume(case_world):
    world = case_world
    pauses = SafetyPauses(world['tenant'])
    now = world['clock']()
    event = classify([{'category':'earthquake','magnitude':4.5,'at':now.isoformat(),'location':'서울'}])
    assert event is not None
    with get_connection() as conn, conn.transaction():
        pause_id = pauses.open(conn, trip_id=world['trip_id'], event=event, day=now.date(),
            from_at=now-timedelta(days=2), until_at=now-timedelta(days=1), guidance={})
        assert pause_id
    _, arguments = _arguments(world)
    with get_connection() as conn:
        assert pauses.active(conn, world['trip_id'], now=now+timedelta(days=2))
        assert world['trip_id'] not in world['store'].active_trip_ids(conn, now=now)
    with pytest.raises(ActionRejected, match='safety_pause_requires_customer_resume'):
        _apply(world, arguments)
    assert len(_versions(world)) == 1
    with get_connection() as conn, conn.transaction():
        assert pauses.resume(conn, trip_id=world['trip_id'], via='web', by=world['customer']) == 1
        assert not pauses.active(conn, world['trip_id'])
    _apply(world, arguments)
    assert len(_versions(world)) == 2
