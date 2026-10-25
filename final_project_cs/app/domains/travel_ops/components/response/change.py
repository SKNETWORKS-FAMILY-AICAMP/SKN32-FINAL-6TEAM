"""채팅 변경 답 작성 — 이미 실행된 변경 결과(`TripDesk.edit` outcome)의 문장만 공통 writer 로 닫는다.

조회 · 승인 · 일정 변경 권한은 없다. 고객 문장은 바꾸지 않는다(한 질문 = 한 문단 — writer 가 같은 글을 돌려준다).
결과는 내부 근거(`basis.response`)로만 남는다 — 공개 response_status/question_status 투영은 L02b 보류(`public.response_status`).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .writing import QuestionResult, ResponseInput, ResponseResult, write_response

#: 변경 outcome status → 질문 종결. 모르는 status 는 `failed`(완료로 올려 세지 않는다).
ANSWERED = frozenset({"adjusted", "already_applied", "answered", "rolled_back", "still_fits", "rechecked", "clear",
                      "not_today", "no_meal", "gone"})
NEEDS_INPUT = frozenset({"clarify", "asked", "ask_rollback", "ask_target", "needs_check", "stale", "knock_on"})
UNSUPPORTED = frozenset({"edit_refused", "no_alternate"})


def closure(status: Any, outcome: dict[str, Any]) -> str:
    if outcome.get("needs_location"):
        return "needs_input"
    if status in ANSWERED:
        return "answered"
    if status in NEEDS_INPUT:
        return "needs_input"
    if status in UNSUPPORTED:
        return "unsupported"
    return "failed"


def compose_change_response(*, action: str, outcome: dict[str, Any], answer: str, version: int,
                            scope: dict[str, str] | None) -> ResponseResult:
    status = outcome.get("status")
    saved = outcome.get("version") if isinstance(outcome.get("version"), int) else None
    question = QuestionResult(
        question_id="change", request={"kind": "chat_change", "action": action}, text=answer,
        status=closure(status, outcome), evidence={}, checked_at="",
        target={k: outcome[k] for k in ("item_id", "version", "proposal_id") if k in outcome})
    result = write_response(ResponseInput(
        source="chat_change", scope=scope, version=version, question_ids=("change",), questions=(question,),
        execution={"status": str(status), "saved_version": saved}, workflow={}, followup=None))
    if result.answer != answer:                       # 한 문단이면 같아야 한다 — 다르면 작성 계약 위반이다
        raise ValueError("change writer must not rewrite the customer answer")
    return result


def change_basis(basis: dict[str, Any], *, action: str, outcome: dict[str, Any], answer: str, version: int,
                 scope: dict[str, str] | None) -> dict[str, Any]:
    """`basis` 에 writer 결과를 더한 새 dict. 작성 실패는 숨기지 않고 `response_writing=failed` 로 남긴다(문장은 그대로)."""
    try:
        written = compose_change_response(action=action, outcome=outcome, answer=answer, version=version, scope=scope)
    except Exception as exc:                          # noqa: BLE001 — 실행된 변경 답을 작성 장애로 막지 않는다(기록만)
        return {**basis, "response_writing": {"status": "failed", "error": type(exc).__name__}}
    return {**basis, "response": asdict(written)}
