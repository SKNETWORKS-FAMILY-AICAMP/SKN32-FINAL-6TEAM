"""급행 내용 판 변경이 안내 보류·재계산·새 문맥·한 번 안내로 이어진다."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app import composition
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import express as EX
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances._shared.itinerary_team import ItineraryWork
from app.domains.travel_ops.scenarios.case_engine import CaseEngine
from .test_trip_reminders import world, _at, _NoEvents, _reminders, _notices  # noqa: F401
from ..unit.travel.mobility.test_departure_walk_v1 import scene
from ..unit.travel.mobility.test_departure_express_basis_v1 import inputs
from ..unit.travel.test_departure_assembly_v1 import POLICY


@pytest.mark.parametrize('saved', ['tracked', 'legacy'])
def test_express_basis_change_replans_and_announces_once(world, monkeypatch, saved):
    runtime, context, _ = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True,
        route=lambda *a: {'distance_m': 300}, last_error=None)
    runtime.express_sources = inputs()
    if saved == 'tracked':
        context['basis'] = input_basis(runtime)
    # 먼저 실제 조립의 프로세스 설정 키를 준비한 뒤 합성 계산기를 꽂는다.
    composition._configure_mobility(composition.get_settings())
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: runtime)
    # 이 시험은 합성 내용 판의 저장 흐름이다. 실제 파일 읽기 교체는 별도 경합 시험이 맡는다.
    monkeypatch.setattr(EX, 'source_signatures', lambda: runtime.express_sources)
    world['clock'].now = _at('19:20')
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        # 무작위 시험 테넌트의 여행만 조정한다. 운영 설정 API나 실운행 시험이 아니다.
        cur.execute('UPDATE trips SET party_size=1,constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s',
            (json.dumps({'first_visit': False, 'survey': {'preferred_mobility': ['도보'], 'on_disruption': 'replace'},
                         'survey_answered': ['on_disruption']}),
             world['tenant'], world['trip_id']))
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
            items=items, reason='stored express version fixture', causes=[])
    runtime.express_sources = inputs('b')
    observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='fixture'),
        SimpleNamespace(bus_arrival=None), guardrails=POLICY)
    held = _reminders(world, departure_observer=observer).tick()
    assert len(held.held) == 1 and not held.sent and not held.fatal, held
    assert held.held[0]['departure_observation']['reason'] == 'basis_changed'
    assert _notices(world) == []
    engine = CaseEngine(tenant_id=world['tenant'], check=lambda **kw: {'verdict': 'clear'},
        route_events=_NoEvents(), classifier=None, report_extractor=None, clock=world['clock'])
    original = ItineraryWork._moment
    monkeypatch.setattr(ItineraryWork, '_moment', staticmethod(lambda value:
        original(value) if value else world['clock']()))
    engine.opener.departure_observer = observer
    changed = engine.opener.tick()
    assert len(changed.opened) == 1 and len(changed.ran) == 1, changed
    assert engine.view(changed.opened[0]['case_id'])['case_status'] == 'resolved'
    with get_connection() as conn:
        latest, new_items = world['store'].latest(conn, world['trip_id'])
    assert latest['version'] == 3
    new = next(item for item in new_items if item.seq == 10)
    assert new.item_id != move.item_id
    assert new.detail['departure_context']['basis'] == input_basis(runtime)
    for _ in range(9):
        assert not engine.opener.tick().opened
    world['clock'].now = new.starts_at
    sent = _reminders(world, departure_observer=observer).tick()
    assert len(sent.sent) == 1 and not sent.held and not sent.fatal, sent
    assert len(_notices(world)) == 2  # 일정 변경1·새 출발1. 외부 채널 발송은 하지 않는다.
