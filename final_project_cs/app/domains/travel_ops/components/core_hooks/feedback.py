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
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.settings import get_settings
from app.core.redaction import masked

logger = logging.getLogger(__name__)


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
    # ★`[2026-09-22]` 자동 실행을 되돌려 달라는 요청(v11 §12 DoD-21). 되돌림은 보상 거래라
    #   실패할 수 있고, 실패하면 사람에게 간다 — 그 경로가 이 코드로 들어온다
    "booking_revert_request",
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
    # ★`[2026-09-29]` 뜻과 예를 붙였다 — 모델이 intent 칸에 issue_code(`booking_revert_request`)를 넣어 「되돌려」가
    #   분류 실패로 끝났다(ui 세션 실서버 · 재현 3/3). intent 는 위 다섯 글자 중 하나뿐이다.
    "intent meanings: itinerary_submit = sends or registers a plan; incident_report = something went wrong "
    "(late, closed, sold out, weather); confirm_request = asks a question or asks to check something; "
    "adjust_reject = wants a change, another option, or to undo/revert a change "
    "(e.g. '다른 데로 바꿔 줘', '원래대로 돌려 줘', '이전 식당으로 되돌려'); other = none of these. "
    "Never put an issue_code value in intent.\n"
    "issue_code names the OBJECT and the situation; its prefix decides which team "
    "handles the case, so pick the prefix that matches what the message is about "
    "(activity_/dining_/mobility_/booking_/lodging_/flight_). "
    "It must be one of: " + ", ".join(sorted(ISSUE_CODES)) + ".\n"
    "sentiment is positive|neutral|negative; severity is low|medium|high|critical.\n"
    "Use 'other' only when no listed code fits — do not guess a prefix."
)


def _openai_llm(text: str, *, system: str = _SYSTEM_PROMPT, timeout_seconds: float | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ClassificationFailed("OpenAI API key is missing")
    try:
        from openai import OpenAI

        options = {"timeout": timeout_seconds, "max_retries": 0} if timeout_seconds is not None else {}
        response = OpenAI(api_key=settings.openai_api_key, **options).chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            seed=settings.llm_seed,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
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


def _ollama_llm(text: str, *, system: str = _SYSTEM_PROMPT, timeout_seconds: float | None = None) -> dict[str, Any]:
    """로컬 Ollama(Gemma 4)로 분류한다 — `ACOP_OLLAMA_BASE_URL` 이 있을 때.

    ★2026-09-14 OpenAI 크레딧 소진(429 실측)으로 붙였다. 같은 프롬프트·같은 검증을 쓴다 —
      제공자만 바뀌고 라벨 규칙은 그대로다.
    """
    from app.infrastructure.ollama_chat import OllamaError, from_settings

    settings = get_settings()
    if timeout_seconds is not None:
        settings = settings.model_copy(update={"ollama_timeout_seconds": timeout_seconds,
                                               "llm_failover_total_seconds": timeout_seconds})
    chat = from_settings(settings)
    if chat is None:
        raise ClassificationFailed("Ollama base url is missing")
    try:
        return chat.json(system, text)
    except OllamaError as exc:
        raise ClassificationFailed(f"Ollama classification failed: {exc}") from exc


def _default_llm() -> LLM:
    """설정이 고른 제공자 — Ollama 주소가 있으면 Ollama, 없으면 OpenAI."""
    return _ollama_llm if (get_settings().ollama_base_url or "").strip() else _openai_llm


def plan_stream() -> dict[str, float]:
    """분류 계획 호출의 답 조각 감시 값(가드레일 `travel.watch.plan_stream` — 값과 근거는 그 주석). 없는 키는 그대로 오류."""
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    return {key: float(guard.get(f"travel.watch.plan_stream.{key}"))
            for key in ("first_token_seconds", "stall_seconds", "max_seconds")}


def ask_json(system: str, text: str, *, schema: dict[str, Any] | None = None,
             num_predict: int | None = None) -> dict[str, Any]:
    """분류 에이전트의 추가 계약도 같은 설정·모델 제공자와 마스킹을 사용한다.

    ★`[2026-10-26]` `schema` 를 주면 Ollama 경로는 그 JSON 스키마를 `format` 으로 보낸다(`structured` — enum·필수 키 밖을 못 낸다).
      실행 계획(`execution_plan.classify_plan`)이 묶음 항목 id 를 스키마에 묶어 모든 항목을 한 번씩 배정하게 한다 — 자유 JSON 이던 때
      로컬 E4B 가 둘째 항목을 빠뜨려 `plan_coverage_invalid` 였다. OpenAI 직접 경로는 지금처럼 json_object 다(검증은 부르는 쪽이 한다).
    ★`[2026-10-26 사용자 결정 · 12c]` 고정 제한시간(`plan_timeout_seconds` 50) 대신 계획 읽기 · 채팅 해석과 같은 **답 조각 감시**
      (`model_stream.collect` — 첫 조각 · 조각 사이 · 맨 위 상한, `travel.watch.plan_stream`). 모델이 조각을 계속 보내는 동안은 기다리고,
      조각 사이 `stall_seconds` 동안 새 조각이 없으면 멈춘 것으로 보고 `ClassificationFailed` → 계획 `plan_provider_failed` →
      Case `classification_failed`(기존 계약 경로). 받다 만 답은 버리고 고정 순서로 대체하지 않는다."""
    stream = plan_stream()
    if schema is not None and (get_settings().ollama_base_url or "").strip():
        return _ollama_structured(masked(text), system=system, schema=schema, stream=stream,
                                  num_predict=int(num_predict or 160))
    return _default_llm()(masked(text), system=system, timeout_seconds=stream["max_seconds"])


def _ollama_structured(text: str, *, system: str, schema: dict[str, Any], stream: dict[str, float],
                       num_predict: int) -> dict[str, Any]:
    """`_ollama_llm` 과 같은 설정으로, 답 모양을 JSON 스키마로 묶어 **조금씩 받으며** 묻는다(`structured_stream`).

    받은 답은 `structured` 와 같이 스키마로 검사하고, 계획의 뜻 검사는 부르는 쪽(`validate_plan`)이 한다.
    ★모델이 안 올라와 있어도 고정 대기로 바꾸지 않는다(Codex 검토) — 적재가 첫 조각 감시를 넘기면 이번 회차는 `classification_failed`,
      그 호출이 적재를 시작했으므로 다음 회차(`retry`)는 올라온 모델로 답한다. 넘김 장치는 식은 로컬을 건너뛰어 다음 경로로 간다.
      넘김 · 재시도까지 한 호출 전체는 맨 위 상한(`max_seconds`, `llm_failover_total_seconds`) 안이다.
    조금씩 받기를 못 하는 대역(시험의 가짜)만 `structured` 로 한 번에 받는다."""
    from app.infrastructure.ollama_chat import OllamaError, from_settings, validate_structured

    settings = get_settings().model_copy(update={"ollama_timeout_seconds": stream["max_seconds"],
                                                  "llm_failover_total_seconds": stream["max_seconds"]})
    chat = from_settings(settings)
    if chat is None:
        raise ClassificationFailed("Ollama base url is missing")
    streamer = getattr(chat, "structured_stream", None)
    try:
        if callable(streamer):
            return validate_structured(streamer(system, text, schema, num_predict=num_predict,
                                                first_wait=stream["first_token_seconds"], stall=stream["stall_seconds"],
                                                max_seconds=stream["max_seconds"]), schema)
        return chat.structured(system, text, schema, num_predict=num_predict)
    except OllamaError as exc:
        # 멈춤(첫 조각 · 조각 사이 · 맨 위 상한)은 원인 이름만 남긴다 — 밖으로는 그대로 `plan_provider_failed`
        logger.warning("classification_plan_stream_failed reason=%s",
                       f"stream_stalled:{exc.which}" if hasattr(exc, "which") else type(exc).__name__)
        raise ClassificationFailed(f"Ollama classification failed: {exc}") from exc


def classify(text: str, llm: LLM | None = None) -> Classification:
    """주입 가능한 LLM 으로 분류한다. 불완전한 출력은 **크게** 실패한다."""
    if not isinstance(text, str) or not text.strip():
        raise ClassificationFailed("feedback text is empty")
    provider: LLM = llm or _default_llm()
    try:
        raw = provider(masked(text))
        # ★`[2026-09-29]` 목록 밖 intent 는 **한 번만** 다시 묻는다 — 무엇이 틀렸는지 알려 주고. 그래도 틀리면 아래에서
        #   실패한다(지어내서 맞추지 않는다). ☆「금용문 이전 식당으로 다시 되돌려」가 분류 실패 한 번으로 끝났다(ui 세션 지적)
        if isinstance(raw, dict) and raw.get("intent") not in INTENTS:
            raw = provider(masked(text) + f"\n\n(Your previous intent '{raw.get('intent')}' is not allowed. "
                           f"intent must be exactly one of: {', '.join(sorted(INTENTS))}.)")
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
