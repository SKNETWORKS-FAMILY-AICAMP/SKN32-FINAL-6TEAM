"""위치 비의존 사실 읽기만 저장된 입력으로 복구한다. 변경 업무에는 관여하지 않는다."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from app.core.contracts import StateConflict
from app.infrastructure.db import repository

from .decision_unit import Decision, FACTS, LOCATION_FACTS, fact_first


NEW_REQUEST = "이전 읽기 요청의 실행 정보를 안전하게 복구할 수 없습니다. 새 요청 번호로 질문을 다시 보내 주세요."


def _reads_without_text(reads):
    return [{k: v for k, v in r.items() if k != "text"} for r in reads or []]


def read_signature(reads, query, social):
    """복수 질문·조회 범위·잡담 답을 묶은 해석 서명. 원문 대신 이것만 스냅샷에 남긴다."""
    payload = {"reads": _reads_without_text(reads), "query": query or None, "social": social or ""}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
                          .encode("utf-8")).hexdigest()


def read_snapshot(decision, *, at, selected, trip, turns):
    """좌표·고객 문장을 저장하지 않고 해석 결과와 당시 문맥 ID만 남긴다."""
    if decision is None:
        return None
    effective = fact_first(decision)
    if effective.action != "answer_fact":
        return None
    previous = next((t for t in reversed(turns) if t.get("role") == "assistant"), {})
    focus = (previous.get("reply") or {}).get("focus") or {}
    kept_focus = {k: focus[k] for k in ("item_id", "version", "at", "source") if k in focus}
    return {"schema": 1, "trip_id": str(trip["trip_id"]), "base_version": trip["version"],
            "at": at.isoformat(), "selected": str(selected) if selected else None,
            "action": effective.action, "fact": effective.fact,
            "item_id": str(effective.item.item_id) if effective.item else None,
            "choices": [{"action": c["action"], "fact": c["fact"],
                         "item_id": str(c["item"].item_id) if c.get("item") else None}
                        for c in effective.choices],
            "focus": kept_focus, "query": effective.query,
            "read_signature": read_signature(effective.reads, effective.query, effective.social),
            "recoverable": effective.fact not in LOCATION_FACTS and not any(r["fact"] in LOCATION_FACTS for r in effective.reads)}


def is_read_record(record):
    if not isinstance(record, dict):
        return False
    if record.get("action") == "answer_fact":
        return True
    choices = record.get("choices") or []
    return (record.get("action") == "clarify" and bool(choices)
            and all(c.get("action") == "answer_fact" for c in choices))


def _legacy_cached_fact(case, message):
    """옛 off/defer는 분류 전 저장한 답만 반환한다. 새 계산은 허용하지 않는다."""
    from .trip_facts import fact_question

    state = case.get("state_json") or {}
    return (case["status"] == "classifying" and isinstance(state.get("answer"), str)
            and bool(state["answer"].strip()) and "decision" not in state
            and "conversation_dispatch" not in state and "subject_ref" not in state
            and not state.get("resume_requests") and not state.get("customer_input_history")
            and fact_question(message) is not None)


def lock_read_case(conn, *, tenant, case_id):
    """경합만 409로 바꾼다. 연결 장애 등은 원래 오류로 보존한다."""
    from psycopg.errors import LockNotAvailable

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s AND case_id=%s FOR UPDATE NOWAIT",
                        (tenant, case_id))
            if cur.fetchone() is None:
                raise LookupError("case not found")
    except LockNotAvailable:
        conn.rollback()
        raise StateConflict("같은 읽기 요청이 처리 중입니다. 잠시 뒤 같은 요청 번호로 확인해 주세요.") from None
    case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
    state = case.get("state_json") or {}
    if ("conversation_dispatch" in state or "subject_ref" in state
            or state.get("resume_requests") or state.get("customer_input_history")):
        raise StateConflict(NEW_REQUEST)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM agent_runs WHERE tenant_id=%s AND case_id=%s "
                    "AND status IN ('active','running','resuming') LIMIT 1", (tenant, case_id))
        if cur.fetchone():
            raise StateConflict("같은 요청의 담당 팀이 실행 중입니다")
    return case


def restore(snapshot, *, state, trip, items):
    """저장된 읽기 증거를 재검사한다. 모델 raw 값으로 쓰기 행동을 읽기로 바꾸지 않는다."""
    record = state.get("decision") or {}
    if not is_read_record(record) or snapshot.get("schema") != 1 or snapshot.get("action") != "answer_fact":
        raise StateConflict(NEW_REQUEST)
    original_fact = (record.get("choices") or [{}])[0].get("fact") if record.get("action") == "clarify" else record.get("fact")
    original_fact = "detail" if original_fact == "none" and record.get("action") == "clarify" else original_fact
    if (snapshot.get("fact") != original_fact or snapshot.get("fact") not in FACTS
            or snapshot.get("fact") in LOCATION_FACTS or snapshot.get("recoverable") is not True
            or snapshot.get("trip_id") != str(trip["trip_id"])
            or snapshot.get("base_version") != trip["version"]):
        raise StateConflict(NEW_REQUEST)
    if record.get("action") == "answer_fact" and record.get("item_id") != snapshot.get("item_id"):
        raise StateConflict(NEW_REQUEST)
    by_id = {str(i.item_id): i for i in items}
    item_id = snapshot.get("item_id")
    if item_id and item_id not in by_id:
        raise StateConflict(NEW_REQUEST)
    if record.get("action") == "clarify" and item_id:
        if record["choices"][0].get("item") != by_id[item_id].title:
            raise StateConflict(NEW_REQUEST)
    try:
        at = datetime.fromisoformat(snapshot["at"])
        if at.tzinfo is None:
            raise ValueError("naive time")
        selected = UUID(snapshot["selected"]) if snapshot.get("selected") else None
    except (KeyError, TypeError, ValueError):
        raise StateConflict(NEW_REQUEST) from None
    choices = []
    for choice in snapshot.get("choices") or []:
        if choice.get("action") != "answer_fact" or choice.get("fact") not in FACTS:
            raise StateConflict(NEW_REQUEST)
        choices.append({"action": "answer_fact", "fact": choice["fact"],
                        "item": by_id.get(choice.get("item_id")), "change": None})
    # 질문 목록은 Case 에 저장된 결정에서 꺼내고, 스냅샷의 서명과 맞을 때만 쓴다.
    #   서명이 없는 옛 스냅샷은 복수 질문을 하나로 줄여 답할 수 있어 새 요청으로 돌린다.
    reads, query, social = _reads_without_text(record.get("reads")), record.get("query"), record.get("social") or ""
    signature = snapshot.get("read_signature")
    if (not signature or signature != read_signature(reads, query, social)
            or snapshot.get("query") != query):
        raise StateConflict(NEW_REQUEST)
    decision = Decision("answer_fact", by_id.get(item_id), None, snapshot["fact"], None, "", choices=choices,
                        query=query, reads=reads, social=social)
    return decision, at, selected


def retry_read(conn, *, case, tenant, trip, items, actor_id, desk, store, message,
               request_id, policy_search, place_source, controller):
    state = case.get("state_json") or {}
    snapshot = state.get("fact_read_snapshot")
    record = state.get("decision") or {}
    # 완료 업무와 실제 변경 업무는 기존 중복·재시도 정책을 유지한다.
    if case["status"] not in ("classifying", "routing", "running"):
        return None
    if (not snapshot and not is_read_record(record) and not state.get("fact_read_cached")
            and not _legacy_cached_fact(case, message)):
        return None
    case_id = case["case_id"]
    case = lock_read_case(conn, tenant=tenant, case_id=case_id)
    state = case.get("state_json") or {}
    if case["status"] not in ("classifying", "routing", "running"):
        return None
    if state.get("decision") and not is_read_record(state["decision"]):
        raise StateConflict(NEW_REQUEST)
    # 저장 완료된 읽기 답을 새 재전송 입력으로 다시 계산하지 않는다.
    if state.get("answer") and (is_read_record(state.get("decision") or {})
                                or state.get("fact_read_cached") is True or _legacy_cached_fact(case, message)):
        reply = state.get("chat_reply") or {}
        return {"case_id": str(case_id), "case_status": str(case["status"]), "status": "duplicate",
                "answer": state["answer"],
                **{k: v for k, v in reply.items() if k in ("choices", "choices_title", "more", "answer_web")}}
    if not isinstance(snapshot, dict):
        raise StateConflict(NEW_REQUEST)
    decision, at, selected = restore(snapshot, state=state, trip=trip, items=items)
    from .trip_messages import _run_decision

    return _run_decision(conn, tenant=tenant, trip_id=UUID(str(trip["trip_id"])), case_id=case_id,
                         message=message, request_id=request_id, at=at, desk=desk, store=store,
                         items=items, decision=decision, failure=None, actor_id=actor_id,
                         policy_search=policy_search, place_source=place_source, selected=selected,
                         controller=controller, read_snapshot=snapshot)
