"""Claim and deliver outbox rows without deleting them."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from app.core.settings import get_guardrails


class OutboxWorker:
    def __init__(self, connection_factory, publisher: Callable[[dict[str, Any]], Any], *,
                 max_attempts: int = 3, tenant_id: str | None = None) -> None:
        # ★tenant_id 를 주면 그 tenant 의 메시지만 집는다.
        #   운영에서는 한 tenant 의 적체가 다른 tenant 를 굶기지 않게 나눠 돌릴 수 있고,
        #   테스트에서는 **남의 tenant 행을 물어 엉뚱하게 실패하는 것**을 막는다.
        #   기본값(None)은 전체를 집는 기존 동작이다.
        self.connection_factory, self.publisher, self.max_attempts = connection_factory, publisher, max_attempts
        self.tenant_id = tenant_id

    def _reclaim_stale_processing(self, conn: Any) -> None:
        """Expose crashed workers' abandoned claims as human-reviewable unknowns."""
        stale_seconds = get_guardrails().get("reliability.outbox_stale_processing_seconds")
        with conn.transaction():
            with conn.cursor() as cur:
                scope = "AND tenant_id=%s " if self.tenant_id else ""
                params = (self.tenant_id,) if self.tenant_id else ()
                cur.execute(
                    "UPDATE outbox SET status='unknown', "
                    "last_error='worker crashed or died while processing (stale lock reclaimed)', "
                    "locked_at=NULL "
                    f"WHERE status='processing' AND locked_at < now() - make_interval(secs => %s) {scope}",
                    (stale_seconds, *params),
                )

    def process_once(self) -> bool:
        with self.connection_factory() as conn:
            self._reclaim_stale_processing(conn)
            with conn.transaction():
                with conn.cursor() as cur:
                    scope = "AND tenant_id=%s " if self.tenant_id else ""
                    params = (self.tenant_id,) if self.tenant_id else ()
                    cur.execute("SELECT message_id,topic,payload_json,attempts FROM outbox WHERE status='pending' "
                                f"AND available_at<=now() {scope}"
                                "ORDER BY available_at FOR UPDATE SKIP LOCKED LIMIT 1", params)
                    row = cur.fetchone()
                    if row is None:
                        return False
                    message_id, topic, payload, attempts = row
                    cur.execute("UPDATE outbox SET status='processing',attempts=attempts+1,locked_at=now() WHERE message_id=%s", (message_id,))
            try:
                self.publisher({"message_id": str(message_id), "topic": topic, "payload": payload})
            except (TimeoutError, ConnectionError) as exc:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("UPDATE outbox SET status='unknown',last_error=%s,locked_at=NULL WHERE message_id=%s", (str(exc), message_id))
                return True
            except Exception as exc:
                status = "dead_letter" if attempts + 1 >= self.max_attempts else "pending"
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("UPDATE outbox SET status=%s,last_error=%s,locked_at=NULL,available_at=now()+interval '1 minute' WHERE message_id=%s", (status, str(exc), message_id))
                return True
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("UPDATE outbox SET status='delivered',locked_at=NULL,last_error=NULL WHERE message_id=%s", (message_id,))
        return True
