"""장소 교체 뒤 저장 문맥이 빠져도 현재 장소로 재계산·재검증한다."""
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from app.domains.travel_ops.instances.mobility import wiring
from .test_departure_assembly_v1 import setup
from .test_departure_observer_notice_v1 import NoEvents
from .mobility.test_departure_observer_v1 import NOW
from .mobility.test_departure_walk_v1 import scene
from .mobility.test_review_fixes_plan import PLACES


def test_missing_context_is_rebuilt_before_current_walking_network_check(monkeypatch):
    _,move,items,source,observer=setup(monkeypatch)
    runtime,context,planned=scene()
    monkeypatch.setattr(wiring.engine_runtime,'get_verifier',lambda **kw:runtime)
    for index,place in ((0,PLACES[0]),(-1,PLACES[1])):
        items[index].place.update(latitude=place['lat'],longitude=place['lon'])
    move.detail.pop('departure_context',None)
    move.detail['route_def']['planned']='walk'
    move.detail['route_def']['options']=[{'id':'walk','label':'도보','eta_min':999,'uses':[]}]
    calculated=[]
    def engine(a,b,deadline,earliest):
        calculated.append((a,b,deadline,earliest))
        return {'departure_context':context,'route':{'planned':'walk'}},None
    monkeypatch.setattr(legs,'leg_planner',lambda *a,**kw:engine)
    status,phrase=build_departure(move,items,route_events=NoEvents(),routes=None,
        now=NOW,departure_observer=observer)
    assert status=='ok' and f"약 {planned['eta_min']}분" in phrase.render()
    assert calculated[0][0]['lat']==PLACES[0]['lat']
    assert calculated[0][1]['lon']==PLACES[1]['lon']
    assert '999' not in phrase.render() and source.calls==[]
