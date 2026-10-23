"""접수 식당 확인의 현재 작업 상태와 등록 경계. 기존 intake_reviews payload에 저장한다."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Callable
from uuid import uuid4

from . import review as review_module

DEFAULT_DEADLINE_S = 120.0
ACTIVE = frozenset({"pending", "running"})
AVAILABILITY = frozenset({"found", "open_at", "closed_day", "business"})
#: 등록을 막을 수 있는 이용 가능성 확인 — `[2026-10-16 사용자 결정]` 「못 찾음」(found)은 자료 부족이라 「확인 못 함」이지 이용 불가가 아니다
BLOCKING = frozenset({"open_at", "closed_day", "business"})
CONDITIONS = frozenset({"dietary", "kids", "payment"})


def fingerprint(payload: dict[str, Any], notes: str = "", *, notes_fingerprint: str | None = None) -> str:
    """현재 식사 입력·원문·동적 조건 답을 결합한다. 고정 설문 응답은 별도다."""
    meals = [{key: item.get(key) for key in ("id", "kind", "title", "date", "starts_at", "ends_at", "place")}
             for item in payload.get("items") or [] if item.get("kind") == "dining"]
    source = {"meals": meals, "notes": notes_fingerprint or hashlib.sha256(notes.encode("utf-8")).hexdigest()}
    from .dining_questions import answers
    clarified = answers(payload)
    if clarified:
        source["dining_answers"] = [{k: q[k] for k in ("id", "quote", "attribute", "required", "answer")} for q in clarified]
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _now(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _date(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


def _deadline_error(metadata: dict[str, Any], revision: int, now: datetime) -> str | None:
    deadline = _date(metadata.get("deadline_at"))
    if metadata.get("revision") != revision or not metadata.get("run_id") or deadline is None:
        return "dining_judge_state_invalid"
    return "dining_judge_deadline_exceeded" if now >= deadline else None


def _failed(payload: dict[str, Any], error_code: str, now: datetime) -> dict[str, Any]:
    # `[2026-10-16 사용자 결정]` 실패는 「확인 못 함」 — 다시 확인은 두되 등록은 막지 않는다(이미 합친 검증된 bad 는 그대로 막는다)
    payload["dining_judge"] = {**payload["dining_judge"], "status": "failed",
                               "completed_at": now.isoformat(), "error_code": error_code}
    payload["dining_judge"]["blocks_registration"] = registration_issue(payload) is not None
    return payload


def prepare(conn, tenant_id: str, intake_id: Any, revision: int, payload: dict[str, Any], *, enabled: bool,
            now: datetime | None = None, deadline_s: float = DEFAULT_DEADLINE_S, notes: str = "") -> dict[str, Any]:
    """응답·review 상태 공개 전에 pending을 저장한다. 강제 재검증은 새 토큰을 만든다.

    부르는 쪽이 검사까지 저장한 같은 트랜잭션에서 호출한다. 잠금 뒤에 읽어 다른 작업이 합친 줄을 보존한다.
    식사가 없거나 판정이 꺼져 있으면 disabled이며 기존 일정 검사 동작을 유지한다.
    """
    with conn.transaction():
        state = review_module.intake_state(conn, tenant_id, intake_id)
        current = review_module.load(conn, tenant_id, intake_id, revision)
        if state is None or state[1] != revision or state[0] not in ("reading", "review"):
            return current or deepcopy(payload)
        current = deepcopy(current if current is not None else payload)
        meals = [i for i in current.get("items") or [] if i.get("kind") == "dining"]
        active = enabled and bool(meals)
        stamp = _now(now)
        days = len({i.get("date") for i in meals if i.get("date")}) or 1
        # 설정된 하루 예산 한 회분을 예약 대기로 남긴다. 고정된 별도 SLA를 만들지 않는다.
        budget = max(1.0, float(deadline_s))
        current["dining_judge"] = {
            "status": "pending" if active else "disabled", "revision": revision,
            "run_id": str(uuid4()) if active else None, "started_at": None,
            "deadline_at": (stamp + timedelta(seconds=budget * (days + 1))).isoformat()
            if active else None,
            "completed_at": None if active else stamp.isoformat(), "error_code": None,
            "blocks_registration": bool(active), "input_fingerprint": fingerprint(current, notes),
            "notes_fingerprint": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
        }
        current.pop("agent_judged", None)
        review_module.store(conn, tenant_id, intake_id, revision, current)
        return current


def refresh(conn, tenant_id: str, intake_id: Any, revision: int, payload: dict[str, Any] | None, *,
            now: datetime | None = None) -> dict[str, Any] | None:
    """현재 토큰을 잠금 안에서 다시 읽고 기한을 넘긴 작업을 failed로 저장한다. 옛 자료는 호환한다."""
    if not payload or not isinstance(payload.get("dining_judge"), dict):
        return payload
    with conn.transaction():
        state = review_module.intake_state(conn, tenant_id, intake_id)
        current = review_module.load(conn, tenant_id, intake_id, revision)
        if state != ("review", revision) or current is None:
            return current or payload
        metadata = current.get("dining_judge")
        if not isinstance(metadata, dict) or metadata.get("status") == "disabled":
            return current
        stamp = _now(now)
        error = _deadline_error(metadata, revision, stamp) if metadata.get("status") in ACTIVE else None
        expected = metadata.get("input_fingerprint")
        if expected and expected != fingerprint(current, notes_fingerprint=metadata.get("notes_fingerprint")):
            error = "dining_judge_input_changed"
        if error:
            _failed(current, error, stamp)
            review_module.store(conn, tenant_id, intake_id, revision, current)
        return current


def begin(conn, tenant_id: str, intake_id: Any, revision: int, run_id: str, *,
          now: datetime | None = None, input_fingerprint: str | None = None) -> dict[str, Any] | None:
    """이미 준비된 pending 한 건만 맡는다. LLM을 호출하기 전에 이 트랜잭션을 끝낸다."""
    with conn.transaction():
        state = review_module.intake_state(conn, tenant_id, intake_id)
        current = review_module.load(conn, tenant_id, intake_id, revision)
        metadata = (current or {}).get("dining_judge") or {}
        if state != ("review", revision) or metadata.get("run_id") != run_id or metadata.get("status") != "pending":
            return None
        stamp = _now(now)
        error = _deadline_error(metadata, revision, stamp)
        expected = metadata.get("input_fingerprint")
        if ((expected and expected != fingerprint(current, notes_fingerprint=metadata.get("notes_fingerprint")))
                or (input_fingerprint is not None and input_fingerprint != expected)):
            error = "dining_judge_input_changed"
        if error:
            _failed(current, error, stamp)
            review_module.store(conn, tenant_id, intake_id, revision, current)
            return None
        current["dining_judge"] = {**metadata, "status": "running", "started_at": stamp.isoformat()}
        review_module.store(conn, tenant_id, intake_id, revision, current)
        return current


def finish(conn, tenant_id: str, intake_id: Any, revision: int, run_id: str, *, error_code: str | None = None,
           update: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
           now: datetime | None = None) -> dict[str, Any] | None:
    """현재 실행 토큰만 끝낸다. update는 잠금 안에서 최신 검사에 결과를 합치는 순수 함수다."""
    with conn.transaction():
        state = review_module.intake_state(conn, tenant_id, intake_id)
        current = review_module.load(conn, tenant_id, intake_id, revision)
        metadata = (current or {}).get("dining_judge") or {}
        if (state != ("review", revision) or metadata.get("revision") != revision
                or metadata.get("run_id") != run_id or metadata.get("status") not in ACTIVE):
            return None
        stamp = _now(now)
        error_code = _deadline_error(metadata, revision, stamp) or error_code
        changed = metadata.get("input_fingerprint") != fingerprint(current, notes_fingerprint=metadata.get("notes_fingerprint"))
        if changed:
            error_code = "dining_judge_input_changed"
        if update is not None and not changed and error_code != "dining_judge_deadline_exceeded":
            current = update(current)
        current["dining_judge"] = {**metadata, "status": "failed" if error_code else "completed",
                                   "completed_at": stamp.isoformat(), "error_code": error_code}
        current["dining_judge"]["blocks_registration"] = registration_issue(current) is not None
        review_module.store(conn, tenant_id, intake_id, revision, current)
        return current


def registration_issue(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """기존 ready=false를 새 관문으로 쓰지 않는다. 확인 중이면 기다리고, 그 밖에는 검증된 이용 불가 · 명시된 필수 조건 bad 만 막는다.

    `[2026-10-16 사용자 결정]` 판정 실패(failed)는 「확인 못 함」이다 — 등록을 막지 않고 실패 전에 합친 검증된 bad 만 본다.
    「못 찾음」(found)도 막지 않는다(`BLOCKING`). 조건 확인은 `required` 가 명시적으로 true 일 때만 필수다."""
    payload = payload or {}
    metadata = payload.get("dining_judge") or {}
    if metadata.get("status") in ACTIVE:
        return {"status": 409, "code": "intake_dining_check_pending",
                "message": "식당 확인을 마무리하고 있어요. 확인이 끝나면 등록해 주세요.",
                "detail": {"dining_judge": metadata}}
    if metadata.get("status") == "disabled":
        return None
    problems = []
    for item in payload.get("items") or []:
        if item.get("kind") != "dining":
            continue
        checks = []
        for row in item.get("rows") or []:
            agent = row.get("agent") or {}
            code = agent.get("check") or {"hours": "open_at", "closed": "closed_day"}.get(row.get("row"), row.get("row"))
            required = code in BLOCKING or (code in CONDITIONS and agent.get("required") is True)
            if (row.get("by") == "agent" and row.get("result") == "bad" and agent.get("validated") is True
                    and agent.get("verdict") == "bad" and agent.get("evidence") and required):
                checks.append({"check": code, "reason": row.get("text"), "evidence": agent["evidence"]})
        if checks:
            problems.append({"item_id": item.get("id"), "title": item.get("title"), "checks": checks})
    if problems:
        return {"status": 422, "code": "intake_dining_conditions_unmet",
                "message": "이용할 수 없거나 필수 조건에 맞지 않는 식당이 있어요. 해당 일정을 고쳐 주세요.",
                "detail": {"items": problems}}
    return None
