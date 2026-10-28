"""실제 23개 고객 문장을 모델→웹 API→격리 DB에 순서대로 재생한다.

명시적인 NAMBU_LIVE_MODEL 환경에서만 실행한다. 이동 계산은 고정 응답이며,
장소 검색은 카카오 실제 응답이다. 외부 알림은 발송하지 않는다.
"""
import json
import os
from pathlib import Path
from datetime import datetime

import pytest

from .test_nambu_progress_web import nambu_scene, latest  # noqa: F401
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _h, _fresh_limit_cache  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_17 = reldate.day("2026-10-17")


@pytest.mark.skipif(os.environ.get('NAMBU_LIVE_MODEL') != '1', reason='명시적 실제 모델 재생에서만 실행')
@pytest.mark.parametrize('_replay',[1,2])
def test_actual_customer_turns_in_order(nambu_scene, monkeypatch, _replay):
    from app.core.settings import get_settings
    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
    from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal
    from app.domains.travel_ops.components.watch.trip_reminders import plan_reminders, ReminderRules

    from .test_nambu_recorded_replay import seed_original
    seed_original(nambu_scene)
    public_seed=os.environ.get('NAMBU_PUBLIC_DINING')
    if public_seed:
        from app.infrastructure.db.session import get_connection
        from tests.helpers.public_dining_replay import seed
        with get_connection() as conn,conn.transaction():
            seeded=seed(conn,public_seed)
        assert seeded>0
    settings = get_settings()
    chat = from_settings(settings)
    assert chat is not None, '실제 해석 모델 설정이 필요하다'
    nambu_scene['decider'].structured = chat.structured

    class Budget:
        count = 0
        def try_reserve(self, _meter):
            self.count += 1
            return self.count <= 30

    budget = Budget()
    kakao = KakaoLocal(api_key=settings.kakao_rest_api_key, budget=budget, timeout=8)
    original = TripDesk.__init__
    def init(self, **kwargs):
        kwargs['edit_lookups'] = lambda: (None, kakao, None)
        original(self, **kwargs)
    monkeypatch.setattr(TripDesk, '__init__', init)

    turns = json.loads((Path(__file__).parents[1]/'fixtures/travel/nambu_field_chat.json').read_text())
    records, failures, checks = [], [], []
    def expect(condition,label):
        checks.append({"label":label,"passed":bool(condition)})
        if not condition:
            failures.append(label)
    scene = nambu_scene
    for index, turn in enumerate(turns,1):
        moment = datetime.fromisoformat(reldate.shift_iso(turn['at']))   # 녹화 시각도 같은 폭으로 옮긴다(`nambu_scene`)
        scene['now']=moment
        response = scene['client'].post(f"/v1/web/trips/{scene['trip']['trip_id']}/messages",
            headers=_h(scene['key']),json={'request_id': f'nambu-replay-{index}',
                'message':reldate.shift_text(turn['message']),'at':moment.isoformat()})
        body = response.json()
        trip, items = latest(scene)
        records.append({'turn':index,'message':reldate.shift_text(turn['message']),'at':moment.isoformat(),
            'http':response.status_code,'status':body.get('status'),'decision':body.get('decision'),
            'answer':body.get('answer'),'outcome':body.get('outcome'), 'version':trip['version'],
            'items':[{'title':i.title,'kind':i.kind,'start':i.starts_at.isoformat(),
                'end':i.ends_at.isoformat() if i.ends_at else None,'execution':i.detail.get('execution'),
                'requested_place':i.detail.get('requested_place'),
                'place_name':(i.place or {}).get('name'),'place_lat':(i.place or {}).get('latitude'),'place_lon':(i.place or {}).get('longitude')} for i in items]})
        expect(response.status_code==200,f'{index}:HTTP')
        if index==2:
            meal=next(i for i in items if i.kind=='dining')
            expect(meal.place is not None and abs(float(meal.place['latitude'])-37.4849)<0.03
                   and abs(float(meal.place['longitude'])-127.0162)<0.03,f'{index}:요청 지역 내 음식 검색')
        if public_seed and index in (3,9):
            expect(body.get('status') in ('adjusted','asked'),f'{index}:공공 원장 대체 추천·변경')
        if index in (6,7,8):
            expect('출발' in (body.get('answer') or '') and '백년옥' in (body.get('answer') or ''),f'{index}:현재 이동 안내')
        if index in (10,11):
            meal=next((i for i in items if i.kind=='dining'),None)
            expect(meal is not None and (meal.detail.get('execution') or {}).get('state')=='arrived',f'{index}:실제 식사 도착')
            expect(meal is not None and '남부터미널' in meal.title,f'{index}:도착 상호의 지역 지점')
        if index==13:
            expect(body.get('outcome',{}).get('state')=='departing',f'{index}:즉시 다이소 이동')
        if index==20:
            daiso=next((i for i in items if '다이소' in i.title and i.kind!='mobility'),None)
            expect(daiso is not None and (daiso.detail.get('execution') or {}).get('state')=='completed',f'{index}:다이소 완료')
            expect(any(i.kind=='mobility' and i.starts_at.hour==21 and i.starts_at.minute==2 for i in items),f'{index}:즉시 다음 이동')
        if index==21:
            expect('이마트' in (body.get('answer') or '') and any('이마트' in i.title for i in items),f'{index}:지정 목적지')
            shop_seq=next(i.seq for i in items if '다이소' in i.title and i.kind!='mobility')
            expect(any(i.kind=='mobility' and '노래방' not in i.title and i.seq>shop_seq for i in items),f'{index}:교체 목적지 이동')
        if index in (20,21):
            from app.domains.travel_ops.components.itinerary.itinerary import TripStore
            from app.infrastructure.db.session import get_connection
            from app.domains.travel_ops.components.watch.trip_reminders import TripReminders
            class NoEvents:
                def affecting(self,_targets):return {}
                def unsupported(self,_uses):return []
            watcher=TripReminders(store=TripStore(scene['tenant']),connection_factory=get_connection,
                clock=lambda:moment,route_events=NoEvents())
            tick=watcher.tick()
            with get_connection() as conn:
                queued=conn.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice' "
                    "AND payload_json->>'kind'='departure' AND payload_json->>'version'=%s",
                    (scene['tenant'],str(trip['version']))).fetchall()
            wanted='이마트' if index==21 else '노래방'
            expect(not tick.fatal and bool(queued) and wanted in queued[0][0]['text'],f'{index}:새 출발 안내 저장')
            records[-1]['departure_notices']=[row[0]['text'] for row in queued]
        if index==22:
            expect(any('이마트' in i.title and (i.detail.get('execution') or {}).get('state')=='completed' for i in items),f'{index}:마지막 실제 방문 완료')
        if index in (22,23):
            expect(not plan_reminders(items,now=datetime.fromisoformat(f'{D_2026_10_17}T21:58:00+09:00'),rules=ReminderRules()),f'{index}:하루 종료 후 안내 종료')
    print('NAMBU_REPLAY_JSON='+json.dumps({'turns':records,'checks':checks,'failures':failures,'kakao_calls':budget.count},ensure_ascii=False,default=str))
    assert not failures, failures
