# -*- coding: utf-8 -*-
"""웹 소셜 로그인의 **저장 · 규칙** — 시작 기록(`state`) · 일회용 표(`ticket`) · 계정 연결. `[2026-10-03 ui 세션 요청서 「소셜 로그인」 — 1단계는 구글 하나]`

저장 마이그레이션 043 · 업체와 말하는 일 `infrastructure/oauth_providers.py` · HTTP `web_auth_api.py`.

★한 바퀴: `start`(시작 기록 저장) → 업체 로그인 화면 → `callback`(기록을 한 번만 꺼내 코드를 고유 번호로 바꾼다 → 연결 · 일회용 표) → `exchange`(표를 한 번만 받고 **이 기기용 새 키** 발급).
★보안(요청서 「보안」):
  ①**로그인 CSRF 막기** — 표는 시작한 브라우저가 만든 `client_nonce` 의 해시와 함께 저장되고, 교환할 때 같은 nonce 가 와야 한다. 공격자가 자기 표가 든 링크를 피해자에게 보내도 피해자 브라우저는 nonce 를 몰라 교환이 안 된다.
  ②`state` 는 서버가 만들고 해시만 저장, **한 번만 · 10분**. PKCE · OIDC nonce 는 서버만 안다.
  ③저장은 업체 이름과 `sub` 의 **HMAC 해시**뿐 — 이메일 · 이름 · 사진은 요청도 저장도 하지 않는다.
  ④한 업체 계정은 **한 사용자에게만** — 이미 다른 사용자에게 있으면 연결은 실패하고 **합치지 않는다**.
★키 원문은 표에 없다. 교환할 때 새 키를 더하고(`web_session.add_key` — 옛 키는 그대로, 다른 기기가 안 끊긴다) 그 응답에만 싣는다.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any
from uuid import UUID

import app.core.settings as settings_module
from app.core.settings import get_guardrails

#: 시작한 브라우저가 만드는 값의 최소 길이 — 짧으면 맞춰 보기 쉽다(요청서: 무작위 32자 이상)
MIN_CLIENT_NONCE = 32
MAX_CLIENT_NONCE = 256


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _guard(name: str) -> int:
    return int(get_guardrails().get(f"security.{name}"))


def subject_hash(provider: str, subject: str) -> str:
    """업체 계정의 저장값 — `HMAC(서버 비밀, 업체 + ":" + sub)`. 원문 `sub` 는 저장하지 않는다."""
    secret = settings_module.get_settings().secret_key.encode()
    return hmac.new(secret, f"social:{provider}:{subject}".encode("utf-8"), hashlib.sha256).hexdigest()


def valid_client_nonce(value: Any) -> bool:
    return isinstance(value, str) and MIN_CLIENT_NONCE <= len(value) <= MAX_CLIENT_NONCE


# ── 시작 ──────────────────────────────────────────────────────────
def begin(conn, *, tenant_id: str, provider: str, mode: str, customer_id: UUID | None, client_nonce: str,
          verifier: str) -> tuple[str, str]:
    """시작 기록을 저장한다. 돌려주는 것 = (`state` 원문, OIDC `nonce`) — 업체 로그인 주소에 실린다. 저장은 `state` 의 해시뿐."""
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO web_oauth_states (state_hash, tenant_id, provider, mode, customer_id, code_verifier, nonce, "
                    "client_nonce_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (_h(state), tenant_id, provider, mode, customer_id, verifier, nonce, _h(client_nonce)))
        # 지나간 기록을 이따금 치운다(한 시간 — 수명보다 한참 길다). 시작할 때마다 하지만 한 줄 삭제라 가볍다
        cur.execute("DELETE FROM web_oauth_states WHERE created_at < now() - interval '1 hour'")
        cur.execute("DELETE FROM web_oauth_tickets WHERE created_at < now() - interval '1 hour'")
    return state, nonce


# ── 콜백 ──────────────────────────────────────────────────────────
def take_state(conn, *, tenant_id: str, state: str) -> dict[str, Any] | None:
    """`state` 를 **한 번만** 꺼낸다(수명 안에서 아직 안 쓴 것). 모르거나 · 썼거나 · 만료됐으면 None — 이유를 알려 주지 않는다."""
    with conn.cursor() as cur:
        cur.execute("UPDATE web_oauth_states SET used_at = now() WHERE state_hash=%s AND tenant_id=%s AND used_at IS NULL "
                    "AND created_at > now() - make_interval(secs => %s) "
                    "RETURNING provider, mode, customer_id, code_verifier, nonce, client_nonce_hash",
                    (_h(state), tenant_id, _guard("web_auth_state_seconds")))
        row = cur.fetchone()
    if row is None:
        return None
    return {"provider": row[0], "mode": row[1], "customer_id": row[2], "verifier": row[3], "nonce": row[4],
            "client_nonce_hash": row[5]}


def _owner(cur, tenant_id: str, provider: str, digest: str) -> UUID | None:
    cur.execute("SELECT customer_id FROM web_social_links WHERE tenant_id=%s AND provider=%s AND subject_hash=%s",
                (tenant_id, provider, digest))
    row = cur.fetchone()
    return row[0] if row else None


def complete(conn, *, tenant_id: str, started: dict[str, Any], subject: str,
             create_customer: Any) -> tuple[str | None, str | None]:
    """업체가 확인해 준 계정(`subject`)을 사용자에 잇고 **일회용 표**를 만든다. 돌려주는 것 = (표 원문, None) 또는 (None, 오류 코드).

    - `login`  그 계정에 붙은 사용자가 있으면 그 사용자(`signed_in`), 없으면 새 사용자를 만들어 붙인다(`created`)
    - `link`   시작할 때 키로 확인한 사용자에게 붙인다(`linked`). 이미 다른 사용자에게 있으면 `already_linked_elsewhere` — **합치지 않는다**
    `create_customer(conn)` — 새 사용자를 만드는 쪽(세션 발급 한도 등을 거친다). 실패하면 그 예외가 그대로 나간다."""
    provider, digest = started["provider"], subject_hash(started["provider"], subject)
    with conn.cursor() as cur:
        owner = _owner(cur, tenant_id, provider, digest)
        if started["mode"] == "link":
            me = started["customer_id"]
            if me is None:
                return None, "failed"
            if owner is not None and owner != me:
                return None, "already_linked_elsewhere"
            if owner is None:
                cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,%s,%s,%s) "
                            "ON CONFLICT DO NOTHING", (tenant_id, provider, digest, me))
                if cur.rowcount == 0 and _owner(cur, tenant_id, provider, digest) != me:    # 동시에 다른 사용자에게 붙었다
                    return None, "already_linked_elsewhere"
            customer, outcome = me, "linked"
        elif owner is not None:
            customer, outcome = owner, "signed_in"
        else:
            created = create_customer(conn)
            cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING", (tenant_id, provider, digest, created))
            if cur.rowcount == 0:                     # 같은 계정으로 동시에 처음 들어온 다른 요청이 먼저 붙었다 — 그 사용자로 들어간다
                owner = _owner(cur, tenant_id, provider, digest)
                customer, outcome = (owner, "signed_in") if owner is not None else (created, "created")
                if owner is not None:
                    cur.execute("DELETE FROM customers WHERE customer_id=%s", (created,))
            else:
                customer, outcome = created, "created"
        ticket = secrets.token_urlsafe(32)
        cur.execute("INSERT INTO web_oauth_tickets (ticket_hash, tenant_id, provider, outcome, customer_id, client_nonce_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s)", (_h(ticket), tenant_id, provider, outcome, customer, started["client_nonce_hash"]))
    return ticket, None


# ── 교환 ──────────────────────────────────────────────────────────
def exchange(conn, *, tenant_id: str, ticket: str, client_nonce: str) -> dict[str, Any] | None:
    """일회용 표를 받는다 — **한 번만 · 수명 안 · 시작한 브라우저의 nonce 가 맞을 때만**. 아니면 None(이유를 가르지 않는다).
    ★nonce 가 틀린 요청은 표를 쓰지 않는다 — 표를 모르는 공격자가 맞춰 보며 진짜 표를 태울 수 없게 맞는 nonce 와 함께일 때만 `used_at` 을 찍는다."""
    with conn.cursor() as cur:
        cur.execute("UPDATE web_oauth_tickets SET used_at = now() WHERE ticket_hash=%s AND tenant_id=%s AND used_at IS NULL "
                    "AND client_nonce_hash=%s AND created_at > now() - make_interval(secs => %s) "
                    "RETURNING provider, outcome, customer_id",
                    (_h(ticket), tenant_id, _h(client_nonce), _guard("web_auth_ticket_seconds")))
        row = cur.fetchone()
    if row is None:
        return None
    return {"provider": row[0], "outcome": row[1], "customer_id": row[2]}


def trip_count(conn, *, tenant_id: str, customer_id: UUID) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
        return int(cur.fetchone()[0])


# ── 연결 목록 · 해제 ──────────────────────────────────────────────
def links(conn, *, tenant_id: str, customer_id: UUID) -> list[dict[str, Any]]:
    """이 사용자에게 붙은 업체 — 업체 이름과 붙인 시각뿐(계정 이름 · 이메일은 없다). 같은 업체가 여럿이면 가장 이른 시각 하나."""
    with conn.cursor() as cur:
        cur.execute("SELECT provider, min(linked_at) FROM web_social_links WHERE tenant_id=%s AND customer_id=%s "
                    "GROUP BY provider ORDER BY min(linked_at)", (tenant_id, customer_id))
        return [{"provider": provider, "linked_at": at.isoformat()} for provider, at in cur.fetchall()]


def unlink(conn, *, tenant_id: str, customer_id: UUID, provider: str) -> bool:
    """연결을 푼다(키와 여행은 그대로). 안 붙어 있었으면 False."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM web_social_links WHERE tenant_id=%s AND customer_id=%s AND provider=%s",
                    (tenant_id, customer_id, provider))
        return cur.rowcount > 0


__all__ = ["MAX_CLIENT_NONCE", "MIN_CLIENT_NONCE", "begin", "complete", "exchange", "links", "subject_hash", "take_state",
           "trip_count", "unlink", "valid_client_nonce"]
