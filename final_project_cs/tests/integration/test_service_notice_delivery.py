"""Service notices use customer delivery and remain in the app without Discord."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application import admin_service as admin
from app.application import service_notifications as service
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.watch import trip_events
from app.domains.travel_ops.components.watch.notice_routing import CustomerNoticeRouter
from app.domains.travel_ops.modules.web_account import admin_customer_api
from app.infrastructure.db.session import get_connection
from app.infrastructure.notify.suppressed import NoticeSuppressed
from app.presentation.admin_api import COMMAND


@pytest.fixture
def state():
    with get_connection() as conn:
        tenant, customer = 'service_notice_' + uuid4().hex, uuid4()
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'여행 공지 시험')", (tenant,))
        conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,'travel-notice-test')", (customer,tenant))
        try:
            yield conn, tenant, customer
        finally:
            conn.rollback()


def command(state, **fields):
    now=datetime.now(admin.KST)
    result={'type':'publish-notice','requestId':str(uuid4()),'notifyUsers':True,'audience':'customer','customerId':str(state[2]),
            'notice':{'kind':'안내','title':'여행 서비스 안내','body':'새 알림 기능을 확인합니다.','titleEn':'','bodyEn':'',
                      'startsAt':(now-timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M'),'endsAt':(now+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')}}
    result.update(fields)
    return result


def mutate(state, payload):
    admin.mutate(state[0],state[1],'test-operator',payload)


def rows(state):
    return state[0].execute("SELECT dedupe_key,payload_json,status,available_at FROM outbox WHERE tenant_id=%s AND topic='customer.notice'",(state[1],)).fetchall()


def test_one_customer_is_enqueued_once_and_retry_does_not_repeat_audit(state):
    payload=command(state);mutate(state,payload)
    audit=state[0].execute('SELECT count(*) FROM admin_audit WHERE tenant_id=%s',(state[1],)).fetchone()[0]
    mutate(state,payload)
    assert len(rows(state))==1
    assert rows(state)[0][0]==f'{state[2]}:service:{payload["requestId"]}'
    assert state[0].execute('SELECT count(*) FROM admin_audit WHERE tenant_id=%s',(state[1],)).fetchone()[0]==audit


def test_conflicting_retry_is_rejected_before_notice_changes(state):
    payload=command(state);mutate(state,payload)
    changed={**payload,'notice':{**payload['notice'],'body':'다른 내용'}}
    with pytest.raises(admin.AdminServiceError) as error:mutate(state,changed)
    assert error.value.status_code==409
    assert admin.record(state[0],state[1],'notice',payload['requestId'])['body']==payload['notice']['body']
    assert len(rows(state))==1


def test_all_recipients_are_scoped_and_blocked_customers_excluded(state):
    conn,tenant,customer=state
    other=uuid4();blocked=uuid4()
    for identity in (other,blocked):conn.execute('INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)',(identity,tenant,str(identity)))
    admin.mutate(conn,tenant,'test-operator',{'type':'block-user','userId':str(blocked),'blocked':True,'reason':'시험'})
    mutate(state,command(state,audience='all',customerId=None))
    assert {row[0].split(':')[0] for row in rows(state)}=={str(customer),str(other)}


def test_customer_from_another_tenant_cannot_be_targeted(state):
    with pytest.raises(admin.AdminServiceError) as error:mutate(state,command(state,customerId=str(uuid4())))
    assert error.value.status_code==404
    assert rows(state)==[]


def test_notification_requires_a_request_id(state):
    with pytest.raises(admin.AdminServiceError) as error:mutate(state,command(state,requestId=None))
    assert error.value.status_code==422
    assert rows(state)==[]


def test_disabled_notification_keeps_public_post_without_external_queue(state):
    payload=command(state,notifyUsers=False,audience='all',customerId=None)
    mutate(state,payload)
    assert rows(state)==[]
    assert admin.record(state[0],state[1],'notice',payload['requestId'])['title']==payload['notice']['title']


def test_future_post_is_queued_for_start_and_not_in_current_trip_fingerprint(state):
    payload=command(state)
    start=datetime.now(admin.KST)+timedelta(hours=2)
    payload['notice'].update(startsAt=start.strftime('%Y-%m-%dT%H:%M'),endsAt=(start+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
    mutate(state,payload)
    trip_id,_=TripStore(state[1]).create_trip(state[0],customer_id=state[2],title='서울 여행',locale='ko',party_size=1,items=[],constraints={})
    assert rows(state)[0][3]>datetime.now(timezone.utc)
    assert trip_events.snapshot(state[0],state[1],trip_id)['notices'][0]==0


def test_customer_notice_is_in_trip_fingerprint_even_when_discord_skipped(state):
    mutate(state,command(state))
    # This rollback-only fixture has a transaction-start now(). Model a notice
    # already visible before that transaction, as a committed notice is in production.
    state[0].execute("UPDATE outbox SET status='skipped', payload_json=jsonb_set(payload_json,'{visible_at}',to_jsonb((now()-interval '1 second')::text)) WHERE tenant_id=%s",(state[1],))
    trip_id,_=TripStore(state[1]).create_trip(state[0],customer_id=state[2],title='서울 여행',locale='ko',party_size=1,items=[],constraints={})
    assert trip_events.snapshot(state[0],state[1],trip_id)['notices'][0]==1
    assert service.delivery(state[0],state[1],rows(state)[0][1]['service_notice_id'])['skipped']==1


def test_targeted_notice_is_not_exposed_to_public_notice_banner(state,monkeypatch):
    mutate(state,command(state))
    @contextmanager
    def connection():yield state[0]
    monkeypatch.setattr(admin_customer_api,'get_connection',connection)
    monkeypatch.setattr(admin_customer_api,'get_settings',lambda:SimpleNamespace(tenant_id=state[1]))
    app=FastAPI();app.include_router(admin_customer_api.build_router())
    assert TestClient(app).get('/v1/web/support/notices').json()['notices']==[]


def test_public_notice_excludes_operator_and_delivery_metadata(state,monkeypatch):
    mutate(state,command(state,audience='all',customerId=None))
    @contextmanager
    def connection():yield state[0]
    monkeypatch.setattr(admin_customer_api,'get_connection',connection)
    monkeypatch.setattr(admin_customer_api,'get_settings',lambda:SimpleNamespace(tenant_id=state[1]))
    app=FastAPI();app.include_router(admin_customer_api.build_router())
    notice=TestClient(app).get('/v1/web/support/notices').json()['notices'][0]
    assert notice['title']=='여행 서비스 안내'
    assert not {'author','deliveryRequestId','customerId'} & notice.keys()


def test_maintenance_and_end_notice_are_enqueued_with_policy(state):
    payload={'type':'maintenance','requestId':str(uuid4()),'notifyUsers':True,'audience':'customer','customerId':str(state[2]),'enabled':True,'message':'점검 중','messageEn':'','endsAt':'2099-01-01T03:00','reason':'여행 서비스 시험'}
    mutate(state,payload)
    assert admin.access_policy(state[0],state[1],str(state[2]))['maintenance']
    mutate(state,{**payload,'requestId':str(uuid4()),'enabled':False})
    assert admin.access_policy(state[0],state[1],str(state[2]))['maintenance'] is None
    assert len(rows(state))==2


def router(state, monkeypatch):
    @contextmanager
    def connection():yield state[0]
    operator=[];sent=[]
    target=CustomerNoticeRouter(operator=operator.append,connection_factory=connection,enabled=lambda:True,renderer=None,allowed_tenants={state[1]})
    monkeypatch.setattr(target,'_send',lambda found,*args,**kwargs:sent.append(found))
    monkeypatch.setattr(target,'_customer_destination',lambda conn,tenant,customer:customer)
    return target,operator,sent


def message(state):
    key,payload,_,_=rows(state)[0]
    return {'topic':'customer.notice','tenant_id':state[1],'dedupe_key':key,'payload':payload}


def test_service_topic_uses_customer_channel_and_never_operator(state,monkeypatch):
    mutate(state,command(state));target,operator,sent=router(state,monkeypatch)
    target(message(state))
    assert sent==[state[2]] and operator==[]


@pytest.mark.parametrize('fault',['tenant','key','expired','switch'])
def test_service_delivery_preserves_send_boundaries(state,monkeypatch,fault):
    mutate(state,command(state));target,operator,sent=router(state,monkeypatch);notice=message(state)
    if fault=='tenant':notice['tenant_id']='other'
    if fault=='key':notice['dedupe_key']=f'{uuid4()}:wrong'
    if fault=='expired':notice['payload']['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    if fault=='switch':monkeypatch.setattr(target,'_enabled',lambda:False)
    with pytest.raises(NoticeSuppressed):target(notice)
    assert sent==[] and operator==[] and len(rows(state))==1


def test_admin_schema_preserves_target_and_rejects_spoofed_actor(state):
    payload=command(state)
    parsed=COMMAND.validate_python(payload).model_dump(mode='json')
    assert parsed['customerId']==str(state[2]) and parsed['requestId']==payload['requestId']
    from pydantic import ValidationError
    with pytest.raises(ValidationError):COMMAND.validate_python({**payload,'actor':'spoofed'})


def test_ended_notice_can_be_saved_without_sending(state):
    now = datetime.now(admin.KST)
    from datetime import timedelta
    payload = command(state, notifyUsers=False, audience='all', customerId=None)
    payload['notice'].update(startsAt=(now-timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
                             endsAt=(now-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
    mutate(state, payload)
    assert rows(state) == []
    assert admin.record(state[0], state[1], 'notice', payload['requestId'])['title'] == payload['notice']['title']


def test_ended_notice_cannot_be_sent_to_customer(state):
    now = datetime.now(admin.KST)
    from datetime import timedelta
    payload = command(state)
    payload['notice'].update(startsAt=(now-timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
                             endsAt=(now-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
    with pytest.raises(admin.AdminServiceError) as error:
        mutate(state, payload)
    assert error.value.status_code == 422
    assert rows(state) == []
    assert not admin.record(state[0], state[1], 'notice', payload['requestId'])
