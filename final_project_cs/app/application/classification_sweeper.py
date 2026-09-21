"""오래 ``classifying`` 상태에 머문 Case의 분류를 다시 시도한다."""
from __future__ import annotations

import logging
from typing import Any

from psycopg import Connection

from app.application.classification import Classifier, classify_case
from app.core.contracts import InvalidTransition, StateConflict
from app.core.settings import get_guardrails
from app.domain.events import EventType

logger = logging.getLogger(__name__)


def sweep_stuck_classifying(
    conn: Connection,
    *,
    tenant_id: str,
    classifier: Classifier | None,
    actor_id: str,
    stuck_after_seconds: int | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """오래 멈춘 Case를 오래된 순서로 골라 각각 독립적으로 분류한다.

    후보를 읽는 트랜잭션은 분류 전에 끝낸다. 외부 분류기를 기다리는 동안 조회
    트랜잭션을 붙들지 않으며, 조회 뒤의 경합은 실제 ``version``을 넘긴 낙관적
    동시성 검사로 판별한다.
    """
    guardrails = None
    if stuck_after_seconds is None or limit is None:
        guardrails = get_guardrails()
    if stuck_after_seconds is None:
        stuck_after_seconds = int(
            guardrails.get("reliability.classification_stuck_after_seconds")
        )
    if limit is None:
        limit = int(guardrails.get("reliability.classification_sweep_limit"))

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """SELECT case_id, subject, version
                   FROM customer_cases
                   WHERE tenant_id=%s AND status='classifying'
                     AND updated_at < now() - make_interval(secs => %s)
                   ORDER BY updated_at ASC
                   LIMIT %s""",
                (tenant_id, stuck_after_seconds, limit),
            )
            rows = cur.fetchall()

    counts = {"scanned": len(rows), "classified": 0, "failed": 0,
              "conflicted": 0, "errored": 0}
    for case_id, subject, version in rows:
        try:
            event = classify_case(
                conn,
                tenant_id=tenant_id,
                case_id=case_id,
                text=subject,
                classifier=classifier,
                actor_id=actor_id,
                expected_version=version,
            )
        except (StateConflict, InvalidTransition):
            # 그 사이 다른 경로가 이 Case 를 옮겼다. 정상적인 경합이다.
            counts["conflicted"] += 1
        except Exception:
            # ★`failed` 와 합치지 않는다(2026-09-03 검수에서 나눴다).
            #   `failed` 는 CLASSIFICATION_FAILED 를 **적는 데 성공한** 것이라
            #   Case 가 `escalated` 로 나아간다. 여기는 아무것도 못 적은 것이라
            #   **Case 가 여전히 `classifying` 에 남아 다음 회차에 또 걸린다.**
            #   운영자가 할 일이 다르므로 세는 칸도 달라야 한다. 두 수를 합치면
            #   "실패는 났지만 처리는 됐다" 와 "아무 일도 못 했다" 를 구분 못 한다.
            counts["errored"] += 1
            logger.exception("분류 되잡기가 기록에 실패했다: tenant=%s case=%s",
                             tenant_id, case_id)
        else:
            if event is EventType.CLASSIFIED:
                counts["classified"] += 1
            else:
                counts["failed"] += 1

    return counts


__all__ = ["sweep_stuck_classifying"]
