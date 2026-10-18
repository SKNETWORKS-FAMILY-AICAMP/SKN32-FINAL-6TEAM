"""Run one outbox delivery attempt: python -m scripts.run_outbox_worker --once"""
from __future__ import annotations

import argparse
import json

from app.infrastructure.db.session import get_connection
from app.infrastructure.messaging.worker import OutboxWorker


def publish(message: dict) -> None:
    # Transport is intentionally an injected boundary in Phase 1. Persisting the
    # row and marking it delivered are the observable MVP delivery semantics.
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--tenant", default=None, help="이 테넌트의 메시지만 집는다")
    parser.add_argument("--drain", action="store_true", help="보낼 것이 없을 때까지 돈다")
    parser.add_argument("--send-tenant", action="append", default=None,
                        help="이 테넌트의 통지도 **바깥으로** 보낸다(기본은 운영 테넌트 하나만)")
    args = parser.parse_args()

    # ★고객 알림은 아래 CustomerNoticeRouter가 고객 연결 여부에 따라 보낸다.
    #   공용 DiscordWebhook은 문구 생성에 재사용하며 고객 알림의 우회 발송에는 쓰지 않는다.
    from app.core.settings import REPO_ROOT, get_settings
    from app.infrastructure.notify import DiscordWebhook, PhraseCache
    from app.infrastructure.notify.translate import make_translator
    from app.infrastructure.ollama_chat import from_settings

    # ★보낼 때 고객 언어로 옮긴다(결정 14) — Ollama(Gemma 4)가 설정돼 있을 때.
    settings = get_settings()
    # ★`[2026-10-19]` 유료 대체 모델 호출 상한(`external_call_budget` 의 openai_failover 줄)은 조립 루트가 꽂는다.
    #   이 일꾼은 조립 루트를 거치지 않아 상한 없이 불렀다(오라클 worker 로그 「no call-budget gate registered」).
    #   넘김 장치는 만들 때 상한을 읽으므로 `from_settings` **앞에서** 꽂는다(이미 꽂혀 있어도 같은 것을 다시 꽂을 뿐이다).
    from app import composition
    composition._register_llm_failover()
    chat = from_settings(settings)
    # ★문구틀·언어마다 한 번만 옮긴다 — 담아 둔 틀을 읽고, 끝나면 새로 옮긴 틀을 남긴다.
    #   ☆담기는 것은 틀뿐이다. 시각·장소·금액·예약번호는 알림마다 그 알림의 값으로 채운다.
    phrases = PhraseCache(path=(REPO_ROOT / settings.notice_phrasebook_path)
                          if settings.notice_phrasebook_path else None)
    phrases.load()
    # ★`[2026-09-22]` **운영 테넌트의 통지만** 바깥으로 보낸다. 시연·시험 테넌트가 실제 채널로 나간
    #   사고가 있었다(8건, 대만 중국어 시연 문구). `--send-tenant` 로 더 주면 그것도 보낸다.
    allowed = {settings.tenant_id, *(args.send_tenant or [])}
    publisher = DiscordWebhook(settings.discord_webhook_url, fallback=publish, allowed_tenants=allowed,
                               translator=make_translator(chat) if chat else None,
                               phrases=phrases)
    # ★`[2026-10-05]` 고객별 발송 — 스위치(`travel.notice_per_customer_enabled`, 기본 꺼짐)가 켜져 있으면 여행 알림을 **고객이 연결한 곳 한 곳**(디스코드 웹훅 · 텔레그램)으로 보낸다.
    #   꺼져 있으면 외부 발송만 `skipped` 로 남기고 앱 알림은 유지한다. 고객 알림을 위의 운영자 채널로 우회하지 않는다. 보내면 안 되는 테넌트 · 연결 없음 · 막힘도 `skipped`(`app/domains/travel_ops/components/watch/notice_routing.py`).
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.watch.notice_routing import CustomerNoticeRouter

    publisher = CustomerNoticeRouter(
        operator=publisher, connection_factory=get_connection, renderer=publisher, allowed_tenants=allowed,
        enabled=lambda: bool(get_guardrails().get("travel.notice_per_customer_enabled")))
    worker = OutboxWorker(get_connection, publisher, tenant_id=args.tenant)
    handled = 0
    while worker.process_once():
        handled += 1
        if not args.drain:
            break
    phrases.save()
    print(json.dumps({"handled": handled, "phrases": phrases.stats()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
