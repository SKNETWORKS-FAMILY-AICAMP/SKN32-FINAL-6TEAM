# -*- coding: utf-8 -*-
"""고객 연락처 — 복구 이메일 · 디스코드 웹훅. `[2026-10-01 사용자 지시 — ui 세션 전달]` 마이그레이션 039

사용자 지시: 「리커버리 이메일 받는 곳에서 나중에 디스코드 웹훅 URL 도 받게 될 건데, 그게 추가되면 받을 수 있게 서버 구현해 두라」.
이 모듈은 **1단계**다 — 받아서 검증 · 저장 · 마스킹 조회 · 시험 발송까지. 바깥함 일꾼이 고객 웹훅으로 계획 변경을 보내는 연결(2단계)은
사용자 확인 뒤에 한다.

★★웹훅 URL 은 비밀값이자 바깥 호출 통로(SSRF)다 — 주소를 아는 사람은 누구나 그 채널에 글을 쓰고, 서버는 나중에 그 주소로 POST 한다.
  ①**받을 때** 엄격히 검사한다: `https://` + 호스트가 디스코드 공식 도메인 목록에 있을 때만 + 경로가 `/api/webhooks/<숫자>/<토큰>`.
     다른 호스트 · http · IP 주소 · 사용자정보(`@`) · 포트 · 쿼리 · 조각 · 점이 붙은 호스트는 모두 거절한다.
  ②**저장은 암호화**만(`encrypt`) — 키는 서버 설정(`secret_key`)에서 파생한다. 원문은 DB 어디에도 없다.
  ③**응답에는 원문을 되돌리지 않는다** — 마스킹한 모양만(`mask`). 검사에서 거절한 값도 오류 문구에 싣지 않는다.
  ④**발송 때 같은 검사를 한 번 더** 한다(저장 뒤 규칙이 바뀌었거나 값이 오염됐을 때를 막는다). 리다이렉트는 따라가지 않는다.
  ⑤**로그에 원문을 남기지 않는다** — `httpx` 는 요청 주소를 INFO 로 찍으므로 웹훅 경로가 든 기록은 걸러낸다(`_DropWebhookRecords`).
★이메일은 형식만 본다(인증 메일은 이번에 안 보낸다). 공백만 있으면 지움으로 본다.
★한계: 서버는 호스트 **이름**만 허용 목록으로 검사한다 — DNS 가 바뀌어 다른 주소로 풀리는 공격(DNS 재결합)까지는 막지 않는다.
  허용 목록이 디스코드 공식 도메인뿐이라 위험은 작다. 배포 때 바깥 호출을 허용 목록 프록시로 보내면 닫힌다.
★`secret_key` 를 바꾸면 저장된 웹훅을 못 푼다 — 고객이 다시 넣어야 한다(`unreadable`). 값에 판 이름(`v1:`)을 붙여 키 교체 때 구분한다.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken

#: 디스코드 공식 웹훅 호스트 — ★우리가 고른 목록(공식 문서의 웹훅 주소 · 하위 도메인 `canary.` · `ptb.`). 이 밖은 받지 않는다
DISCORD_HOSTS = frozenset({"discord.com", "discordapp.com", "canary.discord.com", "ptb.discord.com",
                           "canary.discordapp.com", "ptb.discordapp.com"})
#: `/api/webhooks/<숫자 id>/<토큰>` — id 는 스노우플레이크(숫자 17~20자리가 보통, 여유를 둔 15~25), 토큰은 영숫자·`-`·`_`(보통 68자)
_PATH = re.compile(r"^/api/webhooks/(\d{15,25})/([A-Za-z0-9_-]{20,120})$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")
MAX_EMAIL = 254
ENC_VERSION = "v1"
TEST_TEXT = "triPilot 알림 시험이에요 — 이 메시지가 보이면 연결이 잘 된 거예요."
KST = timezone(timedelta(hours=9))

#: 시험이 바깥 호출을 가로채는 자리 — 실제 운영에서는 비어 있어 진짜 HTTP 로 간다(`ui.routes.API_TRANSPORT` 와 같은 방식)
TRANSPORT: httpx.BaseTransport | None = None


class ProfileError(ValueError):
    """검사에서 거절. ★메시지는 고정 문구다 — 받은 값을 되돌려 싣지 않는다."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.retry_after = 0                                   # 429 일 때 몇 초 뒤에 다시 하라고 알린다


class _DropWebhookRecords(logging.Filter):
    """`httpx` 가 요청 주소를 INFO 로 찍는다(「HTTP Request: POST https://…/api/webhooks/…」) — 웹훅 경로가 든 기록은 버린다."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            return "/api/webhooks/" not in record.getMessage()
        except Exception:                                   # noqa: BLE001 — 문구를 못 만들면 그대로 둔다(걸러낼 근거가 없다)
            return True


for _name in ("httpx", "httpcore"):
    _logger = logging.getLogger(_name)
    if not any(isinstance(f, _DropWebhookRecords) for f in _logger.filters):
        _logger.addFilter(_DropWebhookRecords())


# ── 검사 ────────────────────────────────────────────────────────
def parse_webhook(raw: str) -> tuple[str, str, str]:
    """웹훅 URL 검사 → (호스트, id, 토큰). 틀리면 `ProfileError`(고정 문구 — 받은 값을 싣지 않는다)."""
    bad = ProfileError("invalid_webhook", "디스코드 웹훅 주소 모양이 아니에요 — https://discord.com/api/webhooks/<번호>/<토큰> 이어야 해요")
    text = raw.strip()
    if not text or len(text) > 400 or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) > 0x7E for ch in text) or "\\" in text:
        raise bad
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise bad from None
    if parts.scheme != "https" or parts.username is not None or parts.password is not None or port is not None:
        raise bad
    if parts.query or parts.fragment or ";" in text or "%" in text:
        raise bad
    host = parts.hostname or ""
    if host not in DISCORD_HOSTS or parts.netloc.lower() != host:        # 점이 붙은 호스트 · 대문자 변형 · 사용자정보 모두 여기서 걸린다
        raise bad
    found = _PATH.match(parts.path)
    if found is None:
        raise bad
    return host, found.group(1), found.group(2)


def canonical(parsed: tuple[str, str, str]) -> str:
    host, ident, token = parsed
    return f"https://{host}/api/webhooks/{ident}/{token}"


def mask(parsed: tuple[str, str, str]) -> str:
    """조회에 돌려주는 모양 — 호스트 · id 앞 네 자리만. 토큰은 전부 가린다."""
    host, ident, _ = parsed
    return f"https://{host}/api/webhooks/{ident[:4]}…/••••"


def parse_email(raw: str) -> str | None:
    """이메일 형식 검사. 공백만 있으면 None(지움). 틀리면 `ProfileError`."""
    text = raw.strip()
    if not text:
        return None
    if len(text) > MAX_EMAIL or _EMAIL.match(text) is None or ".." in text:
        raise ProfileError("invalid_email", "이메일 모양이 아니에요")
    return text


# ── 암호화 ──────────────────────────────────────────────────────
def _fernet() -> Fernet:
    from app.core import settings as settings_module

    secret = settings_module.get_settings().secret_key.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(b"acop:customer-profile:webhook:" + secret).digest())
    return Fernet(key)


def encrypt(url: str) -> str:
    return f"{ENC_VERSION}:" + _fernet().encrypt(url.encode()).decode()


def decrypt(stored: str) -> str:
    """못 풀면 `ProfileError('unreadable')` — `secret_key` 가 바뀌었거나 값이 깨졌다. 고객이 다시 넣어야 한다."""
    version, _, body = stored.partition(":")
    try:
        if version != ENC_VERSION:
            raise InvalidToken
        return _fernet().decrypt(body.encode()).decode()
    except InvalidToken:
        raise ProfileError("unreadable", "저장된 웹훅 주소를 읽을 수 없어요 — 다시 입력해 주세요", status=409) from None


# ── 저장 · 조회 ─────────────────────────────────────────────────
@dataclass
class View:
    recovery_email: str | None
    webhook_set: bool
    masked: str | None
    status: str | None
    checked_at: datetime | None
    updated_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {"recovery_email": self.recovery_email,
                "discord_webhook": {"set": self.webhook_set, "masked": self.masked,
                                    "status": self.status if self.webhook_set else None,
                                    "checked_at": self.checked_at.isoformat() if self.checked_at else None},
                "updated_at": self.updated_at.isoformat() if self.updated_at else None}


def read(conn, tenant_id: str, customer_id: UUID) -> View:
    with conn.cursor() as cur:
        cur.execute("SELECT recovery_email, discord_webhook_enc IS NOT NULL, discord_hint, discord_status, "
                    "discord_checked_at, updated_at FROM customer_profiles WHERE tenant_id=%s AND customer_id=%s",
                    (tenant_id, customer_id))
        row = cur.fetchone()
    if row is None:
        return View(None, False, None, None, None, None)
    return View(*row)


def update(conn, tenant_id: str, customer_id: UUID, body: dict[str, Any]) -> View:
    """부분 갱신. ★칸이 없으면 안 건드리고, null(또는 공백만)이면 지운다. 모르는 칸은 거절 — 칸 **이름**만 알린다(값은 싣지 않는다)."""
    unknown = sorted(set(body) - {"recovery_email", "discord_webhook_url"})
    if unknown:
        raise ProfileError("unknown_field", "모르는 칸이 있어요: " + ", ".join(k[:40] for k in unknown))
    sets: dict[str, Any] = {}
    if "recovery_email" in body:
        value = body["recovery_email"]
        if value is not None and not isinstance(value, str):
            raise ProfileError("invalid_email", "이메일 모양이 아니에요")
        sets["recovery_email"] = None if value is None else parse_email(value)
    if "discord_webhook_url" in body:
        value = body["discord_webhook_url"]
        if value is not None and not isinstance(value, str):
            raise ProfileError("invalid_webhook", "디스코드 웹훅 주소 모양이 아니에요")
        if value is None or not value.strip():
            sets.update(discord_webhook_enc=None, discord_hint=None, discord_status="untested",
                        discord_checked_at=None, discord_tested_at=None)
        else:
            parsed = parse_webhook(value)
            sets.update(discord_webhook_enc=encrypt(canonical(parsed)), discord_hint=mask(parsed),
                        discord_status="untested", discord_checked_at=None, discord_tested_at=None)
    if sets:
        columns = list(sets)
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO customer_profiles (tenant_id, customer_id, {', '.join(columns)}) "
                f"VALUES (%s, %s, {', '.join(['%s'] * len(columns))}) "
                f"ON CONFLICT (tenant_id, customer_id) DO UPDATE SET "
                + ", ".join(f"{c}=EXCLUDED.{c}" for c in columns) + ", updated_at=now()",
                (tenant_id, customer_id, *sets.values()))
    return read(conn, tenant_id, customer_id)


# ── 시험 발송 ───────────────────────────────────────────────────
def _classify(response: httpx.Response) -> str:
    code = response.status_code
    if 200 <= code < 300:
        return "ok"
    if code in (401, 403, 404, 410):
        return "invalid"                     # 웹훅이 지워졌거나 토큰이 틀렸다
    if code == 429:
        return "rate_limited"
    return "failed"                          # 리다이렉트(따라가지 않는다) · 5xx · 그 밖


def send_test(conn, tenant_id: str, customer_id: UUID, *, min_interval_seconds: float,
              now: datetime | None = None) -> tuple[str, View]:
    """저장된 웹훅으로 시험 메시지 한 줄. 돌려주는 것 = (결과, 갱신된 조회 모양). 결과: ok · invalid · rate_limited · failed.

    ★고객이 누를 때만 부른다. 마지막 시도로부터 `min_interval_seconds` 안이면 거절(`too_soon` — DB 시각으로 센다).
    ★발송 직전에 같은 검사를 한 번 더 한다. 리다이렉트는 따라가지 않는다. 어떤 실패에도 주소 원문을 문구에 싣지 않는다.
    """
    now = now or datetime.now(KST)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT discord_webhook_enc, discord_tested_at FROM customer_profiles "
                    "WHERE tenant_id=%s AND customer_id=%s FOR UPDATE", (tenant_id, customer_id))
        row = cur.fetchone()
        if row is None or row[0] is None:
            raise ProfileError("no_webhook", "저장된 디스코드 웹훅이 없어요", status=409)
        stored, tested_at = row
        if tested_at is not None and (now - tested_at).total_seconds() < min_interval_seconds:
            wait = max(1, int(min_interval_seconds - (now - tested_at).total_seconds()))
            error = ProfileError("too_soon", f"시험 발송은 잠시 뒤에 다시 할 수 있어요({wait}초 뒤)", status=429)
            error.retry_after = wait
            raise error
        # 시도 시각을 먼저 적는다 — 발송이 오래 걸리거나 실패해도 연타를 막는다
        cur.execute("UPDATE customer_profiles SET discord_tested_at=%s WHERE tenant_id=%s AND customer_id=%s",
                    (now, tenant_id, customer_id))
    url = canonical(parse_webhook(decrypt(stored)))                    # 발송 직전 재검사
    try:
        with httpx.Client(transport=TRANSPORT, timeout=httpx.Timeout(8.0), follow_redirects=False) as client:
            result = _classify(client.post(url, json={"content": TEST_TEXT, "username": "triPilot",
                                                      "allowed_mentions": {"parse": []}}))
    except httpx.HTTPError:
        result = "failed"                                              # 연결 실패 · 시간 초과 — 주소는 싣지 않는다
    status_to_store = {"ok": "ok", "invalid": "invalid"}.get(result)
    with conn.transaction(), conn.cursor() as cur:
        if status_to_store is not None:
            cur.execute("UPDATE customer_profiles SET discord_status=%s, discord_checked_at=%s "
                        "WHERE tenant_id=%s AND customer_id=%s", (status_to_store, now, tenant_id, customer_id))
    return result, read(conn, tenant_id, customer_id)


__all__ = ["DISCORD_HOSTS", "ProfileError", "View", "canonical", "decrypt", "encrypt", "mask", "parse_email",
           "parse_webhook", "read", "send_test", "update"]
