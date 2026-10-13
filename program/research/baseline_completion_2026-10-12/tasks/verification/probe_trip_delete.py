"""새 운영 기록을 둔 합성 여행을 실제 삭제 함수로 지우고 모두 롤백한다."""
from datetime import datetime
import hashlib
import json
import argparse
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo
import psycopg

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--database',default='verification_common_final')
parser.add_argument('--run',default='2026-10-12_common_final_1')
parser.add_argument('--label',default='trip-delete-orphan-reproduction')
args=parser.parse_args()
if not args.database.startswith('verification'):
    parser.error('검증 전용 DB만 허용합니다.')
CS=HERE.parents[4]/'final_project_cs'
sys.path.insert(0,str(CS))
from app.domains.travel_ops.components.itinerary.trip_delete import delete_trip

tenant='verification_delete_'+uuid4().hex
customer,trip,event=uuid4(),uuid4(),uuid4()
dsn=f'host=127.0.0.1 port=55483 user=verification dbname={args.database}'
with psycopg.connect(dsn) as conn:
    with conn.transaction():
        conn.execute('INSERT INTO tenants(tenant_id,name) VALUES(%s,%s)',(tenant,'검증 합성 여행'))
        conn.execute('INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)',(customer,tenant,'synthetic'))
        conn.execute('INSERT INTO trips(trip_id,tenant_id,customer_id,title) VALUES(%s,%s,%s,%s)',(trip,tenant,customer,'검증 합성 여행'))
        conn.execute('INSERT INTO ops_lookup_usage(tenant_id,day,trip_id,used) VALUES(%s,current_date,%s,1)',(tenant,trip))
        conn.execute('INSERT INTO ops_lookup_checks(tenant_id,trip_id,resource_hash,checked_at) VALUES(%s,%s,%s,now())',(tenant,trip,'synthetic'))
        conn.execute("INSERT INTO ops_diagnostic_events(tenant_id,event_id,fingerprint,customer_id,trip_id,occurred_at,expires_at) VALUES(%s,%s,%s,%s,%s,now(),now()+interval '1 day')",(tenant,event,'synthetic',customer,trip))
        deleted=delete_trip(conn,tenant_id=tenant,customer_id=customer,trip_id=trip)
        remaining={table:conn.execute(psycopg.sql.SQL('SELECT count(*) FROM {} WHERE tenant_id=%s AND trip_id=%s').format(psycopg.sql.Identifier(table)),(tenant,trip)).fetchone()[0]
                   for table in ('trips','ops_lookup_usage','ops_lookup_checks')}
        diagnostic=conn.execute('SELECT trip_id IS NULL FROM ops_diagnostic_events WHERE tenant_id=%s AND event_id=%s',(tenant,event)).fetchone()[0]
        raise psycopg.Rollback()
    rollback_verified=conn.execute('SELECT count(*) FROM tenants WHERE tenant_id=%s',(tenant,)).fetchone()[0]==0
source_files=('app/domains/travel_ops/components/itinerary/trip_delete.py','app/infrastructure/db/migrations/902_unattended_operations.sql')
result={'at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'scope':'검증 전용 신규 DB·합성 자료·실제 삭제 함수·전체 롤백','deleted_counts':deleted,'remaining_trip_linked_rows':remaining,'diagnostic_trip_link_cleared':diagnostic,'rollback_verified':rollback_verified,'source_sha256':{path:hashlib.sha256((CS/path).read_bytes()).hexdigest() for path in source_files}}
output=HERE/'runs'/args.run/(args.label+'.json')
if output.exists(): raise SystemExit('기존 결과가 있습니다.')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
