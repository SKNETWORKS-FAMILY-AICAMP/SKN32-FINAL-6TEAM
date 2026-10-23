"""명시적인 내일 미루기·두 날 교체를 공통 수정 경로로 검사한다."""
from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from .test_nambu_progress_web import nambu_scene, latest, at, say  # noqa: F401
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401


def test_one_day_trip_can_be_explicitly_postponed_to_tomorrow(nambu_scene):
    scene=nambu_scene
    scene.update(now=at('19:50'),request_id='postpone-daiso')
    say(scene,'다이소 일정을 내일로 미뤄 줘','change_time','다이소',at_day='tomorrow')
    _, items=latest(scene)
    moved=next(i for i in items if i.title=='다이소')
    assert moved.starts_at.date()==(at('19:50')+timedelta(days=1)).date()
    assert moved.starts_at.hour==21 and moved.starts_at.minute==25


def test_two_days_swap_preserves_both_visits(nambu_scene):
    scene=nambu_scene
    store=TripStore(scene['tenant'])
    with get_connection() as conn,conn.transaction():
        trip,items=store.latest(conn,UUID(scene['trip']['trip_id']))
        today=next(i for i in items if i.title=='다이소')
        tomorrow=replace(today,item_id=uuid4(),seq=max(i.seq for i in items)+1,title='내일 쇼핑',
            starts_at=at('10:00')+timedelta(days=1),ends_at=at('10:43')+timedelta(days=1))
        store.append_version(conn,trip_id=UUID(scene['trip']['trip_id']),base_version=trip['version'],
            items=[*items,tomorrow],reason='test_setup',causes=[])
    scene.update(now=at('19:50'),request_id='swap-tomorrow')
    say(scene,'내일 쇼핑 하나 골라서 다이소랑 바꿔 줘','swap_order','다이소',anchor='내일 쇼핑',anchor_kind='item')
    _,items=latest(scene)
    first=next(i for i in items if i.title=='다이소')
    second=next(i for i in items if i.title=='내일 쇼핑')
    assert first.starts_at==tomorrow.starts_at
    assert second.starts_at==today.starts_at
    assert len([i for i in items if i.kind!='mobility'])==5
