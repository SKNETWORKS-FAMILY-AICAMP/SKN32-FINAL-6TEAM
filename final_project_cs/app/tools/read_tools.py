"""Tenant-scoped, named read tools for Team modules.

The tool layer deliberately exposes no SQL interface.  A Team supplies only
the tool name and business arguments; tenant/customer scope is taken from the
validated ContextPack.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from app.core.contracts import ContextPack, ToolNotAllowed
from app.infrastructure.rag.retriever import search_policy


class ToolBudgetExceeded(RuntimeError):
    """도구 호출이 `manifest.max_steps` 예산을 넘었다.

    ★`ToolLoopExceeded` 와 **다른 예외다.** 원인이 다르기 때문이다 —
      전자는 "같은 것을 또 불렀다"(중복), 이쪽은 "너무 많이 불렀다"(예산).
      한 예외로 묶으면 로그에서 둘을 못 가른다.

    ★2026-09-09 신설. 그전까지 `max_steps` 는 **선언만 되고 아무도 강제하지
      않았다** — 정의·화면표시·introspection 에만 있고 실행 경로 3곳
      (executor·controller·read_tools)에 0회였다. 테스트까지 있었지만
      `manifest.max_steps == 6` 이라는 **선언값**만 봤다.
      경위: wiki/records/reports/debugs/2026-09-09_max_steps가_강제되지_않는다.md
    """


class ToolLoopExceeded(RuntimeError):
    """The same named tool and normalized arguments were requested twice."""


@dataclass
class ToolContext:
    tenant_id: str
    customer_id: UUID
    case_id: UUID
    knowledge_scope: list[str]

    @classmethod
    def from_pack(cls, pack: ContextPack) -> "ToolContext":
        customer = pack.current_state.get("customer_id")
        if customer is None:
            raise ValueError("ContextPack.current_state.customer_id is required for read tools")
        return cls(pack.tenant_id, UUID(str(customer)), pack.case_id, pack.knowledge_scope)


@dataclass
class ReadToolbox:
    """Named database operations with injectable connection and policy search."""

    connection_factory: Callable[[], Any]
    policy_search: Callable[..., list[Any]] = search_policy

    def _one(self, sql: str, params: tuple[Any, ...], columns: tuple[str, ...]) -> dict[str, Any] | None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return None if row is None else dict(zip(columns, row))

    # ★쇼핑몰 CS 도메인 (sample 의 구독·결제에서 교체됨).
    #   `wiki/records/handoff/10_도메인_교체_가이드.md` §1 이 이 파일을 교체 지점으로 놓지 않았다 —
    #   basement 순수성 게이트(`tests/architecture/`)의 대상이 `app/tools/` 를 빼먹었기 때문이다.
    #   실제로 이 파일은 `app/modules/` 와 마찬가지로 **도메인을 안다.**
    #   그 사실을 여기 기록해 둔다. 게이트 확장은 별도 작업이다.
    def order(self, scope: ToolContext, **_: Any) -> dict[str, Any] | None:
        return self._one(
            "SELECT order_id, order_no, total_cents, item_count, status, ordered_at FROM orders "
            "WHERE tenant_id=%s AND customer_id=%s ORDER BY ordered_at DESC LIMIT 1",
            (scope.tenant_id, scope.customer_id),
            ("order_id", "order_no", "total_cents", "item_count", "status", "ordered_at"),
        )

    def shipment(self, scope: ToolContext, **_: Any) -> list[dict[str, Any]]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT shipment_id, order_id, carrier, status, shipped_at, delivered_at FROM shipments "
                    "WHERE tenant_id=%s AND customer_id=%s ORDER BY shipped_at DESC",
                    (scope.tenant_id, scope.customer_id),
                )
                rows = cur.fetchall()
        return [dict(zip(("shipment_id", "order_id", "carrier", "status", "shipped_at", "delivered_at"), row))
                for row in rows]

    def catalog(self, scope: ToolContext, *, sku: str | None = None, **_: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
        # ★`return_restriction` 은 마이그레이션 008 에서 생겼다. NULL 은 "모름" 이다
        #   — 이 값을 받는 쪽이 NULL 을 "제한 없음" 으로 읽으면 안 된다.
        columns = ("product_id", "sku", "name", "unit_cents", "status", "updated_at",
                   "return_restriction")
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                if sku is not None:
                    cur.execute(
                        "SELECT product_id, sku, name, unit_cents, status, updated_at, return_restriction "
                        "FROM products WHERE tenant_id=%s AND sku=%s",
                        (scope.tenant_id, sku),
                    )
                    row = cur.fetchone()
                    return None if row is None else dict(zip(columns, row))
                cur.execute(
                    "SELECT product_id, sku, name, unit_cents, status, updated_at, return_restriction "
                    "FROM products WHERE tenant_id=%s ORDER BY sku",
                    (scope.tenant_id,),
                )
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    def order_items(self, scope: ToolContext, *, order_id: str | None = None, **_: Any) -> list[dict[str, Any]]:
        """Return line items for an owned order, or the customer's latest order."""
        columns = ("order_item_id", "order_id", "sku", "name", "quantity", "unit_cents")
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                if order_id is not None:
                    cur.execute(
                        "SELECT oi.order_item_id, oi.order_id, oi.sku, oi.name, oi.quantity, oi.unit_cents "
                        "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
                        "WHERE oi.tenant_id=%s AND o.tenant_id=%s AND o.customer_id=%s AND oi.order_id=%s "
                        "ORDER BY oi.order_item_id",
                        (scope.tenant_id, scope.tenant_id, scope.customer_id, order_id),
                    )
                else:
                    cur.execute(
                        "SELECT oi.order_item_id, oi.order_id, oi.sku, oi.name, oi.quantity, oi.unit_cents "
                        "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
                        "WHERE oi.tenant_id=%s AND o.tenant_id=%s AND o.customer_id=%s "
                        "AND o.order_id = (SELECT latest.order_id FROM orders latest "
                        "WHERE latest.tenant_id=%s AND latest.customer_id=%s "
                        "ORDER BY latest.ordered_at DESC LIMIT 1) "
                        "ORDER BY oi.order_item_id",
                        (scope.tenant_id, scope.tenant_id, scope.customer_id,
                         scope.tenant_id, scope.customer_id),
                    )
                rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def policy(self, scope: ToolContext, *, query: str, **_: Any) -> list[Any]:
        return self.policy_search(scope.tenant_id, query, scope.knowledge_scope)

    def return_request(self, scope: ToolContext, **_: Any) -> list[dict[str, Any]]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT return_id, order_id, order_item_id, reason_code, quantity, status, "
                    "requested_at FROM returns "
                    "WHERE tenant_id=%s AND customer_id=%s ORDER BY requested_at DESC",
                    (scope.tenant_id, scope.customer_id),
                )
                rows = cur.fetchall()
        # ★`order_item_id` 는 NULL 일 수 있다 — 2026-09-01 이전에 쌓인 반품에는
        #   품목 정보가 없다. NULL 은 "모른다" 이고, 그때는 다품목 주문에서
        #   환불 금액을 만들지 않는다(지어내지 않는다).
        return [dict(zip(("return_id", "order_id", "order_item_id", "reason_code", "quantity",
                          "status", "requested_at"), row))
                for row in rows]

    def account(self, scope: ToolContext, **_: Any) -> dict[str, Any] | None:
        # ★`customers` 는 core 테이블이다(001_schema.sql). 도메인 유출이 아니다.
        return self._one(
            "SELECT customer_id, external_id, email_hash, created_at FROM customers WHERE tenant_id=%s AND customer_id=%s",
            (scope.tenant_id, scope.customer_id),
            ("customer_id", "external_id", "email_hash", "created_at"),
        )

    def call(self, name: str, context: ContextPack, arguments: dict[str, Any],
             allowed_tools: list[str], seen: set[str], budget: int | None = None) -> Any:
        """`budget` 은 이 Team 이 쓸 수 있는 도구 호출 수 상한이다.

        ★기본값이 `None` 이라 **안 넘기면 예전과 똑같이 동작한다.** 호출부를
          한꺼번에 고치지 않아도 되게 한 것이고, 넘기는 쪽은
          `self.manifest.max_steps` 를 준다.
        ★`seen` 의 크기를 그대로 센다 — 새 카운터를 만들지 않았다.
          `seen` 은 중복 차단기지만 그 크기가 곧 호출 횟수라 예산으로 맞는다.
        """
        # ★예산 검사를 allowlist 보다 **먼저** 두지 않는다. 권한 없는 도구는
        #   예산과 무관하게 거부돼야 하고, 그 편이 오류 메시지도 정확하다.
        if name not in allowed_tools:
            raise ToolNotAllowed(f"tool '{name}' is not allowed for this task")
        functions = {
            "read.order": self.order,
            "read.shipment": self.shipment,
            "read.catalog": self.catalog,
            "read.order_items": self.order_items,
            "read.policy": self.policy,
            "read.return": self.return_request,
            "read.account": self.account,
        }
        if name not in functions:
            raise ToolNotAllowed(f"unknown tool '{name}'")
        signature = name + ":" + json.dumps(arguments, sort_keys=True, default=str, separators=(",", ":"))
        if signature in seen:
            raise ToolLoopExceeded(f"repeated tool request: {name}")
        if budget is not None and len(seen) >= budget:
            raise ToolBudgetExceeded(
                f"tool budget {budget} exhausted before '{name}' "
                f"(already called {len(seen)})")
        seen.add(signature)
        return functions[name](ToolContext.from_pack(context), **arguments)


ALLOWED_PROMPT_KEYS = frozenset({"response.generate", "response.review_tone"})


def register_prompt_files(
    conn: Any, prompt_root: str = "prompts", model_family: str = "unknown"
) -> tuple[list[UUID], list[str]]:
    """Register and activate the supported versioned prompt files atomically."""
    import hashlib
    from pathlib import Path

    root = Path(prompt_root)
    ids: list[UUID] = []
    skipped: list[str] = []
    candidates: list[tuple[Any, str, str, str, str]] = []
    for path in sorted(root.glob("*/**/*.v*.md")):
        stem, version = path.name.rsplit(".v", 1)
        version = version.removesuffix(".md")
        key = f"{path.parent.name}.{stem}"
        if key not in ALLOWED_PROMPT_KEYS:
            skipped.append(str(path))
            continue
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        candidates.append((path, key, version, text, digest))

    with conn.transaction():
        with conn.cursor() as cur:
            for path, key, version, text, digest in candidates:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
                cur.execute(
                    "SELECT prompt_id, version, sha256 FROM prompts "
                    "WHERE prompt_key=%s AND (sha256=%s OR version=%s)",
                    (key, digest, version),
                )
                rows = cur.fetchall()
                same_hash = next((row for row in rows if row[2] == digest), None)
                same_version = next((row for row in rows if row[1] == version), None)
                if same_version is not None and same_version[2] != digest:
                    raise ValueError(
                        f"prompt version collision for {key} v{version}: content differs"
                    )
                if same_hash is not None:
                    prompt_id = same_hash[0]
                else:
                    cur.execute(
                        "INSERT INTO prompts (prompt_key, version, template, sha256, model_family, active) "
                        "VALUES (%s,%s,%s,%s,%s,false) RETURNING prompt_id",
                        (key, version, text, digest, model_family),
                    )
                    prompt_id = cur.fetchone()[0]
                cur.execute("UPDATE prompts SET active=false WHERE prompt_key=%s", (key,))
                cur.execute("UPDATE prompts SET active=true WHERE prompt_id=%s", (prompt_id,))
                cur.execute("SELECT count(*) FROM prompts WHERE prompt_key=%s AND active=true", (key,))
                if cur.fetchone()[0] != 1:
                    raise RuntimeError(f"expected exactly one active prompt for {key}")
                ids.append(prompt_id)
    return ids, skipped


register_prompts = register_prompt_files


def record_llm_call(conn: Any, *, run_id: UUID | None, prompt_id: UUID, provider: str, model: str, response_json: dict[str, Any] | None = None, input_tokens: int | None = None, output_tokens: int | None = None, latency_ms: int | None = None, cost_microusd: int | None = None) -> UUID:
    """Record an invocation with the exact registered prompt FK."""
    from app.infrastructure.db.repository import create_llm_call

    return create_llm_call(conn, run_id=run_id, prompt_id=prompt_id, provider=provider, model=model, response_json=response_json, input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms, cost_microusd=cost_microusd)
