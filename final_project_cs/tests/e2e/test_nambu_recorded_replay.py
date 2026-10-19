"""원문 23개를 같은 순서로 실행한다. 해석·검색은 시험용 응답이며 실제 모델 검증이 아니다."""
import json
from pathlib import Path
from datetime import datetime
from uuid import UUID, uuid4

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.intake.reopen_commit import store_place
from app.domains.travel_ops.components.watch.trip_reminders import plan_reminders, ReminderRules
from .test_nambu_progress_web import nambu_scene, latest, at  # noqa: F401
from .test_decision_unit_web import decided  # noqa: F401
from .test_chat_edit_web import _answer
from .test_web_api import api, _h, _fresh_limit_cache  # noqa: F401


def seed_original(scene):
    from dataclasses import replace
    store=TripStore(scene['tenant'])
    trip_id=UUID(scene['trip']['trip_id'])
    with get_connection() as conn,conn.transaction(),conn.cursor() as cur:
        trip,items=store.latest(conn,trip_id)
        meal=next(i for i in items if i.kind=='dining')
        uid=store_place(conn,cur,scene['tenant'],trip_id,name='탐라도야지',kind='dining',
            lat=37.485,lon=127.016,weather_sensitive=False,attributes={'source':'customer_pick'})
        meal=replace(meal,title='거기',place_id=uid)
        visits=[meal if i.kind=='dining' else i for i in items]
        seeded=[]
        clocks=[('20:10','20:20',10),('21:02','21:13',11),('22:08','22:09',1)]
        for position,visit in enumerate(visits):
            seeded.append(replace(visit,seq=position*2+1))
            if position<len(clocks):
                start,end,eta=clocks[position]
                seeded.append(Item(uuid4(),position*2+2,'mobility','기존 도보 이동',None,at(start),at(end),
                    detail={'route_def':{'planned':'walk','options':[{'id':'walk','label':'도보','eta_min':eta,'uses':[]}]},
                            'route_basis':'supplied'}))
        store.append_version(conn,trip_id=trip_id,base_version=trip['version'],
            items=seeded,reason='test_setup',causes=[])


def test_original_23_turns_with_explicit_semantic_responses(nambu_scene, monkeypatch):
    from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
    from app.domains.travel_ops.components.intake import places
    scene=nambu_scene
    seed_original(scene)
    trip_id=UUID(scene['trip']['trip_id'])
    actual_resolve=places.resolve
    def provider(query,**kwargs):
        # A provider miss remains a miss; no invented coordinates for 화화돈/이마트.
        if query in ('돈까스','돈까스 파는 곳'):
            return places.Resolved('resolved','kakao','시험 돈까스 식당',query,'dining',37.485,127.016,needs_review=True)
        if query in ('화화돈','화화동','이마트 슈퍼'):
            return places.Resolved('unresolved',note='시험용 제공처 응답: 위치 확인 불가')
        return actual_resolve(query,**{**kwargs,'tour':None,'kakao':None,'dining':None})
    monkeypatch.setattr(places,'resolve',provider)
    original_init=TripDesk.__init__
    def init(self,**kwargs):
        kwargs['edit_lookups']=lambda:(None,None,None)
        original_init(self,**kwargs)
    monkeypatch.setattr(TripDesk,'__init__',init)
    turns=json.loads((Path(__file__).parents[1]/'fixtures/travel/nambu_field_chat.json').read_text())
    records=[]
    for index,turn in enumerate(turns,1):
        scene['now']=datetime.fromisoformat(turn['at'])
        _,items=latest(scene)
        meal=next((i for i in items if i.kind=='dining'),None)
        meal_name=meal.title if meal else None
        raw={}
        if index in (1,6,7,8):
            action,target='answer_fact',meal_name
            raw={'fact':'detail' if index==1 else 'move'}
        elif index in (2,4):
            action,target='apply_change',meal_name
            raw={'destination_text':'돈까스','change_scope':'mixed' if index==2 else 'place',
                 'minutes':5 if index==2 else 0,'place_text':'남부터미널'}
        elif index in (3,9):
            action,target='propose_alternatives',meal_name
            raw={'change_scope':'place'}
        elif index==5:
            action,target='apply_change',meal_name
            raw={'destination_text':'백년옥','change_scope':'place'}
        elif index in (10,11,12):
            action,target='arrive_item',meal_name
            raw={'destination_text':'화화돈' if index in (10,11) else ''}
        elif index==13:
            action,target='change_time','다이소'
            raw={'anchor_kind':'now'}
        elif index==14:
            action,target='complete_item',meal_name
        elif index in (15,17):
            action,target='arrive_item','다이소'
        elif index==16:
            action,target='remove_item',None
        elif index in (18,19):
            action,target='change_time','다이소'
            raw={'minutes':-5}
        elif index==20:
            action,target='advance_trip','다이소'
        elif index==21:
            action,target='apply_change','노래방'
            raw={'destination_text':'이마트 슈퍼','place_text':'남부터미널','change_scope':'place'}
        else:
            action,target='finish_day', ('이마트' if index==22 else None)
        _answer(scene,action,target=target,**raw)
        response=scene['client'].post(f"/v1/web/trips/{trip_id}/messages",headers=_h(scene['key']),json={
            'request_id':f'original-{index}','message':turn['message'],
            'at':datetime.fromisoformat(turn['at']).isoformat()})
        assert response.status_code==200,response.text
        body=response.json()
        trip,items=latest(scene)
        records.append({'turn':index,'action':(body.get('decision') or {}).get('action'),
            'status':body.get('status'),'version':trip['version'],'answer':body.get('answer'),
            'items':[{'title':i.title,'kind':i.kind,'start':i.starts_at.isoformat()} for i in items]})
        print('NAMBU_RECORDED_TURN='+json.dumps(records[-1],ensure_ascii=False))
        if index==2:
            assert next(i for i in items if i.kind=='dining').starts_at==at('20:25'),body
        if index==10:
            actual=next(i for i in items if i.kind=='dining')
            assert actual.title=='화화돈' and actual.detail['execution']['state']=='arrived',body
        if index==13:
            assert next(i for i in items if i.kind=='dining').detail['execution']['state']=='completed',body
            assert body.get('outcome',{}).get('navigation')=='needs_location',body
        if index==15:
            assert next(i for i in items if i.title=='다이소').starts_at==at('20:54'),body
        if index==20:
            assert next(i for i in items if '다이소' in i.title and i.kind!='mobility').detail['execution']['state']=='completed',body
            assert any(i.kind=='mobility' and i.starts_at==at('21:02') for i in items),body
        if index==21:
            assert any('이마트' in i.title for i in items) and '이마트' in body['answer'],body
        if index==22:
            assert next(i for i in items if '이마트' in i.title).detail['execution']['state']=='completed',body
        if index in (22,23):
            assert not plan_reminders(items,now=at('21:58'),rules=ReminderRules()),body
    print('NAMBU_RECORDED_REPLAY='+json.dumps(records,ensure_ascii=False))
    assert len(records)==23
