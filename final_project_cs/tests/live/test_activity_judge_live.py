"""활동 판정 LLM 어댑터 실호출 1회(D-CS-008) — `-m live` 로만 돈다. 웹 검색 요금이 든다(건당 약 $0.02~0.04, 추정).

★보는 것은 **실제 SDK 응답을 읽을 수 있는가**다 — 판정이 맞는지는 평가(5단계)가 본다.
  인용 URL 이 출처 목록에 있는지는 확인하지만, 모델이 근거를 못 찾아 `unknown` 을 내는 것은 실패가 아니다.
"""
from __future__ import annotations

import pytest

from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM

SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"verdict": {"type": "string", "enum": ["open", "closed", "unknown"]},
                         "citations": {"type": "array", "items": {"type": "string"}}},
          "required": ["verdict", "citations"]}


@pytest.mark.live
@pytest.mark.asyncio
async def test_activity_judge_live_smoke() -> None:
    call = await OpenAIResponsesJudgeLLM().judge(
        "activity_judge.smoke", {"place": "경복궁", "region": "서울 종로구"},
        schema=SCHEMA, schema_name="smoke", web_search=True,
        instructions="장소가 내일 오후 2시에 관람 가능한지 웹 공지로 판정하라. 근거가 없으면 unknown. "
                     "citations 에는 실제로 본 페이지 URL 만 넣는다.")
    assert call.output["verdict"] in {"open", "closed", "unknown"}
    assert call.search_calls >= 1 and call.sources
    if call.output["verdict"] != "unknown":
        assert any(url in call.sources for url in call.output["citations"])
