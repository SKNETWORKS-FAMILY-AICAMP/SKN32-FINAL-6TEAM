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

    # ★`trip.notice`(일정 변경 통지)는 디스코드 웹훅으로 나간다(v11 §6-A). 웹훅이
    #   비어 있으면 **실패로 남긴다** — 보낸 적 없는 알림을 `delivered` 로 찍지 않는다.
    from app.core.settings import REPO_ROOT, get_settings
    from app.infrastructure.notify import DiscordWebhook, PhraseCache
    from app.infrastructure.notify.translate import make_translator
    from app.infrastructure.ollama_chat import from_settings

    # ★보낼 때 고객 언어로 옮긴다(결정 14) — Ollama(Gemma 4)가 설정돼 있을 때.
    settings = get_settings()
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

