"""실사용 순서의 진행 요청을 HTTP·DB·알림 선택기까지 통과시킨다.

해석과 이동 계산은 시험용 고정 응답이다. 실제 모델·경로 확인과 구분한다.
"""
from datetime import datetime
import pytest
from uuid import UUID

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.watch.trip_reminders import plan_reminders, ReminderRules

from .test_decision_unit_web import decided  # noqa: F401
from .test_chat_edit_web import _answer
from .test_trip_reopen import _member, _trip_of
from .test_web_api import api, _h, _fresh_limit_cache  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_17 = reldate.day("2026-10-17")


def at(clock):
    return datetime.fromisoformat(f'{D_2026_10_17}T'+clock+':00+09:00')


def say(scene, message, action, target=None, **raw):
    _answer(scene, action, target=target, **raw)
    response = scene['client'].post(f"/v1/web/trips/{scene['trip']['trip_id']}/messages",
        headers=_h(scene['key']), json={'request_id': scene['request_id'], 'message': message,
                                        'at': scene['now'].isoformat()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['status'] in ('adjusted', 'already_applied', 'duplicate'), body
    assert body['case_status'] == 'resolved', body
    return body


def latest(scene):
    with get_connection() as conn:
        return TripStore(scene['tenant']).latest(conn, UUID(scene['trip']['trip_id']))


@pytest.fixture()
def nambu_scene(decided, api, monkeypatch):
    _member(api, decided['key'])
    places = [('n', '남부터미널', 37.4849, 127.0162), ('b', '백년옥', 37.4806, 127.0110),
              ('d', '다이소 남부터미널점', 37.4845, 127.0155), ('k', '남부터미널 노래방', 37.4847, 127.0158)]
    visits = [(1, 'n', '남부터미널', '20:00', '20:10', 'activity'),
              (2, 'b', '백년옥 식사', '20:20', '20:58', 'dining'),
              (3, 'd', '다이소', '21:25', '22:08', 'activity'),
              (4, 'k', '노래방', '22:10', '23:40', 'activity')]
    trip = _trip_of(decided, decided['key'], places, [
        {'seq': seq, 'kind': kind, 'title': title, 'place': place, 'starts_at': at(start).isoformat(),
         'ends_at': at(end).isoformat()} for seq,place,title,start,end,kind in visits], 'nambu-field')
    # The generic trip helper labels every place activity. This fixture has a restaurant.
    with get_connection() as conn,conn.transaction():
        conn.execute("UPDATE places SET kind='dining' WHERE tenant_id=%s AND name='백년옥'", (api['tenant'],))
    from tests.helpers.plugin_bindings import publish_fixed_mobility
    publish_fixed_mobility(decided['client'].app,arrival_buffer_min=2,source='nambu_progress_fixture')
    scene = {**decided, 'trip': trip, 'tenant': api['tenant'], 'now': at('20:22'), 'request_id': 'meal-arrival'}
    # Historical replay uses the request clock for all review comparisons.
    from app.domains.travel_ops.components.intake import review
    class RequestClock(datetime):
        @classmethod
        def now(cls,tz=None):
            value=scene['now']
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(review,'datetime',RequestClock)
    return scene


def test_reported_meal_arrival_daiso_arrival_exit_and_home_update_one_current_plan(nambu_scene, monkeypatch):
    from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
    monkeypatch.setattr(TripDesk, 'find_place', lambda *a, **kw: None)
    scene = nambu_scene
    # Lookup is injected separately; the HTTP handler must preserve a customer-named
    # place even if an external provider cannot resolve its coordinates.
    say(scene, '화화돈 이라는 식당에 왔어', 'arrive_item', '백년옥', destination_text='화화돈')
    _, items = latest(scene)
    meal = next(i for i in items if i.kind == 'dining')
    assert meal.title == '화화돈' and meal.detail['execution']['state'] == 'arrived'
    assert meal.place_id is None and meal.detail['requested_place']['name'] == '화화돈'
    scene.update(now=at('20:54'), request_id='daiso-arrival')
    say(scene, '밥 다 먹었으니까 완료표시하고 지금 다이소라고', 'arrive_item', '다이소')
    _, items = latest(scene)
    meal = next(i for i in items if i.kind == 'dining')
    daiso = next(i for i in items if i.title == '다이소')
    assert meal.ends_at == at('20:54') and meal.detail['execution']['state'] == 'completed'
    assert daiso.starts_at == at('20:54')
    scene.update(now=at('21:02'), request_id='daiso-exit')
    body = say(scene, '다이소에서 나왔어 이제 다음 일정 진행시켜', 'advance_trip', '다이소')
    _, items = latest(scene)
    assert next(i for i in items if i.title == '다이소').ends_at == at('21:02')
    assert body['outcome']['departure_at'] == at('21:02').isoformat(), body
    assert next(i for i in items if i.kind == 'mobility' and i.starts_at == at('21:02'))
    version = latest(scene)[0]['version']
    say(scene, '다이소에서 나왔어 이제 다음 일정 진행시켜', 'advance_trip', '다이소')
    assert latest(scene)[0]['version'] == version
    from types import SimpleNamespace
    from app.domains.travel_ops.components.watch.notice_routing import CustomerNoticeRouter
    from app.infrastructure.messaging.worker import OutboxWorker
    store = TripStore(scene['tenant'])
    trip_id = UUID(scene['trip']['trip_id'])
    with get_connection() as conn, conn.transaction():
        trip, pending_items = store.latest(conn, trip_id)
        move = next(i for i in pending_items if i.kind == 'mobility' and i.starts_at == at('21:02'))
        following = next(i for i in pending_items if i.title == '노래방')
        assert store.enqueue_message(conn, trip_id=trip_id, key='queued-before-home', payload={
            'type':'guidance','kind':'departure','version':trip['version'],
            'item_id':str(move.item_id),'text':'이전 노래방 출발 안내'})
        assert store.enqueue_message(conn, trip_id=trip_id, key='source-before-home', payload={
            'type':'guidance','kind':'source_failed','items':[str(following.item_id)],'text':'이전 조회 실패 안내'})
    scene.update(now=at('21:09'), request_id='home')
    say(scene, '지금은 집에 왔어 오늘 하루 일정은 이걸로 끝이야', 'finish_day')
    _, items = latest(scene)
    assert not plan_reminders(items, now=at('21:58'), rules=ReminderRules())
    assert all(i.detail.get('execution', {}).get('state') in ('completed', 'skipped') for i in items)
    router = CustomerNoticeRouter(operator=lambda _m: None,connection_factory=get_connection,
        enabled=lambda:True,renderer=SimpleNamespace(text_for=lambda p:p['text']),allowed_tenants={scene['tenant']})
    worker = OutboxWorker(get_connection,router,tenant_id=scene['tenant'])
    for _ in range(30):
        if not worker.process_once():
            break
    with get_connection() as conn:
        rows=conn.execute("SELECT status,last_error FROM outbox WHERE tenant_id=%s AND dedupe_key=ANY(%s)",
            (scene['tenant'],[f'{trip_id}:queued-before-home',f'{trip_id}:source-before-home'])).fetchall()
    assert len(rows)==2 and all(row[0]=='skipped' and '완료·교체' in row[1] for row in rows), rows
