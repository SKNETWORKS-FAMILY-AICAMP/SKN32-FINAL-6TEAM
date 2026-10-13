"""최신 여행 조건 변경이 안내 보류→Case→새 경로·문맥→재안내로 이어진다."""
from copy import deepcopy
import json
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


@pytest.mark.parametrize('changed', ['size', 'fatigue'])
def test_current_party_change_is_held_then_replanned_and_announced_once(world, monkeypatch, changed):
    runtime, context, _ = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True, route=lambda *a: {'distance_m': 300}, last_error=None)
    # 단독 수집에서도 실제 조립의 설정 키와 합성 이동 상태를 맞춘다.
    composition._configure_mobility(composition.get_settings())
    wiring._STATE.update(mode='enabled',kw={})
    monkeypatch.setattr(wiring.engine_runtime,'get_verifier',lambda **kw: runtime)
    world['clock'].now = _at('19:20')
    constraints = {'first_visit': False, 'survey': {'preferred_mobility': ['도보'], 'on_disruption': 'replace'},
                   'survey_answered': ['on_disruption']}
    if changed == 'fatigue':
        constraints['mobility_ease'] = 'needs_rest'
    size = 2 if changed == 'size' else 1
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        trip, items = world['store'].latest(conn,world['trip_id'])
        before, move, after = [next(i for i in items if i.seq == seq) for seq in (9,10,11)]
        after.starts_at = _at('19:50')
        for key,item in [('from_place',before),('to_place',after)]:
            context[key] = {'lat':float(item.place['latitude']),'lon':float(item.place['longitude'])}
        context['party'] = {'size':1}
        move.detail = {**move.detail,'departure_context':deepcopy(context),'route_def':{
            'from':before.title,'to':after.title,'planned':'walk',
            'options':[{'id':'walk','label':'도보 이동','eta_min':999,'uses':[]}]}}
        world['store'].append_version(conn,trip_id=world['trip_id'],base_version=trip['version'],
            items=items,reason='stored party fixture',causes=[])
        # 격리 시험 여행의 메타데이터만 변경한다. 운영 설정 API를 검증한 것이 아니다.
        cur.execute('UPDATE trips SET party_size=%s,constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s',
            (size,json.dumps(constraints),world['tenant'],world['trip_id']))
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=None),guardrails=POLICY)
    got = _reminders(world,departure_observer=observer).tick()
    assert len(got.held) == 1 and not got.sent and not got.fatal,got
    assert got.held[0]['departure_observation']['reason'] == 'party_changed'
    assert _notices(world) == []
    engine = CaseEngine(tenant_id=world['tenant'],check=lambda **kw:{'verdict':'clear'},
        route_events=_NoEvents(),classifier=None,report_extractor=None,clock=world['clock'])
    original = ItineraryWork._moment
    monkeypatch.setattr(ItineraryWork,'_moment',staticmethod(lambda value:
        original(value) if value else world['clock']()))
    engine.opener.departure_observer = observer
    got_case = engine.opener.tick()
    assert len(got_case.opened) == 1 and len(got_case.ran) == 1,got_case
    view = engine.view(got_case.opened[0]['case_id'])
    assert view['case_status'] == 'resolved',view
    with get_connection() as conn:
        latest,new_items = world['store'].latest(conn,world['trip_id'])
    assert latest['version'] == 3
    new = next(i for i in new_items if i.seq == 10)
    assert new.item_id != move.item_id
    assert new.detail['departure_context']['party'] == wiring.party_for_trip(latest)
    for _ in range(9):
        assert not engine.opener.tick().opened
    world['clock'].now = new.starts_at
    sent = _reminders(world,departure_observer=observer).tick()
    assert len(sent.sent) == 1 and not sent.held and not sent.fatal,sent
    notice = next(p for key,p in _notices(world) if key.startswith('departure:'))
    assert notice['departure_observation']['party_check'] == 'matched'
    assert len(_notices(world)) == 2  # 일정 변경 안내1 + 새 출발 안내1, 실제 외부 전송은 안 함.
