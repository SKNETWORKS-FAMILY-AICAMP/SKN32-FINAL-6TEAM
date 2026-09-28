"""Locally-hosted fine-tuned-model adapter used by customer-operations Teams.

Mirrors app/infrastructure/llm/openai.py's OpenAITeamLLM exactly (same
prompts-table lookup, same audit trail via record_llm_call, same duck-typed
complete() signature) so a Team never has to know which backend answered it.
The only difference is where generation happens: instead of calling OpenAI,
this POSTs to a small inference server hosted next to the fine-tuned model
(see eval/finetune/serve.py) and expects back the same JSON shape.
"""
from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

import httpx

from app.tools.read_tools import record_llm_call


class LocalFTTeamLLM:
    """Injectable Team LLM adapter backed by a locally-hosted fine-tuned model."""

    def __init__(self, *, base_url: str, model_name: str = "local-ft",
                 connection_factory=None, timeout: float | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.connection_factory = connection_factory
        # ★가드레일에서 읽는다. 전에는 여기 120.0 이 박혀 있어
        #   `config/guardrails.yaml` 의 `llm_call_timeout_seconds: 20` 이
        #   **아무것도 통제하지 못했다** — 설정에 값이 있으면 그게 지켜지는
        #   줄 알게 된다(2026-09-03 발견). `CLAUDE.md` §3: 가드레일 수치는
        #   한 곳에만 둔다.
        if timeout is None:
            from app.core.settings import get_guardrails
            timeout = float(get_guardrails().get('reliability.local_ft_call_timeout_seconds'))
        self.timeout = timeout

    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any], *, run_id: UUID | None = None) -> dict[str, Any]:
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

        # same wire shape OpenAITeamLLM sends -- the fine-tune was trained on
        # exactly this JSON blob as its user turn (see
        # eval/finetune/build_stage3_dataset.py), so this must not drift from
        # openai.py's construction.
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

        started = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/complete", json={"prompt": prompt})
            response.raise_for_status()
            body = response.json()
        latency_ms = round((time.monotonic() - started) * 1000)

        try:
            result = json.loads(body["text"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"local_ft server returned unparseable output: {exc}") from exc

        if prompt_id is not None:
            try:
                with self.connection_factory() as conn:
                    with conn.transaction():
                        record_llm_call(
                            conn, run_id=run_id, prompt_id=prompt_id, provider="local_ft",
                            model=self.model_name, response_json=result,
                            input_tokens=body.get("input_tokens"), output_tokens=body.get("output_tokens"),
                            latency_ms=latency_ms,
                        )
            except Exception as exc:
                raise RuntimeError(f"failed to record LLM call for {prompt_key}") from exc
        return result


__all__ = ["LocalFTTeamLLM"]
