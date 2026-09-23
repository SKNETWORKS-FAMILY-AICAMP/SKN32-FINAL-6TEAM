# -*- coding: utf-8 -*-
"""웹 사용자 식별 키 — 로그인 없이 「누구인지」를 안다. `[2026-09-24]` D-020 · 마이그레이션 025

★사용자 결정(2026-09-24): 키를 **브라우저 저장소**에 두고, 사용자에게도 **한 번** 보여 줘 보관하게 한다
  (비회원 비밀번호처럼). 다른 기기·지운 브라우저에서는 그 키를 다시 넣으면 이어진다.

★지키는 것
  - 키가 여는 것은 **그 사용자 본인의 여행**뿐이다. 서버용 scope 키(테넌트 전체)와 섞지 않는다.
  - 원문은 저장하지 않는다 — SHA-256 해시만. 원문은 발급할 때 한 번만 돌려준다.
  - 다시 발급하면 옛 키는 바로 무효. 브라우저 저장소는 그 페이지의 모든 스크립트(지도 SDK 포함)가 읽을 수
    있어서 **새는 것을 전제로** 둔다 — 새면 다시 발급해 끊는다.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from uuid import UUID

from app.core import settings as settings_module

PREFIX = "acop_u_"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_key() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def issue(conn, *, tenant_id: str) -> tuple[UUID, str]:
    """새 사용자 + 키. ★원문 키는 여기서만 나온다 — 부르는 쪽이 사용자에게 한 번 보여 준다."""
    raw = _new_key()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s, %s) RETURNING customer_id",
                    (tenant_id, "web:" + secrets.token_hex(8)))
        customer_id = cur.fetchone()[0]
        cur.execute("INSERT INTO web_user_keys (tenant_id, customer_id, key_hash) VALUES (%s,%s,%s)",
                    (tenant_id, customer_id, _hash(raw)))
    return customer_id, raw


def resolve(conn, *, tenant_id: str, raw: str | None) -> UUID | None:
    """키 → 사용자. 모르거나 무효면 None. ★없는 키와 거둔 키를 같게 다룬다(어느 쪽인지 알려 주지 않는다)."""
    if not raw or not raw.startswith(PREFIX):
        return None
    with conn.cursor() as cur:
        cur.execute("UPDATE web_user_keys SET last_used_at=now() WHERE tenant_id=%s AND key_hash=%s "
                    "AND revoked_at IS NULL RETURNING customer_id", (tenant_id, _hash(raw)))
        row = cur.fetchone()
    return row[0] if row else None


def rotate(conn, *, tenant_id: str, customer_id: UUID) -> str:
    """새 키를 주고 **옛 키는 모두 무효**로 한다."""
    raw = _new_key()
    with conn.cursor() as cur:
        cur.execute("UPDATE web_user_keys SET revoked_at=now() WHERE tenant_id=%s AND customer_id=%s "
                    "AND revoked_at IS NULL", (tenant_id, customer_id))
        cur.execute("INSERT INTO web_user_keys (tenant_id, customer_id, key_hash) VALUES (%s,%s,%s)",
                    (tenant_id, customer_id, _hash(raw)))
    return raw


# ── 발급 속도 제한 (프로세스 안) ──────────────────────────────────
#   ★발급 경로만 키 없이 열려 있다 — 한 주소에서 사용자를 찍어 내지 못하게 센다.
_issued: dict[str, list[float]] = {}
_issued_lock = threading.Lock()


def _issue_limit() -> tuple[int, float]:
    guard = settings_module.get_guardrails()
    return int(guard.get("security.web_session_issue_per_hour")), 3600.0


def issue_wait(client: str, now: float | None = None) -> float:
    """이 주소가 지금 새 키를 받을 수 있으면 0 을 돌려주고 한 번으로 센다. 막히면 **기다릴 초**."""
    now = time.time() if now is None else now
    limit, window = _issue_limit()
    with _issued_lock:
        recent = [t for t in _issued.get(client, []) if now - t < window]
        if len(recent) >= limit:
            _issued[client] = recent
            return max(1.0, window - (now - recent[0]))
        recent.append(now)
        _issued[client] = recent
    return 0.0


__all__ = ["PREFIX", "issue", "issue_wait", "resolve", "rotate"]
