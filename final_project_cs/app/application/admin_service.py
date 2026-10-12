"""Persistent operations records; customer policy checks share the same DB state."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb
from app.core.redaction import mask_json, masked

KST = ZoneInfo("Asia/Seoul")


class AdminServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def records(conn, tenant: str, kind: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT id,value FROM admin_records WHERE tenant_id=%s AND kind=%s ORDER BY updated_at DESC", (tenant, kind))
        return [{**row[1], "id": row[0]} for row in cur.fetchall()]


def record(conn, tenant: str, kind: str, identity: str, *, lock: bool = False) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM admin_records WHERE tenant_id=%s AND kind=%s AND id=%s" + (" FOR UPDATE" if lock else ""), (tenant, kind, identity))
        row = cur.fetchone()
        return row[0] if row else {}


def audit(conn, tenant: str, actor: str, action: str, target: str, before: Any, after: Any, reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO admin_audit(tenant_id,actor,action,target,before_value,after_value,reason) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (tenant, actor, action, target, Jsonb(mask_json(before)), Jsonb(mask_json(after)), masked(reason)))


def put(conn, tenant: str, kind: str, identity: str, value: dict, *, actor: str, action: str, reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"admin:{tenant}:{kind}:{identity}",))
    before = record(conn, tenant, kind, identity, lock=True)
    customer = identity if kind == "user" else value.get("userId") if kind == "inquiry" else None
    with conn.cursor() as cur:
        cur.execute("INSERT INTO admin_records(tenant_id,kind,id,value,customer_id) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,kind,id) DO UPDATE SET value=EXCLUDED.value,customer_id=EXCLUDED.customer_id,revision=admin_records.revision+1,updated_at=now()", (tenant, kind, identity, Jsonb(value), customer))
    audit(conn, tenant, actor, action, identity, before, value, reason)


def require_customer(conn, tenant: str, customer: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM customers WHERE tenant_id=%s AND customer_id::text=%s", (tenant, customer))
        if cur.fetchone() is None:
            raise AdminServiceError(404, "사용자를 찾을 수 없습니다.")


def access_policy(conn, tenant_id: str, customer_id: str, now: datetime | None = None) -> dict:
    now = (now or datetime.now(UTC)).astimezone(KST)
    user = record(conn, tenant_id, "user", str(customer_id))
    limits = record(conn, tenant_id, "settings", "limits")
    maintenance = record(conn, tenant_id, "settings", "maintenance")
    expires = maintenance.get("endsAt")
    if not maintenance.get("enabled") or not expires or datetime.fromisoformat(expires).replace(tzinfo=KST) <= now:
        maintenance = None
    exception = user.get("exceptionLimit")
    if user.get("exceptionPeriod") == "today" and user.get("exceptionDay") != now.date().isoformat():
        exception = None
    return {"blocked": bool(user.get("blocked")), "chat_limit": exception if exception is not None else limits.get("chatLimit"), "maintenance": maintenance}


class AdminPolicyRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def consume_chat(conn, tenant_id: str, customer_id: str, now: datetime | None = None) -> int:
    """Atomic daily customer cap; call inside the customer request transaction."""
    now = (now or datetime.now(UTC)).astimezone(KST)
    policy = access_policy(conn, tenant_id, customer_id, now)
    if policy["blocked"]:
        raise AdminPolicyRefused(403, "user_blocked", "이 계정의 이용이 제한되어 있습니다.")
    if policy["maintenance"]:
        raise AdminPolicyRefused(503, "maintenance", policy["maintenance"]["message"])
    cap = policy["chat_limit"]
    if cap is None:
        # 별도 운영자 한도가 없으면 기존 웹 횟수 집계만 사용한다.
        return 0
    with conn.cursor() as cur:
        cur.execute("INSERT INTO admin_chat_usage(tenant_id,customer_id,day,used) VALUES(%s,%s,%s,COALESCE((SELECT used FROM web_usage WHERE tenant_id=%s AND who_kind='key' AND who=%s AND action='message' AND period=%s),0)) ON CONFLICT DO NOTHING", (tenant_id, customer_id, now.date(), tenant_id, str(customer_id), f"day:{now:%Y-%m-%d}"))
        cur.execute("UPDATE admin_chat_usage SET used=used+1 WHERE tenant_id=%s AND customer_id=%s AND day=%s AND (%s::integer IS NULL OR used<%s::integer) RETURNING used", (tenant_id, customer_id, now.date(), cap, cap))
        row = cur.fetchone()
        if row is None:
            raise AdminPolicyRefused(429, "chat_limit", "오늘의 채팅 이용 한도에 도달했습니다.")
        return int(row[0])


def api_cap(conn, meter: str, original: dict[str, int]) -> dict[str, int]:
    """Operator caps can lower but never silently increase provider/config caps."""
    with conn.cursor() as cur:
        cur.execute("SELECT daily,monthly FROM admin_api_caps WHERE meter=%s", (meter,))
        row = cur.fetchone()
    return {"day": min(original["day"], int(row[0])), "month": min(original["month"], int(row[1]))} if row else original


def mutate(conn, tenant: str, actor: str, command: dict) -> None:
    command = mask_json(command)
    kind = command["type"]
    now = datetime.now(KST)
    reason = command.get("reason") or command.get("body") or command.get("title") or "운영자 점검"
    if kind in ("block-user", "user-limit"):
        identity = command["userId"]
        require_customer(conn, tenant, identity)
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"admin:{tenant}:user:{identity}",))
        value = record(conn, tenant, "user", identity, lock=True)
        if kind == "block-user":
            value["blocked"] = command["blocked"]
        else:
            value.update(exceptionLimit=command["limit"], exceptionPeriod=command["period"] if command["limit"] is not None else None, exceptionDay=now.date().isoformat())
        put(conn, tenant, "user", identity, value, actor=actor, action=kind, reason=reason)
    elif kind == "save-limits":
        rules = sorted(command["rules"], key=lambda r: r["threshold"])
        if rules:
            raise AdminServiceError(422, "안전 감시 주기는 예산에 따라 변경하지 않습니다. 감시 단계 편집은 지원하지 않습니다.")
        if len({r["threshold"] for r in rules}) != len(rules) or len({r["id"] for r in rules}) != len(rules) or any(rules[i]["multiplier"] <= rules[i-1]["multiplier"] for i in range(1, len(rules))):
            raise AdminServiceError(422, "감시 단계는 중복 없이 증가해야 합니다.")
        put(conn, tenant, "settings", "limits", {"chatLimit": command["chatLimit"], "watchRules": rules}, actor=actor, action=kind, reason=reason)
    elif kind == "maintenance":
        put(conn, tenant, "settings", "maintenance", {k: command[k] for k in ("enabled", "message", "messageEn", "endsAt")}, actor=actor, action=kind, reason=reason)
    elif kind == "publish-notice":
        value = {**command["notice"], "author": actor}
        if value["startsAt"] >= value["endsAt"]:
            raise AdminServiceError(422, "게시 종료는 시작보다 늦어야 합니다.")
        put(conn, tenant, "notice", str(uuid4()), value, actor=actor, action=kind, reason=value["title"])
    elif kind == "save-template":
        identity = command.get("id") or str(uuid4())
        if command.get("id") and not record(conn, tenant, "template", identity):
            raise AdminServiceError(404, "템플릿을 찾을 수 없습니다.")
        put(conn, tenant, "template", identity, {"title": command["title"], "body": command["body"]}, actor=actor, action=kind, reason=command["body"])
    elif kind in ("inquiry-status", "reply"):
        identity = command["inquiryId"]
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"admin:{tenant}:inquiry:{identity}",))
        value = record(conn, tenant, "inquiry", identity, lock=True)
        if not value:
            raise AdminServiceError(404, "문의를 찾을 수 없습니다.")
        at = now.isoformat()
        if kind == "reply":
            value.setdefault("replies", []).append({"body": command["body"], "operator": actor, "at": at})
            value.update(status="답변 완료", assignee=actor)
        else:
            value.update(status=command["status"], assignee=command["assignee"])
        value.setdefault("history", []).append({"text": f"{value['status']} · {reason}", "at": at})
        put(conn, tenant, "inquiry", identity, value, actor=actor, action=kind, reason=reason)
    elif kind == "api-cap":
        if command["daily"] > command["monthly"]:
            raise AdminServiceError(422, "월 한도는 하루 한도 이상이어야 합니다.")
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM external_call_budget WHERE meter=%s LIMIT 1", (command["apiId"],))
            if cur.fetchone() is None:
                raise AdminServiceError(422, "계측하지 않은 API의 상한은 바꿀 수 없습니다.")
            cur.execute("SELECT daily,monthly FROM admin_api_caps WHERE meter=%s FOR UPDATE", (command["apiId"],))
            before = cur.fetchone()
            cur.execute("INSERT INTO admin_api_caps(meter,daily,monthly,updated_by) VALUES(%s,%s,%s,%s) ON CONFLICT(meter) DO UPDATE SET daily=EXCLUDED.daily,monthly=EXCLUDED.monthly,updated_by=EXCLUDED.updated_by,updated_at=now()", (command["apiId"], command["daily"], command["monthly"], actor))
        audit(conn, tenant, actor, kind, command["apiId"], list(before) if before else None, {"daily": command["daily"], "monthly": command["monthly"]}, reason)
    else:
        raise AdminServiceError(422, "지원하지 않는 저장 명령입니다.")
