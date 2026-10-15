# -*- coding: utf-8 -*-
"""규정 질문의 재순위 + 검증 단계(`policy_rerank.py`)의 제품 연결. `[2026-10-15]`

지키려는 것
 ①스위치가 꺼져 있으면(기본) 지금과 똑같다 — 모델을 안 부르고, 답의 근거에 `rerank` 칸도 안 생긴다.
 ②켜면 후보 N개를 모델이 번호로 다시 고르고, 고른 줄만 돌려준다. 아무것도 안 고르면 빈 목록(검증 단계 — 「못 찾았어요」)이다.
 ③모델을 못 부르면(실패 · 서킷 열림 · 시간 예산 부족) **지금 방식 결과**로 답하고 이유를 남긴다(조용히 넘기지 않는다). 그때 문턱은 지금 문턱이다.
 ④가드레일 값이 잘못되면 거부한다. 기본 가드레일은 `off`.
 ⑤고객 문장 색인은 아직 안 만들어졌으면 지금 방식으로 답하고(뒤에서 만든다), 만들어졌으면 코사인으로 후보를 뽑는다.
 ⑥규정 질문이 아닌 곳(`__call__`)은 늘 지금 검색 그대로다.

재현:  python -m pytest tests/unit/travel/test_policy_rerank.py -v
"""
from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.core.context import PolicyChunk
from app.core.settings import ConfigError, get_guardrails
from app.domains.travel_ops.components.conversation import policy_rerank as pr
from app.domains.travel_ops.components.conversation import trip_replies
from app.infrastructure import llm_failover

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 15, 9, 0, tzinfo=KST)


def _chunk(n: int, score: float) -> PolicyChunk:
    return PolicyChunk(document_id="t_doc_01", chunk_no=n, content=f"직원용 본문 {n} " * 20, score=score, scope="travel_activity")


def _cfg(**over) -> pr.RerankSettings:
    base = dict(mode="on", first_stage="operating", candidates=5, max_picks=3, min_score=0.5, model="", timeout_seconds=5.0,
                min_remaining_seconds=2.0, total_seconds=14.0, failures=2, open_seconds=60.0, embed_timeout_seconds=30.0)
    base.update(over)
    return pr.RerankSettings(**base)


class _Chat:
    def __init__(self, answer=None, error: Exception | None = None):
        self.answer, self.error, self.calls = answer, error, []

    def json(self, system, user):
        self.calls.append((system, user))
        if self.error:
            raise self.error
        return self.answer


SECTIONS = {f"t_doc_01#c{n}": {"doc_title": "활동 규정", "section": f"절 {n}", "line": f"고객 문장 {n}"} for n in range(1, 6)}


def _search(chunks):
    seen = []

    def base(tenant_id, query, allowed_scopes, top_k=None):
        seen.append(top_k)
        return list(chunks[: top_k or len(chunks)])

    base.seen = seen
    return base


@pytest.fixture(autouse=True)
def _clean():
    llm_failover.reset_state()
    for k in pr.STATS:
        pr.STATS[k] = 0
    yield
    llm_failover.reset_state()


def _rerank(cfg, chat, chunks=None, **kw):
    chunks = chunks or [_chunk(n, 0.9 - n * 0.05) for n in range(1, 6)]
    base = _search(chunks)
    app = SimpleNamespace(ollama_base_url="http://m", ollama_model="m", ollama_keep_alive="", ollama_num_ctx=8192)
    obj = pr.PolicyRerank(base_search=base, settings_loader=lambda: cfg, sections=lambda: SECTIONS, chat_factory=lambda c, t: chat,
                          prior_seconds=kw.pop("prior_seconds", lambda: 0.0), app_settings=lambda: app, **kw)
    return obj, base


# ── ① 꺼짐 ──
def test_off_is_exactly_the_plain_search_and_never_calls_the_model():
    chat = _Chat({"ranking": [2]})
    obj, base = _rerank(_cfg(mode="off"), chat)
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert info is None and [c.chunk_no for c in chunks] == [1, 2, 3] and chat.calls == [] and base.seen == [3]
    assert [c.chunk_no for c in obj("t", "질문", ["s"], 3)] == [1, 2, 3]            # ⑥ 규정 질문이 아닌 곳


# ── ② 재순위 · 검증 ──
def test_on_returns_only_the_chosen_lines_in_model_order():
    chat = _Chat({"ranking": [3, 1, 3, 99, "x"]})                                   # 중복 · 범위 밖 · 숫자 아님은 버린다
    obj, base = _rerank(_cfg(), chat)
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert [c.chunk_no for c in chunks] == [3, 1] and info["status"] == "ok" and info["gate"] == 0.5
    assert info["picked"] == ["t_doc_01#c3", "t_doc_01#c1"] and info["candidates"] == 5 and base.seen == [5]
    system, user = chat.calls[0]
    assert system == pr.SYSTEM and "고객 질문: 질문" in user and "1. [절 1] 고객 문장 1" in user and "5. [절 5] 고객 문장 5" in user
    assert pr.STATS["ok"] == 1 and pr.STATS["calls"] == 1


def test_on_empty_ranking_is_the_verification_answer_nothing_directly_answers():
    obj, _ = _rerank(_cfg(), _Chat({"ranking": []}))
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert chunks == [] and info["status"] == "empty" and pr.STATS["empty"] == 1


def test_picks_are_capped_by_max_picks_and_top_k():
    obj, _ = _rerank(_cfg(max_picks=2), _Chat({"ranking": [1, 2, 3, 4]}))
    assert [c.chunk_no for c in obj.search_detailed("t", "q", ["s"], top_k=3)[0]] == [1, 2]
    obj, _ = _rerank(_cfg(max_picks=3), _Chat({"ranking": [1, 2, 3, 4]}))
    assert [c.chunk_no for c in obj.search_detailed("t", "q", ["s"], top_k=1)[0]] == [1]


# ── ③ 지금 방식으로 돌아가기 ──
def test_model_failure_falls_back_to_plain_with_reason_and_counts_it():
    obj, _ = _rerank(_cfg(), _Chat(error=TimeoutError("http://model-host:11434 느림")))
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert [c.chunk_no for c in chunks] == [1, 2, 3] and info["status"] == "plain:llm_failed" and info["gate"] is None
    assert info["reason"] == "llm_failed: TimeoutError" and "model-host" not in str(info) and info["first_stage_used"] == "operating"   # 주소는 근거에 안 싣는다
    assert pr.STATS["failed"] == 1 and pr.STATS["plain_fallback"] == 1


def test_malformed_model_answer_is_a_failure_not_an_empty_verdict():
    obj, _ = _rerank(_cfg(), _Chat({"ranking": "1,2"}))
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert info["status"] == "plain:llm_failed" and len(chunks) == 3


def test_circuit_opens_after_repeated_failures_and_stops_calling_the_model():
    chat = _Chat(error=RuntimeError("꺼짐"))
    obj, _ = _rerank(_cfg(failures=2), chat)
    for _ in range(2):
        obj.search_detailed("t", "질문", ["s"], top_k=3)
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert info["status"] == "plain:circuit_open" and len(chat.calls) == 2 and len(chunks) == 3


def test_no_time_left_after_interpretation_skips_the_model():
    chat = _Chat({"ranking": [1]})
    obj, _ = _rerank(_cfg(), chat, prior_seconds=lambda: 13.0)                    # 해석이 13초를 썼다 → 남은 1초 < 2초
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert info["status"] == "plain:time_budget" and chat.calls == [] and len(chunks) == 3 and pr.STATS["skipped"] == 1


def test_model_timeout_is_min_of_config_and_remaining_time():
    seen = []

    def factory(cfg, timeout):
        seen.append(timeout)
        return _Chat({"ranking": [1]})

    obj, _ = _rerank(_cfg(timeout_seconds=5.0), _Chat(), prior_seconds=lambda: 11.0)
    obj._chat_factory = factory
    obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert seen and 2.9 < seen[0] <= 3.0                                           # 14 − 11 = 3초가 5초보다 짧다


def test_no_candidates_returns_empty_without_calling_the_model():
    chat = _Chat({"ranking": [1]})
    obj = pr.PolicyRerank(base_search=lambda **k: [], settings_loader=_cfg, sections=lambda: SECTIONS, chat_factory=lambda c, t: chat,
                          prior_seconds=lambda: 0.0, app_settings=lambda: SimpleNamespace(ollama_base_url="http://m"))
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert chunks == [] and info["status"] == "empty_candidates" and chat.calls == []


# ── ④ 가드레일 ──
def test_shipped_guardrails_are_off_and_valid():
    cfg = pr.load_settings(get_guardrails())
    assert cfg.mode == "off" and cfg.first_stage == "operating" and cfg.candidates == 20 and cfg.max_picks == 3
    assert cfg.total_seconds == 14.0 and cfg.min_score == 0.55


@pytest.mark.parametrize("key,value", [("mode", True), ("mode", "maybe"), ("first_stage", "dense")])
def test_bad_guardrail_values_are_rejected(key, value):
    values = {"mode": "on", "first_stage": "operating", "candidates": 20, "max_picks": 3, "min_score": 0.55, "model": "", "timeout_seconds": 5,
              "min_remaining_seconds": 2, "total_seconds": 15, "failures": 3, "open_seconds": 60, "embed_timeout_seconds": 30}
    values[key] = value

    class G:
        def get(self, dotted):
            return values[dotted.rsplit(".", 1)[1]]

    with pytest.raises(ValueError):
        pr.load_settings(G())
    assert ConfigError  # (가져오기 확인)


# ── ⑤ 고객 문장 색인 ──
def _vectors():
    # 문장 n 의 벡터 = 단위벡터 e_n(5차원) — 질문 벡터가 e_3 이면 3번이 1등
    import numpy as np

    return {n: np.eye(5)[n - 1].tolist() for n in range(1, 6)}


def _index(query_vec, ready=True, provider=True):
    vecs = _vectors()
    texts = {pr.CustomerTextIndex.text_of(SECTIONS[f"t_doc_01#c{n}"]): vecs[n] for n in range(1, 6)}
    embedded = []

    def embed_texts(batch):
        embedded.extend(batch)
        return [texts[t] for t in batch]

    index = pr.CustomerTextIndex(
        sections=lambda: SECTIONS, fetch_rows=lambda t, s: [("t_doc_01", n, "travel_activity", f"본문 {n}") for n in range(1, 7)],
        embed_query=lambda q: query_vec, embed_texts=embed_texts, model_key=lambda: "bge", provider_ok=lambda: provider, batch=2)
    if ready:
        index.warm()
    return index, embedded


def test_customer_text_index_picks_candidates_by_cosine_and_skips_sections_without_a_customer_line():
    index, embedded = _index([0, 0, 0.9, 0.1, 0])
    assert len(embedded) == 5                                                     # 고객 문장이 있는 절만 임베딩(6번 절은 문장이 없다)
    found = index.search("t", "질문", ["travel_activity"], 3)
    assert [c.chunk.chunk_no for c in found][:2] == [3, 4] and len(found) == 3
    assert found[0].section == "절 3" and found[0].line == "고객 문장 3" and found[0].chunk.score > found[1].chunk.score


def test_customer_text_stage_feeds_the_model_and_uses_its_own_gate():
    index, _ = _index([0, 0, 1.0, 0, 0])
    chat = _Chat({"ranking": [1]})
    obj = pr.PolicyRerank(base_search=_search([_chunk(1, .9)]), settings_loader=lambda: _cfg(first_stage="customer_text", min_score=0.45),
                          index_factory=lambda: index, chat_factory=lambda c, t: chat, prior_seconds=lambda: 0.0,
                          app_settings=lambda: SimpleNamespace(ollama_base_url="http://m"))
    chunks, info = obj.search_detailed("t", "질문", ["travel_activity"], top_k=3)
    assert [c.chunk_no for c in chunks] == [3] and info["first_stage_used"] == "customer_text" and info["gate"] == 0.45
    assert "1. [절 3] 고객 문장 3" in chat.calls[0][1]


def test_cold_customer_text_index_answers_plain_and_starts_warming():
    index, embedded = _index([1, 0, 0, 0, 0], ready=False)
    obj = pr.PolicyRerank(base_search=_search([_chunk(n, .8) for n in range(1, 4)]), settings_loader=lambda: _cfg(first_stage="customer_text"),
                          index_factory=lambda: index, chat_factory=lambda c, t: _Chat({"ranking": [1]}), prior_seconds=lambda: 0.0,
                          app_settings=lambda: SimpleNamespace(ollama_base_url="http://m"))
    chunks, info = obj.search_detailed("t", "질문", ["travel_activity"], top_k=3)
    assert info["status"] == "plain:index_cold" and info["gate"] is None and len(chunks) == 3 and pr.STATS["index_cold"] == 1
    for _ in range(50):                                                           # 뒤 스레드가 색인을 만든다
        if index.ready():
            break
        time.sleep(0.05)
    assert index.ready() and len(embedded) == 5


def test_non_ollama_provider_cannot_build_the_customer_text_index():
    index, _ = _index([1, 0, 0, 0, 0], ready=False, provider=False)
    with pytest.raises(pr.IndexUnavailable, match="provider_not_ollama"):
        index.search("t", "q", ["s"], 3)


# ── 그림자 ──
def test_shadow_answers_plain_and_runs_the_rerank_in_the_background():
    chat = _Chat({"ranking": [4]})
    obj, _ = _rerank(_cfg(mode="shadow"), chat)
    chunks, info = obj.search_detailed("t", "질문", ["s"], top_k=3)
    assert info is None and [c.chunk_no for c in chunks] == [1, 2, 3]
    for _ in range(50):
        if pr.STATS["shadow_runs"]:
            break
        time.sleep(0.05)
    assert pr.STATS["shadow_runs"] == 1 and pr.STATS["shadow_top1_diff"] == 1 and len(chat.calls) == 1


# ── 답 문장 연결(question_reply) ──
LINE_ANSWERS = {f"t_doc_01#c{n}": f"고객 문장 {n}" for n in range(1, 6)}


@pytest.fixture
def _lines(monkeypatch):
    from app.domains.travel_ops.instances._shared import itinerary_team

    monkeypatch.setattr(itinerary_team, "_LINES", LINE_ANSWERS)


def _reply(search, min_score=0.55):
    return trip_replies.question_reply(message="질문", items=[], tenant_id="t", policy_search=search, scopes=["s"], min_score=min_score, now=NOW)


def test_question_reply_uses_the_rerank_gate_and_records_the_info(_lines):
    obj, _ = _rerank(_cfg(min_score=0.45), _Chat({"ranking": [4]}), chunks=[_chunk(1, .9), _chunk(2, .8), _chunk(3, .7), _chunk(4, .5), _chunk(5, .4)])
    status, answer, basis = _reply(obj, min_score=0.55)                          # 4번 줄 점수 0.5 < 지금 문턱 0.55 지만 재순위 문턱 0.45 는 넘는다
    assert status == "answered" and "고객 문장 4" in answer and "고객 문장 1" not in answer
    assert basis["rerank"]["status"] == "ok" and "gate" not in basis["rerank"] and basis["sources"] == ["t_doc_01#c4"]


def test_question_reply_with_empty_verdict_says_it_found_nothing(_lines):
    obj, _ = _rerank(_cfg(), _Chat({"ranking": []}))
    status, answer, basis = _reply(obj)
    assert status == "answered" and "찾지 못해서 지어내 답하지 않았어요" in answer and basis["rerank"]["status"] == "empty"


def test_question_reply_after_plain_fallback_uses_the_current_gate(_lines):
    obj, _ = _rerank(_cfg(min_score=0.1), _Chat(error=RuntimeError("꺼짐")), chunks=[_chunk(1, .52), _chunk(2, .4), _chunk(3, .3), _chunk(4, .2), _chunk(5, .1)])
    status, answer, basis = _reply(obj, min_score=0.55)                          # 재순위 문턱(0.1)이 아니라 지금 문턱 0.55 → 0.52 는 못 넘는다
    assert "고객 문장 1" not in answer and basis["policy_hits"] == 0 and basis["rerank"]["status"].startswith("plain:")


def test_question_reply_with_a_plain_function_is_unchanged(_lines):
    status, answer, basis = _reply(lambda tenant_id, query, allowed_scopes, top_k: [_chunk(2, .9)])
    assert "고객 문장 2" in answer and "rerank" not in basis
