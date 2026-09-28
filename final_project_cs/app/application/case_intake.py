"""Case 를 **여는 한 문** — 고객 접수(REST) · 감시가 여는 시스템 Case · 시나리오가 같이 쓴다.

★왜 뺐나(`[결정 2026-09-17]`). 전에는 이 절차가 `app/presentation/api/cases.py` 의
  라우트 안에만 있었다. 감시 루프가 Case 를 만들려면 HTTP 를 흉내 내거나 절차를
  복사해야 했다 — 복사본은 멱등·잠금 규칙이 조용히 갈린다(2026-09-01 멱등성 세 구멍).

★지키는 것(옮기기 전과 같다):
  - 같은 멱등 키는 Case 를 새로 만들지 않는다. 몸통이 다르면 `IdempotencyConflict`
  - 동시 요청은 advisory lock 으로 하나만 통과한다
  - **분류는 생성 트랜잭션 밖에서** 한다(v8 §3-A 결함 2)

★새로 붙은 것:
  - `subject_ref` — 확인기가 소유를 확인한 뒤에만 저장한다(`app/core/subjects.py`)
  - `labels` — 시스템이 여는 Case 는 무엇이 문제인지 **이미 안다.** LLM 분류를 부르지
    않고 그 라벨로 `CLASSIFIED` 를 남긴다. 사람이 쓴 글이 아니므로 추측할 것이 없다
  - `trigger_source` — v11 §4-B. 고객이 연 것인지 감시가 연 것인지 기록한다
  - `subject_interpreter` — `[2026-09-17]` 대상이 정해진 고객 Case 는 **분류 직전에** 문장을 해석해
    담당을 정한다. 실제 Gemma 로 재 보니 신고 추출(종류)은 정확한데 분류 접두는 자주 빗나갔다 —
    「점심에 70분 늦을 것 같아요」가 `activity_time_conflict` 로 가서 사람에게 넘어갔다.
    해석은 **트랜잭션 밖**에서 하고, 결과는 분류와 **같은 이벤트**의 `state_patch` 로 기록한다
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from app.application.classification import REQUIRED_LABELS, classify_case
from app.core.idempotency import idempotency_key as make_idempotency_key
from app.core.subjects import SubjectNotFound, SubjectUnsupported
from app.core.transition import transition_case
from app.domain.events import EventType


class IdempotencyConflict(RuntimeError):
    """같은 멱등 키가 다른 몸통의 요청에 쓰였다."""


@dataclass(frozen=True)
class OpenedCase:
    case_id: UUID
    created: bool


def open_case(conn: Any, *, repository: Any, tenant_id: str, customer_id: UUID, request_id: str,
              message: str, channel: str, actor_type: str, actor_id: str,
              idempotency_key: str | None = None, subject_ref: dict[str, Any] | None = None,
              subject_resolver: Callable[..., Any] | None = None, trigger_source: str = "customer",
              trigger: dict[str, Any] | None = None, labels: dict[str, str] | None = None,
              classifier: Callable[[str], dict[str, str]] | None = None,
              subject_interpreter: Callable[..., dict[str, Any]] | None = None) -> OpenedCase:
    key = idempotency_key or make_idempotency_key(
        tenant_id=tenant_id, request_id=request_id, action_type="case.create",
        business_subject=f"{customer_id}:{message}")
    fingerprint_source = f"{customer_id}:{message}:{channel}"
    if subject_ref:
        # ★대상이 다르면 다른 요청이다. 대상이 없는 옛 요청의 지문은 그대로 둔다(하위호환).
        fingerprint_source += ":" + json.dumps(subject_ref, sort_keys=True, default=str)
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{tenant_id}:{key}",))
            cur.execute("SELECT case_id, arguments_json FROM action_requests "
                        "WHERE tenant_id=%s AND idempotency_key=%s", (tenant_id, key))
            existing = cur.fetchone()
        if existing:
            existing_case_id, existing_args = existing
            stored = existing_args.get("body_sha256") if isinstance(existing_args, dict) else None
            if stored is not None and stored != fingerprint:
                raise IdempotencyConflict("same idempotency_key was used for a request with a different body")
            return OpenedCase(case_id=existing_case_id, created=False)

        state: dict[str, Any] = {"request_id": request_id, "trigger_source": trigger_source}
        if trigger:
            state["trigger"] = trigger
        if subject_ref:
            if subject_resolver is None:
                raise SubjectUnsupported("this assembly has no subject resolver")
            resolved = subject_resolver(conn, tenant_id=tenant_id, customer_id=customer_id,
                                        subject_ref=dict(subject_ref))
            state["subject_ref"] = resolved.subject_ref
            if resolved.routing_hint:
                state["routing_hint"] = resolved.routing_hint
                state["routing_hint_verified"] = bool(resolved.hint_is_verified)
        case_id = repository.create_case(conn, tenant_id=tenant_id, customer_id=customer_id,
                                         subject=message, state_json=state)
        transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=0,
                        event_type=EventType.CREATED, payload={"channel": channel, "message": message},
                        actor_type=actor_type, actor_id=actor_id)
        # ★Case 생성은 승인 대상이 아니라 이미 끝난 일 — 종결 상태로 남긴다(승인 큐 유령 항목 방지).
        repository.create_action_request(conn, tenant_id=tenant_id, case_id=case_id, action_type="case.create",
                                         arguments={"request_id": request_id, "body_sha256": fingerprint},
                                         idempotency_key=key, status="succeeded")

    # ── 생성 트랜잭션 밖 ──────────────────────────────────────────
    if labels is not None:
        if not all(str(labels.get(label) or "").strip() for label in REQUIRED_LABELS):
            raise ValueError(f"system case labels must fill {REQUIRED_LABELS}")
        with conn.transaction():
            transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=1,
                            event_type=EventType.CLASSIFIED,
                            payload={label: labels[label] for label in REQUIRED_LABELS},
                            actor_type=actor_type, actor_id=actor_id)
    else:
        patch: dict[str, Any] = {}
        if subject_interpreter is not None and state.get("subject_ref"):
            try:
                reading = subject_interpreter(text=message, subject_ref=state["subject_ref"]) or {}
            except Exception as exc:            # ★삼키지 않는다 — 실패를 상태에 남기고 분류 경로로 간다
                reading = {"error": f"{type(exc).__name__}: {exc}"[:200]}
            patch["interpretation"] = reading
            if reading.get("routing_hint"):
                patch["routing_hint"] = reading["routing_hint"]
                patch["routing_hint_verified"] = True
        classify_case(conn, tenant_id=tenant_id, case_id=case_id, text=message,
                      classifier=classifier, actor_id=actor_id, state_patch=patch or None)
    return OpenedCase(case_id=case_id, created=True)


__all__ = ["IdempotencyConflict", "OpenedCase", "SubjectNotFound", "SubjectUnsupported", "open_case"]
