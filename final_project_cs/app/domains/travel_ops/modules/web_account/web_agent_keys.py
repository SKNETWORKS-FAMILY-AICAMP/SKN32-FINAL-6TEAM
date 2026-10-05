# -*- coding: utf-8 -*-
"""에이전트 키 — 개인 AI(MCP · 사용자 API)가 **본인 여행의 작업만** 하는 문. `[2026-10-04 사용자 결정]` D-CS-012 · 마이그레이션 045

계약 `wiki/external/rest-endpoints.md` 「에이전트 키」. 로그인한 사용자(회원)가 브라우저(쿠키 세션)에서 만든다 — 이름 · 권한 범위(`read`/`write`) · 만료(기본 90일, 최대 90일) · 개별 폐기.

★지키는 것
  - 원문은 저장하지 않는다 — SHA-256 해시만. 원문(`acop_a_…`)은 만들 때 **한 번만** 돌려준다.
  - 만료 · 폐기 · 모름은 모두 같은 「없음」(`resolve` 가 None) — 어느 쪽인지 알려 주지 않는다.
  - 만드는 일은 회원만(소셜 계정이 하나라도 붙은 사용자). 활성 키 개수에 상한이 있다(`security.web_agent_keys_per_user`).
  - 마지막 소셜 연결을 해제하면 그 사용자의 에이전트 키를 모두 거둔다(`revoke_all`).
★옛 사용자 키(`web_session.py`, `acop_u_…`)와 다르다 — 그것은 **만료를 검사하지 않고** `rotate` 가 전부 거둔다. 이 표는 에이전트용이라 만료 · 개별 폐기가 있다.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.settings import get_guardrails

PREFIX = "acop_a_"
SCOPES = ("read", "write")
#: 마지막 사용 시각을 이보다 잦게 쓰지 않는다 — 세션 확인과 같은 값(`web_guard.session_touch_seconds`)
_TOUCH_KEY = "web_guard.session_touch_seconds"


class AgentKeyLimit(Exception):
    """활성 키가 상한에 닿았다."""


class NotMember(Exception):
    """소셜 계정이 안 붙은 사용자(게스트 · 에이전트 API 고객)는 만들 수 없다."""


@dataclass(frozen=True)
class AgentKey:
    key_id: UUID
    customer_id: UUID
    scope: str
    name: str


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_member(conn, *, tenant_id: str, customer_id: UUID) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS (SELECT 1 FROM web_social_links WHERE tenant_id=%s AND customer_id=%s)", (tenant_id, customer_id))
        return bool(cur.fetchone()[0])


def create(conn, *, tenant_id: str, customer_id: UUID, name: str, scope: str, expires_days: int | None = None) -> dict[str, Any]:
    """새 키 — ★원문(`key`)은 여기서만 나온다. 회원이 아니면 `NotMember`, 활성 키가 상한이면 `AgentKeyLimit`."""
    guard = get_guardrails()
    max_days = int(guard.get("security.web_agent_key_max_days"))
    days = max_days if expires_days is None else expires_days
    if scope not in SCOPES or not (1 <= days <= max_days) or not (1 <= len(name) <= 60):
        raise ValueError("name · scope · expires_days 가 계약 범위를 벗어났다")
    with conn.cursor() as cur:
        # 사용자 행을 잠가 동시에 두 개가 만들어져 상한을 넘지 않게 한다
        cur.execute("SELECT 1 FROM customers WHERE tenant_id=%s AND customer_id=%s FOR UPDATE", (tenant_id, customer_id))
    if not is_member(conn, tenant_id=tenant_id, customer_id=customer_id):
        raise NotMember()
    cap = int(guard.get("security.web_agent_keys_per_user"))
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_agent_keys WHERE tenant_id=%s AND customer_id=%s AND revoked_at IS NULL AND expires_at > now()",
                    (tenant_id, customer_id))
        if int(cur.fetchone()[0]) >= cap:
            raise AgentKeyLimit()
        raw = PREFIX + secrets.token_urlsafe(32)
        cur.execute("INSERT INTO web_agent_keys (tenant_id, customer_id, name, key_hash, scope, expires_at) "
                    "VALUES (%s,%s,%s,%s,%s, now() + make_interval(days => %s)) RETURNING key_id, created_at, expires_at",
                    (tenant_id, customer_id, name, _hash(raw), scope, days))
        key_id, created, expires = cur.fetchone()
    return {"key_id": key_id, "name": name, "scope": scope, "created_at": created, "expires_at": expires, "key": raw}


def list_keys(conn, *, tenant_id: str, customer_id: UUID) -> list[dict[str, Any]]:
    """내 키 목록 — 원문은 없다. `status`: active · expired · revoked."""
    with conn.cursor() as cur:
        cur.execute("SELECT key_id, name, scope, created_at, expires_at, last_used_at, "
                    "CASE WHEN revoked_at IS NOT NULL THEN 'revoked' WHEN expires_at <= now() THEN 'expired' ELSE 'active' END "
                    "FROM web_agent_keys WHERE tenant_id=%s AND customer_id=%s ORDER BY created_at DESC", (tenant_id, customer_id))
        return [dict(zip(("key_id", "name", "scope", "created_at", "expires_at", "last_used_at", "status"), row)) for row in cur.fetchall()]


def revoke(conn, *, tenant_id: str, customer_id: UUID, key_id: UUID) -> bool:
    """개별 폐기 — 남의 키 · 없는 키는 False(같은 404). 이미 거둔 키를 다시 거두면 False."""
    with conn.cursor() as cur:
        cur.execute("UPDATE web_agent_keys SET revoked_at=now() WHERE tenant_id=%s AND customer_id=%s AND key_id=%s AND revoked_at IS NULL",
                    (tenant_id, customer_id, key_id))
        return cur.rowcount > 0


def revoke_all(conn, *, tenant_id: str, customer_id: UUID) -> int:
    with conn.cursor() as cur:
        cur.execute("UPDATE web_agent_keys SET revoked_at=now() WHERE tenant_id=%s AND customer_id=%s AND revoked_at IS NULL",
                    (tenant_id, customer_id))
        return cur.rowcount


def resolve(conn, *, tenant_id: str, raw: str | None) -> AgentKey | None:
    """키 → 사용자 · 권한. 모르거나 **만료**거나 거뒀으면 None(같은 취급). 마지막 사용은 한 번 쓰면 `web_guard.session_touch_seconds` 동안 안 쓴다."""
    if not raw or not raw.startswith(PREFIX) or len(raw) > 200:
        return None
    touch = float(get_guardrails().get(_TOUCH_KEY))
    with conn.cursor() as cur:
        cur.execute("SELECT key_id, customer_id, scope, name, last_used_at, now() FROM web_agent_keys "
                    "WHERE tenant_id=%s AND key_hash=%s AND revoked_at IS NULL AND expires_at > now()", (tenant_id, _hash(raw)))
        row = cur.fetchone()
        if row is None:
            return None
        key_id, customer, scope, name, last, now = row
        if last is None or (now - last).total_seconds() >= touch:
            cur.execute("UPDATE web_agent_keys SET last_used_at=now() WHERE key_id=%s", (key_id,))
    return AgentKey(key_id=key_id, customer_id=customer, scope=scope, name=name)


def iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


__all__ = ["AgentKey", "AgentKeyLimit", "NotMember", "PREFIX", "SCOPES", "create", "is_member", "iso", "list_keys", "resolve", "revoke", "revoke_all"]
