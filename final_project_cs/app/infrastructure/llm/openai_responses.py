"""OpenAI Responses API 어댑터 — 활동 판정 LLM(D-CS-008) 전용.

★`OpenAITeamLLM`(`openai.py`)과 **따로 둔다.** 그쪽은 TeamResult JSON 하나를 Chat Completions 로
  받는 어댑터라 모든 Team 에 주입된다. 이 어댑터는 판정 스키마(`text.format` json_schema)와
  웹 검색(`web_search`) 출처 목록을 돌려받아야 해서 입력도 출력도 다르다. 섞으면 실험이
  다른 Team 의 경로를 바꾼다.

★실측(2026-10-06, `wiki/records/evidence/2026-10-06_액티비티_LLM_스파이크_실측.md`)으로 정한 것:
  - `temperature`·`seed` 를 넘기지 않는다 — gpt-5.4-nano 는 `seed` 를 400 으로 거절하고,
    `temperature` 는 effort=none 에서만 받는다.
  - json_schema 를 강제하면 `url_citation` 주석이 오지 않는다. 그래서 `include` 로
    `web_search_call.action.sources` 를 받아 **실제로 본 출처 목록**을 돌려준다.
    인용 URL 이 그 목록에 있는지는 판정 계층이 대조한다(계획서 §5.4).

★여기서는 판정하지 않는다. 받은 것을 모양 그대로 돌려주고, 모양이 틀리면 `JudgeResponseError` 로 말한다.
  「모름」으로 바꾸는 일은 판정 계층의 몫이다 — 어댑터가 삼키면 실패 코드를 못 남긴다.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.settings import get_settings
from app.tools.read_tools import record_llm_call

from ._registry import load_active_prompt, write_audit

#: 웹 검색 출처 목록을 받는 `include` 값. 스키마를 강제하면 `url_citation` 이 없어 이것이 유일한 출처 근거다.
WEB_SOURCES_INCLUDE = "web_search_call.action.sources"


class JudgeResponseError(ValueError):
    """모델이 답했지만 판정으로 읽을 수 없다(빈 본문 · JSON 아님 · 객체 아님 · 응답 미완료).

    ★`ValueError` 를 잇는다 — 판정 계층(`app/modules/...`)은 이 모듈을 import 하지 못한다
      (`tests/contract/test_team_tool_discipline.py`). 그래서 표준 예외 계열로 종류를 가른다:
      읽을 수 없는 응답 = `ValueError`, 시간 초과 = `TimeoutError`, 그 밖 = 그 밖.
    """


@dataclass(frozen=True)
class JudgeCall:
    """한 번의 판정 호출 결과 — 판정 원문과 그것을 검증할 재료."""

    output: dict[str, Any]
    model: str
    #: 웹 검색이 실제로 본 URL(중복 제거, 처음 나온 순서). 웹 검색을 안 켰으면 빈 목록.
    sources: list[str] = field(default_factory=list)
    #: `web_search_call` 출력 항목 수. 동작 종류(search · open_page …)는 `search_actions` 에.
    search_calls: int = 0
    search_actions: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    latency_ms: int = 0


class OpenAIResponsesJudgeLLM:
    """Responses API 로 판정 스키마 JSON 하나를 받는다. 설정과 클라이언트는 호출마다 읽는다."""

    def __init__(self, *, connection_factory=None, timeout: float | None = None,
                 client_factory=None) -> None:
        self.connection_factory = connection_factory
        # ★가드레일에서 읽는다 — 웹 검색은 20초를 넘으므로 Team LLM 과 **다른 키**다.
        if timeout is None:
            from app.core.settings import get_guardrails
            timeout = float(get_guardrails().get("reliability.activity_judge_call_timeout_seconds"))
        self.timeout = timeout
        # ★`[2026-10-09]` 재시도를 명시한다 — SDK 기본(2회 더)이면 시간 제한이 세 배가 된다(가드레일 주석).
        from app.core.settings import get_guardrails
        self.max_retries = int(get_guardrails().get("reliability.activity_judge_max_retries"))
        self._client_factory = client_factory

    def _client(self, api_key: str) -> Any:
        if self._client_factory is not None:
            return self._client_factory(api_key=api_key, timeout=self.timeout, max_retries=self.max_retries)
        from openai import OpenAI

        return OpenAI(api_key=api_key, timeout=self.timeout, max_retries=self.max_retries)

    async def judge(self, prompt_key: str, payload: dict[str, Any], *, schema: dict[str, Any],
                    schema_name: str, web_search: bool | None = None,
                    instructions: str | None = None, run_id: UUID | None = None) -> JudgeCall:
        """판정 하나를 부른다.

        - `connection_factory` 가 있으면 지시문은 **등록된 프롬프트**(`prompts` 테이블)에서 읽고 감사 기록을 남긴다.
          없는 프롬프트면 외부 호출 전에 멈춘다.
        - 없으면(시험 · 스파이크) `instructions` 를 그대로 쓴다. 둘 다 없으면 멈춘다 — 지시문 없이 부르지 않는다.
        - `web_search` 가 `None` 이면 설정(`activity_judge_web_search`)을 따른다.
        """
        settings = get_settings()
        if not settings.openai_api_key.strip():
            raise RuntimeError("OpenAI API key is missing")
        model = settings.activity_judge_model
        use_web = settings.activity_judge_web_search if web_search is None else web_search

        prompt_id = None
        if self.connection_factory is not None:
            prompt_id, instructions = load_active_prompt(self.connection_factory, prompt_key)
        if not instructions:
            raise RuntimeError(f"no instructions for {prompt_key} — register the prompt or pass instructions")

        request: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": json.dumps(payload, ensure_ascii=False, default=str),
            "reasoning": {"effort": settings.activity_judge_reasoning_effort},
            "text": {"format": {"type": "json_schema", "name": schema_name,
                                "schema": schema, "strict": True}},
        }
        if use_web:
            request["tools"] = [{"type": "web_search"}]
            request["include"] = [WEB_SOURCES_INCLUDE]

        client = self._client(settings.openai_api_key)
        started = time.monotonic()
        try:
            response = await asyncio.to_thread(lambda: client.responses.create(**request))
        except Exception as exc:
            if _is_timeout(exc):
                raise TimeoutError(f"judge call for {prompt_key} timed out after {self.timeout}s") from exc
            raise
        latency_ms = round((time.monotonic() - started) * 1000)
        call = _read_response(response, model=model, latency_ms=latency_ms)

        if prompt_id is not None:
            write_audit(
                self.connection_factory, record_llm_call, prompt_key=prompt_key,
                run_id=run_id, prompt_id=prompt_id, provider="openai_responses", model=model,
                # ★판정만이 아니라 검증 재료(출처 · 검색 횟수)도 남긴다 — seed 가 없어 재현의 근거는 이 기록뿐이다.
                response_json={"output": call.output, "sources": call.sources,
                               "search_calls": call.search_calls, "search_actions": call.search_actions,
                               "reasoning_tokens": call.reasoning_tokens},
                input_tokens=call.input_tokens, output_tokens=call.output_tokens, latency_ms=latency_ms,
            )
        return call


def _is_timeout(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    try:
        from openai import APITimeoutError
    except ImportError:  # pragma: no cover — SDK 가 없으면 위의 표준 예외만 본다
        return False
    return isinstance(exc, APITimeoutError)


def _read_response(response: Any, *, model: str, latency_ms: int) -> JudgeCall:
    status = getattr(response, "status", None)
    if status not in (None, "completed"):
        # ★`incomplete`(토큰 한도 등)의 본문은 잘린 JSON 이다 — 읽은 척하지 않는다.
        raise JudgeResponseError(f"response not completed: status={status}")
    text = getattr(response, "output_text", None) or ""
    if not text.strip():
        raise JudgeResponseError("empty response text")
    try:
        output = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JudgeResponseError(f"response is not JSON: {exc.msg}") from exc
    if not isinstance(output, dict):
        raise JudgeResponseError(f"response JSON is not an object: {type(output).__name__}")

    sources: list[str] = []
    actions: list[str] = []
    calls = 0
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "web_search_call":
            continue
        calls += 1
        action = getattr(item, "action", None)
        actions.append(str(getattr(action, "type", None)))
        for source in getattr(action, "sources", None) or []:
            url = getattr(source, "url", None)
            if url and url not in sources:
                sources.append(url)

    usage = getattr(response, "usage", None)
    details = getattr(usage, "output_tokens_details", None)
    return JudgeCall(
        output=output, model=model, sources=sources, search_calls=calls, search_actions=actions,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        reasoning_tokens=getattr(details, "reasoning_tokens", None),
        latency_ms=latency_ms,
    )


__all__ = ["JudgeCall", "JudgeResponseError", "OpenAIResponsesJudgeLLM", "WEB_SOURCES_INCLUDE"]
