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
    args = parser.parse_args()

    # ★`trip.notice`(일정 변경 통지)는 디스코드 웹훅으로 나간다(v11 §6-A). 웹훅이
    #   비어 있으면 **실패로 남긴다** — 보낸 적 없는 알림을 `delivered` 로 찍지 않는다.
    from app.core.settings import get_settings
    from app.infrastructure.notify import DiscordWebhook

    publisher = DiscordWebhook(get_settings().discord_webhook_url, fallback=publish)
    worker = OutboxWorker(get_connection, publisher, tenant_id=args.tenant)
    handled = 0
    while worker.process_once():
        handled += 1
        if not args.drain:
            break
    print(json.dumps({"handled": handled}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

