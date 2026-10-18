"""운영자가 시작한 전용 QA 계정 한 개의 수명. 호출자는 트랜잭션을 연다."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.application import admin_service as admin
from app.core.settings import get_guardrails
from . import member_cleanup, web_session

KIND, ID = "settings", "qa-account"


def _lock(conn, tenant):
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"admin:{tenant}:{KIND}:{ID}",))


def _state(conn, tenant):
    return admin.record(conn, tenant, KIND, ID)


def status(conn, tenant):
    state = _state(conn, tenant)
    customer = state.get("customer_id")
    exists = customer and conn.execute(
        "SELECT 1 FROM customers WHERE tenant_id=%s AND customer_id=%s", (tenant, customer)).fetchone()
    enabled = state.get("enabled") is True and bool(exists)
    trips = conn.execute("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s",
                         (tenant, customer)).fetchone()[0] if enabled else 0
    return {"enabled": enabled, "revision": state.get("revision", 0),
            "customer_id": customer if enabled else None, "trips": trips,
            "started_at": state.get("started_at") if enabled else None}


def _checked(conn, tenant, customer):
    row = conn.execute("SELECT external_id FROM customers WHERE tenant_id=%s AND customer_id=%s FOR UPDATE",
                       (tenant, customer)).fetchone()
    user = admin.record(conn, tenant, "user", str(customer))
    linked = conn.execute("SELECT 1 FROM web_social_links WHERE tenant_id=%s AND customer_id=%s",
                          (tenant, customer)).fetchone()
    if not row or not row[0].startswith("web:") or linked or user.get("qaManaged") is not True:
        raise admin.AdminServiceError(409, "전용 테스트 계정 표시가 맞지 않습니다. 일반 계정은 변경하지 않았습니다.")


def _save(conn, tenant, actor, value, action, reason):
    # 표 교환·계정 종료 뒤에는 로그인 표의 검증값도 상태에서 없앤다.
    value = {key: item for key, item in value.items() if not key.startswith("ticket_")}
    admin.put(conn, tenant, KIND, ID, value, actor=actor, action=action, reason=reason)


def change(conn, tenant, actor, *, enabled, expected_revision, reason, confirm_customer_id=None):
    _lock(conn, tenant)
    current = status(conn, tenant)
    if current["revision"] != expected_revision:
        raise admin.AdminServiceError(409, "다른 운영자가 상태를 바꿨습니다. 현재 상태를 다시 읽어 주세요.")
    if enabled == current["enabled"]:
        if enabled:
            _checked(conn, tenant, current["customer_id"])
        return current
    revision = current["revision"] + 1
    if enabled:
        customer = web_session.new_customer(conn, tenant_id=tenant)
        admin.put(conn, tenant, "user", str(customer), {"usageExempt": True, "qaManaged": True},
                  actor=actor, action="qa-account-created", reason=reason)
        value = {"enabled": True, "customer_id": str(customer), "revision": revision,
                 "started_at": datetime.now(UTC).isoformat()}
    else:
        customer = current["customer_id"]
        if str(confirm_customer_id) != customer:
            raise admin.AdminServiceError(409, "삭제할 전용 테스트 계정 번호가 현재 상태와 다릅니다.")
        _checked(conn, tenant, customer)
        done = member_cleanup.erase_customer(conn, tenant, UUID(customer))
        if done["customer"] != 1 or done["kept"]:
            raise admin.AdminServiceError(409, "테스트 계정 삭제가 끝나지 않아 전체 변경을 취소했습니다.")
        value = {"enabled": False, "customer_id": None, "revision": revision, "deleted": done}
    _save(conn, tenant, actor, value, "qa-account-start" if enabled else "qa-account-stop", reason)
    return status(conn, tenant)


def adopt_existing(conn, tenant, actor, customer_id, *, reason):
    """명시적 운영 명령 전용. HTTP 요청으로 임의 고객을 편입하지 않는다."""
    _lock(conn, tenant)
    current = status(conn, tenant)
    if current["enabled"]:
        if current["customer_id"] == str(customer_id):
            return current
        raise admin.AdminServiceError(409, "사용 중인 테스트 계정이 이미 있습니다.")
    admin.require_customer(conn, tenant, str(customer_id))
    user = admin.record(conn, tenant, "user", str(customer_id))
    if user.get("usageExempt") is not True:
        raise admin.AdminServiceError(409, "기존에 승인된 한도 예외 계정만 편입할 수 있습니다.")
    admin.put(conn, tenant, "user", str(customer_id), {**user, "qaManaged": True},
              actor=actor, action="qa-account-adopt", reason=reason)
    _checked(conn, tenant, customer_id)
    _save(conn, tenant, actor, {"enabled": True, "customer_id": str(customer_id),
          "revision": current["revision"] + 1, "started_at": datetime.now(UTC).isoformat()}, "qa-account-adopt", reason)
    return status(conn, tenant)


def issue_ticket(conn, tenant, actor, *, expected_revision, reason):
    _lock(conn, tenant)
    current = status(conn, tenant)
    if not current["enabled"] or current["revision"] != expected_revision:
        raise admin.AdminServiceError(409, "현재 테스트 계정을 다시 확인한 뒤 열어 주세요.")
    _checked(conn, tenant, current["customer_id"])
    raw = secrets.token_urlsafe(32)
    seconds = int(get_guardrails().get("security.web_auth_ticket_seconds"))
    state = {**_state(conn, tenant), "ticket_hash": hashlib.sha256(raw.encode()).hexdigest(),
             "ticket_expires_at": (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()}
    # 표는 하나만 살아 있다. 원문은 응답으로 한 번만 전달한다.
    from psycopg.types.json import Jsonb
    conn.execute("UPDATE admin_records SET value=%s,updated_at=now() WHERE tenant_id=%s AND kind=%s AND id=%s",
                 (Jsonb(state), tenant, KIND, ID))
    admin.audit(conn, tenant, actor, "qa-account-open", current["customer_id"], None,
                {"expires_in_seconds": seconds}, reason)
    return raw, seconds


def consume_ticket(conn, tenant, raw):
    _lock(conn, tenant)
    state, current = _state(conn, tenant), status(conn, tenant)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    expires = state.get("ticket_expires_at")
    if (not current["enabled"] or not expires or datetime.fromisoformat(expires) <= datetime.now(UTC)
            or not hmac.compare_digest(state.get("ticket_hash", ""), digest)):
        raise admin.AdminServiceError(410, "테스트 로그인 링크가 만료됐습니다. 관리자 화면에서 다시 열어 주세요.")
    _checked(conn, tenant, current["customer_id"])
    policy = admin.access_policy(conn, tenant, current["customer_id"])
    if policy["blocked"] or policy["maintenance"]:
        raise admin.AdminServiceError(503, "계정 차단 또는 서비스 점검 중입니다. 관리자 화면에서 상태를 확인해 주세요.")
    _save(conn, tenant, "qa-session", state, "qa-account-login", "관리자가 발급한 일회용 표 교환")
    return UUID(current["customer_id"])
