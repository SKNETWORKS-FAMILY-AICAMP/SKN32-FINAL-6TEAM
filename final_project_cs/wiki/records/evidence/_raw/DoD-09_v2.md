# DoD-09 재측정 원문 (수집: 구현 담당, 판정 없음)

## 재현 명령
```powershell
@'
from uuid import uuid4
from fastapi.testclient import TestClient
import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app
original=settings_module.get_settings(); tenant='measure_api_'+uuid4().hex; customer=uuid4(); configured=original.model_copy(update={'tenant_id':tenant}); settings_module.get_settings=lambda: configured; security.get_settings=lambda: configured
with get_connection() as conn, conn.transaction():
    with conn.cursor() as cur:
        cur.execute('INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)',(tenant,'API measurement')); cur.execute('INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)',(customer,tenant,'api-customer'))
try:
    client=TestClient(create_app(classifier=lambda _: {'intent':'billing','issue_code':'payment_failed','sentiment':'negative'})); token='Bearer '+security._development_key('case:write',original.secret_key); response=client.post('/v1/cases',headers={'Authorization':token},json={'request_id':'api-measurement','customer_id':str(customer),'message':'payment failed','channel':'test'}); print('POST status=',response.status_code); print('response=',response.json()); case_id=response.json()['case_id']
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT intent,issue_code,sentiment,status FROM customer_cases WHERE tenant_id=%s AND case_id=%s',(tenant,case_id)); print('customer_cases=',cur.fetchone()); cur.execute("SELECT event_type FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version",(tenant,case_id)); print('case_events=',[r[0] for r in cur.fetchall()])
finally:
    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute('DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)',(tenant,)); cur.execute('DELETE FROM action_requests WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM case_events WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM customer_cases WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM customers WHERE tenant_id=%s',(tenant,)); cur.execute('DELETE FROM tenants WHERE tenant_id=%s',(tenant,))
'@ | python
```

## 실제 출력
```
POST status= 201
response= {'case_id': '75adf788-2cd7-4844-bef6-450686294ad4', 'status': 'routing', 'version': 2, 'intent': 'billing', 'issue_code': 'payment_failed', 'sentiment': 'negative', 'links': {'self': '/v1/cases/75adf788-2cd7-4844-bef6-450686294ad4'}}
customer_cases= ('billing', 'payment_failed', 'negative', 'routing')
case_events= ['created', 'classified']
```

## 관측 사실
- POST 응답 status는 `201`이다.
- POST 응답의 `intent`는 `billing`, `issue_code`는 `payment_failed`, `sentiment`는 `negative`, `status`는 `routing`이다.
- `customer_cases` 조회 튜플은 `('billing', 'payment_failed', 'negative', 'routing')`이다.
- `case_events` 조회 목록은 `['created', 'classified']`이다.
- 측정 tenant, customer, case 관련 행은 명령의 finally 정리 구문으로 삭제했다.

## 확인하지 못한 것
- 외부 분류기 실호출 결과는 확인하지 못했다. 측정에는 fake classifier를 주입했다.
