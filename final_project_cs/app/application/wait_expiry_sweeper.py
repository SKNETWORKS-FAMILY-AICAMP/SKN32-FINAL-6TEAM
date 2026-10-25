"""고객 입력 대기가 만료됐는데 고객이 돌아오지 않은 Case 를 `escalated` 로 옮긴다 — ★코어 1 소유.

`classification_sweeper` · `routing_sweeper` 와 **같은 성격**의 되잡기 장치다.

    분류를 생성 트랜잭션 밖으로  →  `classifying` 잔류  →  classification_sweeper
    실행을 접수 응답 뒤로        →  `routing` 잔류      →  routing_sweeper
    고객 입력 대기의 재개 토큰 만료 →  `waiting_input` 잔류 →  **이 파일**

★어떤 틈인가: 대기 만료(`wait_expired`)는 지금까지 **재개를 시도할 때만** 기록됐다(Controller 가
  `ResumeTokenExpired` 를 받으면 `WAIT_EXPIRED` 전이). 고객이 끝내 돌아오지 않으면 Case 는
  `waiting_input` 에 영원히 남았다. 계약 `INV-CS-RT-018` — 대기 만료는 자동 resolve 하지 않고 escalate 한다.

★하는 일은 그 전이 하나뿐이다. 고객 알림(outbox)은 내지 않는다 — 운영자 몫으로 넘기는 것이다.
  처리 범위는 `waiting_input` + `wait_reason=customer_input` 뿐이다. 승인·외부 대기는 재개 토큰 만료가 없어
  기준이 정의되지 않았다(2026-10-26 Codex 검토 Q4).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from psycopg import Connection

from app.core.case_lifecycle.events import EventType
from app.core.contracts import InvalidTransition, StateConflict
from app.core.settings import get_guardrails
from app.core.transition import transition_case

logger = logging.getLogger(__name__)

WAIT_REASON = "customer_input"


def _expires(value: object) -> datetime | None:
    """저장된 만료 시각을 읽는다. 못 읽으면 None — 전이하지 않고 따로 센다."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def sweep_expired_waits(
    conn: Connection,
    *,
    tenant_id: str,
    actor_id: str,
    limit: int | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """재개 토큰이 만료된 `waiting_input` Case 를 오래된 순서로 골라 `WAIT_EXPIRED` 로 escalate 한다.

    돌려주는 것:

        scanned         후보로 읽은 수(이 테넌트의 고객 입력 대기, 오래된 순, `limit` 까지)
        expired         `escalated` 로 옮긴 수
        waiting         아직 만료 전이라 그대로 둔 수
        invalid_expiry  만료 시각이 없거나 못 읽어 **옮기지 않은** 수 — 사람이 본다
        conflicted      그 사이 다른 경로(고객 재개 등)가 먼저 옮긴 수. 정상 경합
        errored         아무것도 기록하지 못한 수 — 다음 회차에 또 걸린다

    ★후보 조회 트랜잭션은 전이 **전에** 닫고, 전이는 Case 마다 자기 트랜잭션에서 읽은 `version` 으로(CAS) 한다.
      고객 재개와 겹치면 둘 중 하나만 통과한다.
    """
    if limit is None:
        limit = int(get_guardrails().get("reliability.wait_expiry_sweep_limit"))
    moment = now or datetime.now(UTC)

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """SELECT case_id, version, state_json->>'resume_token_expires_at'
                   FROM customer_cases
                   WHERE tenant_id=%s AND status='waiting_input'
                     AND state_json->>'wait_reason'=%s
                   ORDER BY updated_at ASC
                   LIMIT %s""",
                (tenant_id, WAIT_REASON, limit),
            )
            rows = cur.fetchall()

    counts = {"scanned": len(rows), "expired": 0, "waiting": 0, "invalid_expiry": 0,
              "conflicted": 0, "errored": 0}
    for case_id, version, raw_expires in rows:
        expires = _expires(raw_expires)
        if expires is None:
            counts["invalid_expiry"] += 1
            logger.warning("대기 만료 시각을 읽지 못해 두었다: tenant=%s case=%s", tenant_id, case_id)
            continue
        if moment < expires:
            counts["waiting"] += 1
            continue
        try:
            with conn.transaction():
                transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=version,
                                event_type=EventType.WAIT_EXPIRED, payload={"wait_reason": WAIT_REASON},
                                actor_type="system", actor_id=actor_id)
        except (StateConflict, InvalidTransition):
            counts["conflicted"] += 1
        except Exception:
            counts["errored"] += 1
            logger.exception("대기 만료 되잡기가 기록에 실패했다: tenant=%s case=%s", tenant_id, case_id)
        else:
            counts["expired"] += 1

    return counts


__all__ = ["sweep_expired_waits"]
