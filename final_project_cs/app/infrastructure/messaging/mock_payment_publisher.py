"""In-memory payment-provider substitute for integration tests.

This deliberately performs no network I/O.  It implements the messaging port
so the outbox worker can exercise the same publisher boundary used by a real
provider adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal



PublisherMode = Literal["success", "timeout", "connection_error"]


@dataclass
class MockProviderPublisher:
    """Simulate a payment gateway response selected by ``mode``."""

    mode: PublisherMode = "success"
    published: list[dict[str, Any]] = field(default_factory=list)
    acknowledged: list[str] = field(default_factory=list)

    async def publish(self, topic: str, payload: dict[str, Any], dedupe_key: str) -> str:
        message = {"topic": topic, "payload": payload, "dedupe_key": dedupe_key}
        if self.mode == "timeout":
            raise TimeoutError("mock gateway timed out")
        if self.mode == "connection_error":
            raise ConnectionError("mock gateway connection failed")
        if self.mode != "success":
            raise ValueError(f"unsupported mock gateway mode: {self.mode}")
        self.published.append(message)
        return dedupe_key

    async def ack(self, message_id: str) -> None:
        self.acknowledged.append(message_id)
