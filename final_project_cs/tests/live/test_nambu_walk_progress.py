"""실제 적재된 보행망으로 즉시 이동→출발 문구까지 계산한다. 실시간 외부 관측은 아니다."""
import os
from datetime import datetime
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation.journey_progress import plan
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.watch.departure_revalidation import build_observer
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from app.domains.travel_ops.instances.mobility import wiring


@pytest.mark.skipif(os.environ.get('NAMBU_REAL_MOBILITY')!='1',reason='실제 보행망을 읽기 전용으로 붙인 시험에서 실행')
def test_current_walking_graph_and_departure_guidance_agree():
    wiring.configure(data_dir='/data/mobility/processed',gh_url='',seoul_key='',local_router=True)
    now=datetime.fromisoformat('2026-10-17T21:02:21+09:00')
    def stop(seq,title,lat,lon,start,end):
        uid=uuid4()
        return Item(uuid4(),seq,'activity',title,uid,
            datetime.fromisoformat('2026-10-17T'+start+':00+09:00'),
            datetime.fromisoformat('2026-10-17T'+end+':00+09:00'),
            place={'place_id':str(uid),'name':title,'latitude':lat,'longitude':lon})
    first=stop(1,'다이소 주변 출발점',37.4845,127.0155,'21:00','21:43')
    following=stop(2,'다음 방문 좌표',37.4847,127.0158,'22:10','23:40')
    trip={'party_size':1,'constraints':{}}
    engine=legs.leg_planner(1,{},modes={'walk'},stage='pre_departure')
    assert engine is not None
    after,result=plan(trip=trip,items=[first,following],action='advance_trip',target=first,now=now,engine=engine)
    assert result.get('state')=='departing',result
    move=next(i for i in after if i.kind=='mobility')
    assert move.starts_at==now.replace(second=0) and move.detail.get('departure_context')
    class NoEvents:
        def affecting(self,_targets):return {}
        def unsupported(self,_uses):return []
    observer=build_observer(bus_arrival=lambda *a,**k:pytest.fail('도보에 버스 조회 불필요'))
    status,phrase=build_departure(move,after,route_events=NoEvents(),routes=None,now=now,
        departure_observer=observer,trip=trip)
    assert status=='ok', (status,phrase,result)
    rendered=phrase.render()
    assert '도보' in rendered and '21:03' in rendered
    print('NAMBU_WALK_RESULT',{'departure':result['departure_at'],'arrival':result['arrival_at'],
        'next_start':result['next_start_at'],'guidance':rendered})
