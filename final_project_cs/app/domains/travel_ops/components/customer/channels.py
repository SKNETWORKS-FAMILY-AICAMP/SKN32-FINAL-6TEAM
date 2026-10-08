# -*- coding: utf-8 -*-
"""고객이 연결해 둔 **알림 채널의 저장값**을 읽는다 — 봇 설정 · 대화 번호 암·복호. `[2026-10-06]`

★왜 여기인가. 알림 발송(필수 부품)과 동의 철회(고객 정보)가 이 값을 읽는다. 전에는 연결 설정
  흐름이 든 파일(`modules/web_account/telegram_connect.py`)에서 직접 가져갔는데, 그 파일은
  **웹에서 채널을 연결하는 기능**이라 끌 수 있는 쪽이다 — 필수 부품이 그쪽을 부르면 기능을 끌 때
  알림이 같이 멈춘다(D-CS-013 칸끼리 규칙).

  지금은 저장값 읽기만 여기 있고, 연결 흐름(`modules/web_account/telegram_connect.py`)이 이것을
  가져다 쓴다 — 방향이 뒤집혔다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core import settings as settings_module
from uuid import UUID

from app.domains.travel_ops.components.customer import profile as customer_profile
from app.domains.travel_ops.components.customer.profile import ProfileError

ENC_VERSION = "v1"


# ── 설정 ────────────────────────────────────────────────────────
def config() -> tuple[str, str, str] | None:
    """(봇 토큰, 봇 아이디, 웹훅 비밀값) — **셋 다** 있어야 켜진다. 반쯤 켜진 채 뜨지 않게."""
    settings = settings_module.get_settings()
    token = (getattr(settings, "telegram_bot_token", "") or "").strip()
    username = (getattr(settings, "telegram_bot_username", "") or "").strip().lstrip("@")
    secret = (getattr(settings, "telegram_webhook_secret", "") or "").strip()
    return (token, username, secret) if token and username and secret else None


def available() -> bool:
    return config() is not None


def public_state() -> dict[str, Any]:
    """프로필 응답에 싣는 모양 — 봇 설정이 있을 때만 `available: true`(없으면 웹이 텔레그램 줄을 통째로 숨긴다)."""
    return {"available": available()}


def verify_secret(provided: str | None) -> bool:
    """웹훅 비밀 헤더 확인 — 상수 시간 비교. 설정이 없으면 늘 거짓(열려 있는 웹훅을 만들지 않는다)."""
    cfg = config()
    return bool(cfg and provided and hmac.compare_digest(provided.encode("utf-8"), cfg[2].encode("utf-8")))


# ── 대화 번호 암호화 · 해시 ─────────────────────────────────────
def _fernet() -> Fernet:
    secret = settings_module.get_settings().secret_key.encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"acop:customer-profile:telegram:" + secret).digest()))


def encrypt_chat(chat_id: int) -> str:
    return f"{ENC_VERSION}:" + _fernet().encrypt(str(chat_id).encode()).decode()


def decrypt_chat(stored: str) -> int:
    """못 풀면 `ProfileError('unreadable')` — `secret_key` 가 바뀌었거나 값이 깨졌다. 고객이 다시 연결해야 한다."""
    version, _, body = stored.partition(":")
    try:
        if version != ENC_VERSION:
            raise InvalidToken
        return int(_fernet().decrypt(body.encode()).decode())
    except (InvalidToken, ValueError):
        raise ProfileError("unreadable", "저장된 텔레그램 연결을 읽을 수 없어요 — 다시 연결해 주세요", status=409) from None


def chat_hash(tenant_id: str, chat_id: int) -> str:
    """같은 대화가 다른 사용자에게 묶이는 것을 막는 유일 확인용 — 서버 비밀 HMAC(원문 대화 번호는 여기서도 안 남는다)."""
    secret = settings_module.get_settings().secret_key.encode()
    return hmac.new(secret, f"telegram-chat:{tenant_id}:{chat_id}".encode(), hashlib.sha256).hexdigest()


# ── 연결 해제 — 동의 철회가 부른다(저장값 지우기라 여기 둔다) ──────
def disconnect(conn, tenant_id: str, customer_id: UUID) -> customer_profile.View:
    """대화 번호를 지운다. 알림 받는 곳이 텔레그램이었으면 디스코드가 있으면 디스코드로 · 없으면 없음."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE customer_profiles SET telegram_chat_enc=NULL, telegram_chat_hash=NULL, telegram_status=NULL, telegram_connected_at=NULL, "
            "telegram_checked_at=NULL, telegram_tested_at=NULL, "
            "notice_channel = CASE WHEN notice_channel='telegram' THEN (CASE WHEN discord_webhook_enc IS NOT NULL THEN 'discord' ELSE NULL END) "
            "ELSE notice_channel END, updated_at=now() WHERE tenant_id=%s AND customer_id=%s", (tenant_id, customer_id))
    return customer_profile.read(conn, tenant_id, customer_id)
