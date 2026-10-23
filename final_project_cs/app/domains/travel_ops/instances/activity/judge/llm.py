# -*- coding: utf-8 -*-
"""LLMJudge — gpt-5.4-nano(Responses API)로 판정하고, **코드가 검증한다**.

★예외를 밖으로 던지지 않는다. 실패는 전부 `unknown` + 실패 코드다(시간 초과 · 읽을 수 없음 · 그 밖).
  고객 응답을 만드는 쪽(규칙 · 섀도 · LLM 모드)이 이 판정을 받아 어떻게 쓸지 정한다.

★코드가 맡는 검증(계획서 §5.4) — 통과하지 못하면 판정을 `unknown` 으로 내린다(`llm_uncited`):
  1. 인용 검증: 원문을 해석하는 판정(휴무 · 운영시간 · 재난문자)은 `quotes` 가 **입력 원문에 실제로 있어야** 한다.
  2. 출처 검증: 웹 판정(실시간 운영 상태)은 `citations[].url` 이 그 호출의 **검색 출처 목록에 있어야** 한다.
     json_schema 를 강제하면 `url_citation` 주석이 오지 않아(2026-10-06 실측) 출처 목록과 대조한다.
     게시일이 너무 오래된 근거는 버리고, 게시일이 없는 근거는 남기되 `undated` 로 센다.

★판정 어댑터는 조립이 넣는다(`ActivityTeam.judge_llm`). 이 모듈은 인프라를 import 하지 않는다 —
  어댑터의 오류는 표준 예외 계열로 가른다(시간 초과 = `TimeoutError`, 읽을 수 없음 = `ValueError`).
"""
from __future__ import annotations

import asyncio
import re
import threading
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .. import failure_codes as fc
from .types import DISASTER_EFFECT, QUOTE_SOURCES, UNKNOWN, VALUES, WEB_KINDS, JudgeContext, JudgeRequest, Verdict

#: 원문이 **비어 있는 것 자체가 근거**인 경우 — 재난문자 0건이면 「막지 않는다」에 인용할 구절이 없다.
_EMPTY_SOURCE_IS_EVIDENCE = {DISASTER_EFFECT: "no_effect"}

#: 프롬프트 키 접두. 파일은 `prompts/activity_judge/<kind>.v<N>.md`, 키는 `activity_judge.<kind>`.
PROMPT_DIR = "activity_judge"


def prompt_key(kind: str) -> str:
    return f"{PROMPT_DIR}.{kind}"


def schema_for(kind: str) -> dict[str, Any]:
    """Structured Outputs(strict) 스키마. ★strict 는 모든 칸을 `required` 로 요구한다 — 빈 값은 빈 목록·null 로."""
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "verdict": {"type": "string", "enum": list(VALUES[kind])},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
            "quotes": {"type": "array", "items": {"type": "string"}},
            "citations": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"url": {"type": "string"}, "quote": {"type": "string"},
                               "published_at": {"type": ["string", "null"]}},
                "required": ["url", "quote", "published_at"]}},
        },
        "required": ["verdict", "confidence", "reason", "quotes", "citations"],
    }


def payload_for(request: JudgeRequest) -> dict[str, Any]:
    """모델에게 보낼 입력 — 원래 시각 객체와 인용 대조용 칸은 뺀다(날짜 사실은 이미 문자열로 들어 있다)."""
    return {"kind": request.kind,
            **{k: v for k, v in request.inputs.items()
               if k not in ("starts_at_raw", "message_texts", "holidays_raw", "weather_sensitive_raw")}}


@lru_cache(maxsize=None)
def file_instructions(kind: str) -> str | None:
    """등록 경로(DB)를 쓰지 않을 때(시험 · 실호출 점검)의 지시문 — 가장 높은 버전 파일."""
    from app.core.settings import REPO_ROOT

    files = sorted((REPO_ROOT / "prompts" / PROMPT_DIR).glob(f"{kind}.v*.md"),
                   key=lambda p: int(p.name.rsplit(".v", 1)[1].removesuffix(".md")))
    return files[-1].read_text(encoding="utf-8") if files else None


#: 웹 검색 동시 호출 자리 — 프로세스에 하나(팀 인스턴스 · 섀도 스레드가 같이 쓴다). 크기는 처음 쓸 때 가드레일에서. `[2026-10-12]` 1.6
_web_slots: threading.BoundedSemaphore | None = None
_web_slots_lock = threading.Lock()


def web_slots(size: int) -> threading.BoundedSemaphore:
    global _web_slots
    with _web_slots_lock:
        if _web_slots is None:
            _web_slots = threading.BoundedSemaphore(size)
        return _web_slots


def is_rate_limited(exc: BaseException) -> bool:
    """429 인가 — SDK(`openai.RateLimitError`)를 import 하지 않고 모양으로 본다(이 모듈은 인프라를 import 하지 않는다)."""
    return getattr(exc, "status_code", None) == 429 or type(exc).__name__ == "RateLimitError"


class LLMJudge:
    """★`[2026-10-12]` 구현 계획 1.6 — 웹 판정은 동시 호출 상한 · 응답 대기 상한을 두고, 429 는 잠깐 쉬었다 다시 부른다.
    값은 `travel.activity_judge`(`web_max_concurrent` · `web_wait_seconds` · `web_answer_timeout_seconds` · `rate_limit_*`)."""

    def __init__(self, llm: Any, *, citation_max_age_days: int | None = None,
                 today: date | None = None, reliability: dict[str, Any] | None = None,
                 slots: threading.BoundedSemaphore | None = None, sleep: Any = None) -> None:
        self.llm = llm
        if citation_max_age_days is None or reliability is None:
            from app.core.settings import get_guardrails
            g = get_guardrails()
            if citation_max_age_days is None:
                citation_max_age_days = int(g.get("travel.activity_judge.citation_max_age_days"))
            if reliability is None:
                reliability = {key: g.get(f"travel.activity_judge.{key}")
                               for key in ("web_max_concurrent", "web_wait_seconds", "web_answer_timeout_seconds",
                                           "rate_limit_retries", "rate_limit_backoff_seconds")}
        self.citation_max_age_days = citation_max_age_days
        self._today = today
        self.reliability = reliability
        self._slots = slots
        self._sleep = sleep or asyncio.sleep

    async def judge(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:
        kind = request.kind
        if kind not in WEB_KINDS:
            return await self._judge_once(ctx, request)
        slots = self._slots or web_slots(int(self.reliability["web_max_concurrent"]))
        # ★자리는 스레드 단위로 잡는다 — 판정은 호출마다 새 이벤트 루프(`modes._run` · 섀도 스레드)에서 돈다
        got = await asyncio.to_thread(slots.acquire, True, float(self.reliability["web_wait_seconds"]))
        if not got:
            return _failed(kind, fc.LLM_BUSY, basis="web_slots_full")
        # ★응답 대기 상한(`web_answer_timeout_seconds`)은 여기서 걸지 않는다 — 어댑터가 스레드에서 돌아 끊어도 `asyncio.run` 이
        #   스레드를 기다린다. 고객이 기다리는 자리(`modes.rule_first`)가 건다. 자리는 호출이 **실제로 끝날 때** 돌려준다.
        try:
            return await self._judge_once(ctx, request)
        finally:
            slots.release()

    async def _judge_once(self, ctx: JudgeContext, request: JudgeRequest) -> Verdict:
        kind = request.kind
        retries = int(self.reliability["rate_limit_retries"])
        for attempt in range(retries + 1):
            try:
                call = await self.llm.judge(
                    prompt_key(kind), payload_for(request), schema=schema_for(kind),
                    schema_name=f"activity_{kind}",
                    # ★웹 판정은 설정을 따른다(None). 웹이 꺼져 있으면 출처가 없어 검증에서 `unknown` 이 된다.
                    web_search=None if kind in WEB_KINDS else False,
                    instructions=file_instructions(kind), run_id=ctx.run_id)
            except TimeoutError:
                return _failed(kind, fc.LLM_TIMEOUT)
            except ValueError as exc:
                return _failed(kind, fc.LLM_SCHEMA_INVALID, basis=type(exc).__name__)
            except Exception as exc:  # 429 · 키 없음 · 네트워크 — 종류만 남기고 「모름」
                # ★`[2026-10-12]` 1.6 — 429 만 쉬었다 다시 부른다. 그 밖(키 없음 · 네트워크)은 다시 불러도 같다
                if is_rate_limited(exc) and attempt < retries:
                    await self._sleep(float(self.reliability["rate_limit_backoff_seconds"]))
                    continue
                return _failed(kind, fc.LLM_ERROR, basis=type(exc).__name__)
            return self._validate(request, call)
        raise AssertionError("unreachable")

    # ── 검증 ────────────────────────────────────────────────
    def _validate(self, request: JudgeRequest, call: Any) -> Verdict:
        kind, out = request.kind, call.output
        metrics = {"latency_ms": call.latency_ms, "search_calls": call.search_calls,
                   "input_tokens": call.input_tokens, "output_tokens": call.output_tokens,
                   "reasoning_tokens": call.reasoning_tokens, "model": call.model}
        value = out.get("verdict")
        confidence = out.get("confidence")
        quotes = out.get("quotes")
        citations = out.get("citations")
        if (value not in VALUES[kind]
                or not isinstance(confidence, int | float) or not 0 <= confidence <= 1
                or not isinstance(quotes, list) or not isinstance(citations, list)):
            return _failed(kind, fc.LLM_SCHEMA_INVALID, basis="output_out_of_schema", metrics=metrics)

        dropped: list[str] = []
        kept_quotes = self._check_quotes(request, quotes, dropped)
        kept_citations: list[dict[str, Any]] = []
        if kind in WEB_KINDS:
            kept_citations = self._check_citations(citations, call.sources, dropped, metrics)

        failure = None
        if value != UNKNOWN:
            if kind in QUOTE_SOURCES and not kept_quotes and not (
                    not _has_source(request) and _EMPTY_SOURCE_IS_EVIDENCE.get(kind) == value):
                failure = fc.LLM_UNCITED
            if kind in WEB_KINDS and not kept_citations:
                failure = fc.LLM_UNCITED
        if failure:
            dropped.append(f"verdict:{value}->unknown")
            value = UNKNOWN
        return Verdict(kind, value, "llm", confidence=float(confidence), basis=str(out.get("reason") or ""),
                       quotes=kept_quotes, citations=kept_citations, failure_code=failure,
                       dropped=dropped, metrics=metrics)

    @staticmethod
    def _check_quotes(request: JudgeRequest, quotes: list[Any], dropped: list[str]) -> list[str]:
        fields = QUOTE_SOURCES.get(request.kind)
        if not fields:
            return [q for q in quotes if isinstance(q, str) and q.strip()]
        sources: list[str] = []
        for name in fields:
            value = request.inputs.get(name)
            sources.extend(value if isinstance(value, list) else [value])
        haystack = [_squash(s) for s in sources if isinstance(s, str) and s.strip()]
        kept = []
        for quote in quotes:
            squashed = _squash(quote) if isinstance(quote, str) else ""
            if squashed and any(squashed in text for text in haystack):
                kept.append(quote)
            else:
                dropped.append("quote:not_in_source")
        return kept

    def _check_citations(self, citations: list[Any], sources: list[str], dropped: list[str],
                         metrics: dict[str, Any]) -> list[dict[str, Any]]:
        seen = {_normalize_url(u) for u in sources}
        today = self._today or date.today()
        kept, undated = [], 0
        for cite in citations:
            url = cite.get("url") if isinstance(cite, dict) else None
            if not url or _normalize_url(url) not in seen:
                dropped.append("citation:not_in_sources")
                continue
            published = _parse_date(cite.get("published_at"))
            if published is None:
                undated += 1
            elif (today - published).days > self.citation_max_age_days:
                dropped.append("citation:stale")
                continue
            kept.append(cite)
        metrics["undated_citations"] = undated
        return kept


def _has_source(request: JudgeRequest) -> bool:
    for name in QUOTE_SOURCES.get(request.kind, ()):
        value = request.inputs.get(name)
        for text in value if isinstance(value, list) else [value]:
            if isinstance(text, str) and text.strip():
                return True
    return False


def _failed(kind: str, code: str, *, basis: str | None = None, metrics: dict[str, Any] | None = None) -> Verdict:
    return Verdict(kind, UNKNOWN, "llm", basis=basis, failure_code=code, metrics=metrics or {})


def _squash(text: str) -> str:
    """공백을 지워 비교한다 — 원문의 줄바꿈·`<br>` 자리 공백 차이로 인용이 떨어지지 않게."""
    return re.sub(r"\s+", "", re.sub(r"<br\s*/?>", " ", text, flags=re.I))


def _normalize_url(url: str) -> str:
    """같은 페이지를 같게 본다 — 호스트 소문자 · `www.` · 끝 `/` · `utm_*` 파라미터 차이만 지운다.
    ★나머지 쿼리는 남긴다 — 공지 게시판은 글 번호가 쿼리에 있다(`...R403000000.do?id=...`)."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_")])
    return urlunsplit(("", host, parts.path.rstrip("/"), query, ""))


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"\s*(\d{4})[-./](\d{1,2})[-./](\d{1,2})", value)
    if not match:
        return None
    try:
        return datetime(int(match[1]), int(match[2]), int(match[3])).date()
    except ValueError:
        return None


def known_prompt_files() -> dict[str, Path]:
    """판정 종류별 프롬프트 파일(가장 높은 버전). 시험이 키 등록과 파일 존재를 맞춰 본다."""
    from app.core.settings import REPO_ROOT

    found = {}
    for kind in VALUES:
        files = sorted((REPO_ROOT / "prompts" / PROMPT_DIR).glob(f"{kind}.v*.md"))
        if files:
            found[kind] = files[-1]
    return found
