"""접수 식사 조건의 모호한 적용 대상 질문과 고객의 구조화 답변."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any


ATTRIBUTES = frozenset({"halal", "vegetarian", "kids", "card"})


class QuestionError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _valid(question: dict[str, Any], notes: str) -> bool:
    quote = question.get("quote")
    return (isinstance(quote, str) and bool(quote.strip()) and quote in notes
            and isinstance(question.get("attribute"), str) and question["attribute"] in ATTRIBUTES
            and isinstance(question.get("required"), bool))


def answers(review: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(q) for q in review.get("dining_questions") or [] if q.get("answer") is not None]


def merge_questions(review: dict[str, Any], gaps: list[dict[str, Any]], notes: str) -> None:
    choices = [{"item_id": str(i["id"]), **{k: i.get(k) for k in ("date", "starts_at", "title")}}
               for i in review.get("items") or [] if i.get("kind") == "dining"]
    known = {c["item_id"] for c in choices}
    questions = {q["id"]: {**q, "choices": choices} for q in answers(review)
                 if _valid(q, notes) and set(q["answer"].get("item_ids") or []) <= known}
    for gap in gaps:
        if gap.get("failure") != "request_scope_unclear" or not _valid(gap, notes):
            continue
        source = {k: gap[k] for k in ("quote", "attribute", "required")}
        key = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        questions.setdefault(key, {"id": key, **source, "choices": choices, "answer": None})
    if questions or "dining_questions" in review:
        review["dining_questions"] = list(questions.values())


def apply_answer(review: dict[str, Any], *, revision: int, run_id: str, question_id: str,
                 item_ids: list[str], excluded: bool, notes: str) -> dict[str, Any]:
    metadata = review.get("dining_judge") or {}
    if (metadata.get("revision") != revision or review.get("revision", revision) != revision
            or metadata.get("run_id") != run_id or metadata.get("status") not in ("completed", "failed")):
        raise QuestionError(409, "stale_dining_question", "식당 확인 상태가 바뀌었어요. 새로 불러와 다시 답해 주세요.")
    from .dining_review import fingerprint
    if metadata.get("input_fingerprint") and metadata["input_fingerprint"] != fingerprint(review, notes):
        raise QuestionError(409, "stale_dining_question", "계획이나 원문이 바뀌었어요. 식당 확인을 다시 시작해 주세요.")
    question = next((q for q in review.get("dining_questions") or [] if q.get("id") == question_id), None)
    if question is None or not _valid(question, notes):
        raise QuestionError(422, "invalid_dining_answer", "현재 원문에 해당하는 식사 조건 질문을 찾지 못했어요.")
    known = {str(i["id"]) for i in review.get("items") or [] if i.get("kind") == "dining"}
    if not isinstance(excluded, bool) or not isinstance(item_ids, list) or any(not isinstance(i, str) for i in item_ids):
        raise QuestionError(422, "invalid_dining_answer", "적용할 식사를 선택해 주세요.")
    if not set(item_ids) <= known or (excluded and item_ids) or (not excluded and not item_ids):
        raise QuestionError(422, "invalid_dining_answer", "현재 식사를 선택하거나 조건 취소를 골라 주세요.")
    changed = deepcopy(review)
    target = next(q for q in changed["dining_questions"] if q["id"] == question_id)
    target["answer"] = {"item_ids": list(dict.fromkeys(item_ids)), "excluded": excluded}
    # 고객이 정정한 조건의 과거 결과만 제거한다. 다른 조건·영업·휴무의 검증 결과는 유지한다.
    removed = False
    for item in changed.get("items") or []:
        previous = item.get("rows") or []
        item["rows"] = [r for r in previous if not (
            r.get("by") == "agent" and r.get("row") in ("dietary", "kids", "payment")
            and all((r.get("agent", {}).get("customer_request") or {}).get(k) == question[k]
                                           for k in ("quote", "attribute")))]
        if len(item["rows"]) != len(previous):
            removed = True
            baseline = item.get("before_dining_judge")
            if baseline and not any(r.get("result") == "bad" for r in item["rows"]):
                item.update(baseline)
    if removed:
        needs_items = sum(i.get("status") == "review" for i in changed.get("items") or [])
        needs_moves = sum(m.get("status") == "review" for m in changed.get("moves") or [])
        changed["needs"] = {"items": needs_items, "moves": needs_moves, "total": needs_items + needs_moves}
        changed["ready"] = (changed.get("before_dining_judge") or {}).get("ready", changed.get("ready", False)) and not (needs_items + needs_moves)
    return changed


def apply_inventory(plan: dict[str, Any], raw: list[Any]) -> list[Any]:
    """모델이 읽은 목록의 해당 조건에 고객이 직접 정한 대상을 우선 적용한다."""
    effective = deepcopy(raw)
    known = {str(i.get("item_id")) for i in (plan.get("itinerary_context") or []) + (plan.get("items") or [])
             if i.get("kind") == "dining"}
    for question in plan.get("customer_clarifications") or []:
        answer = question.get("answer") or {}
        if not _valid(question, plan.get("customer_notes") or "") or not set(answer.get("item_ids") or []) <= known:
            continue
        updates = {"item_ids": list(answer.get("item_ids") or []), "required": question["required"],
                   "state": "excluded" if answer.get("excluded") is True else "active"}
        matches = [r for r in effective if isinstance(r, dict)
                   and (r.get("quote"), r.get("attribute")) == (question["quote"], question["attribute"])]
        if matches:
            for request in matches:
                request.update(updates)
        else:
            effective.append({"request_id": question["id"], "quote": question["quote"],
                              "attribute": question["attribute"], **updates})
    return effective


def save_answer(conn, *, tenant_id: str, customer_id: Any, intake_id: Any, revision: int, run_id: str,
                question_id: str, item_ids: list[str], excluded: bool, enabled: bool) -> dict[str, Any]:
    from . import dining_review, pipeline, review as review_module

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        if row[0] != "review" or row[1] != revision:
            raise QuestionError(409, "stale_dining_question", "접수가 바뀌었어요. 현재 계획을 다시 불러와 주세요.")
        current = review_module.load(conn, tenant_id, intake_id, revision)
        if current is None:
            raise QuestionError(409, "stale_dining_question", "식당 확인을 다시 시작해 주세요.")
        if not enabled:
            raise QuestionError(503, "dining_check_unavailable", "식당 조건을 다시 확인할 수 없어요. 잠시 뒤 시도해 주세요.")
        notes = "\n".join(s.get("transcript") or "" for s in pipeline._sources(conn, tenant_id, intake_id))
        changed = apply_answer(current, revision=revision, run_id=run_id, question_id=question_id,
                               item_ids=item_ids, excluded=excluded, notes=notes)
        review_module.store(conn, tenant_id, intake_id, revision, changed)
        return dining_review.prepare(conn, tenant_id, intake_id, revision, changed, enabled=True, notes=notes)
