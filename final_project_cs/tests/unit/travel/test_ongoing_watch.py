"""진행 중인 실제 일정이 감시에서 빠지거나 시작 시각의 사건만 조회하는 결함 회귀."""
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.watch import trip_watch, trip_watch_cases, trip_watch_batch
from app.domains.travel_ops.components.planning.pending import PendingStore

NOW=datetime(2030,1,1,11,30,tzinfo=ZoneInfo('Asia/Seoul'))


def item(start,end,kind='activity'):
    return Item(item_id=uuid4(),seq=1,kind=kind,title='여행지',starts_at=start,ends_at=end,place_id=None,
                place={'name':'여행지','latitude':37.57,'longitude':127.10,'attributes':{}},detail={})


@pytest.mark.parametrize('start,end,wanted',[
    (NOW-timedelta(hours=1),NOW+timedelta(hours=1),True),
    (NOW,NOW+timedelta(hours=1),True),
    (NOW+timedelta(minutes=30),NOW+timedelta(hours=1),True),
    (NOW-timedelta(hours=1),NOW,False),
    (NOW-timedelta(hours=2),NOW-timedelta(hours=1),False),
    (NOW-timedelta(hours=1),None,False),
    (NOW+timedelta(hours=2),NOW+timedelta(hours=3),False),
])
def test_due_contains_future_and_still_ongoing_but_never_invents_unknown_end(monkeypatch,start,end,wanted):
    stop=item(start,end);trip_id=uuid4();store=TripStore('synthetic')
    calls=[]
    monkeypatch.setattr(store,'_open_trips',lambda conn,columns,now:calls.append(now) or [(trip_id,1)])
    monkeypatch.setattr(store,'_items_of_trips',lambda conn,keys:{trip_id:[stop]})
    due=store.due(None,start=NOW,end=NOW+timedelta(hours=1))
    assert bool(due) is wanted
    assert calls==[NOW]  # 기존 본인 여행·게스트·정지 제외 필터를 그대로 호출한다.


class Conn:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def transaction(self):return nullcontext(self)


@pytest.mark.parametrize('module', [trip_watch,trip_watch_cases])
@pytest.mark.parametrize('offset', [-60,30])
def test_both_watch_executors_query_current_time_for_ongoing_and_visit_time_for_future(monkeypatch,module,offset):
    start=NOW+timedelta(minutes=offset)
    stop=item(start,NOW+timedelta(hours=2));trip_id=uuid4();seen=[]
    store=SimpleNamespace(tenant_id='synthetic',due=lambda *a,**k:[(trip_id,stop)],places=lambda *a,**k:[])
    monkeypatch.setattr(PendingStore,'expire',lambda *a,**k:[])
    monkeypatch.setattr(trip_watch_batch,'skipped_watch',lambda *a,**k:None)
    monkeypatch.setattr(module,'forecast_attention',lambda *a,**k:None)
    if module is trip_watch:
        monkeypatch.setattr(module,'rejudge_activity_disasters',lambda report,_:report)
    def check(**kw):seen.append(kw['starts_at']);return {'verdict':'clear','checks':[],'disruptions':[]}
    args=dict(store=store,check=check,connection_factory=Conn,clock=lambda:NOW)
    watch=(module.TripWatchCaseOpener(**args,repository=None,run_case=None) if module is trip_watch_cases else module.TripWatcher(**args))
    result=watch.tick()
    assert result.checked==1 and seen==[max(start,NOW)]
    assert stop.starts_at==start  # 일정 자체의 시작 시각은 바꾸지 않는다.
