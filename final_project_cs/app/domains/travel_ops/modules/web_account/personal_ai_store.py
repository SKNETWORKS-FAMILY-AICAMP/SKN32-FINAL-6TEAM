"""개인 AI OAuth 저장. 모든 읽기·교환은 tenant별 트랜잭션 잠금 안에서 수행한다."""
from contextlib import contextmanager

from psycopg.types.json import Jsonb

from app.infrastructure.db.session import get_connection


class PostgresStore:
    def __init__(self, tenant_id, connection=get_connection):
        self.tenant_id, self.connection = tenant_id, connection

    @contextmanager
    def transaction(self):
        with self.connection() as conn, conn.transaction():
            # 프로세스가 여럿이어도 코드 소비와 갱신·폐기가 교차하지 않는다.
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 901))", (self.tenant_id,))
            yield Records(conn, self.tenant_id)


class Records:
    def __init__(self, conn, tenant):
        self.conn, self.tenant = conn, tenant

    def get(self, kind, key):
        with self.conn.cursor() as cur:
            cur.execute("SELECT body FROM personal_ai_oauth_records WHERE tenant_id=%s AND kind=%s AND record_key=%s",
                        (self.tenant, kind, key))
            row = cur.fetchone()
            return row[0] if row else None

    def put(self, kind, key, body):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO personal_ai_oauth_records(tenant_id,kind,record_key,customer_id,body) "
                        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,kind,record_key) "
                        "DO UPDATE SET body=excluded.body,customer_id=excluded.customer_id,updated_at=now()",
                        (self.tenant, kind, key, body.get("customer"), Jsonb(body)))

    def list_grants(self, customer):
        with self.conn.cursor() as cur:
            cur.execute("SELECT record_key,body FROM personal_ai_oauth_records WHERE tenant_id=%s AND kind='grant' AND customer_id=%s",
                        (self.tenant, customer))
            return list(cur.fetchall())

    def is_member(self, customer):
        with self.conn.cursor() as cur:
            cur.execute("SELECT EXISTS(SELECT 1 FROM web_social_links WHERE tenant_id=%s AND customer_id=%s)",
                        (self.tenant, customer))
            return bool(cur.fetchone()[0])


def revoke_customer(conn, tenant_id, customer_id):
    """마지막 소셜 연결 해제와 같은 트랜잭션 안에서 동의를 거둔다."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 901))", (tenant_id,))
        cur.execute("UPDATE personal_ai_oauth_records SET body=body || jsonb_build_object('revoked',true,'revoked_at',extract(epoch from now())),updated_at=now() "
                    "WHERE tenant_id=%s AND customer_id=%s AND kind='grant'", (tenant_id, customer_id))
