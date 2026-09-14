# -*- coding: utf-8 -*-
"""인라인 분류기 — 여행 도메인의 **어휘**.

★계층. 언제 부르고·실패를 어떻게 처리하고·어느 상태로 보내는가는 **코어 1**
  (`app/application/classification.py`)이 정한다. 이 파일은 **라벨 어휘와
  프롬프트**만 갖는다(v8 §3-A 가 그은 경계 그대로). 커머스 시절
  `app/modules/customer_ops/feedback.py` 가 있던 자리다.

★**라우팅은 두 축이다**(v11 §5-B). 이 파일이 내는 두 라벨이 각각 한 축이다:

      intent      요청 종류 — 다섯. 무엇을 해 달라는 요청인가
      issue_code  대상 객체 종류가 **접두**로 들어간다. 여기서 `case_type` 이 나온다

  ★**요청 종류 다섯만으로는 여섯 팀 어디에도 못 간다.** 2026-09-09 실행으로
    확인됐다 — `registry.resolve(case_type=...)` 는 팀의 `accepted_case_types`
    (`activity`·`dining`·`mobility`·`booking`·`lodging`·`flight`)와 맞춰 보는데,
    `itinerary_submit` 같은 요청 종류는 그 어느 것과도 안 맞는다. 그래서
    **접두를 issue_code 에 실어 보낸다.** 뽑는 쪽은
    `app/application/routing.py::case_type_of` 다(그쪽은 어휘를 모른다 —
    `_` 앞을 자를 뿐이다).

★**지어내지 않는다.** provider 가 네 라벨을 다 주지 않으면 실패다. 조용한
  기본값 경로는 없다 — 커머스에서 `INTENTS` 가 옛 도메인 어휘로 남아 **운영
  분류가 전량 실패**하던 사고가 있었고(2026-08-17), 그 재발 방지가
  `tests/unit/travel/test_feedback_case_type_alignment.py` 다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.settings import get_settings
from app.presentation.security import masked


class ClassificationFailed(RuntimeError):
    """분류를 완성하지 못했다. ★조용히 넘기지 않는다."""


@dataclass(frozen=True)
class Classification:
    sentiment: str
    intent: str
    issue_code: str
    severity: str


#: 요청 종류 다섯 (v11 §5-A). ★슬러그가 정본이다 — 한국어 이름은 화면용이다.
INTENTS = frozenset({
    "itinerary_submit",   # 일정 제출
    "incident_report",    # 사건 신고
    "confirm_request",    # 확인 요청
    "adjust_reject",      # 조정 거부
    "other",              # 그 외
})

SENTIMENTS = frozenset({"positive", "neutral", "negative"})
SEVERITIES = frozenset({"low", "medium", "high", "critical"})

#: ★`issue_code` 의 **접두**가 곧 `case_type` 이고, 그것이 팀을 고른다.
#:  접두는 등록된 팀의 `accepted_case_types` 와 같아야 한다 — 정렬 검사가 센다.
ISSUE_CODES = frozenset({
    # 활동 — 「여행지에서 하는 활동」 그 자체. 레저 전용이 아니다
    "activity_cancel_or_change", "activity_weather_risk",
    "activity_time_conflict", "activity_other",
    # 식당
    "dining_hours", "dining_conditions", "dining_other",
    # 이동
    "mobility_missed_or_disrupted", "mobility_route_infeasible", "mobility_other",
    # 예약 인계 — 우리 기록과 공급자 원장의 대조
    "booking_mismatch", "booking_change_request",
    "booking_cancel_request", "booking_other",
    # 등록만 — 잠긴 예약
    "lodging_other", "flight_other",
    # 어디에도 안 붙는 것. ★접두가 없으므로 라우팅은 실패하고 escalate 된다.
    #   그게 맞다 — 모르는 것을 아무 팀에나 보내지 않는다
    "other",
})


class LLM(Protocol):
    def __call__(self, text: str) -> dict[str, Any]: ...


_SYSTEM_PROMPT = (
    "You classify a traveller's message for a travel customer-operations system. "
    "Return JSON with exactly these keys: sentiment, intent, issue_code, severity.\n"
    "intent is the KIND OF REQUEST, one of: " + ", ".join(sorted(INTENTS)) + ".\n"
    "issue_code names the OBJECT and the situation; its prefix decides which team "
    "handles the case, so pick the prefix that matches what the message is about "
    "(activity_/dining_/mobility_/booking_/lodging_/flight_). "
    "It must be one of: " + ", ".join(sorted(ISSUE_CODES)) + ".\n"
    "sentiment is positive|neutral|negative; severity is low|medium|high|critical.\n"
    "Use 'other' only when no listed code fits — do not guess a prefix."
)


def _openai_llm(text: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ClassificationFailed("OpenAI API key is missing")
    try:
        from openai import OpenAI

        response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            seed=settings.llm_seed,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": _SYSTEM_PROMPT},
                      {"role": "user", "content": text}],
        )
        content = response.choices[0].message.content
        if not content:
            raise ClassificationFailed("LLM returned an empty response")
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ClassificationFailed("LLM response is not an object")
        return value
    except ClassificationFailed:
        raise
    except Exception as exc:
        raise ClassificationFailed(f"LLM classification failed: {exc}") from exc


def _ollama_llm(text: str) -> dict[str, Any]:
    """로컬 Ollama(Gemma 4)로 분류한다 — `ACOP_OLLAMA_BASE_URL` 이 있을 때.

    ★2026-09-14 OpenAI 크레딧 소진(429 실측)으로 붙였다. 같은 프롬프트·같은 검증을 쓴다 —
      제공자만 바뀌고 라벨 규칙은 그대로다.
    """
    from app.infrastructure.ollama_chat import OllamaError, from_settings

    chat = from_settings(get_settings())
    if chat is None:
        raise ClassificationFailed("Ollama base url is missing")
    try:
        return chat.json(_SYSTEM_PROMPT, text)
    except OllamaError as exc:
        raise ClassificationFailed(f"Ollama classification failed: {exc}") from exc


def _default_llm() -> LLM:
    """설정이 고른 제공자 — Ollama 주소가 있으면 Ollama, 없으면 OpenAI."""
    return _ollama_llm if (get_settings().ollama_base_url or "").strip() else _openai_llm


def classify(text: str, llm: LLM | None = None) -> Classification:
    """주입 가능한 LLM 으로 분류한다. 불완전한 출력은 **크게** 실패한다."""
    if not isinstance(text, str) or not text.strip():
        raise ClassificationFailed("feedback text is empty")
    provider: LLM = llm or _default_llm()
    try:
        raw = provider(masked(text))
    except ClassificationFailed:
        raise
    except Exception as exc:
        raise ClassificationFailed(f"classifier provider failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClassificationFailed("classifier output is not an object")
    required = ("sentiment", "intent", "issue_code", "severity")
    if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):
        raise ClassificationFailed("classifier output is missing a required label")
    result = Classification(*(raw[key].strip() for key in required))
    if result.intent not in INTENTS or result.sentiment not in SENTIMENTS:
        raise ClassificationFailed("classifier returned an invalid intent or sentiment")
    if result.issue_code not in ISSUE_CODES or result.severity not in SEVERITIES:
        raise ClassificationFailed("classifier returned an invalid issue code or severity")
    return result


__all__ = ["Classification", "ClassificationFailed", "INTENTS", "ISSUE_CODES",
           "SENTIMENTS", "SEVERITIES", "classify"]
