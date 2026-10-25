"""Historical failure fixtures, not new real-model acceptance."""
import asyncio
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

CASES = json.loads(Path(__file__).with_name('public_decision_failure_cases.json').read_text(encoding='utf8'))

@pytest.mark.parametrize('case_id', ['T08', 'T11', 'P03'])
def test_same_public_entrypoint_keeps_failure_private_for_json_sse(monkeypatch, case_id):
    from fastapi import BackgroundTasks
    from starlette.requests import Request
    from app.domains.travel_ops.entry import trip_api
    from app.domains.travel_ops.components.conversation import trip_messages as tm, chat_log
    from app.domains.travel_ops.modules.web_account import web_guard
    from app.domains.travel_ops.modules.live_progress import op_stream
    from app.application import classification
    from app.infrastructure.db import repository

    row = next(r for r in CASES if r['id']==case_id)
    old = row['old_public']
    failure = old['failure']
    customer, trip = uuid4(), uuid4()
    conn = object()
    case = {'version': 1, 'status': 'escalated'}
    private_errors, saved_turns = [], []
    def classify(*args, **kwargs):
        with pytest.raises(RuntimeError) as exc:
            kwargs['classifier'](row['input_text'])
        private_errors.append(str(exc.value))
    monkeypatch.setattr(classification, 'classify_case', classify)
    monkeypatch.setattr(repository, 'get_case', lambda *a, **kw: case)
    def handle(**kw):
        return tm._run_decision(conn, tenant=kw['tenant'], trip_id=trip, case_id=uuid4(),
            message=kw['message'], request_id=kw['request_id'], at=datetime.now(timezone.utc),
            desk=None, store=None, items=[], decision=None, failure=failure, actor_id='fixture',
            policy_search=None, place_source=None, selected=None)
    monkeypatch.setattr(tm, 'handle_trip_message', handle)
    monkeypatch.setattr(web_guard, 'assert_human_check_configured', lambda: None)
    monkeypatch.setattr(web_guard, 'values', lambda tenant: {'web.dev_mode': 'off'})
    monkeypatch.setattr(web_guard, 'count', lambda *a, **kw: None)
    monkeypatch.setattr(trip_api, 'get_connection', lambda: nullcontext(conn))
    monkeypatch.setattr(trip_api.TripStore, 'latest', lambda *a: ({'customer_id': customer}, []))
    monkeypatch.setattr(chat_log, 'record', lambda *a, **kw: saved_turns.append(deepcopy(kw)))
    monkeypatch.setattr(op_stream, 'limits', lambda op: {'beat_seconds': .01, 'slow_seconds': 1, 'max_per_user': 2, 'max_seconds': 5})
    router=trip_api.build_trip_router()
    endpoint=next(r.endpoint for r in router.routes if r.path=='/v1/web/trips/{trip_id}/messages')
    def http(stream):
        async def receive(): return {'type':'http.request','body':b'', 'more_body':False}
        return Request({'type':'http','headers':[(b'accept', b'text/event-stream' if stream else b'application/json')],
            'client':('127.0.0.1',1), 'app':SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace(controller=None)))},receive)
    request=trip_api.WebMessageIn(request_id='fixture', message=row['input_text'])
    plain=endpoint(trip,request,http(False),BackgroundTasks(),('fixture',customer))
    stream=endpoint(trip,request,http(True),BackgroundTasks(),('fixture',customer))
    async def consume(): return ''.join([chunk async for chunk in stream.body_iterator])
    wire=asyncio.run(consume())
    result=[json.loads(f.split('data: ',1)[1]) for f in wire.split('\n\n') if f.startswith('event: result\n')][0]
    # IDs differ because these are separate fresh requests; authoritative failure fields agree.
    assert {k:v for k,v in result.items() if k!='case_id'} == {k:v for k,v in plain.items() if k!='case_id'}
    assert plain['status']=='escalated' and plain['reason']=='decision_failed'
    assert plain['case_status']=='escalated' and plain['answer']==old['answer']
    assert private_errors and all(failure in error for error in private_errors)
    assert saved_turns and all(turn['answer']==old['answer'] for turn in saved_turns)
    assert 'failure' not in plain
    assert failure not in json.dumps(plain,ensure_ascii=False) and failure not in wire
    assert 'evidence_validation' not in wire and 'OllamaContentError' not in wire
