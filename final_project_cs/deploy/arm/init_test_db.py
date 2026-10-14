"""격리된 ARM DB에 시험 테넌트만 만든다. 운영 사용자·외부 통지 설정은 가져오지 않는다."""
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection

with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
    cur.execute("INSERT INTO tenants(tenant_id,name) VALUES (%s,%s) ON CONFLICT(tenant_id) DO NOTHING",
                (get_settings().tenant_id, "ARM isolated travel serving test"))
print("ARM_TEST_TENANT_READY")
