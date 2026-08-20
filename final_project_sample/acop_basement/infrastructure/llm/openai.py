"""OpenAI adapter used by customer-operations Teams."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from acop_basement.core.settings import get_settings


class OpenAITeamLLM:
    """Injectable Team LLM adapter; settings and client are resolved per call."""

    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout

    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.openai_api_key.strip():
            raise RuntimeError("OpenAI API key is missing")

        from openai import OpenAI

        prompt = json.dumps(
            {
                "prompt_key": prompt_key,
                "input_text": input_text,
                "context": context,
                "instructions": (
                    "Return one json object only. Follow this TeamResult schema: "
                    "outcome (completed, waiting, escalated, handoff, or failed), "
                    "confidence (number from 0 to 1), answer (string or null), "
                    "next_action (string), evidence (array), decisions (array), "
                    "action_proposals (array), failure_code (string or null), "
                    "warnings (array). Use only supplied evidence; do not invent facts."
                ),
            },
            ensure_ascii=False,
            default=str,
        )

        def call() -> dict[str, Any]:
            client = OpenAI(api_key=settings.openai_api_key, timeout=self.timeout)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature,
                seed=settings.llm_seed,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content or "{}")

        return await asyncio.to_thread(call)


__all__ = ["OpenAITeamLLM"]
