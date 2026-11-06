from uuid import uuid4
from app.domains.travel_ops.components.intake import review, stream, pipeline

TOLD={'open':'10:00','close':'19:00','closed_days':['sun']}
PLACE={'name':'통인시장','source':'kakao','latitude':37.5809,'longitude':126.9696}
class Conn:
    def transaction(self): return self
    def __enter__(self): return self
    def __exit__(self,*a): return False

def test_completed_feed_retains_customer_hours(monkeypatch):
    monkeypatch.setattr(review,'_fixed_neighbours',lambda *a:[])
    sid=str(uuid4()); iid=uuid4()
    sources=[{'source_id':sid,'position':0,'transcript':'통인시장'}]
    vals={'title':'통인시장','date':'2026-10-15','starts_at':'12:30','ends_at':'13:30','place':PLACE,'hours':TOLD}
    claims=[{'source_id':sid,'field':'items[0].'+k,'value':v,'method':'customer','evidence':{'line':1},'needs_review':False,'note':None} for k,v in vals.items()]
    built=review.build(Conn(),tenant_id='t',intake_id=iid,revision=1,sources=sources,claims=claims,use_engine=False)
    assert built['items'][0]['customer_hours']==TOLD
    monkeypatch.setattr(pipeline,'_sources',lambda *a:sources)
    monkeypatch.setattr(pipeline,'_claims',lambda *a:claims)
    monkeypatch.setattr(pipeline,'_review_of',lambda *a:(built,None))
    monkeypatch.setattr(review,'public',lambda value,**kw:value)
    monkeypatch.setattr(stream.progress_module,'drain',lambda *a:([],0))
    events=stream.Feed('t',uuid4(),iid).poll(Conn(),{'status':'review','revision':1,'stage':'review'})
    emitted=next(b for n,b in events if n=='item')
    assert emitted.get('hours_state')=='customer', emitted
    assert emitted.get('customer_hours')==TOLD


def test_customer_closed_hours_do_not_enter_other_trips_blacklist():
    import sqlite3
    from types import SimpleNamespace
    from app.domains.travel_ops.components.watch.dawn_check import DawnCheck, TOLD_SOURCE
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE place_open_checks (tenant_id TEXT, trip_id TEXT, item_id TEXT, day TEXT, place_id TEXT, verdict TEXT, detail TEXT, source TEXT, UNIQUE(tenant_id,item_id,day))')
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,sql,args): self.c=db.execute(sql.replace('%s','?'),args)
        def fetchall(self): return self.c.fetchall()
    class Connection:
        def cursor(self): return Cursor()
    checker=object.__new__(DawnCheck); checker.store=SimpleNamespace(tenant_id='tenant')
    item=SimpleNamespace(item_id='customer-a-item',place={'place_id':'shared-place'})
    checker._insert_check(Connection(),'trip-a',item,'2026-10-18','closed','customer A only',source=TOLD_SOURCE)
    # _apply_verdict supplies this tenant-wide set to replanning for every trip.
    excluded_for_customer_b=checker._closed_places(Connection(),'2026-10-18')
    assert 'shared-place' not in excluded_for_customer_b, excluded_for_customer_b
    db.close()


import pytest


@pytest.mark.parametrize('status', ['review', 'confirmed'])
def test_live_build_completion_and_reconnection_preserve_hours(monkeypatch, status):
    monkeypatch.setattr(review, '_fixed_neighbours', lambda *a: [])
    sid = str(uuid4())
    iid, customer = uuid4(), uuid4()
    sources = [{'source_id': sid, 'position': 0, 'transcript': '통인시장'}]
    vals = {'title': '통인시장', 'date': '2026-10-15', 'starts_at': '12:30',
            'ends_at': '13:30', 'place': PLACE, 'hours': TOLD}
    claims = [{'source_id': sid, 'field': 'items[0].'+k, 'value': v,
               'method': 'customer', 'evidence': {'line': 1},
               'needs_review': False, 'note': None} for k, v in vals.items()]
    progress = []
    built = review.build(Conn(), tenant_id='t', intake_id=iid, revision=1,
                         sources=sources, claims=claims, use_engine=False,
                         on_event=lambda name, body: progress.append((name, body)))
    monkeypatch.setattr(pipeline, '_sources', lambda *a: sources)
    monkeypatch.setattr(pipeline, '_claims', lambda *a: claims)
    monkeypatch.setattr(pipeline, '_review_of', lambda *a: (built, None))
    # Keep real review.public and real Feed; only persistence is substituted.
    monkeypatch.setattr(stream.progress_module, 'drain',
                        lambda intake, cursor: (progress[cursor:], len(progress)))
    feed = stream.Feed('t', customer, iid)
    live = feed.poll(Conn(), {'status': 'reading', 'revision': 1, 'stage': 'checking'})
    live_item = next(body for name, body in reversed(live) if name == 'item')
    assert live_item['hours_state'] == 'customer'
    assert live_item['customer_hours'] == TOLD
    state = {'status': status, 'revision': 1, 'stage': 'review'}
    completed = feed.poll(Conn(), state)
    final_item = feed.sent['item:0-0']
    assert final_item['hours_state'] == 'customer'
    assert final_item['customer_hours'] == TOLD
    assert any(name == 'done' for name, body in completed)
    assert feed.poll(Conn(), state) == []
    # Reconnection after progress eviction must recover from persisted review.
    monkeypatch.setattr(stream.progress_module, 'drain', lambda *a: ([], 0))
    replay = stream.Feed('t', customer, iid).poll(Conn(), state)
    restored = next(body for name, body in replay if name == 'item')
    assert restored == final_item
    assert any(name == 'done' for name, body in replay)


@pytest.mark.parametrize('kind', ['activity', 'dining'])
@pytest.mark.parametrize('other_customer,other_trip', [
    ('customer-b', 'trip-b'), ('customer-a', 'trip-a2'), ('customer-a', 'trip-a'),
])
def test_dawn_customer_closure_stays_on_item_with_real_sql(monkeypatch, kind, other_customer, other_trip):
    import sqlite3
    from datetime import datetime
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo
    from app.domains.travel_ops.components.intake.hours import customer_week
    from app.domains.travel_ops.components.itinerary.itinerary import Item, with_told_hours
    from app.domains.travel_ops.components.watch import dawn_check as dawn

    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE place_open_checks (tenant_id TEXT, trip_id TEXT, item_id TEXT, day TEXT, place_id TEXT, verdict TEXT, detail TEXT, source TEXT, UNIQUE(tenant_id,item_id,day))')
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql, args): self.c = db.execute(sql.replace('%s', '?'), args)
        def fetchall(self): return self.c.fetchall()
    class Connection(Conn):
        def cursor(self): return Cursor()
    conn = Connection()
    kst = ZoneInfo('Asia/Seoul')
    start = datetime(2026, 10, 18, 12, 30, tzinfo=kst)
    end = datetime(2026, 10, 18, 13, 30, tzinfo=kst)
    day = '2026-10-18'
    detail = {'customer_hours': {'told': TOLD, 'hours_week': customer_week(TOLD)}}
    place = {'place_id': 'shared-place', 'name': '통인시장', 'attributes': {}}
    def item(iid, told):
        return Item(iid, 1, kind, '통인시장', 'shared-place', start, end,
                    detail=told, place=with_told_hours(place, told))
    origin, other = item('origin-item', detail), item('other-item', {})
    trips = {'trip-a': ({'customer_id': 'customer-a'}, [origin])}
    trips[other_trip] = ({'customer_id': other_customer}, [origin, other] if other_trip == 'trip-a' else [other])
    checker = object.__new__(dawn.DawnCheck)
    checker.store = SimpleNamespace(tenant_id='tenant', latest=lambda conn, tid: trips[tid])
    checker._connect = lambda: conn
    checker.clock = lambda: start
    checker._price_lookup = lambda: None
    monkeypatch.setattr(dawn.dining_ledger, 'state_lookup', lambda *a: None)
    monkeypatch.setattr(dawn.dining_ledger, 'add_nearby', lambda conn, store, tid, meals, places: places)
    calls = []
    def plan(**kw):
        calls.append(kw)
        return SimpleNamespace(summary={})
    monkeypatch.setattr(dawn, 'plan_activity_closed_on_day', plan)
    monkeypatch.setattr(dawn, 'plan_closed_on_day', plan)
    applied = []
    monkeypatch.setattr(dawn, 'apply_or_ask', lambda conn, **kw: (applied.append(kw) or {'status': 'asked'}))
    result = dawn.DawnResult()
    checker._apply_verdict('trip-a', origin, day, [place], result, 'unknown', 'provider unknown')
    assert len(result.closed) == 1 and len(result.asked) == 1
    assert applied[0]['trip_id'] == 'trip-a' and applied[0]['item_id'] == 'origin-item'
    assert calls[0]['source'] == dawn.TOLD_SOURCE
    assert db.execute('SELECT trip_id,item_id,source,verdict FROM place_open_checks').fetchall() == [
        ('trip-a', 'origin-item', dawn.TOLD_SOURCE, 'closed')]
    assert checker._checked_items(conn, day) == {'origin-item'}
    assert checker._closed_places(conn, day) == set()
    untouched = dawn.DawnResult()
    checker._apply_verdict(other_trip, other, day, [place], untouched, 'unknown', 'provider unknown')
    assert not untouched.closed and len(untouched.unknown) == 1
    assert len(applied) == 1
    # Official closures still reach planning in every trip/customer. Other day/tenant do not.
    for tenant, when, pid in [('tenant', day, 'official-place'), ('elsewhere', day, 'alien-place'),
                              ('tenant', '2026-10-19', 'tomorrow-place')]:
        checker.store.tenant_id = tenant
        control = SimpleNamespace(item_id=pid, place={'place_id': pid})
        checker._insert_check(conn, 'official-trip', control, when, 'closed', 'official', source=dawn.PROVIDER)
    checker.store.tenant_id = 'tenant'
    assert checker._closed_places(conn, day) == {'official-place'}
    checker._apply_verdict(other_trip, other, day, [place], dawn.DawnResult(), 'closed', 'official')
    assert calls[-1]['exclude'] == {'official-place'}
    assert calls[-1]['source'] == dawn.PROVIDER
    assert applied[-1]['trip_id'] == other_trip and applied[-1]['item_id'] == 'other-item'
    db.close()
