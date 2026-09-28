# DoD-07 재측정 원문 (수집: 구현 담당, 판정 없음)

## 재현 명령
```powershell
python -m pytest tests\security -q
@'
from uuid import uuid4
from fastapi.testclient import TestClient
import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app
original=settings_module.get_settings(); tenant='measure_pii_'+uuid4().hex; customer=uuid4(); configured=original.model_copy(update={'tenant_id':tenant})
settings_module.get_settings=lambda: configured; security.get_settings=lambda: configured
with get_connection() as conn, conn.transaction():
    with conn.cursor() as cur:
        cur.execute('INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)',(tenant,'PII measurement')); cur.execute('INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)',(customer,tenant,'pii-customer'))
try:
    client=TestClient(create_app(classifier=lambda _: {'intent':'billing','issue_code':'payment_failed','sentiment':'negative'})); token='Bearer '+security._development_key('case:write',original.secret_key)
    values=['010-1234-5678','4111 1111 1111 1111','sk-measure-original-api-key','pay_measure_original_987654']; message='phone='+values[0]+' card='+values[1]+' api_key='+values[2]+' payment='+values[3]
    response=client.post('/v1/cases',headers={'Authorization':token},json={'request_id':'pii-measurement','customer_id':str(customer),'message':message,'channel':'test'}); print('POST status=',response.status_code); case_id=response.json()['case_id']; print('case_id=',case_id)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT subject, state_json::text FROM customer_cases WHERE tenant_id=%s AND case_id=%s',(tenant,case_id)); print('customer_cases=',cur.fetchone()); cur.execute('SELECT event_type,payload_json::text,actor_id FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version',(tenant,case_id)); print('case_events=',cur.fetchall())
finally:
    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute('DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)',(tenant,)); cur.execute('DELETE FROM action_requests WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM case_events WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM customer_cases WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM customers WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM tenants WHERE tenant_id=%s',(tenant,))
'@ | python -
```

## 실제 출력
```
...                                                                      [100%]
… warning 상세 6줄 생략
3 passed, 1 warning in 3.74s
POST status= 201
case_id= 166ad2ae-8f99-4402-9781-cc956a447969
customer_cases= ('phone=010-****-5678 card=**** **** **** 1111 api_key=[REDACTED_API_KEY] payment=[REDACTED_PAYMENT_ID]', '{"last_event": "classified"}')
case_events= [('created', '{"channel": "test", "message": "phone=010-****-5678 card=**** **** **** 1111 api_key=[REDACTED_API_KEY] payment=[REDACTED_PAYMENT_ID]"}', 'key-2'), ('classified', '{"intent": "billing", "sentiment": "negative", "issue_code": "payment_failed"}', 'key-2')]
```

## 관측 사실
- `tests\security` 출력의 집계는 `3 passed, 1 warning`이다.
- `customer_cases.subject` 출력에는 `010-****-5678`, `**** **** **** 1111`, `[REDACTED_API_KEY]`, `[REDACTED_PAYMENT_ID]`가 포함되어 있다.
- `case_events`에는 `created`, `classified` 두 행이 출력되었다.
- 측정 tenant, customer, case 관련 행은 명령의 finally 정리 구문으로 삭제했다.

## 확인하지 못한 것
- 동일 PII 문자열을 포함한 기존 `demo` 데이터 전체 검색 결과는 확인하지 못했다.
