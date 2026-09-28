"""OpenAI adapter used by customer-operations Teams."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import UUID

from app.core.settings import get_settings
from app.tools.read_tools import record_llm_call


class AuditWriteError(RuntimeError):
    """The model responded, but its audit record could not be persisted."""


class OpenAITeamLLM:
    """Injectable Team LLM adapter; settings and client are resolved per call."""

    def __init__(self, *, connection_factory=None, timeout: float | None = None) -> None:
        self.connection_factory = connection_factory
        # ★가드레일에서 읽는다. 전에는 여기 60.0 이 박혀 있어
        #   `config/guardrails.yaml` 의 `llm_call_timeout_seconds: 20` 이
        #   **아무것도 통제하지 못했다** — 설정에 값이 있으면 그게 지켜지는
        #   줄 알게 된다(2026-09-03 발견). `CLAUDE.md` §3: 가드레일 수치는
        #   한 곳에만 둔다.
        if timeout is None:
            from app.core.settings import get_guardrails
            timeout = float(get_guardrails().get('reliability.llm_call_timeout_seconds'))
        self.timeout = timeout

    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any], *, run_id: UUID | None = None) -> dict[str, Any]:
        settings = get_settings()
        if not settings.openai_api_key.strip():
            raise RuntimeError("OpenAI API key is missing")

        prompt_id = None
        instructions = (
            "Return one json object only. Follow this TeamResult schema: "
            "outcome (completed, waiting, escalated, handoff, or failed), "
            "confidence (number from 0 to 1), answer (string or null), "
            "next_action (string), evidence (array), decisions (array), "
            "action_proposals (array), failure_code (string or null), "
            "warnings (array). Use only supplied evidence; do not invent facts."
        )
        if self.connection_factory is not None:
            with self.connection_factory() as conn:
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute(
                        "SELECT prompt_id, template FROM prompts WHERE prompt_key=%s AND active=true",
                        (prompt_key,),
                    )
                    rows = cur.fetchall()
            if len(rows) == 0:
                raise RuntimeError(f"no active prompt registered for {prompt_key}")
            if len(rows) != 1:
                raise RuntimeError(f"expected exactly one active prompt for {prompt_key}")
            prompt_id, instructions = rows[0]

        from openai import OpenAI

        prompt = json.dumps(
            {
                "prompt_key": prompt_key,
                "input_text": input_text,
                "context": context,
                "instructions": instructions,
            },
            ensure_ascii=False,
            default=str,
        )

        def call() -> tuple[dict[str, Any], int | None, int | None]:
            client = OpenAI(api_key=settings.openai_api_key, timeout=self.timeout)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature,
                seed=settings.llm_seed,
                response_format={"type": "json_object"},
            )
            usage = response.usage
            return (
                json.loads(response.choices[0].message.content or "{}"),
                getattr(usage, "prompt_tokens", None) if usage else None,
                getattr(usage, "completion_tokens", None) if usage else None,
            )

        started = time.monotonic()
        result, input_tokens, output_tokens = await asyncio.to_thread(call)
        if prompt_id is not None:
            try:
                with self.connection_factory() as conn:
                    with conn.transaction():
                        record_llm_call(
                            conn, run_id=run_id, prompt_id=prompt_id, provider="openai",
                            model=settings.llm_model, response_json=result,
                            input_tokens=input_tokens, output_tokens=output_tokens,
                            latency_ms=round((time.monotonic() - started) * 1000),
                        )
            except Exception as exc:
                raise AuditWriteError(f"failed to record LLM call for {prompt_key}") from exc
        return result


__all__ = ["AuditWriteError", "OpenAITeamLLM"]
