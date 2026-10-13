"""외부 호출 없이 실제 PostgreSQL 다중 연결의 예산·설정 경합을 검증한다."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
from threading import Barrier, Lock
from uuid import uuid4
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
CS=HERE.parents[4]/'final_project_cs'
sys.path[:0]=[str(HERE/'.deps'),str(CS)]
import psycopg
from app.infrastructure.db.migrate import apply_all,safety_manifest
from app.application import operations_policy as policy

dbname='verification_ops_concurrency_'+uuid4().hex[:12]
base='host=127.0.0.1 port=55483 user=verification '
dsn=base+'dbname='+dbname
checks=[]
trial_rows=[]
created=False
stopped=False

@contextmanager
def connection():
    with psycopg.connect(dsn) as conn:
        yield conn

def check(name,condition,actual):
    checks.append({'name':name,'passed':bool(condition),'actual':actual})

try:
    with psycopg.connect(base+'dbname=postgres',autocommit=True) as conn:
        conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(dbname)))
        created=True
    with connection() as conn:
        apply_all(conn)
    sql_inputs=safety_manifest()
    for trial in range(3):
        tenant='verification_concurrency_'+uuid4().hex
        customer,trip=uuid4(),uuid4()
        with connection() as conn:
            conn.execute('INSERT INTO tenants(tenant_id,name) VALUES(%s,%s)',(tenant,'검증 합성 여행'))
            conn.execute('INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)',(customer,tenant,'synthetic'))
            conn.execute('INSERT INTO trips(trip_id,tenant_id,customer_id,title) VALUES(%s,%s,%s,%s)',(trip,tenant,customer,'검증 합성 여행'))
            policy.save(conn,tenant,expected_revision=0,policy=policy.SourcePolicy(allow_paid=True,daily_paid_cap=1,trip_paid_cap=1),actor='verification',reason='합성 경합 시험')
        now=datetime.now(ZoneInfo('Asia/Seoul')).replace(hour=4)
        barrier=Barrier(8)
        lock=Lock()
        calls=[]
        def free():
            return policy.Verdict(status='unverifiable',source='synthetic',checked_at=now,valid_until=now+timedelta(minutes=1))
        def paid():
            with lock: calls.append('in_process_only')
            return policy.Verdict(status='closed',source='synthetic',checked_at=now,valid_until=now+timedelta(minutes=1))
        def lookup(index):
            barrier.wait(timeout=15)
            return policy.select(connection_factory=connection,tenant=tenant,customer_id=customer,trip_id=trip,resource='synthetic-'+str(index),free=free,paid=paid,provider_reserve=lambda:True,context='dawn',now=now)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses=list(pool.map(lookup,range(8)))
        reasons=dict(Counter(row['reason'] for row in responses))
        with connection() as conn:
            used=conn.execute('SELECT coalesce(sum(used),0) FROM ops_lookup_usage WHERE tenant_id=%s',(tenant,)).fetchone()[0]
        check(f'budget-race-{trial+1}',reasons=={'verified_paid':1,'budget_exhausted':7} and len(calls)==1 and used==1,{'reasons':reasons,'local_paid_calls':len(calls),'used':used})
        cas_barrier=Barrier(2)
        def save(index):
            cas_barrier.wait(timeout=15)
            try:
                with connection() as conn:
                    policy.save(conn,tenant,expected_revision=1,policy=policy.SourcePolicy(),actor='verification',reason='합성 설정 경합')
                return 'saved'
            except Exception as exc:
                return 'conflict' if getattr(exc,'status_code',None)==409 or '다시 읽어' in str(exc) else type(exc).__name__
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(save,range(2)))
        with connection() as conn:
            revision=policy.read(conn,tenant)['revision']
            audits=conn.execute("SELECT count(*) FROM admin_audit WHERE tenant_id=%s AND action='source-policy'",(tenant,)).fetchone()[0]
        check(f'policy-cas-{trial+1}',Counter(results)==Counter({'saved':1,'conflict':1}) and revision==2 and audits==2,{'results':results,'revision':revision,'audits':audits})
        trial_rows.append({'trial':trial+1,'budget_reasons':reasons,'cas':results})
finally:
    if created:
        with psycopg.connect(base+'dbname=postgres',autocommit=True) as conn:
            assert dbname.startswith('verification_ops_concurrency_')
            conn.execute(psycopg.sql.SQL('DROP DATABASE {}').format(psycopg.sql.Identifier(dbname)))
            stopped=not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(dbname,)).fetchone()

source='app/application/operations_policy.py'
result={'at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'scope':'새 격리 PostgreSQL 전체 SQL·실제 다중 연결·제공처 함수는 프로세스 안 대역·외부 유료 호출 0회','checks':checks,'trials':trial_rows,'created_database_dropped':stopped,'source_sha256':hashlib.sha256((CS/source).read_bytes()).hexdigest(),'migration_manifest':sql_inputs}
output=HERE/'runs/2026-10-12_common_final_1/operations-concurrency.json'
if output.exists(): raise SystemExit('기존 결과가 있습니다.')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:value for key,value in result.items() if key!='migration_manifest'},ensure_ascii=False,indent=2))
raise SystemExit(0 if all(row['passed'] for row in checks) and stopped else 1)
