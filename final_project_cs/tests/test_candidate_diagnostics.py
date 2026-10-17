"""뚝섬 실패 유형의 회귀와 운영 기록/고객 전달 경계를 검증한다."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import os
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import psycopg
import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, plan_activity_adjustment
from app.domains.travel_ops.components.itinerary import itinerary_fit
from app.domains.travel_ops.components.planning.replan import Candidate, choose
from app.domains.travel_ops.components.watch import monitoring, watch_relaxed
from app.domains.travel_ops.entry import admin_watch_api
from app.domains.travel_ops.components import candidate_diagnostics as diagnostics


START = datetime.fromisoformat('2026-10-17T11:46:00+09:00')


def place(name='검증 대상', offset=0, hours=True):
    return dict(place_id=str(uuid4()), name=name, kind='activity', latitude=37.53 + offset,
                longitude=127.066, weather_sensitive=True,
                attributes={'hours': ['00:00', '23:59']} if hours else {})


def item(spot):
    return Item(uuid4(), 1, 'activity', spot['name'], spot['place_id'], START,
                START + timedelta(minutes=45), place=spot)


def plan(spots, check, limit=None):
    original = item(place('뚝섬 검증용 출발점'))
    return plan_activity_adjustment(item=original, places=[original.place, *spots], items=[original],
        report={'verdict': 'disrupted', 'disruptions': [{'category': 'disaster_msg', 'impact': 'closure'}]},
        check=check, now=START, limit=limit)


@pytest.mark.parametrize('verdict', ['fatal', 'not_checked', 'unchecked', None])
def test_unverified_candidates_are_not_reported_as_absent(verdict):
    events = []
    with diagnostics.observe(events.append):
        result = plan([place('후보 하나', .001)], lambda **_: {
            'verdict': verdict, 'failed_categories': ['traffic_control'], 'reason': 'ToolBudgetExceeded',
            'checks': [{'category': 'traffic_control', 'status': 'failed', 'tried': ['its', 'utic'],
                        'reason': '조회 실패 https://private.invalid/request', 'raw_secret': 'do-not-store'}]})
    assert result.status == 'source_failed'
    assert result.detail['failed_categories'] == ['traffic_control']
    assert events[0]['name'] == '후보 하나'
    assert events[0]['error_code'] == 'ToolBudgetExceeded'
    assert events[0]['checks'][0]['tried'] == ['its', 'utic']
    assert 'raw_secret' not in json.dumps(events) and 'private.invalid' not in json.dumps(events)


def test_confirmed_disruption_and_hours_failure_remain_unresolved():
    events = []
    with diagnostics.observe(events.append):
        result = plan([place('통제된 후보', .001), place('영업 미확인 후보', .002, hours=False)],
                      lambda **_: {'verdict': 'disrupted'})
    assert result.status == 'unresolved'
    assert len(events) == 2
    assert any('영업' in reason for e in events for reason in e['reasons'])


def test_no_candidates_is_unresolved():
    assert plan([], lambda **_: pytest.fail('후보가 없으면 조회하지 않는다')).status == 'unresolved'


def test_recheck_limit_is_recorded_and_does_not_claim_exhaustive_failure():
    events, called = [], []
    with diagnostics.observe(events.append):
        result = plan([place('가까운 후보', .001), place('다음 후보', .002)],
                      lambda **kw: called.append(kw) or {'verdict': 'disrupted'}, limit=1)
    assert result.status == 'source_failed'
    assert len(called) == 1
    assert len(events) == 2
    assert [e['outcome'] for e in events].count('deferred') == 1
    assert any(e['error_code'] == 'candidate_limit' for e in events)


def test_verified_alternative_survives_other_source_failure_without_private_fields():
    good, bad = place('확인된 대안', .001), place('비공개 탈락 장소', .002)
    events = []
    with diagnostics.observe(events.append):
        result = plan([bad, good], lambda **kw: {'verdict': 'clear'} if kw['place'] == good else
                      {'verdict': 'fatal', 'failed_categories': ['traffic_control']})
    assert isinstance(result, ItineraryChange)
    payload = json.dumps(result.notice, ensure_ascii=False)
    assert '비공개 탈락 장소' not in payload
    assert 'candidate_key' not in payload and 'failed_categories' not in payload
    assert any(e['name'] == bad['name'] and e['outcome'] == 'rejected' for e in events)


def test_duplicate_and_lower_ranked_candidates_are_recorded():
    events = []
    candidates = [Candidate(str(n), place=place('장소 ' + str(n)), changed_items=1,
                            extra_cost_krw=0, shift_minutes=0) for n in range(5)]
    with diagnostics.observe(events.append):
        choose(candidates, distinct=lambda a, b: a.key == '1' and b.key == '0')
    assert len(events) == 5
    assert {'duplicate', 'selected', 'alternate', 'ranked_out'} <= {e['outcome'] for e in events}


@pytest.mark.parametrize('verdict', ['fatal', 'not_checked', None])
def test_relaxed_verification_does_not_hide_source_failure(verdict):
    current, candidate = item(place()), place('대안', .001)
    option = dict(key=candidate['place_id'], place_id=candidate['place_id'], name=candidate['name'])
    with pytest.raises(watch_relaxed.VerificationUnavailable) as failure:
        watch_relaxed.verified_options(trip={'version': 1}, items=[current], places=[candidate],
            current=current, options=[option], check=lambda **_: {
                'verdict': verdict, 'failed_categories': ['traffic_control']})
    assert failure.value.categories == ['traffic_control']


def test_relaxed_confirmed_disruption_is_a_rejection():
    current, candidate = item(place()), place('대안', .001)
    option = dict(key=candidate['place_id'], place_id=candidate['place_id'], name=candidate['name'])
    result = watch_relaxed.verified_options(trip={'version': 1}, items=[current], places=[candidate],
        current=current, options=[option], check=lambda **_: {'verdict': 'disrupted'})
    assert result == []


def test_relaxed_runtime_error_is_not_absent_alternatives(monkeypatch):
    @contextmanager
    def broken():
        raise OSError('private connection detail')
        yield
    result = watch_relaxed.try_offer(broken, store=None, trip_id=uuid4(), item_id=uuid4(), causes=[])
    assert result['status'] == 'source_failed'
    assert 'private connection detail' not in json.dumps(result)


def test_schedule_rejection_reasons_are_only_internal(monkeypatch):
    monkeypatch.setattr(itinerary_fit, 'get_guardrails', lambda: {})
    monkeypatch.setattr(ItineraryChange, 'new_items', lambda change, before, **kwargs:
                        [change.replacements.get(i.item_id, i) for i in before])
    original, first, second = item(place()), place('비공개 탈락 장소', .001), place('최종 장소', .002)
    a, b = original.replaced_by(place=first, title=first['name']), original.replaced_by(place=second, title=second['name'])
    def change(replacement):
        return ItineraryChange(reason='auto_adjusted', causes=[], notice={'text': '최종 장소 안내'},
            replacements={original.item_id: replacement}, summary={'to': replacement.title})
    primary, fallback = change(a), change(b)
    primary.fallbacks = [fallback]
    monkeypatch.setattr(itinerary_fit, 'introduced_violations', lambda trip, before, after:
        [SimpleNamespace(reason='비공개 상세 이동 실패')] if after[0].title == a.title else [])
    monkeypatch.setattr(itinerary_fit, 'density_regressions', lambda *args: [])
    events = []
    with diagnostics.observe(events.append):
        result = itinerary_fit.fit_change(primary, trip={'trip_id': str(uuid4())}, items=[original])
    assert result.rank == 2
    customer = json.dumps({'notice': result.change.notice, 'summary': result.change.summary}, ensure_ascii=False)
    assert '비공개' not in customer and 'skipped' not in customer
    assert events[0]['reasons'] == ['비공개 상세 이동 실패']


@pytest.fixture
def db():
    # 명시적인 시험 DB만 허용한다. 운영 DB 설정으로 대체하지 않는다.
    with psycopg.connect(os.environ['TEST_DATABASE_URL']) as conn:
        conn.execute('CREATE TEMP TABLE travel_watch_runs(tenant_id text,run_id uuid,started_at timestamptz DEFAULT now(),finished_at timestamptz,forced bool,interval_seconds float,status text,counts jsonb,error_type text)')
        conn.execute('CREATE TEMP TABLE travel_watch_checks(check_id bigserial,tenant_id text,run_id uuid,at timestamptz DEFAULT now(),stage text,trip_id uuid,item_id uuid,target_title text,report jsonb)')
        conn.execute('CREATE TEMP TABLE trips(tenant_id text,trip_id uuid,title text)')
        yield conn


@contextmanager
def connect(db):
    yield db


def test_watch_persists_all_candidates_with_async_scope_and_masks_addresses(db):
    trip, part, case = uuid4(), uuid4(), uuid4()
    async def work():
        await asyncio.sleep(0)
        with diagnostics.scope(trip_id=str(trip), item_id=str(part), case_id=str(case), phase='activity_adjustment'):
            for n in range(125):
                diagnostics.record(key=n, name='후보 ' + str(n), outcome='rejected',
                                   reasons=['token=do-not-store https://private.invalid/example'],
                                   report={'verdict': 'fatal', 'failed_categories': ['traffic_control']})
        return {'checked': 125}
    monitoring.execute('one', forced=False, interval=120, work=lambda: asyncio.run(work()),
                       connection_factory=lambda: connect(db))
    rows = db.execute('SELECT stage,trip_id,item_id,report FROM travel_watch_checks ORDER BY check_id').fetchall()
    assert len(rows) == 125
    assert all(r[:3] == ('candidate_evaluation', trip, part) for r in rows)
    assert rows[-1][3]['candidate_key'] == '124'
    assert rows[-1][3]['case_id'] == str(case)
    assert 'do-not-store' not in json.dumps(rows, default=str)
    assert 'private.invalid' not in json.dumps(rows, default=str)


def client(db, monkeypatch, tenant, permission):
    monkeypatch.setattr(admin_watch_api, 'get_connection', lambda: connect(db))
    monkeypatch.setattr(admin_watch_api, 'get_settings', lambda: SimpleNamespace(tenant_id=tenant))
    app = FastAPI()
    app.include_router(admin_watch_api.build_router(operator_dependency=lambda: 'operator',
                                                   require_permission=permission))
    return TestClient(app)


def test_operator_route_requires_introspection_permission(db, monkeypatch):
    def deny(op, scope):
        assert scope == 'ops:introspect'
        raise HTTPException(403, '권한 없음')
    assert client(db, monkeypatch, 'one', deny).get('/admin/api/watch-runs/' + str(uuid4())).status_code == 403


def test_operator_detail_is_tenant_scoped_and_paginated(db, monkeypatch):
    def work():
        for n in range(125):
            diagnostics.record(key=n, name='후보', outcome='rejected', reasons=['영업시간 미확인'])
        return {'checked': 125}
    monitoring.execute('one', forced=False, interval=120, work=work, connection_factory=lambda: connect(db))
    run = db.execute('SELECT run_id FROM travel_watch_runs').fetchone()[0]
    api = client(db, monkeypatch, 'one', lambda *args: None)
    first = api.get('/admin/api/watch-runs/' + str(run)).json()
    second = api.get('/admin/api/watch-runs/' + str(run), params={'after': first['next_after']}).json()
    assert len(first['events']) == 100 and len(second['events']) == 25
    assert second['events'][-1]['report']['candidate_key'] == '124'
    other = client(db, monkeypatch, 'two', lambda *args: None)
    assert other.get('/admin/api/watch-runs/' + str(run)).status_code == 404


def test_record_failure_is_visible_and_scope_resets(monkeypatch):
    def broken(event):
        raise OSError('record failed')
    with pytest.raises(OSError), diagnostics.observe(broken), diagnostics.scope(trip_id='one'):
        diagnostics.record(key='a', name='후보', outcome='rejected')
    events = []
    with diagnostics.observe(events.append):
        diagnostics.record(key='b', name='후보', outcome='rejected')
    assert 'trip_id' not in events[0]


@pytest.mark.asyncio
async def test_team_run_records_case_trip_item_without_customer_diagnostics():
    from tests.unit.travel.activity.test_activity_trigger_budget import _setup
    from app.domains.travel_ops.instances.activity import ActivityTeam
    tools, task, places = _setup(2, verdicts_for=lambda ps: {p['place_id']: 'fatal' for p in ps[1:]})
    events = []
    with diagnostics.observe(events.append):
        result = await ActivityTeam(tools).execute(task)
    assert result.failure_code == 'itinerary_source_failed'
    assert events and all(e['case_id'] == str(task.case_id) for e in events)
    assert all(e['trip_id'] == task.context.current_state['subject_ref']['id'] for e in events)
    assert all(e['item_id'] == task.context.current_state['trigger']['item_id'] for e in events)
    output = json.dumps({'answer': result.answer, 'warnings': result.warnings,
                         'decisions': result.decisions,
                         'proposals': [p.model_dump(mode='json') for p in result.action_proposals]}, ensure_ascii=False)
    assert all(p['name'] not in output for p in places[1:])
    assert 'candidate_key' not in result.model_dump_json() and 'reasons' not in result.model_dump_json()


def test_watch_relaxed_failure_sends_defer_notice_without_absence_claim(monkeypatch):
    from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
    monkeypatch.setattr(watch_relaxed, 'try_offer', lambda *args, **kwargs:
                        {'status': 'source_failed', 'failed_categories': ['traffic_control'], 'options': []})
    calls = []
    opener = SimpleNamespace(_connect=None, store=None, check=None, clock=lambda: START,
                             _defer_notice=lambda *args, **kwargs: calls.append((args, kwargs)))
    result = SimpleNamespace(relaxed=[])
    assert TripWatchCaseOpener._offer_relaxed(opener, uuid4(), item(place()), [], False, result, uuid4())
    assert len(calls) == 1 and calls[0][0][2]['error_code'] == 'alternate_verification_failed'
    assert result.relaxed == []
