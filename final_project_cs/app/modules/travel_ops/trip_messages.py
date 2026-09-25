# -*- coding: utf-8 -*-
"""고객 **자유 문장** 한 통 처리 — 여행 API(`/v1/trips/{id}/messages`)와 시나리오 모드가 같이 쓴다.

    Case 생성 → 분류 → 신고 추출 → 여행 창구 → Case 닫기

★Case 는 코어의 한 문(`transition_case`)으로만 움직인다:
    CREATED → (분류) CLASSIFIED → ROUTED(여행 창구) → COMPLETED(= resolved)
  분류 실패는 `classify_case` 가 escalated 로 보낸다. 신고 내용을 못 뽑았거나 창구가
  받지 않는 문장이면 ROUTING_FAILED, 창구가 처리하지 못하면 GUARDRAIL_ESCALATED —
  **추측으로 일정을 바꾸지 않고 사람에게 넘긴다.**
★같은 `request_id` 는 Case 를 새로 만들지 않는다.
★재요청(「다른 안으로 바꿔 줘」, v11 §1) — 가장 최근에 바뀐 항목을 우리가 들고 있던
  「다른 안」으로 바꾼다. 무엇으로 바꿀지 모델이 지어내게 두지 않는다.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any
from uuid import UUID

from app.infrastructure.db.session import get_connection

from .itinerary import TripStore
from .trip_desk import TripDesk
from .trip_intake import extract

REGISTERED_TEAMS = frozenset({"activity", "dining", "mobility", "booking", "lodging", "flight"})


class TripNotFound(LookupError):
    pass


def _latest_changed_item(store: TripStore, trip_id: UUID):
    """가장 최근 버전에서 새로 바뀐, 「다른 안」을 가진 항목. 없으면 가장 뒤의 그런 항목."""
    with get_connection() as conn:
        trip, items = store.latest(conn, trip_id)
        previous = {i.item_id for i in store.items(conn, trip_id, trip["version"] - 1)} \
            if trip["version"] > 1 else set()
    candidates = [i for i in items if i.detail.get("alternates")]
    fresh = [i for i in candidates if i.item_id not in previous]
    pick = (fresh or candidates)
    return trip, (max(pick, key=lambda i: i.seq) if pick else None)


def handle_trip_message(*, tenant: str, trip_id: UUID, request_id: str, message: str,
                        at: datetime, classifier: Any, chat: Any, desk: TripDesk,
                        actor_id: str) -> dict[str, Any]:
    from app.application.classification import classify_case
    from app.application.routing import case_type_of
    from app.core.transition import transition_case
    from app.domain.events import EventType
    from app.infrastructure.db import repository
    from app.infrastructure.ollama_chat import OllamaError

    store = TripStore(tenant)
    marker = {"trip_message": {"trip_id": str(trip_id), "request_id": request_id}}
    with get_connection() as conn:
        try:
            trip, _ = store.latest(conn, trip_id)
        except KeyError:
            raise TripNotFound(str(trip_id)) from None
        with conn.cursor() as cur:
            cur.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s "
                        "AND state_json @> %s::jsonb", (tenant, json.dumps(marker)))
            existing = cur.fetchone()
        if existing:
            case = repository.get_case(conn, tenant_id=tenant, case_id=existing[0])
            return {"status": "duplicate", "case_id": str(existing[0]),
                    "case_status": str(case["status"])}
        with conn.transaction():
            case_id = repository.create_case(conn, tenant_id=tenant,
                                             customer_id=trip["customer_id"],
                                             subject=message, state_json=marker)
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                            event_type=EventType.CREATED,
                            payload={"channel": "trip_message", "message": message},
                            actor_type="api", actor_id=actor_id)
        # ★분류는 생성 트랜잭션 **밖**에서(v8 §3-A) — REST 접수와 같은 이유다.
        event = classify_case(conn, tenant_id=tenant, case_id=case_id, text=message,
                              classifier=classifier, actor_id=actor_id)

        def move(event_type, payload):
            case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
            with conn.transaction():
                transition_case(conn, tenant_id=tenant, case_id=case_id,
                                expected_version=case["version"], event_type=event_type,
                                payload=payload, actor_type="api", actor_id=actor_id)

        def view(extra):
            case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
            return {"case_id": str(case_id), "case_status": str(case["status"]),
                    "classification": {"intent": case.get("intent"),
                                       "issue_code": case.get("issue_code")}, **extra}

        if event is not EventType.CLASSIFIED:
            return view({"status": "escalated", "reason": "classification_failed"})
        try:
            report = extract(message, chat) if chat is not None else None
            why = "no_extractor" if chat is None else "not_understood"
        except OllamaError as exc:
            report, why = None, f"extractor_failed: {exc}"[:120]
        if report is None or report["type"] == "other":
            reason = why if report is None else "not_a_trip_report"
            move(EventType.ROUTING_FAILED, {"failure_code": reason})
            return view({"status": "escalated", "reason": reason, "report": report})

        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        # ★분류가 `other` 여도(실측: 품절 문장) 처리는 추출값으로 간다 — 담당은 여행 창구로 적는다.
        team = case_type_of(case.get("issue_code") or "", fallback="trip_desk") or "trip_desk"
        if team not in REGISTERED_TEAMS:
            team = "trip_desk"
        move(EventType.ROUTED, {"owner_team_id": team, "capability": f"trip_desk.{report['type']}"})

    if report["type"] == "delay":
        outcome = desk.report_delay(trip_id=trip_id, at=at, minutes=report["minutes"],
                                    message=message, request_id=request_id)
    elif report["type"] == "closed":
        outcome = desk.report_closed(trip_id=trip_id, at=at, message=message,
                                     request_id=request_id)
    elif report["type"] == "stock_out":
        outcome = desk.ask_nearby_store(trip_id=trip_id, at=at, products=report["products"],
                                        message=message, request_id=request_id)
    else:                                            # change — 재요청
        current, target = _latest_changed_item(store, trip_id)
        outcome = ({"status": "no_alternate"} if target is None else
                   desk.swap_alternate(trip_id=trip_id, item_id=target.item_id,
                                       base_version=current["version"], message=message,
                                       request_id=request_id))
    with get_connection() as conn:
        def move2(event_type, payload):
            case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
            with conn.transaction():
                transition_case(conn, tenant_id=tenant, case_id=case_id,
                                expected_version=case["version"], event_type=event_type,
                                payload=payload, actor_type="api", actor_id=actor_id)
        # ★`asked` — 「먼저 물어봐줘」·「변경 안 할 일정」이라 바꾸지 않고 물었다(D-020). 처리한 것이다 —
        #   답은 묻는 문장이고, 고객은 계획서 링크·웹에서 고른다. 사람에게 넘길 일이 아니다.
        if outcome.get("status") in ("adjusted", "answered", "still_fits", "asked"):
            answer = (outcome.get("notice") or {}).get("text") or outcome.get("text") \
                or outcome.get("status")
            ref = f"trip:{trip_id}:" + (f"v{outcome['version']}" if outcome.get("version")
                                         else str(outcome.get("status")))
            # ★컨트롤러와 같은 모양 — 답은 `state_patch.answer` 로 Case 에 들어간다.
            move2(EventType.COMPLETED, {"answer_ref": ref, "state_patch": {"answer": answer}})
        else:
            move2(EventType.GUARDRAIL_ESCALATED, {"guardrail": "trip_desk",
                                                  "observed": str(outcome.get("status"))})
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        return {"case_id": str(case_id), "case_status": str(case["status"]),
                "classification": {"intent": case.get("intent"),
                                   "issue_code": case.get("issue_code")},
                "status": outcome.get("status"), "report": report, "outcome": outcome}


__all__ = ["TripNotFound", "handle_trip_message"]
