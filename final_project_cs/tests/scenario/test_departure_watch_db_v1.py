"""안내 보류→감시 Case→Controller·이동 Team·일정 적용의 로컬 DB 경로."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app import composition
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances._shared.itinerary_team import ItineraryWork
from app.domains.travel_ops.scenarios.case_engine import CaseEngine
from .test_trip_reminders import world, _at, _NoEvents, _reminders, _notices  # noqa: F401
from ..unit.travel.mobility.test_departure_walk_v1 import scene
from ..unit.travel.test_departure_assembly_v1 import POLICY


@pytest.mark.parametrize('published', [False, True])
def test_legacy_context_replans_through_case_once_or_preserves_announced_move(world, monkeypatch, published):
    runtime, context, _ = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True, route=lambda *a: {'distance_m': 300}, last_error=None)
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    world['clock'].now = _at('19:34')
    with get_connection() as conn, conn.transaction():
        trip, items = world['store'].latest(conn, world['trip_id'])
        before, move, after = [next(i for i in items if i.seq == seq) for seq in (9, 10, 11)]
        move.ends_at = _at('19:33')  # 옛 예정 도착이 지나도 다음 방문 전에는 미발행 이동을 감시한다.
        after.starts_at = _at('19:50')
        for key, item in [('from_place', before), ('to_place', after)]:
            context[key] = {'lat': float(item.place['latitude']), 'lon': float(item.place['longitude'])}
        old_context = deepcopy(context)
        old_context['schema_version'] = 0
        move.detail = {**move.detail, 'departure_context': old_context, 'route_def': {
            'from': before.title, 'to': after.title, 'planned': 'walk',
            'options': [{'id': 'walk', 'label': '도보 이동', 'eta_min': 999, 'uses': []}]}}
        world['store'].append_version(conn, trip_id=world['trip_id'], base_version=trip['version'],
            items=items, reason='legacy departure context fixture', causes=[])
        if published:
            world['store'].enqueue_message(conn, trip_id=world['trip_id'], key=f'departure:{move.item_id}',
                payload={'text': '이미 발행한 출발 안내'})
    engine = CaseEngine(tenant_id=world['tenant'], check=lambda **k: {'verdict': 'clear'},
        route_events=_NoEvents(), classifier=None, report_extractor=None, clock=world['clock'])
    original_moment = ItineraryWork._moment
    monkeypatch.setattr(ItineraryWork, '_moment', staticmethod(lambda value:
        original_moment(value) if value else world['clock']()))
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=None), guardrails=POLICY)
    engine.opener.departure_observer = observer
    got = engine.opener.tick()
    with get_connection() as conn:
        current_trip, current_items = world['store'].latest(conn, world['trip_id'])
    if published:
        assert not got.opened and current_trip['version'] == 2
        assert len(_notices(world)) == 1
        return
    assert len(got.opened) == 1 and len(got.ran) == 1, got
    view = engine.view(got.opened[0]['case_id'])
    assert view['case_status'] == 'resolved' and view['owner_team_id'] == 'mobility', view
    assert current_trip['version'] == 3
    new = next(i for i in current_items if i.seq == 10)
    assert new.item_id != move.item_id and new.starts_at >= world['clock']()
    assert new.detail['departure_context']['schema_version'] == 1
    assert new.detail['planner']['travel_min'] != 999
    for _ in range(9):
        assert not engine.opener.tick().opened
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM customer_cases WHERE tenant_id=%s', (world['tenant'],))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND status='succeeded' "
                    "AND action_type='itinerary.apply'", (world['tenant'],))
        assert cur.fetchone()[0] == 1
    assert len(_notices(world)) == 1  # 일정 변경 통지 1회, 외부 전송은 수행하지 않는다.
    world['clock'].now = new.starts_at
    reminders = _reminders(world, departure_observer=observer)
    got_notice = reminders.tick()
    assert len(got_notice.sent) == 1 and not got_notice.held and not got_notice.fatal, got_notice
    assert len(_notices(world)) == 2
