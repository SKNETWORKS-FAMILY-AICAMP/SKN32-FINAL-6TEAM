"""Generic, injected read-tool dispatch for Team modules.

This module intentionally knows nothing about a product domain or its storage
schema. Concrete tool implementations belong to the owning module and are
passed in through ``tool_functions`` at the composition boundary.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from acop_basement.core.contracts import ContextPack, ToolNotAllowed


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
    """Dispatch named tools supplied by the composition root.

    ★버그사냥 2026-08-18 (versioning 스트림 3) — 이전 판은 옛 호출부와의
      "호환"을 위해 `_legacy_connection_factory` 를 저장만 하고 실제로는
      한 번도 쓰지 않는 죽은 필드를 뒀다. 저장은 되는데 동작은 안 하는
      코드는 CLAUDE.md 의 "폴백 금지" 원칙이 정확히 막으려는 것이다 —
      호출자는 연결이 배선됐다고 믿지만 실제로는 아무 도메인 tool 도
      동작하지 않는다. 옛 호출부(테스트)를 새 시그니처로 직접 고쳐서
      암묵적 브리지 자체를 없앴다.
    """

    tool_functions: dict[str, Callable[..., Any]] = field(default_factory=dict)
    #: ★일부 Team(예: `FeedbackAnalyticsTeam`)은 이름 붙은 tool 하나가 아니라
    #:   배치 작업 전체를 위한 원본 connection 이 필요하다. named tool 우회가
    #:   아니라 **명시적으로 선언된 필드**다 — 안 쓰는 Team 은 그냥 안 쓴다.
    connection_factory: Callable[[], Any] | None = None

    def call(self, name: str, context: ContextPack, arguments: dict[str, Any],
             allowed_tools: list[str], seen: set[str]) -> Any:
        if name not in allowed_tools:
            raise ToolNotAllowed(f"tool '{name}' is not allowed for this task")
        function = self.tool_functions.get(name)
        if function is None:
            raise ToolNotAllowed(f"unknown tool '{name}'")
        signature = name + ":" + json.dumps(
            arguments, sort_keys=True, default=str, separators=(",", ":"))
        if signature in seen:
            raise ToolLoopExceeded(f"repeated tool request: {name}")
        seen.add(signature)
        return function(ToolContext.from_pack(context), **arguments)


def register_prompt_files(conn: Any, prompt_root: str = "prompts", model_family: str = "unknown") -> list[UUID]:
    """Register versioned prompt files with content hashes and return IDs."""
    import hashlib
    from pathlib import Path
    from acop_basement.infrastructure.db.repository import create_prompt

    root = Path(prompt_root)
    ids: list[UUID] = []
    for path in sorted(root.glob("*/**/*.v*.md")):
        text = path.read_text(encoding="utf-8")
        stem, version = path.name.rsplit(".v", 1)
        version = version.removesuffix(".md")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        ids.append(create_prompt(conn, prompt_key=stem, version=version, template=text,
                                 sha256=digest, model_family=model_family))
    return ids


register_prompts = register_prompt_files


def record_llm_call(conn: Any, *, run_id: UUID | None, prompt_id: UUID, provider: str,
                    model: str, response_json: dict[str, Any] | None = None,
                    input_tokens: int | None = None, output_tokens: int | None = None,
                    latency_ms: int | None = None, cost_microusd: int | None = None) -> UUID:
    """Record an invocation with the exact registered prompt FK."""
    from acop_basement.infrastructure.db.repository import create_llm_call
    return create_llm_call(conn, run_id=run_id, prompt_id=prompt_id, provider=provider,
                           model=model, response_json=response_json,
                           input_tokens=input_tokens, output_tokens=output_tokens,
                           latency_ms=latency_ms, cost_microusd=cost_microusd)
