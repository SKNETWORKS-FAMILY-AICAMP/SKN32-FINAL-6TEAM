"""접수 뒤 실행이 시작되지 못한 Case 를 되잡는다 — ★코어 1 소유.

`classification_sweeper` 와 **같은 성격**의 장치다. 요청·트랜잭션 경계를 나눌
때마다 "그 사이에 죽으면?" 이 생기고, 그때마다 되잡는 손이 필요하다.

    분류를 생성 트랜잭션 밖으로  →  `classifying` 잔류  →  classification_sweeper
    실행을 접수 응답 뒤로        →  `routing` 잔류      →  **이 파일**

★어떤 틈인가: `POST /v1/cases` 는 분류까지 마치고 201 을 돌려준 뒤,
  `run_case()` 를 응답 **뒤에서** 돌린다(2026-09-03, v8 §3-A [교정]).
  그 사이에 프로세스가 죽거나 background task 가 시작조차 못 하면 Case 는
  `routing` 에 남고 **아무도 다시 집지 않는다.**

★`agent_runs` 가 있는 Case 는 건드리지 않는다. 실행이 시작은 됐다는 뜻이고,
  그 뒤의 일은 Controller 와 재개 경로의 몫이다. 여기는 **시작조차 못 한 것**만
  본다 — 남의 일에 손대면 같은 Case 를 둘이 돌리게 된다.
"""
from __future__ import annotations

import logging
from typing import Any

from psycopg import Connection

from app.core.settings import get_guardrails

logger = logging.getLogger(__name__)


def sweep_stuck_routing(
    conn: Connection,
    *,
    tenant_id: str,
    run_case: Any,
    actor_id: str,
    stuck_after_seconds: int | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """`routing` 에 멈춘 Case 를 오래된 순서로 골라 실행을 다시 건다.

    `run_case` 는 Controller 의 `run_case` 를 그대로 받는다(주입). 이 파일이
    Controller 를 import 하지 않는 이유는 두 가지다 — 조립은 composition 의
    일이고, 테스트가 DB·LLM 없이 절차만 볼 수 있어야 한다.

    돌려주는 것:

        scanned    후보로 고른 수
        started    실행을 다시 걸어 끝까지 간 수
        errored    다시 걸었지만 터진 수. ★Case 는 여전히 `routing` 이라
                   다음 회차에 또 걸린다 — `started` 와 합치지 않는다

    ★후보 조회 트랜잭션은 실행 **전에** 닫는다. 외부 네트워크를 기다리는 동안
      조회 트랜잭션을 붙들지 않는다(`classification_sweeper` 와 같은 이유).
    """
    guardrails = None
    if stuck_after_seconds is None or limit is None:
        guardrails = get_guardrails()
    if stuck_after_seconds is None:
        stuck_after_seconds = int(guardrails.get("reliability.routing_stuck_after_seconds"))
    if limit is None:
        limit = int(guardrails.get("reliability.routing_sweep_limit"))

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.case_id
                   FROM customer_cases c
                   WHERE c.tenant_id=%s AND c.status='routing'
                     AND c.updated_at < now() - make_interval(secs => %s)
                     AND NOT EXISTS (SELECT 1 FROM agent_runs r
                                     WHERE r.tenant_id=c.tenant_id AND r.case_id=c.case_id)
                   ORDER BY c.updated_at ASC
                   LIMIT %s""",
                (tenant_id, stuck_after_seconds, limit),
            )
            rows = cur.fetchall()

    counts = {"scanned": len(rows), "started": 0, "errored": 0}
    for (case_id,) in rows:
        try:
            run_case(tenant_id=tenant_id, case_id=case_id, actor_id=actor_id)
        except Exception:
            # ★삼키지 않는다. 다시 걸었는데 또 터진 것이라 사람이 봐야 한다.
            counts["errored"] += 1
            logger.exception("실행 되잡기가 실패했다: tenant=%s case=%s", tenant_id, case_id)
        else:
            counts["started"] += 1

    return counts


__all__ = ["sweep_stuck_routing"]
