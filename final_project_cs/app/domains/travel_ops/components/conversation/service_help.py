"""고객 기능 안내 — 인증된 운영 지식 검색 결과의 고객용 문장만 사용한다."""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Any, Callable

SERVICE_SCOPE = "travel_service"
MANIFEST = Path(__file__).resolve().parents[5] / "knowledge" / "service" / "manifest.json"


@lru_cache(maxsize=1)
def _sections() -> dict[str, tuple[str, str]]:
    from knowledge.ingest import load_corpus

    found = {}
    for document in load_corpus(MANIFEST):
        if document.frontmatter["scope"] != SERVICE_SCOPE:
            raise ValueError("기능 안내 코퍼스의 검색 범위가 다릅니다")
        answers = document.frontmatter.get("customer_answers") or {}
        for section in document.sections:
            line = answers.get(section.title)
            if isinstance(line, str) and line.strip():
                source = f"{document.frontmatter['document_id']}#c{section.number}"
                found[source] = (section.content.strip(), line.strip())
    return found


def reply(*, message: str, tenant_id: str, policy_search: Callable[..., list[Any]] | None,
          min_score: float, now: datetime) -> tuple[str, str, dict[str, Any]]:
    """검색 실패·미적재·오래된 근거를 성공이나 고정 안내로 숨기지 않는다."""
    basis: dict[str, Any] = {"kind": "service_help", "scope": SERVICE_SCOPE,
                             "sources": [], "checked_at": now.isoformat(), "policy_hits": 0}

    def unavailable(reason: str):
        basis["service_help"] = reason
        return ("service_help_unavailable", "지금은 서비스 기능 안내를 확인하지 못했어요. "
                "잠시 뒤 다시 물어봐 주세요. 일정은 바꾸지 않았어요.", basis)

    if policy_search is None:
        return unavailable("search_unavailable")
    try:
        sections = _sections()
        chunks = policy_search(tenant_id=tenant_id, query=message,
                               allowed_scopes=[SERVICE_SCOPE], top_k=3) or []
    except Exception as exc:  # 검색·코퍼스 장애는 고객 응답과 감사 기록에 드러낸다.
        return unavailable(f"error:{type(exc).__name__}")

    lines = []
    ranked = []
    for chunk in chunks:
        def value(key, default=None):
            return chunk.get(key, default) if isinstance(chunk, dict) else getattr(chunk, key, default)

        try:
            score = float(value("score", 0))
        except (TypeError, ValueError):
            continue
        if not isfinite(score) or score < min_score or value("scope") != SERVICE_SCOPE:
            continue
        source = f"{value('document_id')}#c{value('chunk_no')}"
        known = sections.get(source)
        # 기존 버전·잘못된 출처에 현재 문장을 연결해 근거가 있는 척하지 않는다.
        if known is None or str(value("content", "")).strip() != known[0]:
            continue
        ranked.append((score, source, known[1]))
    for _score, source, line in sorted(ranked, key=lambda entry: -entry[0]):
        if source not in basis["sources"]:
            basis["sources"].append(source)
            lines.append(line)
    basis["policy_hits"] = len(lines)
    if not lines:
        return unavailable("no_verified_match")
    return "answered", "\n\n".join(lines), basis
