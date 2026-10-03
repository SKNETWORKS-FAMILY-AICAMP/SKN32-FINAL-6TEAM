"""Claim and deliver outbox rows without deleting them."""
from __future__ import annotations

from typing import Any, Callable

from app.core.settings import get_guardrails
from app.infrastructure.notify.discord import RetryAfter
from app.infrastructure.notify.suppressed import NoticeSuppressed


class OutboxWorker:
    def __init__(self, connection_factory, publisher: Callable[[dict[str, Any]], Any], *,
                 max_attempts: int = 3, tenant_id: str | None = None) -> None:
        # ★tenant_id 를 주면 그 tenant 의 메시지만 집는다.
        #   운영에서는 한 tenant 의 적체가 다른 tenant 를 굶기지 않게 나눠 돌릴 수 있고,
        #   테스트에서는 **남의 tenant 행을 물어 엉뚱하게 실패하는 것**을 막는다.
        #   기본값(None)은 전체를 집는 기존 동작이다.
        self.connection_factory, self.publisher, self.max_attempts = connection_factory, publisher, max_attempts
        self.tenant_id = tenant_id

    @staticmethod
    def _retry_seconds() -> float:
        """공급자가 말해 주지 않을 때 쓰는 기본 간격.

        ★`[2026-10-03]` 전에는 SQL 에 `interval '1 minute'` 로 박혀 있어 설정으로
          바꿀 수 없었다. 값 자체는 그대로 60초다 — 바꿀 근거가 없어서 옮기기만 했다.
        ★간격을 점점 늘리는 방식(지수 백오프)은 **안 쓴다.** 그 방식은 여럿이 한
          상대를 두드려 서로를 밀어낼 때 쓰는 것이고, 여기는 내보내는 곳이 하나에
          양도 적다. 그리고 정작 조심해야 할 429 는 공급자가 정확한 값을 준다 —
          추측으로 덮을 이유가 없다.
        """
        return float(get_guardrails().get("reliability.outbox_retry_seconds") or 60.0)

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
                    cur.execute("SELECT message_id,topic,payload_json,attempts,tenant_id FROM outbox "
                                "WHERE status='pending' "
                                f"AND available_at<=now() {scope}"
                                "ORDER BY available_at FOR UPDATE SKIP LOCKED LIMIT 1", params)
                    row = cur.fetchone()
                    if row is None:
                        return False
                    message_id, topic, payload, attempts, tenant_id = row
                    cur.execute("UPDATE outbox SET status='processing',attempts=attempts+1,locked_at=now() WHERE message_id=%s", (message_id,))
            try:
                self.publisher({"message_id": str(message_id), "topic": topic, "payload": payload,
                                "tenant_id": tenant_id})
            except NoticeSuppressed as exc:
                # ★`[2026-09-22]` **보내면 안 되는 것**이다(시연·시험 테넌트). `delivered` 로 찍으면
                #   보낸 적 없는 알림이 보낸 것으로 남는다. 다시 집지도 않는다 — 사유와 함께 남긴다.
                #   경위: 시연 테넌트의 통지 8건이 실제 채널로 나갔다(2026-09-22).
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("UPDATE outbox SET status='skipped',last_error=%s,locked_at=NULL "
                                    "WHERE message_id=%s", (str(exc)[:500], message_id))
                return True
            except RetryAfter as exc:
                # ★공급자가 「이때 다시 와라」고 말한 경우다. 우리가 간격을 지어내지
                #   않는다 — 디스코드 문서가 `Retry-After` 를 따르라고 요구하고,
                #   어기면 IP 단위로 막는다(유효하지 않은 요청 10분에 10,000건).
                #   시도 횟수는 **올리지 않는다**. 우리 잘못이 아니라 「지금은 말고」라
                #   이것으로 dead_letter 가 되면 보낼 수 있는 알림을 버리는 것이다.
                wait = exc.seconds if exc.seconds is not None else self._retry_seconds()
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE outbox SET status='pending',attempts=attempts-1,"
                            "last_error=%s,locked_at=NULL,"
                            "available_at=now()+make_interval(secs => %s) "
                            "WHERE message_id=%s", (str(exc)[:500], wait, message_id))
                return True
            except (TimeoutError, ConnectionError) as exc:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("UPDATE outbox SET status='unknown',last_error=%s,locked_at=NULL WHERE message_id=%s", (str(exc), message_id))
                return True
            except Exception as exc:
                status = "dead_letter" if attempts + 1 >= self.max_attempts else "pending"
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                        "UPDATE outbox SET status=%s,last_error=%s,locked_at=NULL,"
                        "available_at=now()+make_interval(secs => %s) WHERE message_id=%s",
                        (status, str(exc), self._retry_seconds(), message_id))
                return True
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("UPDATE outbox SET status='delivered',locked_at=NULL,last_error=NULL WHERE message_id=%s", (message_id,))
        return True
