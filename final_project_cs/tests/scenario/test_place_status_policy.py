"""정책에서 실제 조회·감시까지: 격리 PostgreSQL, HTTP 응답 대역."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app.application import operations_policy as policy
from app.domains.travel_ops.components.watch.place_status import PlaceStatus
from app.domains.travel_ops.components.watch.dawn_check import DawnCheck
from app.domains.travel_ops.components.team_hooks import dining_ledger
from app.domains.travel_ops.instances.dining.ledger import closure_observation
from app.domains.travel_ops.ports.data_sources.google_places import GooglePlaces, METER_SEARCH, METER_DETAILS
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from .test_case_version_day import _seed, _at, Clock


@pytest.fixture
def world(monkeypatch):
    tenant = 'status_' + uuid4().hex[:12]
    store, customer, trip = _seed(tenant)
    with get_connection() as conn:
        _, items = store.latest(conn, trip)
    meal = next(i for i in items if i.kind == 'dining')
    with get_connection() as conn:
        uid = conn.execute("INSERT INTO dining.dn_place(name_ko,area,record_status) "
                           "VALUES(%s,'시험','active') RETURNING place_uid", (tenant,)).fetchone()[0]
        conn.execute("INSERT INTO dining.dn_core_place_link(tenant_id,core_place_id,place_uid,linked_by) VALUES(%s,%s,%s,'test')",
                     (tenant, meal.place_id, uid))
    monkeypatch.setattr(dining_ledger, 'closure_observation', closure_observation)
    yield SimpleNamespace(tenant=tenant, customer=customer, trip=trip, store=store, meal=meal, uid=uid, now=_at('04:00'))
    with get_connection() as conn:
        audit = conn.execute('SELECT count(*) FROM admin_audit WHERE tenant_id=%s', (tenant,)).fetchone()[0]
        conn.execute('DELETE FROM dining.dn_live_check WHERE place_uid=%s', (uid,))
        conn.execute('DELETE FROM dining.dn_core_place_link WHERE tenant_id=%s', (tenant,))
        conn.execute('DELETE FROM dining.dn_place WHERE place_uid=%s', (uid,))
    # 감사는 append-only다. 전용 시험 DB의 정책 변경 증거를 삭제하거나 트리거를 끄지 않는다.
    if not audit:
        cleanup_tenant(tenant)


def observe(w, state='yes', *, target=None, source='operator_check', outcome='ok', ttl=86400, asked=None):
    with get_connection() as conn:
        conn.execute("INSERT INTO dining.dn_live_check(place_uid,source_code,topic,asked_at,target_at,outcome,"
                     "value_state,ttl_seconds,checked_by) VALUES(%s,%s,'closure',%s,%s,%s,%s,%s,'test')",
                     (w.uid, source, asked or w.now, target or w.meal.starts_at, outcome, state, ttl))


def lookup(w, source=None, **kwargs):
    args = dict(tenant=w.tenant, customer_id=w.customer, trip_id=w.trip, place=w.meal.place,
                start=w.meal.starts_at, end=w.meal.ends_at, now=w.now, context='dawn')
    args.update(kwargs)
    return PlaceStatus(get_connection, google=source).lookup(**args)


class Budget:
    def __init__(self, denied=None):
        self.calls, self.denied = [], denied
    def try_reserve(self, meter):
        self.calls.append(meter)
        return meter != self.denied


def google(w, budget, *, unmatched=False):
    calls = []
    def request(method, url, headers, body):
        calls.append((method, url))
        payload = {'places': [] if unmatched else [{'id':'matched', 'location':{
            'latitude': w.meal.place['latitude'], 'longitude': w.meal.place['longitude']}}]} if method == 'POST' else {
            'regularOpeningHours': {'periods': [{'open': {'day': 0, 'hour': 0}}]}}
        return httpx.Response(200, json=payload, request=httpx.Request(method, url))
    return GooglePlaces(api_key='test-only', budget=budget, request=request), calls


def enable(w):
    with get_connection() as conn, conn.transaction():
        policy.save(conn, w.tenant, expected_revision=0, policy=policy.SourcePolicy(allow_paid=True, daily_paid_cap=2, trip_paid_cap=2),
                    actor='test', reason='isolated test')


@pytest.mark.parametrize('state,expected', [('yes','closed'), ('no','open')])
def test_free_observation_precedes_google_and_preserves_times(world, state, expected):
    w = world
    observe(w, state)
    source, calls = google(w, Budget())
    result = lookup(w, source)
    assert result['status'] == expected and result['reason'] == 'verified_free'
    assert result['source'] == 'operator_check' and result['checked_at'] == w.now.isoformat()
    assert result['valid_until'] == (w.now+timedelta(days=1)).isoformat()
    assert not calls and not source._budget.calls


@pytest.mark.parametrize('mode', ['wrong_slot','expired','trial','unknown','failed','future'])
def test_unverified_observations_never_become_open(world, mode):
    w = world
    kwargs = {'target': w.meal.starts_at+timedelta(minutes=1)} if mode == 'wrong_slot' else {}
    if mode == 'expired': kwargs['ttl'] = 60
    if mode == 'trial': kwargs['source'] = 'catchtable_trial'
    if mode == 'future': kwargs['asked'] = w.now+timedelta(minutes=1)
    observe(w, 'unknown' if mode in ('unknown','failed') else 'yes', outcome='timeout' if mode == 'failed' else 'ok', **kwargs)
    result = lookup(w)
    assert result['status'] == 'unverifiable' and result['diagnostic']['status'] == 'stored'


def test_wrong_customer_never_calls_free_or_paid(world, monkeypatch):
    w = world
    monkeypatch.setattr(dining_ledger, 'closure_observation', lambda *a: pytest.fail('cross customer lookup'))
    source, calls = google(w, Budget())
    assert lookup(w, source, customer_id=uuid4())['reason'] == 'trip_not_owned'
    assert calls == [] and source._budget.calls == []


def test_dawn_first_http_is_reserved_once_and_details_separately(world):
    w = world
    enable(w)
    source, calls = google(w, Budget())
    result = lookup(w, source)
    assert result['status'] == 'open' and result['reason'] == 'verified_paid'
    assert len(calls) == 2 and source._budget.calls == [METER_SEARCH, METER_DETAILS]
    assert source._prepaid_meter is None
    with get_connection() as conn:
        assert conn.execute('SELECT used FROM ops_lookup_usage WHERE tenant_id=%s', (w.tenant,)).fetchone()[0] == 1


@pytest.mark.parametrize('mode', ['disabled','daytime','outside_dawn','provider_budget'])
def test_denial_does_not_make_an_http_request(world, mode):
    w = world
    if mode != 'disabled': enable(w)
    source, calls = google(w, Budget(denied=METER_SEARCH if mode == 'provider_budget' else None))
    kwargs = {'context':'daytime'} if mode == 'daytime' else {'now':_at('10:00')} if mode == 'outside_dawn' else {}
    result = lookup(w, source, **kwargs)
    assert result['status'] == 'unverifiable' and calls == []


def test_place_mismatch_is_one_distinct_diagnostic_and_no_details(world):
    w = world
    enable(w)
    source, calls = google(w, Budget(), unmatched=True)
    result = lookup(w, source)
    assert result['reason'] == 'place_unmatched' and len(calls) == 1
    with get_connection() as conn:
        rows = conn.execute('SELECT kind,code,occurrences FROM ops_defects WHERE tenant_id=%s', (w.tenant,)).fetchall()
    assert rows == [('place_unmatched', 'PLACE_UNMATCHED', 1)]


def test_dawn_unknown_retries_without_marking_day_complete_and_notifies_once(world):
    w = world
    runner = DawnCheck(store=w.store, connection_factory=get_connection, clock=Clock(w.now), source=None,
                       place_status=PlaceStatus(get_connection))
    first, second = runner.tick(), runner.tick()
    assert first.fatal and second.fatal and first.disabled is None
    with get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM place_open_checks WHERE tenant_id=%s', (w.tenant,)).fetchone()[0] == 0
        count = conn.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND dedupe_key LIKE %s", (w.tenant, '%:dawn-deferred:%')).fetchone()[0]
    assert count == len(first.fatal)


def test_daytime_closed_and_failed_merge_preserve_other_failures(world):
    w = world
    observe(w)
    status = lookup(w, context='daytime')
    report = PlaceStatus.merge({'verdict':'clear','disruptions':[]}, status)
    assert report['verdict'] == 'disrupted' and report['disruptions'][0]['kind'] == 'closed'
    assert PlaceStatus.merge({'verdict':'fatal','failed_categories':['weather']}, status)['verdict'] == 'fatal'


@pytest.mark.parametrize('known', [True, False])
def test_day_watch_and_team_read_share_free_closure_without_duplicate_diagnostic(world, known):
    from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
    from app.infrastructure.db import repository
    from app.tools.read_tools import ReadToolbox, ToolContext
    w = world
    w.now = w.meal.starts_at - timedelta(minutes=10)
    if known: observe(w)
    status = PlaceStatus(get_connection)
    notices = []
    watch = TripWatchCaseOpener(store=w.store, check=lambda **_: {'verdict':'clear','disruptions':[]},
        connection_factory=get_connection, clock=Clock(w.now), repository=repository, run_case=None,
        place_status=status, diagnostic_recorder=lambda event: notices.append(event) or {'status':'stored'})
    result = watch.tick()
    if known:
        case_id = next(UUID(entry['case_id']) for entry in result.opened if entry['item'] == w.meal.title)
        tools = ReadToolbox(get_connection, check=lambda **_: {'verdict':'clear','disruptions':[]}, place_status=status)
        scope = ToolContext(w.tenant, w.customer, case_id, [])
        # 무료 관측의 만료는 실제 도구 호출 시각보다 뒤로 둔다. 방문 시각은 그대로다.
        from datetime import UTC, datetime
        with get_connection() as conn:
            conn.execute('UPDATE dining.dn_live_check SET asked_at=%s WHERE place_uid=%s', (datetime.now(UTC)-timedelta(seconds=1), w.uid))
            saved = conn.execute('SELECT customer_id,state_json FROM customer_cases WHERE case_id=%s', (case_id,)).fetchone()
            target = conn.execute('SELECT kind,trip_scope FROM places WHERE place_id=%s', (w.meal.place_id,)).fetchone()
        assert saved[0] == w.customer and saved[1].get('subject_ref',{}).get('id') == str(w.trip), saved
        assert w.meal.kind == 'dining'  # 숙소 안 조식도 장소 종류가 아닌 일정 항목으로 확인한다.
        report = tools.disruptions(scope, place_id=w.meal.place_id, starts_at=w.meal.starts_at)
        assert report['verdict'] == 'disrupted' and report['disruptions'][0]['kind'] == 'closed', report
    else:
        assert result.fatal and result.notified and not result.opened and notices == []
        with get_connection() as conn:
            assert conn.execute('SELECT sum(occurrences) FROM ops_defects WHERE tenant_id=%s', (w.tenant,)).fetchone()[0] == len(result.fatal)


def test_daytime_saved_interval_gates_only_scheduled_reads(world):
    w = world
    with get_connection() as conn, conn.transaction():
        policy.save(conn, w.tenant, expected_revision=0,
                    policy=policy.SourcePolicy(check_interval_seconds=600), actor='test', reason='ten minute watch')
    assert lookup(w, context='daytime', scheduled=True)['status'] == 'unverifiable'
    assert lookup(w, context='daytime', scheduled=True, now=w.now+timedelta(minutes=3))['status'] == 'skipped'
    assert lookup(w, context='daytime')['status'] == 'unverifiable'  # Team 재점검은 건너뛰지 않는다.
    assert lookup(w, context='daytime', scheduled=True, now=w.now+timedelta(minutes=11))['status'] == 'unverifiable'
