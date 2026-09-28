"""Guard the set of messaging consumers covered by idempotency evidence.

Verification method: locally adding ``class DummyConsumer`` under
``app/infrastructure/messaging/`` without updating this set makes this test fail.
"""
from __future__ import annotations

import re
from pathlib import Path


MESSAGING_DIR = Path("acop_basement/infrastructure/messaging")
CONSUMER_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*(?:Worker|Consumer))\b")

# Every name here must have a duplicate-delivery idempotency test.
PROVEN_IDEMPOTENT_CONSUMERS = {"OutboxWorker"}


def _consumer_names() -> set[str]:
    names: set[str] = set()
    for path in MESSAGING_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = CONSUMER_CLASS.match(line)
            if match:
                names.add(match.group(1))
    return names


def test_every_messaging_consumer_is_explicitly_proven_idempotent():
    discovered = _consumer_names()
    undeclared = discovered - PROVEN_IDEMPOTENT_CONSUMERS
    stale = PROVEN_IDEMPOTENT_CONSUMERS - discovered

    assert not undeclared and not stale, (
        "Consumer 목록과 검증된 목록이 일치하지 않는다. "
        "새 consumer 를 추가했으면 duplicate-delivery idempotency 테스트를 쓰고 "
        "PROVEN_IDEMPOTENT_CONSUMERS 에 추가하라. "
        f"discovered={sorted(discovered)}, undeclared={sorted(undeclared)}, "
        f"stale={sorted(stale)}"
    )
