"""발표 시나리오 Case 2건을 demo tenant 에 남긴다 (삭제하지 않는다).

★왜 필요한가 — DoD-18 이 요구하는 것은 화면이 200 을 내는 것이 아니라
  **"발표 시나리오를 끝까지 보여주는 것"** 이다.
  Controller 통합테스트는 두 시나리오를 코드로 끝까지 통과시키지만
  그 Case 들은 teardown 에서 삭제된다. 화면에는 아무것도 남지 않는다.

★상태는 `transition_case()` 로만 만든다 (CLAUDE.md §0.3).
  `customer_cases` 직접 UPDATE 금지. `case_events` 가 append-only 로 쌓여야
  trace 화면이 전이 단계를 보여줄 수 있다.

★LLM 을 부르지 않는다. 분류·proposal 은 고정값이고,
  **그 값이 seed 에서 왔다는 사실을 데이터에 남긴다** (CLAUDE.md §1 — 지어내지 않는다).
  `state_json.seeded_by = "scripts.seed_demo_cases"` 로 구분된다.

시나리오 1 — 해지 후 결제 → 환불 제안 → `waiting_approval` 에서 **멈춘다.**
             ★승인하지 않는다. 발표에서 사람이 /ui/approvals 에서 누른다.
시나리오 2 — Pro/Free 권한 불일치 → `resolved` 종단 완료.

재실행 안전: 같은 `external_id` 의 seed customer 를 찾아 그 Case 를 지우고 다시 만든다.
             그래서 두 번 돌려도 Case 가 4건이 되지 않는다.

    python -m scripts.seed_demo_cases
"""
from __future__ import annotations

import json
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.types.json import Json

from acop_basement.core.settings import get_settings
from acop_basement.core.transition import transition_case
from acop_basement.domain.events import EventType
from acop_basement.infrastructure.db.session import get_connection

SEEDED_BY = "scripts.seed_demo_cases"
MARKER = {"seeded_by": SEEDED_BY, "note": "발표 시연용. LLM 호출 없이 고정값으로 만든 Case"}

SCENARIO_1 = "demo-scenario-1-cancelled-then-charged"
SCENARIO_2 = "demo-scenario-2-entitlement-mismatch"


def _reset(conn, tenant: str, external_id: str) -> UUID:
    """seed customer 를 찾거나 만들고, 그 customer 의 기존 Case 를 지운다."""
    with conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers WHERE tenant_id=%s AND external_id=%s", (tenant, external_id))
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s,%s) RETURNING customer_id", (tenant, external_id))
            return cur.fetchone()[0]
        customer_id = row[0]
        # ★재실행 안전: 이 seed 가 만든 Case 만 지운다. 다른 Case 는 건드리지 않는다.
        cur.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s AND customer_id=%s", (tenant, customer_id))
        case_ids = [r[0] for r in cur.fetchall()]
        for case_id in case_ids:
            cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s AND case_id=%s)", (tenant, case_id))
            cur.execute("DELETE FROM action_requests WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        return customer_id


def _fixed_case_id(tenant: str, scenario: str) -> UUID:
    """★case_id 를 시나리오 이름에서 결정적으로 만든다.

    돌릴 때마다 id 가 바뀌면 발표 자료의 URL 과 판정 문서의 실측값이 매번 죽는다.
    uuid5 는 같은 입력에 같은 값을 준다.
    """
    return uuid5(NAMESPACE_URL, f"acop://{tenant}/demo/{scenario}")


def _create(conn, tenant: str, customer_id: UUID, case_id: UUID, subject: str) -> UUID:
    """★create_case() 는 case_id 를 받지 않아 여기서 직접 INSERT 한다.

    상태 전이가 아니라 **생성**이므로 CLAUDE.md §0.3(`transition_case()` 단일 진입점)에
    걸리지 않는다. status 는 초기값 'new' 그대로 두고, 이후 전이는 전부 transition_case() 다.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customer_cases (case_id, tenant_id, customer_id, status, subject, state_json) "
            "VALUES (%s,%s,%s,'new',%s,%s) RETURNING case_id",
            (case_id, tenant, customer_id, subject, Json(dict(MARKER))),
        )
        return cur.fetchone()[0]


def _step(conn, tenant: str, case_id: UUID, version: int, event: EventType, payload: dict) -> int:
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=version,
                        event_type=event, payload=payload, actor_type="seed", actor_id=SEEDED_BY)
    return version + 1


def scenario_1(conn, tenant: str) -> tuple[UUID, int]:
    """해지 후 결제 → 환불 제안 → waiting_approval 에서 멈춘다."""
    customer_id = _reset(conn, tenant, SCENARIO_1)
    case_id = _create(conn, tenant, customer_id, _fixed_case_id(tenant, SCENARIO_1),
                      "해지했는데 이번 달 요금이 또 청구됐습니다")
    v = _step(conn, tenant, case_id, 0, EventType.CREATED,
              {"channel": "email", "message": "지난달에 해지했는데 8월분 19,900원이 결제됐습니다. 환불 부탁드립니다."})
    v = _step(conn, tenant, case_id, v, EventType.CLASSIFIED,
              {"intent": "billing_refund", "issue_code": "charged_after_cancellation", "sentiment": "negative"})
    v = _step(conn, tenant, case_id, v, EventType.ROUTED,
              {"owner_team_id": "billing_subscription", "capability": "billing.investigate"})

    # ★APPROVAL_REQUIRED 는 payload 에 action_id 를 요구한다 — 제안이 먼저 있어야 한다.
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO action_requests (tenant_id, case_id, action_type, arguments_json, idempotency_key, status) "
            "VALUES (%s,%s,'refund',%s,%s,'pending_approval') RETURNING action_id",
            # ★evidence 가 비면 승인 화면의 버튼이 disabled 된다 (routes.py — 근거 없는 제안은
            #   승인할 수 없다, CLAUDE.md §0.1). 처음 seed 를 짤 때 이걸 빠뜨려
            #   "승인 버튼이 왜 안 눌리지" 로 한 번 헤맸다. 가드레일이 옳았고 seed 가 틀렸다.
            (tenant, case_id, Json({"amount": 19900, "currency": "KRW", "payment_id": "seed-pay-0001",
                                    "rationale": "해지 완료 시각 이후 결제. 정책 doc_06 §환불 기준",
                                    "evidence": [
                                        {"source_type": "policy_chunk", "source_id": "doc_06#c3",
                                         "claim": "해지 완료 시각 이후 발생한 결제는 전액 환불 대상",
                                         "observed_at": "2026-08-14T00:00:00+09:00"},
                                        {"source_type": "payment", "source_id": "seed-pay-0001",
                                         "claim": "2026-08-05 결제 19,900원 — 해지 시각(2026-07-28) 이후",
                                         "observed_at": "2026-08-14T00:00:00+09:00"},
                                        {"source_type": "subscription", "source_id": "seed-sub-0001",
                                         "claim": "status=cancelled, cancelled_at=2026-07-28",
                                         "observed_at": "2026-08-14T00:00:00+09:00"},
                                    ],
                                    "seeded_by": SEEDED_BY}),
             f"{tenant}:{SCENARIO_1}:refund:seed-pay-0001"),
        )
        action_id = cur.fetchone()[0]

    v = _step(conn, tenant, case_id, v, EventType.APPROVAL_REQUIRED,
              {"action_id": str(action_id), "action_type": "refund",
               "reason": "해지 시각 이후 결제 1건 확인 — 환불 제안. 승인 필요"})
    conn.commit()
    return case_id, v


def scenario_2(conn, tenant: str) -> tuple[UUID, int]:
    """Pro/Free 권한 불일치 → resolved 종단."""
    customer_id = _reset(conn, tenant, SCENARIO_2)
    case_id = _create(conn, tenant, customer_id, _fixed_case_id(tenant, SCENARIO_2),
                      "Pro 결제했는데 기능이 Free로 보입니다")
    v = _step(conn, tenant, case_id, 0, EventType.CREATED,
              {"channel": "web", "message": "Pro 구독 중인데 내보내기 기능이 잠겨 있습니다."})
    v = _step(conn, tenant, case_id, v, EventType.CLASSIFIED,
              {"intent": "technical_entitlement", "issue_code": "entitlement_mismatch", "sentiment": "neutral"})
    v = _step(conn, tenant, case_id, v, EventType.ROUTED,
              {"owner_team_id": "technical_entitlement", "capability": "entitlement.inspect"})
    # ★running → resolved 는 COMPLETED 이벤트다. answer_ref 가 필수다.
    v = _step(conn, tenant, case_id, v, EventType.COMPLETED,
              {"answer_ref": "seed-answer-0002",
               "resolution": "entitlement 재동기화로 Pro 권한 반영 확인",
               "evidence": [{"source_type": "entitlement", "source_id": "seed-ent-0002", "claim": "plan=pro, features=export"}]})
    conn.commit()
    return case_id, v


def main() -> int:
    tenant = get_settings().tenant_id
    with get_connection() as conn:
        case1, v1 = scenario_1(conn, tenant)
        case2, v2 = scenario_2(conn, tenant)
        with conn.cursor() as cur:
            cur.execute("SELECT case_id, status, version FROM customer_cases WHERE tenant_id=%s AND case_id=ANY(%s) ORDER BY subject", (tenant, [case1, case2]))
            rows = cur.fetchall()
            cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (tenant,))
            total = cur.fetchone()[0]
    print(json.dumps({
        "tenant_id": tenant,
        "scenario_1": {"case_id": str(case1), "expected_version": v1},
        "scenario_2": {"case_id": str(case2), "expected_version": v2},
        "observed": [{"case_id": str(r[0]), "status": r[1], "version": r[2]} for r in rows],
        "cases_in_tenant": total,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
