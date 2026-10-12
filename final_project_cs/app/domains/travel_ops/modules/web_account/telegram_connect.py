# -*- coding: utf-8 -*-
"""「텔레그램으로 알림 받기」 — 연결 · 웹훅 업데이트 처리 · 시험 발송 · 연결 풀기. `[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만 하는 걸로」 — ui 세션 요청서]` 마이그레이션 048

계약 `wiki/records/plans/2026-10-05_텔레그램_연결_백엔드_요청.md` · HTTP `trip_api.py` · 발송 `notice_routing.py` · 텔레그램과 말하기 `infrastructure/notify/telegram.py`.

★한 바퀴: 마이페이지 「텔레그램으로 연결」 → `begin`(일회용 코드 → `https://t.me/<봇>?start=<코드>`) → 고객이 텔레그램에서 「시작」 → 텔레그램이 웹훅으로 `/start <코드>` 를 보냄(`handle_update`)
  → 코드를 한 번만 꺼내 그 사용자에 **대화 번호(chat.id)를 묶고** 알림 받는 곳을 텔레그램으로 → 봇이 인사 → 웹은 프로필을 몇 초마다 읽어 「연결됨」을 보인다.
★**알림만 한다.** 고객이 봇에 쓴 글에는 **고정 문장**으로만 답한다 — 모델을 부르지 않고, 글 내용은 저장도 로그도 하지 않는다(보는 것은 `/start <코드>` 의 코드뿐이고 그것도 해시로만 찾는다).
★저장하는 것은 **대화 번호(암호화) · 그 해시 · 연결 시각 · 상태**뿐이다 — 텔레그램 이름 · 사용자명 · 전화 · 사진은 받아도 저장하지 않는다. 응답에는 대화 번호를 가린 모양으로도 안 준다(「연결됨」만).
★보안: ①웹훅은 **비밀 헤더**(`X-Telegram-Bot-Api-Secret-Token` = 서버 비밀값, 상수 시간 비교)가 맞을 때만 처리한다 ②코드는 서버가 만들고 **해시만** 저장 · 10분 · 한 번만 · 사용자에 묶음(남의 코드를 써도
  코드를 만든 사용자에 묶일 뿐이다) ③같은 대화가 **다른 사용자에게 이미 묶여 있으면 묶지 않는다**(합치지 않는다 — 소셜 로그인의 `already_linked_elsewhere` 와 같은 원칙) ④봇 토큰은 환경 파일에만 · 로그 · 응답 ·
  오류에 쓰지 않는다(`infrastructure/notify/telegram.py` 가 요청 주소의 토큰 기록을 거른다) ⑤텔레그램은 2xx 가 아니면 같은 업데이트를 **다시** 보낸다 — 처리한 `update_id` 를 이틀 동안 기억해 두 번 처리하지 않는다.
★`my_chat_member`(개인 대화에서는 고객이 봇을 차단 · 해제할 때만 온다 — 공식 문서) → 차단이면 상태 `blocked`(발송은 보낸 것으로 기록하지 않는다) · 해제면 `untested`.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

import httpx
from psycopg import errors as pg_errors

from app.core.settings import get_guardrails
from app.infrastructure.notify import telegram as client

from app.domains.travel_ops.components.customer import consents
from app.domains.travel_ops.components.customer import profile as customer_profile
from app.domains.travel_ops.components.customer.profile import ProfileError

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
ENC_VERSION = "v1"
#: `/start` 링크 인자 — 텔레그램 규칙상 64자 이하 · `A-Z a-z 0-9 _ -` 만(공식 문서 확인). `token_urlsafe(32)` = 43자
_CODE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
TEST_TEXT = "triPilot 알림 시험이에요 — 이 메시지가 보이면 연결이 잘 된 거예요."
#: 봇이 하는 말 — 고정 문장뿐이다(모델을 부르지 않는다)
SAY_CONNECTED = "연결됐어요. 이 채팅은 알림 전용이에요 — 일정 수정과 질문은 웹이나 여행계획서 링크에서 해 주세요."
SAY_EXPIRED = "연결 시간이 지났거나 이미 쓴 링크예요. 웹 마이페이지에서 다시 눌러 주세요."
SAY_ELSEWHERE = "이 텔레그램은 이미 다른 계정에 연결돼 있어요. 그 계정에서 연결을 풀고 다시 해 주세요."
SAY_CONSENT = "웹 마이페이지에서 알림 채널 동의를 먼저 해 주세요. 그다음 연결 링크를 다시 눌러 주세요."
SAY_OTHER = "알림 전용 봇이에요. 일정 수정과 질문은 웹이나 여행계획서 링크에서 해 주세요."

#: 시험이 바깥 호출을 가로채는 자리는 `infrastructure/notify/telegram.TRANSPORT` 다


# ★`[2026-10-06]` 설정·암복호는 `components/customer/channels.py` 로 옮겼다 — 알림 발송(필수 부품)이
#   이 파일(끌 수 있는 기능)을 부르지 않게 하려는 것이다(D-CS-013). 여기서는 다시 내보내기만 한다.
from app.domains.travel_ops.components.customer.channels import (      # noqa: E402
    available, chat_hash, config, decrypt_chat, disconnect, encrypt_chat, public_state, verify_secret)


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 연결 시작 ───────────────────────────────────────────────────
def begin(conn, *, tenant_id: str, customer_id: UUID) -> dict[str, Any]:
    """일회용 코드를 만들고(해시만 저장) `{link, expires_at}` 를 돌려준다. 지나간 코드는 이따금 치운다."""
    cfg = config()
    if cfg is None:
        raise ProfileError("not_found", "텔레그램 연결을 쓸 수 없어요", status=404)
    seconds = int(get_guardrails().get("security.telegram_link_code_seconds"))
    code = secrets.token_urlsafe(32)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO telegram_link_codes (code_hash, tenant_id, customer_id) VALUES (%s,%s,%s)", (_h(code), tenant_id, customer_id))
        cur.execute("DELETE FROM telegram_link_codes WHERE created_at < now() - interval '1 hour'")
        cur.execute("SELECT now() + make_interval(secs => %s)", (seconds,))
        expires = cur.fetchone()[0]
    return {"link": f"https://t.me/{cfg[1]}?start={code}", "expires_at": expires.isoformat()}


def count_start(tenant_id: str, customer_id: UUID | str) -> None:
    """`start` 를 사용자당 한 시간에 몇 번까지(`security.telegram_connect_start_per_hour`). 막히면 `web_guard.UsageRefused`(429)."""
    from app.domains.travel_ops.modules.web_account import web_guard

    web_guard.count_per_key_hour(tenant_id, "telegram_connect_start", customer_id=customer_id,
                                 cap=int(get_guardrails().get("security.telegram_connect_start_per_hour")))


# ── 웹훅 업데이트 처리 ──────────────────────────────────────────
def handle_update(conn, *, tenant_id: str, update: Any, send: Callable[[int, str], None]) -> None:
    """텔레그램이 보낸 업데이트 한 건. ★어떤 경우에도 예외를 올리지 않는다(텔레그램은 2xx 가 아니면 같은 것을 다시 보낸다) — 실패는 **종류만** 로그에 남긴다.

    `send(chat_id, text)` — 봇이 답하는 자리(운영은 실제 `sendMessage`, 시험은 가짜). 답이 실패해도 처리는 끝난 것으로 본다."""
    try:
        if not isinstance(update, dict):
            return
        update_id = update.get("update_id")
        if isinstance(update_id, int) and not _first_time(conn, update_id):
            return                                                    # 텔레그램이 다시 보낸 같은 업데이트 — 두 번 처리하지 않는다
        if isinstance(update.get("my_chat_member"), dict):
            _on_member(conn, tenant_id, update["my_chat_member"])
        elif isinstance(update.get("message"), dict):
            _on_message(conn, tenant_id, update["message"], send)
    except Exception as exc:                                         # noqa: BLE001 — 글 내용 · 대화 번호가 든 예외 문구는 싣지 않는다
        log.warning("telegram update handling failed: %s", type(exc).__name__)


def _first_time(conn, update_id: int) -> bool:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO telegram_seen_updates (update_id) VALUES (%s) ON CONFLICT DO NOTHING", (update_id,))
        fresh = cur.rowcount == 1
        if fresh:
            cur.execute("DELETE FROM telegram_seen_updates WHERE seen_at < now() - interval '2 days'")
    return fresh


def _reply(send: Callable[[int, str], None], chat_id: int, text: str) -> None:
    try:
        send(chat_id, text)
    except Exception as exc:                                         # noqa: BLE001
        log.warning("telegram reply failed: %s", type(exc).__name__)


def _on_message(conn, tenant_id: str, message: dict[str, Any], send: Callable[[int, str], None]) -> None:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id")
    if chat.get("type") != "private" or not isinstance(chat_id, int):
        return                                                        # 그룹 · 채널은 받지 않는다(고객과 1:1 대화만)
    text = message.get("text")
    if isinstance(text, str) and text.startswith("/start"):
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        if parts[0] in ("/start",) or parts[0].startswith("/start@"):
            if payload:
                _reply(send, chat_id, _bind(conn, tenant_id, chat_id, payload))
                return
    _reply(send, chat_id, SAY_OTHER)                                 # ★글 내용은 읽지도 저장하지도 않는다 — 고정 문장 한 줄


def _bind(conn, tenant_id: str, chat_id: int, code: str) -> str:
    """코드를 한 번만 꺼내 그 사용자에게 대화를 묶는다 — 봇이 할 말을 돌려준다."""
    if not _CODE.match(code):
        return SAY_EXPIRED
    seconds = int(get_guardrails().get("security.telegram_link_code_seconds"))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM telegram_link_codes WHERE code_hash=%s AND tenant_id=%s AND used_at IS NULL "
                    "AND created_at > now() - make_interval(secs => %s)", (_h(code), tenant_id, seconds))
        row = cur.fetchone()
        if row is None:
            return SAY_EXPIRED
        customer_id = row[0]
        try:
            consents.require(conn, tenant_id, customer_id, "alert_channel")           # 게이트가 켜져 있으면 동의 없이는 연결하지 않는다(코드는 그대로 둔다)
        except consents.ConsentError:
            return SAY_CONSENT
        cur.execute("UPDATE telegram_link_codes SET used_at=now() WHERE code_hash=%s AND used_at IS NULL RETURNING 1", (_h(code),))
        if cur.fetchone() is None:
            return SAY_EXPIRED                                                           # 동시에 다른 업데이트가 먼저 썼다
        cur.execute("SELECT customer_id FROM customer_profiles WHERE tenant_id=%s AND telegram_chat_hash=%s",
                    (tenant_id, chat_hash(tenant_id, chat_id)))
        owner = cur.fetchone()
        if owner is not None and owner[0] != customer_id:
            return SAY_ELSEWHERE
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO customer_profiles (tenant_id, customer_id, telegram_chat_enc, telegram_chat_hash, telegram_status, "
                "telegram_connected_at, telegram_checked_at, telegram_tested_at, notice_channel) "
                "VALUES (%s,%s,%s,%s,'untested',now(),NULL,NULL,'telegram') "
                "ON CONFLICT (tenant_id, customer_id) DO UPDATE SET telegram_chat_enc=EXCLUDED.telegram_chat_enc, "
                "telegram_chat_hash=EXCLUDED.telegram_chat_hash, telegram_status='untested', telegram_connected_at=now(), "
                "telegram_checked_at=NULL, telegram_tested_at=NULL, notice_channel='telegram', updated_at=now()",
                (tenant_id, customer_id, encrypt_chat(chat_id), chat_hash(tenant_id, chat_id)))
    except pg_errors.UniqueViolation:                                                    # 같은 대화가 동시에 다른 사용자에게 묶였다
        return SAY_ELSEWHERE
    return SAY_CONNECTED


def _on_member(conn, tenant_id: str, change: dict[str, Any]) -> None:
    """고객이 봇을 차단(`kicked`)하면 `blocked`, 해제(`member`)하면 `untested`. 개인 대화에서는 이때만 온다(공식 문서)."""
    chat = change.get("chat") if isinstance(change.get("chat"), dict) else {}
    chat_id = chat.get("id")
    new = change.get("new_chat_member") if isinstance(change.get("new_chat_member"), dict) else {}
    status = new.get("status")
    if chat.get("type") != "private" or not isinstance(chat_id, int) or status not in ("kicked", "left", "member"):
        return
    with conn.transaction(), conn.cursor() as cur:
        if status in ("kicked", "left"):
            cur.execute("UPDATE customer_profiles SET telegram_status='blocked', telegram_checked_at=now(), updated_at=now() "
                        "WHERE tenant_id=%s AND telegram_chat_hash=%s", (tenant_id, chat_hash(tenant_id, chat_id)))
        else:
            cur.execute("UPDATE customer_profiles SET telegram_status='untested', updated_at=now() "
                        "WHERE tenant_id=%s AND telegram_chat_hash=%s AND telegram_status='blocked'", (tenant_id, chat_hash(tenant_id, chat_id)))


def real_send(chat_id: int, text: str) -> None:
    """운영의 봇 답 — 실제 `sendMessage`. 설정이 없으면 아무것도 안 한다(웹훅이 켜졌다면 설정이 있다)."""
    cfg = config()
    if cfg is not None:
        client.send_message(cfg[0], chat_id, text)


# ── 연결 풀기 · 시험 발송 ───────────────────────────────────────
def send_test(conn, tenant_id: str, customer_id: UUID, *, min_interval_seconds: float,
              now: datetime | None = None) -> tuple[str, customer_profile.View]:
    """연결된 대화로 시험 메시지 한 줄. 돌려주는 것 = (결과, 갱신된 조회 모양). 결과: ok · blocked · rate_limited · failed.
    ★고객이 누를 때만 · 마지막 시도로부터 `min_interval_seconds` 안이면 `too_soon`(429). 어떤 실패에도 대화 번호 · 토큰을 문구에 싣지 않는다."""
    from app.infrastructure.notify.discord import RetryAfter

    cfg = config()
    if cfg is None:
        raise ProfileError("not_found", "텔레그램 연결을 쓸 수 없어요", status=404)
    now = now or datetime.now(KST)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT telegram_chat_enc, telegram_tested_at FROM customer_profiles WHERE tenant_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, customer_id))
        row = cur.fetchone()
        if row is None or row[0] is None:
            raise ProfileError("no_telegram", "연결된 텔레그램이 없어요", status=409)
        stored, tested_at = row
        if tested_at is not None and (now - tested_at).total_seconds() < min_interval_seconds:
            wait = max(1, int(min_interval_seconds - (now - tested_at).total_seconds()))
            error = ProfileError("too_soon", f"시험 발송은 잠시 뒤에 다시 할 수 있어요({wait}초 뒤)", status=429)
            error.retry_after = wait
            raise error
        cur.execute("UPDATE customer_profiles SET telegram_tested_at=%s WHERE tenant_id=%s AND customer_id=%s", (now, tenant_id, customer_id))
    chat_id = decrypt_chat(stored)
    try:
        client.send_message(cfg[0], chat_id, TEST_TEXT)
        result = "ok"
    except client.ChatUnavailable:
        result = "blocked"
    except RetryAfter:
        result = "rate_limited"
    except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError):
        result = "failed"
    status = {"ok": "ok", "blocked": "blocked"}.get(result)
    if status is not None:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE customer_profiles SET telegram_status=%s, telegram_checked_at=%s WHERE tenant_id=%s AND customer_id=%s",
                        (status, now, tenant_id, customer_id))
    return result, customer_profile.read(conn, tenant_id, customer_id)


__all__ = ["SAY_CONNECTED", "SAY_ELSEWHERE", "SAY_EXPIRED", "SAY_OTHER", "available", "begin", "chat_hash", "config", "count_start", "decrypt_chat",
           "disconnect", "encrypt_chat", "handle_update", "public_state", "real_send", "send_test", "verify_secret"]
