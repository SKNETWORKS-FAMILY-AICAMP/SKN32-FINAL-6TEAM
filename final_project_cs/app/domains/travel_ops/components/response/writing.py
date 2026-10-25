"""기존 workflow 결과만 작성한다. 조회·승인·일정 변경 권한은 없다."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    request: dict[str, Any]
    text: str
    status: Literal["answered", "needs_input", "unsupported", "failed"]
    evidence: dict[str, Any]
    checked_at: str
    target: dict[str, Any]
    more: str = ""


@dataclass(frozen=True)
class ResponseInput:
    source: str
    scope: dict[str, str] | None
    version: int
    question_ids: tuple[str, ...]
    questions: tuple[QuestionResult, ...]
    execution: dict[str, Any]
    workflow: dict[str, Any]
    followup: dict[str, Any] | None
    social: str = ""


@dataclass(frozen=True)
class ResponseResult:
    answer: str
    more: str
    completion: Literal["complete", "partial"]
    source: str
    scope: dict[str, str] | None
    version: int
    questions: tuple[QuestionResult, ...]
    execution: dict[str, Any]
    workflow: dict[str, Any]
    followup: dict[str, Any] | None


def write_response(data: ResponseInput) -> ResponseResult:
    """질문별 확인된 문장을 순서대로 작성하고 업무 스냅샷을 독립 보존한다."""
    actual = tuple(q.question_id for q in data.questions)
    if (not data.question_ids or any(not isinstance(qid, str) or not qid.strip() for qid in data.question_ids)
            or len(set(data.question_ids)) != len(data.question_ids)
            or actual != data.question_ids):
        raise ValueError("Every question must have exactly one ordered closure")
    for question in data.questions:
        if not question.text.strip() or question.status not in ("answered", "needs_input", "unsupported", "failed"):
            raise ValueError("Question closure requires text and an explicit supported status")
        if question.status == "answered" and question.evidence.get("unresolved"):
            raise ValueError("Answered question cannot contain unresolved evidence")
    paragraphs: list[str] = []
    details: list[str] = []
    for question in data.questions:
        if question.text not in paragraphs:
            paragraphs.append(question.text)
        if question.more:
            details.append(question.more)
    if data.social:
        paragraphs.insert(0, data.social)
    return ResponseResult(
        answer="\n\n".join(paragraphs), more="\n\n".join(details),
        completion="complete" if all(q.status == "answered" for q in data.questions) else "partial",
        source=data.source, scope=deepcopy(data.scope), version=data.version,
        questions=deepcopy(data.questions), execution=deepcopy(data.execution),
        workflow=deepcopy(data.workflow), followup=deepcopy(data.followup))
