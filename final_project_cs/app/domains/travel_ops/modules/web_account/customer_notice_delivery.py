"""관리자가 저장한 테넌트별 고객 발송 설정을 발송 직전에 읽는다."""
from app.core.settings import get_guardrails
from app.infrastructure.db.session import get_connection

KEY = "travel.notice_per_customer_enabled"


def enabled(tenant_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM runtime_limits WHERE tenant_id=%s AND name=%s",
                           (tenant_id, KEY)).fetchone()
    if row is None:
        return get_guardrails().get(KEY) is True
    if not isinstance(row[0], bool):
        raise ValueError("고객 외부 알림 설정이 boolean이 아닙니다")
    return row[0]
