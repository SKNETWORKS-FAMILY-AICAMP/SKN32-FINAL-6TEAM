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
    parser.parse_args()
    worker = OutboxWorker(get_connection, publish)
    worker.process_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

