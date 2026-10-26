"""감시 결과 작성: 업무 실행·저장·승인과 분리한다."""
from copy import deepcopy
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
from importlib import import_module

import pytest


def adapter():
    return import_module('app.domains.travel_ops.components.response.monitoring')


def test_applied_requires_matching_saved_version_and_preserves_snapshots():
    payload = {'text': '박물관으로 바꿨어요.', 'causes': [{'category': 'closed_today'}],
               'item_id': 'item-1', 'rollback': {'base_version': 4, 'to_version': 3}}
    workflow = {'approval_required': True, 'approval_status': 'pending',
                'required_input_schema': {'confirmed': 'boolean'}, 'resume_token': 'opaque'}
    before = deepcopy((payload, workflow))
    result = adapter().monitoring_payload(payload, status='applied', version=4, saved_version=4,
                                          scope={'tenant_id': 't', 'customer_id': 'c', 'trip_id': 'trip'},
                                          workflow=workflow)
    assert result['text'] == payload['text']
    assert result['response']['execution']['status'] == 'applied'
    assert result['response']['completion'] == 'complete'
    assert result['response']['workflow'] == workflow
    assert result['response']['followup']['causes'] == payload['causes']
    result['response']['workflow']['approval_status'] = 'changed'
    assert (payload, workflow) == before
    for saved in (None, 3):
        with pytest.raises(ValueError, match='saved_version'):
            adapter().monitoring_payload(payload, status='applied', version=4, saved_version=saved)


def test_real_consent_outbox_is_waiting_and_duplicate_does_not_enqueue(monkeypatch):
    from app.domains.travel_ops.components.planning import pending
    proposal_id, trip_id, item_id = uuid4(), uuid4(), uuid4()
    item = SimpleNamespace(item_id=item_id, title='서울숲', ends_at=None)
    opened = iter([proposal_id, None])
    monkeypatch.setattr(pending.PendingStore, 'open', lambda *a, **kw: next(opened))
    sent = []
    store = SimpleNamespace(tenant_id='tenant', enqueue_message=lambda *a, **kw: sent.append(kw),
                            latest=lambda *a: ({'version': 7, 'customer_id': 'customer'}, [item]))
    causes = [{'category': 'forecast', 'value': 80}]
    for _ in range(2):
        outcome = pending.ask_consent(None, store=store, trip_id=trip_id, item=item, base_version=7, causes=causes)
        assert outcome['status'] == 'asked'
    assert len(sent) == 1
    payload = sent[0]['payload']
    expected = pending.consent_notice(item=item, causes=causes, proposal_id=proposal_id)
    assert {k: v for k, v in payload.items() if k != 'response'} == expected
    response = payload['response']
    assert response['execution']['status'] == 'awaiting_choice'
    assert response['execution']['saved_version'] is None
    assert response['completion'] == 'partial'
    assert response['version'] == 7
    assert response['scope']['trip_id'] == str(trip_id)
    assert response['followup']['causes'] == causes
    assert response['followup']['proposal_id'] == str(proposal_id)
    assert response['workflow']['approval_status'] == 'awaiting_choice'


@pytest.mark.parametrize('status', ['awaiting_choice', 'failed', 'unknown'])
def test_non_applied_never_claims_complete(status):
    result = adapter().monitoring_payload({'text': '기존 일정을 유지했어요.'}, status=status, version=3)
    assert result['response']['completion'] == 'partial'
    assert result['response']['execution']['status'] == status


def plan_world():
    from app.domains.travel_ops.components.itinerary.itinerary import Item
    from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange
    item = Item(uuid4(), 1, 'activity', '서울숲', None, datetime(2026, 10, 24, 10, tzinfo=UTC), None)
    plan = ItineraryChange('auto_adjusted', [{'category': 'closed_today'}],
                           {'text': '다른 장소로 바꿨어요.', 'changed': {'title': '박물관'}}, full_items=[item])
    sent, events = [], []
    trip = {'version': 7, 'customer_id': 'customer', 'constraints': {}}
    def append(*a, **kw):
        events.append('append')
        trip['version'] = 8
        return 8
    def send(*a, **kw):
        events.append('notify')
        sent.append(kw)
    store = SimpleNamespace(tenant_id='tenant', latest=lambda *a: (dict(trip), [item]),
                            append_version=append, enqueue_notice=send, enqueue_message=send)
    return store, item, plan, sent, events


@pytest.mark.parametrize('mode', ['apply', 'ask', 'recheck_failed'])
def test_real_apply_or_ask_outbox_only_reports_applied_after_save(monkeypatch, mode):
    from app.domains.travel_ops.components.planning import pending
    from app.domains.travel_ops.components.itinerary import itinerary_fit
    store, item, plan, sent, events = plan_world()
    monkeypatch.setattr(pending, 'decide', lambda **kw: pending.Decision('ask' if mode == 'ask' else 'apply',
                                                                 'protected', 'customer_pinned', False))
    monkeypatch.setattr(pending, 'options_from', lambda *a: [{'key': 'one', 'rank': 1, 'name': '박물관'}])
    monkeypatch.setattr(pending.PendingStore, 'open', lambda *a, **kw: uuid4())
    monkeypatch.setattr(itinerary_fit, 'fit_change', lambda *a, **kw: SimpleNamespace(
        change=None if mode == 'recheck_failed' else plan, skipped=[]))
    outcome = pending.apply_or_ask(None, store=store, trip_id=uuid4(), item_id=item.item_id, plan=plan)
    response = sent[0]['payload']['response']
    expected = {'apply': 'applied', 'ask': 'awaiting_choice', 'recheck_failed': 'failed'}[mode]
    assert response['execution']['status'] == expected
    assert response['version'] == (8 if mode == 'apply' else 7)
    assert events == (['append', 'notify'] if mode == 'apply' else ['notify'])
    if mode == 'apply':
        assert response['questions'][0]['target']['item_id'] == str(item.item_id)
    if mode == 'ask':
        assert response['workflow']['protected_by'] == 'customer_pinned'
        assert response['followup']['options'][0]['key'] == 'one'
    assert outcome['status'] == {'apply': 'adjusted', 'ask': 'asked', 'recheck_failed': 'rechecked'}[mode]


class Connection:
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def transaction(self):
        return nullcontext()


@pytest.mark.parametrize('mode', ['applied', 'asked', 'unknown', 'failed', 'mismatched_version'])
def test_watch_reads_actual_saved_case_instead_of_resolved_or_digest(monkeypatch, mode):
    from app.domains.travel_ops.components.watch import trip_watch_cases as watch
    store, item, plan, sent, _ = plan_world()
    case_id, trip_id = uuid4(), uuid4()
    state = {'answer': '이미 바꿨어요.', 'required_input_schema': {'confirmed': 'boolean'},
             'resume_token': 'keep', 'approval_status': 'pending'}
    if mode == 'applied':
        state['applied_actions'] = [{'result_ref': f'trip:{trip_id}:v7', 'summary': {'version': 7}}]
    if mode == 'asked':
        state['applied_actions'] = [{'result_ref': f'trip:{trip_id}:proposal:one', 'summary': {'status': 'asked', 'proposal_id': 'one'}}]
    if mode == 'mismatched_version':
        state['applied_actions'] = [{'result_ref': f'trip:{trip_id}:v6', 'summary': {'version': 6}}]
    before = deepcopy(state)
    repo = SimpleNamespace(get_case=lambda *a, **kw: {'status': 'failed' if mode == 'failed' else 'resolved', 'state_json': state})
    watcher = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=Connection,
                                       clock=lambda: datetime(2026, 10, 24, tzinfo=UTC), repository=repo,
                                       run_case=lambda **kw: pytest.fail('writing must not run business'))
    watcher._contexts = {case_id: {'trip_id': trip_id, 'item': item, 'causes': plan.causes}}
    result = watch.CaseTickResult()
    watcher._after_run(case_id, {'status': 'resolved'}, result)
    response = result.responses[0]['response']
    assert response['execution']['status'] == {'asked': 'awaiting_choice', 'mismatched_version': 'unknown'}.get(mode, mode)
    assert response['workflow']['approval_status'] == 'pending'
    assert response['workflow']['resume_token'] == 'keep'
    assert state == before and not sent
    if mode in ('unknown', 'failed', 'mismatched_version'):
        assert '이미 바꿨어요' not in response['answer']
        assert response['completion'] == 'partial'


def test_watch_failure_outbox_uses_common_response_and_existing_dedupe():
    from app.domains.travel_ops.components.watch import trip_watch_cases as watch
    store, item, _, sent, _ = plan_world()
    watcher = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=Connection,
        clock=lambda: datetime(2026, 10, 24, tzinfo=UTC), repository=None, run_case=None)
    result = watch.CaseTickResult()
    watcher._defer_notice(uuid4(), item, {'error_code': 'timeout', 'failed_categories': ['weather']}, watcher.clock(), result)
    payload = sent[0]['payload']
    assert payload['response']['execution']['status'] == 'failed'
    # 최신 upstream은 임의 error_code를 공개하지 않고 허용 enum으로 정규화한다.
    assert 'source_failed' in payload['text'] and '기존 일정을 유지' in payload['text']
    assert sent[0]['key'].startswith('watch-deferred:')


def test_response_reformat_is_idempotent_and_never_reexecutes_business():
    first = adapter().monitoring_payload({'text': '선택해 주세요.', 'options': [{'key': 'one'}]},
                                          status='awaiting_choice', version=3)
    second = adapter().monitoring_payload(first, status='awaiting_choice', version=3)
    assert second == first


def test_saved_case_with_explicit_unknown_is_not_applied():
    scope = {'tenant_id': 't', 'customer_id': 'c', 'trip_id': 'trip'}
    state = {'applied_actions': [{'result_ref': 'trip:trip:v3', 'summary': {'status': 'unknown'}}]}
    payload = adapter().case_payload(case={'status': 'resolved', 'state_json': state}, trip={'version': 3},
        scope=scope, case_id='case', causes=[], items=[], checked_at='now')
    assert payload['response']['execution']['status'] == 'unknown'
    assert payload['response']['completion'] == 'partial'


def test_append_failure_never_builds_a_completed_notice(monkeypatch):
    from app.domains.travel_ops.components.planning import pending
    from app.domains.travel_ops.components.itinerary import itinerary_fit
    store, item, plan, sent, _ = plan_world()
    monkeypatch.setattr(pending, 'decide', lambda **kw: pending.Decision('apply', None, None, False))
    monkeypatch.setattr(itinerary_fit, 'fit_change', lambda *a, **kw: SimpleNamespace(change=plan))
    def failed(*a, **kw):
        raise pending.StaleItinerary('changed')
    store.append_version = failed
    assert pending.apply_or_ask(None, store=store, trip_id=uuid4(), item_id=item.item_id, plan=plan)['status'] == 'stale'
    assert not sent


def test_watch_writer_error_never_reexecutes_or_closes_business(monkeypatch):
    from app.domains.travel_ops.components.watch import trip_watch_cases as watch
    store, item, _, sent, _ = plan_world()
    case_id = uuid4()
    watcher = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=Connection,
        clock=lambda: datetime.now(UTC), repository=SimpleNamespace(get_case=lambda *a, **k: {}),
        run_case=lambda **kw: pytest.fail('rerun'))
    watcher._contexts = {case_id: {'trip_id': uuid4(), 'item': item, 'causes': []}}
    def failed(**kw):
        raise ValueError('writer failed')
    monkeypatch.setattr(adapter(), 'case_payload', failed)
    monkeypatch.setattr(watcher, '_close_failed', lambda *a: pytest.fail('closed business'))
    result = watch.CaseTickResult()
    watcher._after_run(case_id, {'status': 'resolved'}, result)
    assert result.responses == [{'case_id': str(case_id), 'status': 'writing_failed', 'error': 'ValueError'}]
    assert not sent


def test_watch_unresolved_customer_outbox_is_failed_not_complete(monkeypatch):
    from app.domains.travel_ops.components.watch import trip_watch_cases as watch
    store, item, plan, sent, _ = plan_world()
    case_id = uuid4()
    watcher = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=Connection,
        clock=lambda: datetime.now(UTC), repository=SimpleNamespace(get_case=lambda *a, **k: {'status': 'escalated'}), run_case=None)
    watcher._contexts = {case_id: {'trip_id': uuid4(), 'item': item, 'causes': plan.causes}}
    monkeypatch.setattr(watcher, '_escalation', lambda *a: ('itinerary_unresolved', ''))
    monkeypatch.setattr(watcher, '_offer_relaxed', lambda *a: False)
    watcher._after_run(case_id, {'status': 'escalated'}, watch.CaseTickResult())
    assert sent[0]['payload']['response']['execution']['status'] == 'failed'
    assert '일정은 그대로' in sent[0]['payload']['text']


def test_tick_runs_business_once_and_writing_does_not_enqueue_a_second_change(monkeypatch):
    from app.domains.travel_ops.components.watch import trip_watch_cases as watch
    store, item, _, sent, _ = plan_world()
    case_id, trip_id = uuid4(), uuid4()
    store.due = lambda *a, **kw: []
    state = {'answer': '박물관으로 바꿨어요.', 'applied_actions': [{'result_ref': f'trip:{trip_id}:v7', 'summary': {}}]}
    repo = SimpleNamespace(get_case=lambda *a, **kw: {'status': 'resolved', 'state_json': state})
    calls = []
    def run(**kw):
        calls.append(kw)
        return {'status': 'resolved'}
    watcher = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=Connection,
        clock=lambda: datetime.now(UTC), repository=repo, run_case=run)
    def opened(issues, now, result, cases):
        cases.append(case_id)
        watcher._contexts[case_id] = {'trip_id': trip_id, 'item': item, 'causes': []}
    monkeypatch.setattr(watcher, '_open_issues', opened)
    monkeypatch.setattr(watch.PendingStore, 'expire', lambda *a, **kw: [])
    result = watcher.tick()
    assert len(calls) == 1
    assert result.responses[0]['response']['execution']['status'] == 'applied'
    assert result.ran == [{'case_id': str(case_id), 'status': 'resolved'}]
    assert not sent


def test_batch_unresolved_outbox_also_uses_common_response(monkeypatch):
    from app.domains.travel_ops.components.watch import trip_watch_cases as watch
    store, item, plan, sent, _ = plan_world()
    case_id, trip_id = uuid4(), uuid4()
    watcher = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=Connection,
        clock=lambda: datetime.now(UTC), repository=None, run_case=None)
    issue = watch.Issue(trip_id, item, plan.causes, 'activity_other', 'place')
    monkeypatch.setattr(watcher, '_escalation', lambda *a: ('itinerary_unresolved', f'outcome:{item.item_id}:no_alternate'))
    monkeypatch.setattr(watcher, '_offer_relaxed', lambda *a: False)
    watcher._after_batch(case_id, {'trip_id': trip_id, 'batch': [issue]}, watch.CaseTickResult())
    assert sent[0]['payload']['response']['execution']['status'] == 'failed'
    assert sent[0]['payload']['response']['followup']['causes'] == plan.causes


def test_pre_save_digest_is_not_decorated_as_completed():
    from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, digest
    _, item, plan, _, _ = plan_world()
    payload = digest([Outcome(item, 'applied', causes=plan.causes, change=plan)], kind='change_notice')
    assert 'response' not in payload
    assert 'version' not in payload


@pytest.mark.parametrize('mode', ['forecast', 'consent_options', 'chosen'])
def test_remaining_pending_notices_keep_waiting_or_saved_status(monkeypatch, mode):
    from app.domains.travel_ops.components.planning import pending
    from app.domains.travel_ops.components.itinerary import itinerary_changes, itinerary
    store, item, plan, sent, _ = plan_world()
    item.place = {'place_id': 'place'}
    trip_id, proposal_id = uuid4(), uuid4()
    options = [{'key': 'one', 'rank': 1, 'name': '박물관'}]
    monkeypatch.setattr(pending.PendingStore, 'open', lambda *a, **kw: proposal_id)
    monkeypatch.setattr(pending, 'options_from', lambda *a: options)
    if mode == 'forecast':
        cursor = SimpleNamespace(execute=lambda *a: None, fetchone=lambda: None)
        class Cursor:
            def __enter__(self): return cursor
            def __exit__(self, *a): pass
        conn = SimpleNamespace(cursor=Cursor)
        pending.forecast_attention(conn, store=store, trip_id=trip_id, item=item,
            report={'verdict': 'clear', 'advisories': [{'category': 'forecast', 'field': 'precipitation_probability', 'value': 80}]})
    elif mode == 'consent_options':
        monkeypatch.setattr(itinerary, 'catalog_activity_places', lambda *a, **kw: [])
        monkeypatch.setattr(itinerary_changes, 'plan_activity_adjustment', lambda **kw: plan)
        pending._consented(None, store=store,
            pending=SimpleNamespace(set_options=lambda *a, **kw: None), trip_id=trip_id,
            proposal={'proposal_id': proposal_id, 'cause_json': plan.causes, 'reason': pending.CONSENT_REASON},
            current=item, items=[item], places_by_id={}, check=lambda **kw: {})
    else:
        proposal = {'status': 'open', 'expires_at': None, 'options_json': options, 'item_id': item.item_id,
                    'base_version': 7, 'reason': 'ask_first'}
        monkeypatch.setattr(pending, 'plan_swap', lambda **kw: plan)
        pending.choose(conn=None, store=store,
            pending=SimpleNamespace(get=lambda *a, **kw: proposal, close=lambda *a, **kw: None),
            trip_id=trip_id, proposal_id=proposal_id, key='one', by='customer', places_by_id={}, check=None)
    response = sent[0]['payload']['response']
    assert response['execution']['status'] == ('applied' if mode == 'chosen' else 'awaiting_choice')
    assert response['version'] == (8 if mode == 'chosen' else 7)
    if mode == 'forecast':
        assert '80%' in sent[0]['payload']['text']


def test_planning_preserves_existing_approval_fields_without_inventing_approval():
    from app.domains.travel_ops.components.planning import pending
    store, _, _, _, _ = plan_world()
    payload = {'text': '선택해 주세요.', 'approval_status': 'supplier_pending', 'approval_required': True,
               'required_input_schema': {'confirmed': 'boolean'}, 'resume_token': 'opaque'}
    result = pending._response_payload(None, store=store, trip_id=uuid4(), payload=payload, status='awaiting_choice')
    for key in ('approval_status', 'approval_required', 'required_input_schema', 'resume_token'):
        assert result['response']['workflow'][key] == payload[key]


@pytest.mark.parametrize('setting,pinned,expected', [('on', False, 'applied'), ('off', False, 'awaiting_choice'),
    ('missing', False, 'awaiting_choice'), ('on', True, 'awaiting_choice')])
def test_real_d020_gate_is_unchanged_by_response_adapter(monkeypatch, setting, pinned, expected):
    from app.domains.travel_ops.components.planning import pending
    from app.domains.travel_ops.components.itinerary import itinerary_fit
    store, item, plan, sent, _ = plan_world()
    original_latest = store.latest
    constraints = {} if setting == 'missing' else {'survey': {'on_disruption': 'replace' if setting == 'on' else 'ask_first'},
                                                  'survey_answered': ['on_disruption']}
    store.latest = lambda *a: ({**original_latest(*a)[0], 'constraints': constraints}, [item])
    item.detail['customer_pinned'] = pinned
    monkeypatch.setattr(pending, 'options_from', lambda *a: [{'key': 'one', 'rank': 1, 'name': '박물관'}])
    monkeypatch.setattr(pending.PendingStore, 'open', lambda *a, **kw: uuid4())
    monkeypatch.setattr(itinerary_fit, 'fit_change', lambda *a, **kw: SimpleNamespace(change=plan))
    pending.apply_or_ask(None, store=store, trip_id=uuid4(), item_id=item.item_id, plan=plan)
    assert sent[0]['payload']['response']['execution']['status'] == expected


@pytest.mark.parametrize('summary,expected', [({'status': 'failed'}, 'failed'),
    ({'batch': {'applied': ['one'], 'retry': ['two']}}, 'failed'),
    ({'batch': {'applied': ['one'], 'asked': [{'proposal_id': 'two'}]}}, 'awaiting_choice')])
def test_mixed_or_failed_saved_action_is_not_whole_batch_complete(summary, expected):
    scope = {'tenant_id': 't', 'customer_id': 'c', 'trip_id': 'trip'}
    case = {'status': 'resolved', 'state_json': {'applied_actions': [{'result_ref': 'trip:trip:v3', 'summary': summary}]}}
    result = adapter().case_payload(case=case, trip={'version': 3}, scope=scope, case_id='case',
        causes=[], items=['one', 'two'], checked_at='now')
    assert result['response']['execution']['status'] == expected
    assert result['response']['completion'] == 'partial'
    assert result['response']['execution']['saved_version'] == 3
    assert result['response']['execution']['applied_actions'][0]['summary'] == summary
