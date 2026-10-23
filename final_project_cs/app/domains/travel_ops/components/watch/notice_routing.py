# -*- coding: utf-8 -*-
"""고객별 알림 발송 — 일정 변경 알림(`trip.notice`)을 **고객이 연결한 곳 한 곳**으로 보낸다. `[2026-10-05 사용자 지시 「다 진행해」 — 텔레그램 요청서의 전제]`

★왜. 지금까지 바깥함 일꾼은 알림을 **운영자 채널 하나**(전역 웹훅)로만 보냈다 — 고객이 저장한 디스코드 웹훅은 시험 발송만 되고 실제 알림이 가지 않았다(2026-10-05 확인).
★어떻게. 일꾼의 발행자 자리에 끼운다(`scripts/run_outbox_worker.py`). 알림의 `dedupe_key`(`{여행 번호}:…`)로 **여행 → 고객 → 알림 받는 곳**(`customer_profiles.notice_channel`)을 찾고,
  그 채널로 **한 곳에만** 보낸다(같은 알림이 두 곳으로 가지 않는다 · 여러 곳 동시 발송은 이번 범위가 아니다). 문구 · 번역 · `[재생]` 표시는 운영자 채널과 **같은 규칙**(`DiscordWebhook.text_for`)이다.
★스위치 `travel.notice_per_customer_enabled`(**기본 꺼짐**) — 꺼져 있으면 외부 발송만 건너뛰고 앱 알림은 유지한다. 고객 알림을 개발용 디스코드로 우회하지 않는다(`[2026-10-09 사용자 정정]`). 켜는 것은 실제 고객에게 메시지가 나가는 일이라 사용자 승인 뒤에만 켠다.
★규칙은 `DiscordWebhook` 과 같다: 전송 성공만 `delivered` · 시간 초과/연결 끊김은 `unknown`(자동 재전송 없음) · 한도(429)는 공급자가 말한 시각에 다시 · **설정이 없으면 실패로 올림**(조용한 성공 위장 금지) ·
  운영 테넌트만(`allowed_tenants` — 시험 알림이 고객에게 나간 2026-09-22 사고를 막는다).
★**외부 발송을 건너뛰는 것은 `skipped`**(`NoticeSuppressed`) 로 사유와 함께 남긴다 — `delivered` 로 찍지 않고 다시 집지도 않는다: 외부 알림 꺼짐 · 연결한 곳이 없음 · 알림 채널 동의가 없음(게이트가 켜져 있을 때) · 텔레그램 대화 막힘 ·
  디스코드 웹훅이 지워졌거나 거부됨 · 저장값을 못 읽음 · 여행이 지워짐. 앱 알림 API는 이 배달 상태로 목록을 거르지 않으며, 고객은 **여행계획서 링크**에서도 최신 상태를 본다(상태의 정본은 링크).
★막힘 · 거부를 알게 되면 그 상태를 프로필에 남긴다(`telegram_status='blocked'` · `discord_status='invalid'`) — 마이페이지가 「다시 연결」을 안내할 수 있게. 성공하면 `ok`.
★비밀: 웹훅 주소 · 대화 번호 · 봇 토큰 · 알림 본문은 로그 · 예외 문구에 싣지 않는다(예외는 상태 코드만).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

import httpx

from app.infrastructure.notify import telegram as telegram_client
from app.infrastructure.notify.discord import NoticeNotConfigured, RetryAfter, _cut as discord_cut, _retry_after as discord_retry_after
from app.infrastructure.notify.suppressed import NoticeSuppressed

from app.domains.travel_ops.components.customer import consents
from app.domains.travel_ops.components.customer import profile as customer_profile
from app.domains.travel_ops.components.customer import channels as telegram_connect

log = logging.getLogger(__name__)

TOPICS = frozenset({"trip.notice", "customer.notice"})
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



def guidance_item_ids(items) -> list[str]:
    """안내 알림의 일정 목록에서 항목 id 만 꺼낸다.

    ★`[2026-10-19 x600 운영]` 대부분의 안내는 id 문자열 목록이지만, 위험 확인 안내(`risk_detected`)는
    `{item_id, title, starts_at, ...}` 객체 목록을 싣는다. 객체를 그대로 `uuid[]` 로 넘기면
    「cannot adapt type 'dict'」로 발송 전체가 실패했다(16:38~16:52 3건). id 가 없는 칸은 건너뛴다."""
    ids = []
    for item in items or []:
        value = item.get("item_id") if isinstance(item, dict) else item
        if value:
            ids.append(str(value))
    return ids

class CustomerNoticeRouter:
    """일꾼의 발행자 — `trip.notice`는 고객 연결로만 보내며, 다른 주제만 `operator`에 넘긴다."""

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
        if message.get("topic") not in TOPICS:
            return self._operator(message)
        simulated = bool((message.get("payload") or {}).get("simulation"))
        run_id = (message.get("payload") or {}).get("simulation_id")
        if simulated and (not run_id or trip_id_of(message.get("dedupe_key")) is None):
            raise NoticeSuppressed("재난 시뮬레이션 외부 발송이 허용되지 않았다")
        if not self._enabled():
            raise NoticeSuppressed("고객 외부 알림이 꺼져 있다 — 앱 알림에서 확인한다")
        tenant = str(message.get("tenant_id") or "")
        if self.allowed_tenants is not None and tenant not in self.allowed_tenants:
            raise NoticeSuppressed(f"보낼 대상이 아닌 테넌트({tenant or '이름 없음'}) — 바깥으로 보내지 않았다. 보내는 테넌트: {sorted(self.allowed_tenants)}")
        if message.get('topic') == 'customer.notice':
            if simulated:
                raise NoticeSuppressed('고객 공지는 재난 시뮬레이션 권한을 재사용하지 않는다')
            identity = trip_id_of(message.get('dedupe_key'))
            expected = (message.get('payload') or {}).get('service_notice_id')
            if identity is None or not expected or message.get('dedupe_key') != f'{identity}:service:{expected}':
                raise NoticeSuppressed('고객 공지 발송 대상이 올바르지 않다')
            expires = (message.get('payload') or {}).get('expires_at')
            if expires and datetime.fromisoformat(expires) <= datetime.now(timezone.utc):
                raise NoticeSuppressed('공지 게시 기간이 종료되어 외부 발송하지 않는다')
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1 FROM customers WHERE tenant_id=%s AND customer_id=%s', (tenant, identity))
                    if not cur.fetchone():
                        raise NoticeSuppressed('이 테넌트의 고객이 아니다')
                found = self._customer_destination(conn, tenant, identity)
        else:
            return self._trip(message, tenant, simulated, run_id)
        self._send(found, tenant, message.get('payload') or {}, simulated=False)

    def _trip(self, message, tenant, simulated, run_id):
        trip_id = trip_id_of(message.get("dedupe_key"))
        if trip_id is None:
            raise NoticeSuppressed("어느 여행의 알림인지 알 수 없다 — 보내지 않았다")
        with self._connect() as conn:
            if simulated:
                from app.domains.travel_ops.components.watch.simulation import external_delivery_allowed
                if not external_delivery_allowed(conn, tenant, trip_id, str(run_id)):
                    raise NoticeSuppressed("이 여행·실행의 시뮬레이션 외부 발송이 꺼져 있거나 종료됐다")
            payload = message.get("payload") or {}
            if payload.get("kind") in ("departure", "next_item") and payload.get("item_id"):
                with conn.cursor() as cur:
                    cur.execute("SELECT i.detail FROM trips t JOIN itinerary_items i ON i.tenant_id=t.tenant_id "
                                "AND i.trip_id=t.trip_id AND i.version=t.latest_version "
                                "WHERE t.tenant_id=%s AND t.trip_id=%s AND i.item_id=%s",
                                (tenant, trip_id, UUID(str(payload["item_id"]))))
                    current = cur.fetchone()
                if not current or (current[0].get("execution") or {}).get("state") in ("completed", "skipped"):
                    raise NoticeSuppressed("현재 일정에서 완료·교체된 안내라 보내지 않았다")
            for basis in payload.get("schedule_basis") or []:
                with conn.cursor() as cur:
                    cur.execute("SELECT i.starts_at,i.ends_at,i.detail FROM itinerary_items i JOIN trips t "
                        "ON t.tenant_id=i.tenant_id AND t.trip_id=i.trip_id AND t.latest_version=i.version "
                        "WHERE t.tenant_id=%s AND t.trip_id=%s AND i.item_id=%s",
                        (tenant, trip_id, UUID(basis["item_id"])))
                    row = cur.fetchone()
                expected_end = datetime.fromisoformat(basis["ends_at"]) if basis.get("ends_at") else None
                if (not row or row[0] != datetime.fromisoformat(basis["starts_at"]) or row[1] != expected_end
                        or (row[2].get("execution") or {}).get("state") in ("completed", "skipped")):
                    raise NoticeSuppressed("이 안내의 일정 시각이 바뀌거나 완료·교체되어 보내지 않았다")
            if payload.get("type") == "guidance" and payload.get("items"):
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM itinerary_items i JOIN trips t "
                        "ON t.tenant_id=i.tenant_id AND t.trip_id=i.trip_id AND t.latest_version=i.version "
                        "WHERE t.tenant_id=%s AND t.trip_id=%s AND i.item_id=ANY(%s::uuid[]) "
                        "AND COALESCE(i.detail->'execution'->>'state','') NOT IN ('completed','skipped')",
                        (tenant, trip_id, guidance_item_ids(payload['items'])))
                    relevant = cur.fetchone()[0]
                if not relevant:
                    raise NoticeSuppressed("이 안내의 일정이 모두 완료·교체되어 보내지 않았다")
            found = self._destination(conn, tenant, trip_id)
        self._send(found, tenant, message.get('payload') or {}, simulated=simulated)

    def _send(self, found, tenant, payload, *, simulated):
        customer, channel, secret, status = found
        text = self._renderer.text_for(payload)
        if simulated and not text.startswith('[시뮬레이션]'):
            text = '[시뮬레이션] ' + text
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
        return self._customer_destination(conn, tenant, row[0])

    def _customer_destination(self, conn, tenant: str, customer: UUID):
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
