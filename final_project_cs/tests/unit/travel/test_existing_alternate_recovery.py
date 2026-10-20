"""이전 대안 부재도 개선된 검색으로 다시 확인하되 같은 결과는 반복하지 않는다."""
from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.watch import monitoring, trip_watch_cases as watch


def setup(monkeypatch, *, recording=True, guard='itinerary_unresolved', outcome='asked', seen=False,
          enabled=True, current_due=True, changed=False):
    monkeypatch.setattr(monitoring, 'recording', lambda: recording)
    from app.domains.travel_ops.components.watch import watch_relaxed
    monkeypatch.setattr(watch_relaxed, 'enabled', lambda: enabled)
    marker = {'seen': seen}
    events = []; calls = []
    class Connection:
        active = False
        closed = 0
        def __enter__(self):
            self.active = True
            return self
        def __exit__(self, *_):
            self.active = False
            self.closed += 1
        def execute(self, sql, params):
            return SimpleNamespace(fetchone=lambda: (1,) if marker['seen'] else None)
    conn = Connection()
    opener = object.__new__(watch.TripWatchCaseOpener)
    opener.repository = object()
    opener.store = SimpleNamespace(tenant_id='synthetic')
    opener._connect = lambda: conn
    opener.clock = lambda: datetime.now(timezone.utc)
    opener._escalation = lambda identifier: (guard, '')
    def offer(*args):
        assert not conn.active, '읽기·보완 연결은 대안 검색 전에 닫혀야 한다'
        calls.append(args)
        if outcome == 'asked':args[-2].relaxed.append({'proposal_id':str(uuid4())})
        return outcome != 'no_alternate'
    opener._offer_relaxed = offer
    def record(stage, **kw):
        events.append((stage,kw))
        marker['seen'] = kw['report']['status'] in {'asked','no_alternate'}
    monkeypatch.setattr(watch,'record_check',record)
    issue=watch.Issue(uuid4(),SimpleNamespace(item_id=uuid4(),kind='activity',title='시험 문화관'),
                      [{'category':'weather_warning','kind':'강풍주의보'}],'activity_weather_risk','place')
    current = SimpleNamespace(**vars(issue.item))
    if changed:current.title = '수정한 문화관'
    opener.store.due = lambda *args, **kwargs: [(issue.trip_id,current)] if current_due else []
    return opener,conn,issue,watch.CaseTickResult(),str(uuid4()),events,calls


@pytest.mark.parametrize('outcome',['asked','no_alternate'])
def test_completed_search_is_recorded_and_not_repeated(monkeypatch,outcome):
    opener,conn,issue,result,case,events,calls=setup(monkeypatch,outcome=outcome)
    opener._refresh_existing_alternatives(issue,case,result)
    opener._refresh_existing_alternatives(issue,case,result)
    assert len(calls)==1 and len(events)==1 and events[0][1]['report']['status']==outcome


def test_failed_verification_is_not_mistaken_for_no_alternate_and_can_retry(monkeypatch):
    opener,conn,issue,result,case,events,calls=setup(monkeypatch,outcome='source_failed')
    opener._refresh_existing_alternatives(issue,case,result)
    opener._refresh_existing_alternatives(issue,case,result)
    assert len(calls)==2 and all(e[1]['report']['status']=='source_failed' for e in events)


@pytest.mark.parametrize('recording,guard,seen',[(False,'itinerary_unresolved',False),(True,'fatal_source_failure',False),(True,'itinerary_unresolved',True)])
def test_standalone_or_other_failure_or_recorded_result_does_not_search(monkeypatch,recording,guard,seen):
    opener,conn,issue,result,case,events,calls=setup(monkeypatch,recording=recording,guard=guard,seen=seen)
    opener._refresh_existing_alternatives(issue,case,result)
    assert calls==[] and events==[]


@pytest.mark.parametrize('options',[{'enabled':False},{'current_due':False},{'changed':True}])
def test_disabled_or_no_longer_current_item_does_not_mark_search_completed(monkeypatch,options):
    opener,conn,issue,result,case,events,calls=setup(monkeypatch,**options)
    opener._refresh_existing_alternatives(issue,case,result)
    assert calls==[] and events==[]


def test_repair_connection_is_closed_before_refresh(monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings,'get_guardrails',lambda:{'travel.watch.batch_enabled':False,
                                                       'travel.watch.batch_max_items':2})
    opener,conn,issue,result,case,events,calls=setup(monkeypatch)
    order=[]
    opener._attempt=lambda *args:(None,case)
    def repair(*args):
        assert conn.active
        order.append('repair')
    def refresh(*args):
        assert not conn.active and conn.closed==1
        order.append('refresh')
    opener._repair_traffic_notice=repair
    opener._refresh_existing_alternatives=refresh
    monkeypatch.setattr(opener,"_early_notice",lambda *a: None)
    opener._open_issues([issue],opener.clock(),result,[])
    assert order==['repair','refresh']
