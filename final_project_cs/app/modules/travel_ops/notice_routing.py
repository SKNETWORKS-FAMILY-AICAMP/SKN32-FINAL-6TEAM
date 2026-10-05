# -*- coding: utf-8 -*-
"""고객별 알림 발송 — 일정 변경 알림(`trip.notice`)을 **고객이 연결한 곳 한 곳**으로 보낸다. `[2026-10-05 사용자 지시 「다 진행해」 — 텔레그램 요청서의 전제]`

★왜. 지금까지 바깥함 일꾼은 알림을 **운영자 채널 하나**(전역 웹훅)로만 보냈다 — 고객이 저장한 디스코드 웹훅은 시험 발송만 되고 실제 알림이 가지 않았다(2026-10-05 확인).
★어떻게. 일꾼의 발행자 자리에 끼운다(`scripts/run_outbox_worker.py`). 알림의 `dedupe_key`(`{여행 번호}:…`)로 **여행 → 고객 → 알림 받는 곳**(`customer_profiles.notice_channel`)을 찾고,
  그 채널로 **한 곳에만** 보낸다(같은 알림이 두 곳으로 가지 않는다 · 여러 곳 동시 발송은 이번 범위가 아니다). 문구 · 번역 · `[재생]` 표시는 운영자 채널과 **같은 규칙**(`DiscordWebhook.text_for`)이다.
★스위치 `travel.notice_per_customer_enabled`(**기본 꺼짐**) — 꺼져 있으면 옛 동작 그대로(운영자 채널). 켜는 것은 실제 고객에게 메시지가 나가는 일이라 사용자 승인 뒤에만 켠다.
★규칙은 `DiscordWebhook` 과 같다: 전송 성공만 `delivered` · 시간 초과/연결 끊김은 `unknown`(자동 재전송 없음) · 한도(429)는 공급자가 말한 시각에 다시 · **설정이 없으면 실패로 올림**(조용한 성공 위장 금지) ·
  운영 테넌트만(`allowed_tenants` — 시험 알림이 고객에게 나간 2026-09-22 사고를 막는다).
★**보낼 수 없는 것은 `skipped`**(`NoticeSuppressed`) 로 사유와 함께 남긴다 — `delivered` 로 찍지 않고 다시 집지도 않는다: 연결한 곳이 없음 · 알림 채널 동의가 없음(게이트가 켜져 있을 때) · 텔레그램 대화 막힘 ·
  디스코드 웹훅이 지워졌거나 거부됨 · 저장값을 못 읽음 · 여행이 지워짐. 고객은 그래도 **여행계획서 링크**에서 최신 상태를 본다(상태의 정본은 링크).
★막힘 · 거부를 알게 되면 그 상태를 프로필에 남긴다(`telegram_status='blocked'` · `discord_status='invalid'`) — 마이페이지가 「다시 연결」을 안내할 수 있게. 성공하면 `ok`.
★비밀: 웹훅 주소 · 대화 번호 · 봇 토큰 · 알림 본문은 로그 · 예외 문구에 싣지 않는다(예외는 상태 코드만).
"""
from __future__ import annotations

import logging
from typing import Any, Callable
from uuid import UUID

import httpx

from app.infrastructure.notify import telegram as telegram_client
from app.infrastructure.notify.discord import NoticeNotConfigured, RetryAfter, _cut as discord_cut, _retry_after as discord_retry_after
from app.infrastructure.notify.suppressed import NoticeSuppressed

from . import consents, customer_profile, telegram_connect

log = logging.getLogger(__name__)

TOPICS = frozenset({"trip.notice"})
#: 웹훅이 지워졌거나 거부된 응답 — 더 보내도 소용없다
_DISCORD_GONE = (401, 403, 404, 410)
#: 시험이 바깥 호출을 가로채는 자리(디스코드). 텔레그램은 `infrastructure/notify/telegram.TRANSPORT`
TRANSPORT: httpx.BaseTransport | None = None


def trip_id_of(dedupe_key: Any) -> UUID | None:
    """여행 알림의 키 `{여행 번호}:…` 에서 여행 번호를 꺼낸다. 모양이 다르면 None."""
    if not isinstance(dedupe_key, str) or ":" not in dedupe_key:
        return None
    try:
        return UUID(dedupe_key.split(":", 1)[0])
    except ValueError:
        return None


class CustomerNoticeRouter:
    """일꾼의 발행자 — `trip.notice` 만 고객 채널로 보내고 나머지(와 스위치가 꺼졌을 때)는 `operator` 에 넘긴다."""

    def __init__(self, *, operator: Callable[[dict[str, Any]], Any], connection_factory: Callable[[], Any],
                 enabled: Callable[[], bool], renderer: Any, allowed_tenants: set[str] | None = None,
                 telegram_token: Callable[[], str] | None = None, timeout: float = 8.0) -> None:
        self._operator = operator
        self._connect = connection_factory
        self._enabled = enabled
        self._renderer = renderer                           # `text_for(payload)` 를 가진 것(운영자 채널의 `DiscordWebhook`)
        self.allowed_tenants = None if allowed_tenants is None else set(allowed_tenants)
        self._token = telegram_token or (lambda: (telegram_connect.config() or ("", "", ""))[0])
        self._timeout = timeout

    def __call__(self, message: dict[str, Any]) -> None:
        if message.get("topic") not in TOPICS or not self._enabled():
            return self._operator(message)                  # 옛 동작 — 운영자 채널(스위치가 꺼졌을 때) · 다른 주제
        tenant = str(message.get("tenant_id") or "")
        if self.allowed_tenants is not None and tenant not in self.allowed_tenants:
            raise NoticeSuppressed(f"보낼 대상이 아닌 테넌트({tenant or '이름 없음'}) — 바깥으로 보내지 않았다. 보내는 테넌트: {sorted(self.allowed_tenants)}")
        trip_id = trip_id_of(message.get("dedupe_key"))
        if trip_id is None:
            raise NoticeSuppressed("어느 여행의 알림인지 알 수 없다 — 보내지 않았다")
        with self._connect() as conn:
            found = self._destination(conn, tenant, trip_id)
        customer, channel, secret, status = found
        payload = message.get("payload") or {}
        text = self._renderer.text_for(payload)
        if channel == "telegram":
            self._send_telegram(tenant, customer, secret, text)
        else:
            self._send_discord(tenant, customer, secret, text)

    # ── 누구에게 · 어디로 ────────────────────────────────────────
    def _destination(self, conn, tenant: str, trip_id: UUID) -> tuple[UUID, str, str, str | None]:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id FROM trips WHERE tenant_id=%s AND trip_id=%s", (tenant, trip_id))
            row = cur.fetchone()
        if row is None:
            raise NoticeSuppressed("그 여행이 지워졌다 — 보낼 곳이 없다")
        customer = row[0]
        with conn.cursor() as cur:
            cur.execute("SELECT notice_channel, discord_webhook_enc, telegram_chat_enc, telegram_status FROM customer_profiles "
                        "WHERE tenant_id=%s AND customer_id=%s", (tenant, customer))
            profile = cur.fetchone()
        if profile is None or profile[0] is None:
            raise NoticeSuppressed("고객이 알림 받을 곳을 연결하지 않았다 — 여행계획서 링크에서 확인한다")
        try:
            consents.require(conn, tenant, customer, "alert_channel")
        except consents.ConsentError:
            raise NoticeSuppressed("알림 채널 동의가 없다 — 보내지 않았다") from None
        channel, webhook_enc, chat_enc, tg_status = profile
        if channel == "telegram":
            if chat_enc is None:
                raise NoticeSuppressed("텔레그램 연결이 없다")
            if tg_status == "blocked":
                raise NoticeSuppressed("텔레그램 대화가 막혀 있다(고객이 봇을 차단) — 다시 연결하면 풀린다")
            try:
                return customer, "telegram", str(telegram_connect.decrypt_chat(chat_enc)), tg_status
            except customer_profile.ProfileError:
                raise NoticeSuppressed("저장된 텔레그램 연결을 읽을 수 없다 — 고객이 다시 연결해야 한다") from None
        if webhook_enc is None:
            raise NoticeSuppressed("디스코드 웹훅이 없다")
        try:
            return customer, "discord", customer_profile.decrypt(webhook_enc), None
        except customer_profile.ProfileError:
            raise NoticeSuppressed("저장된 디스코드 웹훅을 읽을 수 없다 — 고객이 다시 넣어야 한다") from None

    # ── 보내기 ───────────────────────────────────────────────────
    def _send_telegram(self, tenant: str, customer: UUID, chat_id: str, text: str) -> None:
        token = self._token()
        if not token:
            raise NoticeNotConfigured("ACOP_TELEGRAM_BOT_TOKEN 이 비어 있다 — 알림을 보내지 않았다")
        try:
            telegram_client.send_message(token, int(chat_id), text, timeout=self._timeout)
        except telegram_client.ChatUnavailable:
            self._mark(tenant, customer, "telegram", "blocked")
            raise NoticeSuppressed("텔레그램 대화로 보낼 수 없다(차단 · 대화 없음) — 막힘으로 표시했다") from None
        self._mark(tenant, customer, "telegram", "ok")                 # 예외가 아니면 2xx 다

    def _send_discord(self, tenant: str, customer: UUID, url: str, text: str) -> None:
        try:
            canonical = customer_profile.canonical(customer_profile.parse_webhook(url))        # 보내기 직전 같은 검사를 한 번 더(저장 뒤 값이 오염됐을 때)
        except customer_profile.ProfileError:
            raise NoticeSuppressed("저장된 디스코드 웹훅이 규칙에 맞지 않는다 — 보내지 않았다") from None
        body = {"content": discord_cut(text), "allowed_mentions": {"parse": []}}                # 본문 속 @ 호출로 남의 채널을 울리지 않는다
        try:
            with httpx.Client(transport=TRANSPORT, timeout=httpx.Timeout(self._timeout), follow_redirects=False) as client:
                response = client.post(canonical, json=body)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"discord webhook timeout: {type(exc).__name__}") from None
        except httpx.TransportError as exc:
            raise ConnectionError(f"discord webhook transport: {type(exc).__name__}") from None
        if 200 <= response.status_code < 300:
            self._mark(tenant, customer, "discord", "ok")
            return
        if response.status_code == 429:
            raise RetryAfter("discord webhook 429 — 공급자가 말한 시각에 다시 보낸다", discord_retry_after(response))
        if response.status_code in _DISCORD_GONE:
            self._mark(tenant, customer, "discord", "invalid")
            raise NoticeSuppressed(f"디스코드 웹훅이 지워졌거나 거부됐다(HTTP {response.status_code}) — 무효로 표시했다")
        raise RuntimeError(f"discord webhook HTTP {response.status_code}")

    def _mark(self, tenant: str, customer: UUID, channel: str, status: str) -> None:
        """보낸 결과를 프로필 상태에 남긴다. ★못 남겨도 발송 결과를 바꾸지 않는다(로그에 종류만)."""
        column = "telegram" if channel == "telegram" else "discord"
        try:
            with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute(f"UPDATE customer_profiles SET {column}_status=%s, {column}_checked_at=now() WHERE tenant_id=%s AND customer_id=%s",
                            (status, tenant, customer))
        except Exception as exc:                                    # noqa: BLE001
            log.warning("notice channel status mark failed (%s): %s", channel, type(exc).__name__)


__all__ = ["CustomerNoticeRouter", "TOPICS", "trip_id_of"]
