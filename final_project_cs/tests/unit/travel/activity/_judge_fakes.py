"""판정 계층 시험용 가짜 — 판정 어댑터(`OpenAIResponsesJudgeLLM`)와 같은 모양으로 답한다."""
from __future__ import annotations

from types import SimpleNamespace


class FakeJudgeLLM:
    def __init__(self, output=None, *, sources=(), exc=None):
        self.output = output
        self.sources = list(sources)
        self.exc = exc
        self.calls = []

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None,
                    instructions=None, run_id=None):
        self.calls.append({"prompt_key": prompt_key, "payload": payload, "schema": schema,
                           "schema_name": schema_name, "web_search": web_search,
                           "instructions": instructions, "run_id": run_id})
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(output=self.output, sources=self.sources, search_calls=len(self.sources),
                               latency_ms=5, input_tokens=10, output_tokens=3, reasoning_tokens=1,
                               model="fake-nano")


def out(verdict, *, quotes=(), citations=(), confidence=0.8, reason="이유"):
    return {"verdict": verdict, "confidence": confidence, "reason": reason,
            "quotes": list(quotes), "citations": list(citations)}
