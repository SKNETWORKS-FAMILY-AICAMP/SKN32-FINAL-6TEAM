"""실제 임시 급행 파일의 늦은 교체에서 안내 INSERT를 확정하지 않는다."""
from copy import deepcopy
import json
import os
from types import SimpleNamespace

import pytest

from app import composition
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import express as EX
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from .test_trip_reminders import world, _at, _reminders, _notices  # noqa: F401
from ..unit.travel.mobility.test_departure_walk_v1 import scene
from ..unit.travel.mobility.test_express_source_reload_v1 import source, write_runs  # noqa: F401
from ..unit.travel.test_departure_assembly_v1 import POLICY


def setup(world, monkeypatch, source):
    write_runs(source)
    runtime, context, _ = scene()
    runtime.express_sources = EX.source_signatures()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True,
        route=lambda *a: {'distance_m': 300}, last_error=None)
    context['basis'] = input_basis(runtime)
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    world['clock'].now = _at('19:20')
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute('UPDATE trips SET party_size=1,constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s',
            (json.dumps({'first_visit': False}), world['tenant'], world['trip_id']))
        trip, items = world['store'].latest(conn, world['trip_id'])
        before, move, after = [next(i for i in items if i.seq == seq) for seq in (9, 10, 11)]
        after.starts_at = _at('19:50')
        for key, item in [('from_place', before), ('to_place', after)]:
            context[key] = {'lat': float(item.place['latitude']), 'lon': float(item.place['longitude'])}
        context['party'] = wiring.party_for_trip(trip)
        context['first_visit'] = False
        move.detail = {**move.detail, 'departure_context': deepcopy(context), 'route_def': {
            'from': before.title, 'to': after.title, 'planned': 'walk',
            'options': [{'id': 'walk', 'label': '도보 이동', 'eta_min': 999, 'uses': []}]}}
        world['store'].append_version(conn, trip_id=world['trip_id'], base_version=trip['version'],
            items=items, reason='express storage race fixture', causes=[])
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=None), guardrails=POLICY)
    return runtime, observer, _reminders(world, departure_observer=observer)


@pytest.mark.parametrize('point', ['after_observation', 'after_insert', 'after_insert_mutates_payload'])
def test_late_express_change_rolls_back_departure_insert(world, monkeypatch, source, point):
    runtime, observer, reminders = setup(world, monkeypatch, source)
    if point == 'after_observation':
        original = reminders._payload

        def changed(*a, **kw):
            payload = original(*a, **kw)
            assert payload['departure_observation']['status'] == 'model_revalidated'
            write_runs(source, 300)
            return payload

        monkeypatch.setattr(reminders, '_payload', changed)
    else:
        original = world['store'].enqueue_message

        def changed(*a, **kw):
            fresh = original(*a, **kw)
            assert fresh
            # 같은 거래에서 INSERT까지 갔으나 아직 COMMIT하지 않은 지점이다.
            write_runs(source, 300)
            if point == 'after_insert_mutates_payload':
                kw['payload']['departure_observation']['basis']['express_version'] = input_basis(
                    SimpleNamespace(timetable_built_at=runtime.timetable_built_at,
                                    rules_version=runtime.rules_version,
                                    express_sources=EX.source_signatures()))['express_version']
            return fresh

        monkeypatch.setattr(world['store'], 'enqueue_message', changed)
    result = reminders.tick()
    assert not result.sent and len(result.stale) == 1 and not result.fatal, result
    assert result.stale[0]['reason'] == 'departure express basis changed'
    assert _notices(world) == []
    with get_connection() as conn:
        trip, _ = world['store'].latest(conn, world['trip_id'])
    assert trip['version'] == 2
    # 옛 저장 문맥은 다음 관측에서 보류된다. 실제 운행 재경로 시험은 아니다.
    runtime.express_sources = EX.source_signatures()
    again = _reminders(world, departure_observer=observer).tick()
    assert not again.sent and len(again.held) == 1 and not again.fatal
    assert again.held[0]['departure_observation']['reason'] == 'basis_changed'


def test_unchanged_express_basis_is_checked_twice_and_enqueued_once(world, monkeypatch, source):
    _, observer, reminders = setup(world, monkeypatch, source)
    calls = []
    validate = observer.validate_basis
    observer.validate_basis = lambda basis: (calls.append(deepcopy(basis)), validate(basis))[1]
    result = reminders.tick()
    assert len(result.sent) == 1 and not result.stale and not result.fatal, result
    assert len(calls) == 2 and calls[0] == calls[1]
    assert len(_notices(world)) == 1
    for _ in range(9):
        assert not reminders.tick().sent
    assert len(calls) == 2 and len(_notices(world)) == 1


@pytest.mark.parametrize('failure_call', [1, 2])
def test_validation_exception_rolls_back_and_reports_fatal(world, monkeypatch, source, failure_call):
    _, observer, reminders = setup(world, monkeypatch, source)
    calls = []
    validate = observer.validate_basis

    def broken(basis):
        calls.append(basis)
        if len(calls) == failure_call:
            raise RuntimeError('secret fixture detail')
        return validate(basis)

    observer.validate_basis = broken
    result = reminders.tick()
    assert not result.sent and not result.stale and len(result.fatal) == 1, result
    assert result.fatal[0]['reason'] == 'departure_basis_unavailable'
    assert 'secret' not in str(result)
    assert _notices(world) == []


@pytest.mark.parametrize('invalid', [None, 1])
def test_invalid_validation_result_is_fatal(world, monkeypatch, source, invalid):
    _, observer, reminders = setup(world, monkeypatch, source)
    observer.validate_basis = lambda basis: invalid
    result = reminders.tick()
    assert not result.sent and len(result.fatal) == 1 and not result.stale, result
    assert _notices(world) == []


def test_metadata_only_change_keeps_content_version_and_notice(world, monkeypatch, source):
    _, _, reminders = setup(world, monkeypatch, source)
    original = reminders._payload

    def changed_metadata(*a, **kw):
        payload = original(*a, **kw)
        stat = source.stat()
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns+1_000_000_000))
        return payload

    monkeypatch.setattr(reminders, '_payload', changed_metadata)
    result = reminders.tick()
    assert len(result.sent) == 1 and not result.stale and not result.fatal, result
    assert len(_notices(world)) == 1
