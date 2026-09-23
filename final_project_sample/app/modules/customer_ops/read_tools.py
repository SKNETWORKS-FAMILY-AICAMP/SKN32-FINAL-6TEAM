"""Customer-operations read tool implementations and their tool map."""
from __future__ import annotations

from typing import Any, Callable

from acop_basement.infrastructure.rag.retriever import search_policy
from acop_basement.tools.read_tools import ToolContext


def _one(connection_factory: Callable[[], Any], sql: str, params: tuple[Any, ...],
         columns: tuple[str, ...]) -> dict[str, Any] | None:
    with connection_factory() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return None if row is None else dict(zip(columns, row))


def _subscription(connection_factory: Callable[[], Any], scope: ToolContext, **_: Any):
    return _one(connection_factory, "SELECT subscription_id, plan, status, started_at, ended_at FROM subscriptions WHERE tenant_id=%s AND customer_id=%s ORDER BY started_at DESC LIMIT 1", (scope.tenant_id, scope.customer_id), ("subscription_id", "plan", "status", "started_at", "ended_at"))


def _payment_history(connection_factory: Callable[[], Any], scope: ToolContext, **_: Any):
    with connection_factory() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_id, subscription_id, amount_cents, status, paid_at FROM payments WHERE tenant_id=%s AND customer_id=%s ORDER BY paid_at DESC", (scope.tenant_id, scope.customer_id))
            rows = cur.fetchall()
    return [dict(zip(("payment_id", "subscription_id", "amount_cents", "status", "paid_at"), row)) for row in rows]


def _policy(policy_search: Callable[..., list[Any]], scope: ToolContext, *, query: str, **_: Any):
    return policy_search(scope.tenant_id, query, scope.knowledge_scope)


def _entitlement(connection_factory: Callable[[], Any], scope: ToolContext, **_: Any):
    return _one(connection_factory, "SELECT entitlement_id, plan, source, updated_at FROM entitlements WHERE tenant_id=%s AND customer_id=%s ORDER BY updated_at DESC LIMIT 1", (scope.tenant_id, scope.customer_id), ("entitlement_id", "plan", "source", "updated_at"))


def _account(connection_factory: Callable[[], Any], scope: ToolContext, **_: Any):
    return _one(connection_factory, "SELECT customer_id, external_id, email_hash, created_at FROM customers WHERE tenant_id=%s AND customer_id=%s", (scope.tenant_id, scope.customer_id), ("customer_id", "external_id", "email_hash", "created_at"))


def _incident(connection_factory: Callable[[], Any], scope: ToolContext, **_: Any):
    with connection_factory() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT incident_id, case_id, summary, status, created_at FROM incidents WHERE tenant_id=%s AND customer_id=%s ORDER BY created_at DESC", (scope.tenant_id, scope.customer_id))
            rows = cur.fetchall()
    return [dict(zip(("incident_id", "case_id", "summary", "status", "created_at"), row)) for row in rows]


def build_read_tool_functions(connection_factory: Callable[[], Any],
                              policy_search_fn: Callable[..., list[Any]] = search_policy) -> dict[str, Callable[..., Any]]:
    return {
        "read.subscription": lambda scope, **kw: _subscription(connection_factory, scope, **kw),
        "read.payment_history": lambda scope, **kw: _payment_history(connection_factory, scope, **kw),
        "read.policy": lambda scope, **kw: _policy(policy_search_fn, scope, **kw),
        "read.entitlement": lambda scope, **kw: _entitlement(connection_factory, scope, **kw),
        "read.account": lambda scope, **kw: _account(connection_factory, scope, **kw),
        "read.incident": lambda scope, **kw: _incident(connection_factory, scope, **kw),
    }


__all__ = ["build_read_tool_functions"]
