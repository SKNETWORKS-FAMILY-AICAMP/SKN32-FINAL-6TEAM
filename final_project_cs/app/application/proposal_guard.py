"""제안을 실행 경로에 넣기 전에 사실과 대조한다 (v7 §9-E).

★검증은 **두 번** 한다:
  1. approval 전 — 제안이 만들어질 때
  2. 실행 직전 — 승인 후. 그 사이에 상태가 바뀔 수 있다

  한 번만 하면 "승인 시점엔 맞았는데 실행 시점엔 틀린" 경우를 놓친다.
  환불 가능 잔액은 사람이 승인 버튼을 누르는 사이에도 바뀐다.

★사실은 **매번 다시 읽는다.** Team 이 넘긴 값이나 캐시를 믿지 않는다 —
  그걸 믿으면 대조의 의미가 없다.

★이 파일도 basement 다. **어떤 테이블을 읽는지 모른다** —
  질의와 필드 어휘는 도메인 선언(`FACT_QUERIES`·`VerificationPolicy`)이 준다.
  전에는 여기에 도메인 테이블 SQL 이 박혀 있었고,
  그러면 다른 도메인으로 복사할 때 이 파일을 고쳐야 했다.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from app.core.verification import Facts, Mismatch, VerificationPolicy, verify_proposal

#: (컬렉션 이름, SQL, 컬럼 이름들) — 도메인이 선언한다
FactQueries = Sequence[tuple[str, str, tuple[str, ...]]]


def load_facts(conn, *, tenant_id: str, customer_id: UUID, queries: FactQueries,
               evidence_ids: Iterable[str] = ()) -> Facts:
    """선언된 질의로 사실을 재조회한다.

    ★savepoint 안에서 읽는다. 조회가 실패해도 **호출자의 트랜잭션을 죽이지 않는다.**
      savepoint 없이 짰다가 컬럼명을 하나 틀렸고, 그 한 번의 실패가 트랜잭션을
      aborted 로 만들어 뒤따르는 전이까지 전부 무너졌다.
      **대조는 거들 뿐이지 본 흐름을 망가뜨리면 안 된다.**
    """
    collections: dict[str, dict[str, dict[str, Any]]] = {}
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                for name, sql, columns in queries:
                    cur.execute(sql, (tenant_id, customer_id))
                    collections[name] = {
                        str(row[0]): {col: (str(val) if isinstance(val, UUID) else val)
                                      for col, val in zip(columns, row)}
                        for row in cur.fetchall()
                    }
    except Exception:
        # ★조회 실패를 "행이 없다" 로 읽지 않는다. 사실을 모르는 상태로 표시한다.
        #   Facts(loaded=False) 는 verify_proposal 에서 **전건 거부**로 이어진다.
        return Facts(loaded=False)

    return Facts(collections=collections,
                 evidence_ids=frozenset(str(e) for e in evidence_ids), loaded=True)


def check_proposal(conn, *, tenant_id: str, customer_id: UUID, proposal: Any,
                   policy: VerificationPolicy, queries: FactQueries,
                   evidence_ids: Iterable[str] = ()) -> list[Mismatch]:
    """제안 하나를 대조한다. 빈 목록이면 통과."""
    facts = load_facts(conn, tenant_id=tenant_id, customer_id=customer_id,
                       queries=queries, evidence_ids=evidence_ids)
    return verify_proposal(
        arguments=dict(getattr(proposal, "arguments", {}) or {}),
        rationale_evidence_ids=list(getattr(proposal, "rationale_evidence_ids", []) or []),
        facts=facts, policy=policy)


def recheck_before_execution(conn, *, tenant_id: str, case: Mapping[str, Any], action_id: UUID,
                             policy: VerificationPolicy, queries: FactQueries) -> list[Mismatch]:
    """승인 직후, 실행 직전에 **저장된 제안**을 다시 대조한다 (두 번째 검증).

    ★근거(evidence)는 여기서 다시 세지 않는다. ContextPack 은 제안 시점의 것이고
      지금 다시 만들 수 없다. 여기서 재는 것은 **실재·소유권·수량**이다.
    """
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT arguments_json FROM action_requests "
                            "WHERE tenant_id=%s AND action_id=%s", (tenant_id, action_id))
                row = cur.fetchone()
    except Exception:
        return [Mismatch("__facts__", "제안을 다시 읽지 못했다", "", "")]

    if row is None:
        return [Mismatch("action_id", "제안 행이 없다", "", "")]

    facts = load_facts(conn, tenant_id=tenant_id, customer_id=case["customer_id"], queries=queries)
    return verify_proposal(arguments=dict(row[0] or {}), rationale_evidence_ids=[],
                           facts=facts, policy=policy)


def audit_payload(*, action_type: str, mismatches: list[Mismatch],
                  case_id: Any, run_id: Any = None, task_id: Any = None) -> dict[str, Any]:
    """거부 사유를 감사 로그에 남길 형태로 만든다.

    ★기대값·실제값은 **hash 로만** 남는다 — 금액·식별자 원문을 기록하지 않는다.
    """
    return {
        "action_type": action_type,
        "case_id": str(case_id),
        "run_id": str(run_id) if run_id else None,
        "task_id": str(task_id) if task_id else None,
        "failed_fields": [m.field for m in mismatches],
        "mismatches": [m.as_audit() for m in mismatches],
    }


def describe(mismatches: list[Mismatch]) -> str:
    """사람이 읽을 한 줄 요약. ★원문 값은 넣지 않는다."""
    return "; ".join(f"{m.field}: {m.reason}" for m in mismatches)
