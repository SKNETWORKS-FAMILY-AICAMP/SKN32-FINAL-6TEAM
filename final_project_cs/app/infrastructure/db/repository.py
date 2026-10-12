"""Minimal tenant-scoped persistence operations."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Json
from app.core.redaction import mask_json, masked


def create_case(conn: Connection, *, tenant_id: str, customer_id: UUID, subject: str, state_json: dict[str, Any] | None = None) -> UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO customer_cases (tenant_id, customer_id, status, subject, state_json) VALUES (%s, %s, 'new', %s, %s) RETURNING case_id", (tenant_id, customer_id, masked(subject), Json(mask_json(state_json or {}))))
        return cur.fetchone()[0]


def get_case(conn: Connection, *, tenant_id: str, case_id: UUID) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute("SELECT case_id, tenant_id, customer_id, status, subject, state_json, intent, issue_code, sentiment, owner_team_id, version, created_at, updated_at FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant_id, case_id))
        row = cur.fetchone()
        if row is None: return None
        return dict(zip(("case_id","tenant_id","customer_id","status","subject","state_json","intent","issue_code","sentiment","owner_team_id","version","created_at","updated_at"), row))


def list_cases(conn: Connection, *, tenant_id: str, customer_id: UUID | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT case_id, customer_id, status, subject, version, created_at, updated_at FROM customer_cases WHERE tenant_id=%s"
    params: list[Any] = [tenant_id]
    if customer_id is not None: query += " AND customer_id=%s"; params.append(customer_id)
    query += " ORDER BY created_at DESC, case_id DESC LIMIT %s"; params.append(limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        return [dict(zip(("case_id","customer_id","status","subject","version","created_at","updated_at"), r)) for r in cur.fetchall()]


def get_case_events(conn: Connection, *, tenant_id: str, case_id: UUID) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT event_id, aggregate_version, event_type, payload_json, actor_type, actor_id, created_at FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version", (tenant_id, case_id))
        return [dict(zip(("event_id","aggregate_version","event_type","payload_json","actor_type","actor_id","created_at"), r)) for r in cur.fetchall()]


def _json_text(value: Any) -> str:
    """★UUID·시각을 문자열로 — 제안 인자는 DB 에서 읽은 값(UUID 객체)을 그대로 싣는다.
    그대로 쓰면 `TypeError: Object of type UUID is not JSON serializable` 로 Case 실행이 통째로
    실패했다(2026-09-17, wiki/records/reports/debugs/2026-09-17_1450_여행_승인제안이_근거대조에서_전부_막힌다.md)."""
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


def create_action_request(conn: Connection, *, tenant_id: str, case_id: UUID, action_type: str, arguments: dict[str, Any], idempotency_key: str, status: str = "proposed", provider_ref: str | None = None) -> UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO action_requests (tenant_id, case_id, action_type, arguments_json, idempotency_key, status, provider_ref) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id, idempotency_key) DO UPDATE SET idempotency_key=EXCLUDED.idempotency_key RETURNING action_id", (tenant_id, case_id, action_type, Json(arguments, dumps=_json_text), idempotency_key, status, provider_ref))
        return cur.fetchone()[0]


def find_action_request(conn: Connection, *, tenant_id: str, idempotency_key: str) -> dict[str, Any] | None:
    """멱등 키로 이미 기록된 작업을 찾는다. 없으면 None."""
    with conn.cursor() as cur:
        cur.execute("SELECT action_id, case_id, action_type, status, provider_ref, arguments_json "
                    "FROM action_requests WHERE tenant_id=%s AND idempotency_key=%s",
                    (tenant_id, idempotency_key))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("action_id", "case_id", "action_type", "status", "provider_ref", "arguments"), row))


def approved_pending_actions(conn: Connection, *, tenant_id: str, case_id: UUID) -> list[dict[str, Any]]:
    """승인됐지만 아직 실행하지 않은 제안(`[2026-09-18]`). 승인 뒤 재개가 읽는다."""
    with conn.cursor() as cur:
        cur.execute("SELECT ar.action_id, ar.action_type, ar.arguments_json FROM action_requests ar "
                    "WHERE ar.tenant_id=%s AND ar.case_id=%s AND ar.status='pending_approval' "
                    "AND EXISTS (SELECT 1 FROM action_approvals ap WHERE ap.action_id=ar.action_id "
                    "AND ap.decision='approved') ORDER BY ar.created_at, ar.action_id", (tenant_id, case_id))
        return [dict(zip(("action_id", "action_type", "arguments"), row)) for row in cur.fetchall()]


def set_action_status(conn: Connection, *, tenant_id: str, action_id: UUID, status: str,
                      provider_ref: str | None = None, ledger: dict[str, Any] | None = None) -> None:
    """작업의 상태(+결과 참조)를 적는다.

    ★`[2026-09-22]` `ledger` 는 실행 장부 칸(v11 §12 DoD-20, 마이그레이션 019) —
      `amount_cents`·`amount_source`·`reason`·`revert_deadline`·`delegation`. 적용기가 채운
      값이며 코어는 뜻을 모른다. ★**None 으로 기존 값을 지우지 않는다**(`COALESCE`) — 실패
      경로에서 상태만 바꿀 때 앞서 적은 근거가 사라지면 「왜 실행했나」가 없어진다.
    """
    fields = ledger or {}
    with conn.cursor() as cur:
        cur.execute("UPDATE action_requests SET status=%s, provider_ref=COALESCE(%s, provider_ref), "
                    "amount_cents=COALESCE(%s, amount_cents), "
                    "amount_source=COALESCE(%s, amount_source), "
                    "reason=COALESCE(%s, reason), "
                    "revert_deadline=COALESCE(%s, revert_deadline), "
                    # ★`::jsonb` 를 빼면 COALESCE 가 `json` 과 `jsonb` 를 못 맞춘다
                    #   (`CannotCoerce`) — INSERT 는 대상 칼럼이 타입을 정해 주지만 COALESCE 는 아니다.
                    "delegation_json=COALESCE(%s::jsonb, delegation_json), "
                    "prior_state_json=COALESCE(%s::jsonb, prior_state_json) "
                    "WHERE tenant_id=%s AND action_id=%s",
                    (status, provider_ref, fields.get("amount_cents"), fields.get("amount_source"),
                     fields.get("reason"), fields.get("revert_deadline"),
                     Json(fields["delegation"], dumps=_json_text) if fields.get("delegation") else None,
                     Json(fields["prior_state"], dumps=_json_text) if fields.get("prior_state") else None,
                     tenant_id, action_id))


def action_execution_record(conn: Connection, *, tenant_id: str, action_id: UUID) -> dict[str, Any] | None:
    """실행 장부 한 줄 — 무엇을 · 왜 · 얼마에 · 되돌림 기한 (v11 §12 DoD-20).

    ★`amount_cents` 가 None 이면 **「확인되지 않았다」**다. 0 으로 읽지 않는다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT action_type, arguments_json, status, provider_ref, amount_cents, "
                    "amount_source, reason, revert_deadline, delegation_json, prior_state_json, "
                    "created_at FROM action_requests WHERE tenant_id=%s AND action_id=%s",
                    (tenant_id, action_id))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("action_type", "arguments", "status", "provider_ref", "amount_cents",
                     "amount_source", "reason", "revert_deadline", "delegation", "prior_state",
                     "created_at"), row))


def create_approval(conn: Connection, *, action_id: UUID, decision: str, approver_id: str | None = None) -> UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO action_approvals (action_id, approver_id, decision, decided_at) VALUES (%s,%s,%s,now()) RETURNING approval_id", (action_id, approver_id, decision)); return cur.fetchone()[0]


def create_prompt(conn: Connection, *, prompt_key: str, version: str, template: str, sha256: str, model_family: str, active: bool = False) -> UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO prompts (prompt_key, version, template, sha256, model_family, active) VALUES (%s,%s,%s,%s,%s,%s) RETURNING prompt_id", (prompt_key, version, template, sha256, model_family, active)); return cur.fetchone()[0]


#: 섀도 로그의 사건 이름 → 표의 `event` 값(`031_activity_judge_shadow.sql`).
_SHADOW_EVENTS = {"activity_judge_shadow": "shadow", "activity_judge_shadow_skipped": "skipped",
                  "activity_judge_shadow_error": "error"}
#: 표에 싣는 칸 — 이 밖의 키는 버린다(장소명·원문이 실수로 섞여 와도 저장되지 않게).
_SHADOW_COLUMNS = ("origin", "tenant_id", "case_id", "run_id", "capability", "kind", "rule_value", "rule_basis",
                   "llm_value", "agree", "comparable", "llm_failure_code", "llm_error", "llm_confidence",
                   "quotes", "citations", "dropped", "undated_citations", "latency_ms", "search_calls",
                   "input_tokens", "output_tokens", "reasoning_tokens", "model", "eval_run", "eval_case",
                   "eval_repeat")


def create_activity_judge_shadow(conn: Connection, record: dict[str, Any]) -> UUID:
    """섀도 로그 한 줄(`judge/modes.py` 의 기록)을 한 행으로. 로그 키 `rule`·`llm` 은 `rule_value`·`llm_value` 로 옮긴다."""
    row = {**record, "rule_value": record.get("rule"), "llm_value": record.get("llm"),
           "origin": record.get("origin") or "live"}
    event = _SHADOW_EVENTS[record["event"]]
    columns = ["event", *_SHADOW_COLUMNS]
    values = [event, *(row.get(name) for name in _SHADOW_COLUMNS)]
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO activity_judge_shadow ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) "
                    "RETURNING shadow_id", values)
        return cur.fetchone()[0]


def create_llm_call(conn: Connection, *, run_id: UUID | None, prompt_id: UUID, provider: str, model: str, response_json: dict[str, Any] | None = None, input_tokens: int | None = None, output_tokens: int | None = None, latency_ms: int | None = None, cost_microusd: int | None = None) -> UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO llm_calls (run_id,prompt_id,provider,model,response_json,input_tokens,output_tokens,latency_ms,cost_microusd) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING call_id", (run_id,prompt_id,provider,model,Json(response_json) if response_json is not None else None,input_tokens,output_tokens,latency_ms,cost_microusd)); return cur.fetchone()[0]
