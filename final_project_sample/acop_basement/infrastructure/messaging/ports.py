from __future__ import annotations

from typing import Protocol, Any


class MessageBrokerPort(Protocol):
    async def publish(self, topic: str, payload: dict[str, Any], dedupe_key: str) -> str: ...
    async def ack(self, message_id: str) -> None: ...

