"""LLMJudge — 코드가 검증한다: 인용은 원문에, 출처는 검색 목록에. 통과 못 하면 「모름」(계획서 §5.4)."""
from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest

from app.domains.travel_ops.instances.activity import failure_codes_a as fc
from app.domains.travel_ops.instances.activity.judge import JudgeContext, LLMJudge, requests, schema_for
from app.domains.travel_ops.instances.activity.judge.llm import file_instructions

from ._judge_fakes import FakeJudgeLLM, out

TUESDAY = datetime(2026, 10, 13, 14, 0)
NOTICE = "https://royal.cha.go.kr/ROYAL/contents/R403000000.do?id=20260930144202825885&schM=view"


def _judge(llm, request, *, today=date(2026, 10, 6), ctx=JudgeContext()):
    return asyncio.run(LLMJudge(llm, citation_max_age_days=180, today=today).judge(ctx, request))


# ── 인용 검증(원문 해석 판정) ───────────────────────────────────

def test_closure_quote_in_source_is_kept():
    llm = FakeJudgeLLM(out("closed", quotes=["매월 둘째 주 화요일 휴무"]))
    verdict = _judge(llm, requests.closure("매월 둘째 주 화요일 휴무 (공휴일 제외)", TUESDAY))
    assert (verdict.value, verdict.source, verdict.failure_code) == ("closed", "llm", None)
    assert verdict.quotes == ["매월 둘째 주 화요일 휴무"]


def test_quote_matching_ignores_whitespace_and_br():
    llm = FakeJudgeLLM(out("closed", quotes=["매월 둘째 주 화요일"]))
    verdict = _judge(llm, requests.closure("매월 둘째<br>주  화요일 휴무", TUESDAY))
    assert verdict.value == "closed"


def test_invented_quote_downgrades_to_unknown():
    llm = FakeJudgeLLM(out("closed", quotes=["매주 화요일 휴무"]))
    verdict = _judge(llm, requests.closure("연중무휴", TUESDAY))
    assert (verdict.value, verdict.failure_code) == ("unknown", fc.LLM_UNCITED)
    assert "quote:not_in_source" in verdict.dropped and "verdict:closed->unknown" in verdict.dropped


def test_known_verdict_without_quotes_is_uncited():
    verdict = _judge(FakeJudgeLLM(out("within")), requests.operating_hours("09:00~18:00", TUESDAY))
    assert (verdict.value, verdict.failure_code) == ("unknown", fc.LLM_UNCITED)


def test_unknown_needs_no_quotes():
    verdict = _judge(FakeJudgeLLM(out("unknown")), requests.closure("공휴일 다음날 휴무", TUESDAY))
    assert (verdict.value, verdict.failure_code) == ("unknown", None)


def test_no_disaster_messages_is_its_own_evidence():
    """★재난문자 0건이면 「막지 않는다」에 인용할 구절이 없다 — 그것 자체가 근거다."""
    verdict = _judge(FakeJudgeLLM(out("no_effect")), requests.disaster_effect("경복궁", "activity", [], TUESDAY))
    assert (verdict.value, verdict.failure_code) == ("no_effect", None)


def test_disaster_messages_need_quotes():
    messages = [{"step": "위급재난", "kind": "호우", "text": "부산 해운대 일대 침수, 접근 금지"}]
    uncited = _judge(FakeJudgeLLM(out("no_effect")),
                     requests.disaster_effect("경복궁", "activity", messages, TUESDAY))
    assert uncited.value == "unknown"
    cited = _judge(FakeJudgeLLM(out("no_effect", quotes=["부산 해운대 일대 침수"])),
                   requests.disaster_effect("경복궁", "activity", messages, TUESDAY))
    assert cited.value == "no_effect"


def test_weather_sensitive_needs_no_quotes():
    verdict = _judge(FakeJudgeLLM(out("outdoor")), requests.weather_sensitive("경복궁", None))
    assert verdict.value == "outdoor"


# ── 출처 검증(웹 판정) ─────────────────────────────────────────

def _cite(url, published_at="2026-09-30"):
    return {"url": url, "quote": "정상 개방", "published_at": published_at}


def _live(llm):
    return _judge(llm, requests.live_status("경복궁", "activity", None, TUESDAY))


def test_citation_in_sources_is_kept():
    verdict = _live(FakeJudgeLLM(out("open", citations=[_cite(NOTICE)]), sources=[NOTICE]))
    assert (verdict.value, len(verdict.citations)) == ("open", 1)


def test_citation_not_in_sources_downgrades():
    verdict = _live(FakeJudgeLLM(out("closed", citations=[_cite("https://blog.example/x")]), sources=[NOTICE]))
    assert (verdict.value, verdict.failure_code) == ("unknown", fc.LLM_UNCITED)
    assert "citation:not_in_sources" in verdict.dropped


def test_url_normalization_keeps_notice_id():
    """`www.`·끝 `/`·`utm_*` 차이는 같게 보고, 글 번호(쿼리)가 다르면 다른 페이지로 본다."""
    same = _live(FakeJudgeLLM(out("open", citations=[_cite("https://www.royal.cha.go.kr/ROYAL/contents/R403000000.do?id=20260930144202825885&schM=view&utm_source=openai")]),
                              sources=[NOTICE]))
    assert same.value == "open"
    other = _live(FakeJudgeLLM(out("open", citations=[_cite(NOTICE.replace("825885", "000000"))]), sources=[NOTICE]))
    assert other.value == "unknown"


def test_stale_citation_is_dropped():
    verdict = _live(FakeJudgeLLM(out("closed", citations=[_cite(NOTICE, "2024-01-02")]), sources=[NOTICE]))
    assert verdict.value == "unknown" and "citation:stale" in verdict.dropped


def test_undated_citation_is_kept_and_counted():
    verdict = _live(FakeJudgeLLM(out("open", citations=[_cite(NOTICE, None)]), sources=[NOTICE]))
    assert verdict.value == "open" and verdict.metrics["undated_citations"] == 1


def test_web_disabled_means_no_sources_means_unknown():
    """웹 검색을 끄면 출처 목록이 비고, 그러면 웹 판정은 근거가 없어 「모름」이다(지어내지 않는다)."""
    verdict = _live(FakeJudgeLLM(out("open", citations=[_cite(NOTICE)]), sources=[]))
    assert verdict.value == "unknown"


# ── 실패는 던지지 않고 「모름」 + 코드 ─────────────────────────

@pytest.mark.parametrize("exc, code", [
    (TimeoutError("slow"), fc.LLM_TIMEOUT),
    (ValueError("not json"), fc.LLM_SCHEMA_INVALID),
    (RuntimeError("429"), fc.LLM_ERROR),
])
def test_call_failures_become_unknown_with_code(exc, code):
    verdict = _judge(FakeJudgeLLM(exc=exc), requests.closure("매주 월요일 휴무", TUESDAY))
    assert (verdict.value, verdict.failure_code) == ("unknown", code)


@pytest.mark.parametrize("output", [
    out("open"),                         # closure 에 없는 값
    out("closed", confidence=1.5),       # 범위 밖
    {"verdict": "closed"},               # 칸이 빠졌다
])
def test_out_of_schema_output_is_schema_invalid(output):
    verdict = _judge(FakeJudgeLLM(output), requests.closure("매주 화요일 휴무", TUESDAY))
    assert (verdict.value, verdict.failure_code) == ("unknown", fc.LLM_SCHEMA_INVALID)


# ── 요청 모양 ─────────────────────────────────────────────────

def test_request_shape():
    llm = FakeJudgeLLM(out("unknown"))
    run_id = __import__("uuid").uuid4()
    _judge(llm, requests.closure("매주 월요일 휴무", TUESDAY), ctx=JudgeContext(run_id=run_id))
    _live_llm = FakeJudgeLLM(out("unknown"))
    _live(_live_llm)
    closure_call, live_call = llm.calls[0], _live_llm.calls[0]
    assert closure_call["prompt_key"] == "activity_judge.closure" and closure_call["run_id"] == run_id
    # ★웹은 실시간 운영 상태에만 — 원문 해석 판정은 웹을 끈다
    assert closure_call["web_search"] is False and live_call["web_search"] is None
    assert "starts_at_raw" not in closure_call["payload"]
    assert closure_call["payload"]["weekday"] == "화요일"
    assert closure_call["instructions"]           # 파일 지시문(등록 경로가 없을 때 쓴다)


@pytest.mark.parametrize("kind", ["closure", "operating_hours", "weather_sensitive", "disaster_effect", "live_status"])
def test_schema_is_strict_compatible(kind):
    """strict 스키마는 모든 칸이 required 이고 추가 칸이 없어야 한다(아니면 API 가 400)."""
    schema = schema_for(kind)
    assert set(schema["required"]) == set(schema["properties"]) and schema["additionalProperties"] is False
    item = schema["properties"]["citations"]["items"]
    assert set(item["required"]) == set(item["properties"]) and item["additionalProperties"] is False
    assert "unknown" in schema["properties"]["verdict"]["enum"]
    assert file_instructions(kind)
