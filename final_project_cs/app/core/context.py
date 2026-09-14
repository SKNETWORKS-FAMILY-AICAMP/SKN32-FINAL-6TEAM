"""Context Broker — 근거를 12,000 토큰 예산 안에서 결정적으로 조합한다.

★12,000 의 근거는 모델 context window 한계가 **아니다**(v5 §7-2).
  (1) 건당 LLM 비용 통제 (2) lost-in-the-middle 품질 저하 완화 (3) 실험 재현성.
  다른 이유를 문서·주석에 쓰지 않는다.

예산표와 제거 순서는 `config/guardrails.yaml` 의 `context.*` 가 유일한 출처다(v5 §9-1).

★토큰은 **세는 것이지 추정하는 것이 아니다.** `tiktoken` 으로 실측한다.
  문자수÷4 같은 어림은 예산 초과를 조용히 통과시킨다.

★무엇을 뺐으면 반드시 `omissions` 에 남긴다. **신호 없는 축소는 폴백이다**(RULE.md §3.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

import tiktoken

from app.core.contracts import ContextPack, Evidence
from app.core.settings import get_guardrails

#: 섹션을 채우는 순서. ★앞에 있을수록 먼저 자리를 잡는다.
#: guardrails 의 eviction_order(제거 순서)와 정확히 역순이어야 한다 —
#: 마지막에 채우는 것이 자리가 없을 때 가장 먼저 잘려 나간다.
SECTION_FILL_ORDER: tuple[str, ...] = (
    "system_instruction",
    "case_state",
    "tool_facts",
    "policy_rag",
    "history_summary",
    "similar_cases",
)

#: 어떤 경우에도 잘라내지 않는 섹션 (v5 §9-1).
NEVER_EVICT: frozenset[str] = frozenset({"system_instruction", "case_state"})


@lru_cache(maxsize=4)
def _encoder(model: str = "cl100k_base") -> tiktoken.Encoding:
    return tiktoken.get_encoding(model)


def count_tokens(text: str) -> int:
    """tiktoken 실측. ★추정하지 않는다."""
    return len(_encoder().encode(text))


@dataclass(frozen=True)
class PolicyChunk:
    """RAG 가 돌려준 정책 청크. score 가 낮은 것부터 잘린다."""

    document_id: str
    chunk_no: int
    content: str
    score: float
    scope: str

    @property
    def source_id(self) -> str:
        return f"{self.document_id}#c{self.chunk_no}"


@dataclass
class ContextInputs:
    """Broker 에 들어가는 원재료. 수집은 호출자(Controller) 몫이다."""

    case_id: UUID
    tenant_id: str
    team_id: str
    knowledge_scope: list[str]
    system_instruction: str
    current_state: dict[str, Any]
    tool_facts: list[Evidence] = field(default_factory=list)
    policy_chunks: list[PolicyChunk] = field(default_factory=list)
    history_entries: list[str] = field(default_factory=list)  # 최신 우선
    similar_cases: list[dict[str, Any]] = field(default_factory=list)
    #: RAG 조회 자체가 실패했을 때 True. 근거가 없다는 사실을 숨기지 않는다(v5 §9-4).
    retrieval_failed: bool = False


class ContextBudgetError(RuntimeError):
    """잘라낼 수 없는 섹션이 예산을 넘었다. 조용히 통과시키지 않는다."""


class ContextBroker:
    """근거를 예산 안에서 조합한다. **답변을 만들지 않는다**(v5 §4-2)."""

    def __init__(self) -> None:
        guardrails = get_guardrails()
        self.budget: int = guardrails.get("context.token_budget")
        self.sections: dict[str, int] = dict(guardrails.get("context.sections"))
        self.max_evidence: int = guardrails.get("context.max_evidence_items")
        self.max_similar: int = guardrails.get("context.max_similar_cases")
        self.max_history_chars: int = guardrails.get("context.max_history_summary_chars")

        # ★예산표가 총량과 어긋나면 여기서 멈춘다. 어긋난 채로 도는 것이 더 나쁘다.
        total = sum(self.sections.values())
        if total != self.budget:
            raise ContextBudgetError(
                f"섹션 예산 합 {total} 이 token_budget {self.budget} 과 다르다 "
                "(config/guardrails.yaml context.sections)"
            )
        missing = set(SECTION_FILL_ORDER) - set(self.sections)
        if missing:
            raise ContextBudgetError(f"guardrails 에 없는 섹션: {sorted(missing)}")

    # ── 섹션별 적재 ──────────────────────────────────────────────────

    def _fit_tool_facts(
        self, facts: list[Evidence], limit: int, omissions: list[str]
    ) -> list[Evidence]:
        """오래된 fact 부터 뺀다(v5 §9-1). 중복 claim 은 먼저 접는다."""
        # 최신 우선 정렬 후, 같은 (source_id, claim) 은 하나만 남긴다
        ordered = sorted(facts, key=lambda e: e.observed_at, reverse=True)
        seen: set[tuple[str, str]] = set()
        deduped: list[Evidence] = []
        for fact in ordered:
            key = (fact.source_id, fact.claim)
            if key in seen:
                omissions.append(f"tool_facts:duplicate:{fact.evidence_id}")
                continue
            seen.add(key)
            deduped.append(fact)

        kept: list[Evidence] = []
        used = 0
        for fact in deduped:
            if len(kept) >= self.max_evidence:
                omissions.append(f"tool_facts:max_items:{fact.evidence_id}")
                continue
            cost = count_tokens(f"{fact.claim} {fact.value}")
            if used + cost > limit:
                omissions.append(f"tool_facts:budget:{fact.evidence_id}")
                continue
            kept.append(fact)
            used += cost
        return kept

    def _fit_policy(
        self, chunks: list[PolicyChunk], limit: int, omissions: list[str]
    ) -> tuple[list[PolicyChunk], int]:
        """낮은 similarity 부터 뺀다(v5 §9-1)."""
        ordered = sorted(chunks, key=lambda c: c.score, reverse=True)
        kept: list[PolicyChunk] = []
        used = 0
        for chunk in ordered:
            cost = count_tokens(chunk.content)
            if used + cost > limit:
                omissions.append(f"policy_rag:low_score:{chunk.source_id}")
                continue
            kept.append(chunk)
            used += cost
        return kept, used

    def _fit_history(
        self, entries: list[str], limit: int, omissions: list[str]
    ) -> tuple[str, int]:
        """상세 history 부터 뺀다(v5 §9-1). 최신 항목을 남긴다."""
        kept: list[str] = []
        used = 0
        for index, entry in enumerate(entries):
            cost = count_tokens(entry)
            if used + cost > limit:
                omissions.append(f"history_summary:detail:{index}")
                continue
            kept.append(entry)
            used += cost
        summary = "\n".join(kept)[: self.max_history_chars]
        return summary, count_tokens(summary)

    def _fit_similar(
        self, cases: list[dict[str, Any]], limit: int, omissions: list[str]
    ) -> tuple[list[dict[str, Any]], int]:
        """★자리가 없으면 통째로 빠진다 — 제거 1순위(v5 §9-1)."""
        kept: list[dict[str, Any]] = []
        used = 0
        for case in cases[: self.max_similar]:
            cost = count_tokens(str(case))
            if used + cost > limit:
                omissions.append(f"similar_cases:budget:{case.get('case_id', '?')}")
                continue
            kept.append(case)
            used += cost
        for case in cases[self.max_similar :]:
            omissions.append(f"similar_cases:max_items:{case.get('case_id', '?')}")
        return kept, used

    # ── 조립 ────────────────────────────────────────────────────────

    def build(self, inputs: ContextInputs) -> ContextPack:
        omissions: list[str] = []

        # 1. 잘라낼 수 없는 섹션부터 — 넘치면 예외다. 조용히 자르지 않는다.
        system_tokens = count_tokens(inputs.system_instruction)
        if system_tokens > self.sections["system_instruction"]:
            raise ContextBudgetError(
                f"system_instruction 이 예산을 넘었다: {system_tokens} > "
                f"{self.sections['system_instruction']}. 프롬프트를 줄여야 한다"
            )
        state_tokens = count_tokens(str(inputs.current_state))
        if state_tokens > self.sections["case_state"]:
            raise ContextBudgetError(
                f"case_state 가 예산을 넘었다: {state_tokens} > {self.sections['case_state']}. "
                "Case state 는 제거 대상이 아니다 — 상태 자체를 줄여야 한다"
            )

        # 2. 잘라낼 수 있는 섹션 — 채우는 순서의 역순으로 잘려 나간다.
        # Fit each section independently, then report omissions in the global
        # eviction order from guardrails (the section fit order is not that order).
        section_omissions: dict[str, list[str]] = {name: [] for name in ("tool_facts", "policy_rag", "history_summary", "similar_cases")}
        facts = self._fit_tool_facts(inputs.tool_facts, self.sections["tool_facts"], section_omissions["tool_facts"])
        facts_tokens = sum(count_tokens(f"{f.claim} {f.value}") for f in facts)
        chunks, policy_tokens = self._fit_policy(inputs.policy_chunks, self.sections["policy_rag"], section_omissions["policy_rag"])
        history, history_tokens = self._fit_history(inputs.history_entries, self.sections["history_summary"], section_omissions["history_summary"])
        similar, similar_tokens = self._fit_similar(inputs.similar_cases, self.sections["similar_cases"], section_omissions["similar_cases"])
        omissions.extend(item for name in ("similar_cases", "history_summary", "policy_rag", "tool_facts") for item in section_omissions[name])

        # 3. 정책 근거를 Evidence 로 승격 — 모든 주장에 출처가 붙어야 한다.
        policy_evidence = [
            Evidence(
                evidence_id=f"policy:{chunk.source_id}",
                source_type="policy",
                source_id=chunk.source_id,
                claim=chunk.content,
                value={"score": chunk.score, "scope": chunk.scope},
                confidence=min(max(chunk.score, 0.0), 1.0),
                observed_at=max((f.observed_at for f in facts), default=None)
                or _now(),
            )
            for chunk in chunks
        ]
        evidence = facts + policy_evidence
        if len(evidence) > self.max_evidence:
            for dropped in evidence[self.max_evidence :]:
                omissions.append(f"evidence:max_items:{dropped.evidence_id}")
            evidence = evidence[: self.max_evidence]

        total = (
            system_tokens
            + state_tokens
            + facts_tokens
            + policy_tokens
            + history_tokens
            + similar_tokens
        )

        # 4. ★degraded 판정 — RAG 가 죽었거나 정책 근거가 하나도 없으면 숨기지 않는다.
        degraded = inputs.retrieval_failed or (
            bool(inputs.policy_chunks or inputs.retrieval_failed) and not chunks
        )
        if inputs.retrieval_failed:
            omissions.append("policy_rag:retrieval_failed")
        elif not chunks and not inputs.policy_chunks:
            # 애초에 조회 결과가 없었던 것도 근거 부족이다.
            degraded = True
            omissions.append("policy_rag:no_results")

        return ContextPack(
            pack_id=uuid4(),
            case_id=inputs.case_id,
            team_id=inputs.team_id,
            tenant_id=inputs.tenant_id,
            knowledge_scope=list(inputs.knowledge_scope),
            current_state=inputs.current_state,
            evidence=evidence,
            history_summary=history,
            similar_cases=similar,
            estimated_input_tokens=total,
            degraded=degraded,
            omissions=omissions,
        )


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
