"""Claim and deliver outbox rows without deleting them."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from acop_basement.core.settings import get_guardrails


class OutboxWorker:
    def __init__(self, connection_factory, publisher: Callable[[dict[str, Any]], Any], *,
                 max_attempts: int = 3, tenant_id: str | None = None) -> None:
        # ★tenant_id 를 주면 그 tenant 의 메시지만 집는다. 기본값(None)은 전체다.
        #
        # 두 가지 이유로 필요하다:
        #  1. 운영 — 전체를 집으면 한 tenant 의 적체가 다른 tenant 를 굶긴다(head-of-line).
        #     tenant 별로 나눠 돌릴 수단이 없었다.
        #  2. ★테스트 — worker 가 **가장 오래된 pending 을 tenant 무관하게** 집으므로
        #     남의 tenant 행 하나만 남아 있어도 엉뚱한 행을 물어 테스트가 깨진다.
        #     실측: `zz_foreign` tenant 의 pending 1행을 심자
        #     `test_provider_timeout_stays_unknown_and_is_not_retried` 가 즉시 실패했다.
        #     쇼핑몰 복사본에서 먼저 드러났고, 여기서 재현해 확인한 뒤 함께 고쳤다.
        self.connection_factory, self.publisher, self.max_attempts = connection_factory, publisher, max_attempts
        self.tenant_id = tenant_id

    def _reclaim_stale_processing(self, conn: Any) -> None:
        """★claim 커밋 후·`publisher()` 완료 전에 워커가 죽으면 그 행은 영영
        'processing' 에 멈춘다 — 재시작한 워커는 'pending' 만 본다(버그사냥
        2026-08-17). 실제로 배달됐는지 모르므로 provider timeout 과 같은 근거로
        'unknown' 으로 되돌린다 — **자동 재실행하지 않는다.** 사람이 `/ops/outbox`
        에서 결론짓는다."""
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
                    (stale_seconds, *params))

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

