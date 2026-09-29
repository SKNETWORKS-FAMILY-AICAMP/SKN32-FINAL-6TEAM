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
import logging
from typing import Any, Callable
from uuid import UUID

from app.infrastructure.db.session import get_connection

from .itinerary import TripStore
from .trip_desk import TripDesk
from .trip_intake import extract

logger = logging.getLogger(__name__)

REGISTERED_TEAMS = frozenset({"activity", "dining", "mobility", "booking", "lodging", "flight"})


class TripNotFound(LookupError):
    pass


#: 끼니 말 → 시작 시각 범위(시). 「점심 바꿔 줘」처럼 식당이라는 말이 없어도 식사를 가리킨다
_MEALS = {"아침": (0, 11), "조식": (0, 11), "브런치": (9, 13), "점심": (11, 15), "중식": (11, 15),
          "저녁": (17, 24), "석식": (17, 24)}


def _change_target(items: list[Any], message: str, selected: UUID | None, at: datetime):
    """「바꿔 줘」가 가리키는 식사·활동.

    ★`[2026-09-29 ui 세션 지적]` **문장이 분명히 말하면 문장이 이긴다** — 경복궁을 눌러 둔 채 「점심 식당 바꿔 줘」라고
      쓰면 점심이 바뀌어야 한다(전에는 화면에서 고른 일정이 먼저라 경복궁이 바뀌었다). 순서:
      ①번호(「2번」 = 식사·활동을 시각 순으로 센 차례) ②이름(제목·장소 이름의 단어) ③끼니(「점심」 — 그 시간대 식사,
      여럿이면 지금 날짜의 것 → 다음 것) ④화면에서 고른 일정. 모르면 None(부르는 쪽이 들고 있던 안 · 다음 일정으로).
    """
    import re

    from .itinerary_team import mentioned_item

    text = message or ""
    stops = sorted((i for i in items if i.kind in ("dining", "activity")), key=lambda i: (i.starts_at, i.seq))
    number = re.search(r"(\d+)\s*번", text)
    if number and 1 <= int(number.group(1)) <= len(stops):
        return stops[int(number.group(1)) - 1]
    named = mentioned_item(stops, text)
    if named is not None:
        return named
    for word, (start, end) in _MEALS.items():
        if word in text:
            meals = [i for i in stops if i.kind == "dining" and start <= i.starts_at.hour < end]
            today = [i for i in meals if i.starts_at.date() == at.date()]
            upcoming = [i for i in meals if i.starts_at >= at]
            found = (today or upcoming or meals or [None])[0]
            if found is not None:
                return found
    if selected is not None:
        return next((i for i in stops if i.item_id == selected), None)
    return None


def _rollback_target(store: TripStore, trip_id: UUID, items: list[Any], message: str,
                     selected: UUID | None, at: datetime) -> tuple[int | None, str | None]:
    """번호 없는 되돌리기 — (되돌릴 버전, None) 또는 (None, 되묻는 문장).

    ★`[2026-09-29 사용자 지적 · ui 세션 합의안 4번]` 모델이 번호를 만들지 않는다. 서버가 정한다:
      ①문장·화면이 가리키는 항목(`_change_target` — 번호 · 이름 · 끼니 · 고른 일정)이 있으면 **그 항목이 바뀐 버전**을
        찾아(안 바뀐 항목은 버전을 건너 같은 id 로 이어진다) 그 직전 버전으로. 그 뒤에 다른 변경이 끼었으면 되돌리지 않고 되묻는다
        (되돌리면 뒤 변경까지 함께 돌아간다).
      ②가리키는 항목이 없으면 **가장 최근 변경**(「방금 바꾼 것」)의 직전 버전으로.
    예: v1 등록 → v2 저녁을 금용문으로 → 「금용문 이전 식당으로 되돌려」 = v1 로.
    """
    target = _change_target(items, message, selected, at)
    with get_connection() as conn:
        history = store.versions(conn, trip_id)
        latest = history[-1]["version"] if history else 1
        if latest <= 1:
            return None, "되돌릴 변경이 없어요 — 이 여행은 처음 만든 일정 그대로예요."
        if target is None:
            return latest - 1, None
        introduced = latest
        while introduced > 1 and target.item_id in {i.item_id for i in store.items(conn, trip_id, introduced - 1)}:
            introduced -= 1
    if introduced <= 1:
        return None, f"「{target.title}」은(는) 처음 일정 그대로라 되돌릴 변경이 없어요."
    if introduced != latest:
        return None, (f"「{target.title}」은(는) {introduced}번 일정에서 바뀌었고, 그 뒤에 다른 변경이 "
                      f"{latest - introduced}번 더 있었어요. 되돌리면 그 변경도 함께 되돌아가요 — 괜찮으시면 "
                      f"「{introduced - 1}번 일정으로 되돌려」라고 말씀해 주세요.")
    return introduced - 1, None


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


def _finish_fact_case(*, tenant: str, case_id: UUID, trip_id: UUID, message: str, classifier: Any,
                      actor_id: str, fact: str, answer: str) -> bool:
    """사실 질문 Case 를 끝낸다 — 분류하고, 되면 담당을 적고 완료로. 분류가 실패하면 기록만 남기고(escalated —
    모델 장애를 운영이 본다) False. ★이 여행의 사실을 묻는 말(하루 요약 · 일정 상세 · 다음 일정 · 예약 · 주소 ·
    운영시간 · 이동)은 규정 검색이 아니라 여행 기록으로 답한다(`trip_facts.py`) — 답은 이미 나갔다. 여기는 기록이다."""
    from app.application.classification import classify_case
    from app.application.routing import case_type_of
    from app.core.transition import transition_case
    from app.domain.events import EventType
    from app.infrastructure.db import repository

    try:
        with get_connection() as conn:
            event = classify_case(conn, tenant_id=tenant, case_id=case_id, text=message, classifier=classifier,
                                  actor_id=actor_id, state_patch={"answer": answer})
            if event is not EventType.CLASSIFIED:
                return False
            case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
            team = case_type_of(case.get("issue_code") or "", fallback="trip_desk") or "trip_desk"
            if team not in REGISTERED_TEAMS:
                team = "trip_desk"
            for event_type, payload in ((EventType.ROUTED, {"owner_team_id": team, "capability": "trip_desk.fact"}),
                                        (EventType.COMPLETED, {"answer_ref": f"trip:{trip_id}:fact:{fact}",
                                                               "state_patch": {"answer": answer}})):
                case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
                with conn.transaction():
                    transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=case["version"],
                                    event_type=event_type, payload=payload, actor_type="api", actor_id=actor_id)
            return True
    except Exception:            # noqa: BLE001 — 뒤에서 돌 때 죽으면 아무도 모른다. 세어 남긴다(조용히 넘기지 않는다)
        logger.exception("fact case finish failed case=%s", case_id)
        return False


def handle_trip_message(*, tenant: str, trip_id: UUID, request_id: str, message: str,
                        at: datetime, classifier: Any, chat: Any, desk: TripDesk,
                        actor_id: str, policy_search: Any = None, place_source: Any = None,
                        defer: Callable[[Callable[[], None]], None] | None = None,
                        selected_item_id: UUID | None = None) -> dict[str, Any]:
    """★`[2026-09-28]` **어떤 결과로 끝나든 `answer`(고객에게 보일 문장)를 싣는다** — `trip_replies.py` 머리.
    질문은 규정 근거로 답하고(`policy_search`, 없으면 못 찾았다고 답한다), 잡담·모호한 말은 할 수 있는 일과
    이 여행의 사실로 답한다. 답은 서버가 가진 사실로만 만든다.

    `defer` — ★`[2026-09-29]` 사실 질문의 **분류를 응답 뒤로** 미루는 자리(웹 입구가 넣는다). 모델이 식어 있으면
    분류가 30초 넘게 걸려 답이 기록으로 이미 만들어져 있는데도 「하루 일정 요약」이 34.8·33.5초 걸렸다(ui 세션 실측,
    깨어 있으면 2.0·2.1초). 넣으면 사실 질문은 곧바로 답하고 분류·완료 기록은 뒤에서 한다 — 분류는 **그대로 한다**
    (모든 Case 가 분류를 거치고 실패는 기록한다, CLAUDE.md §1). 에이전트 입구는 넣지 않아 지금처럼 끝까지 기다린다."""
    from app.application.classification import classify_case
    from app.application.routing import case_type_of
    from app.core.transition import transition_case
    from app.domain.events import EventType
    from app.infrastructure.db import repository
    from app.infrastructure.ollama_chat import OllamaError

    store = TripStore(tenant)
    marker = {"trip_message": {"trip_id": str(trip_id), "request_id": request_id}}
    from app.core.settings import get_guardrails

    from . import trip_facts, trip_replies

    with get_connection() as conn:
        try:
            trip, items = store.latest(conn, trip_id)
        except KeyError:
            raise TripNotFound(str(trip_id)) from None
        with conn.cursor() as cur:
            cur.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s "
                        "AND state_json @> %s::jsonb", (tenant, json.dumps(marker)))
            existing = cur.fetchone()
        if existing:
            case = repository.get_case(conn, tenant_id=tenant, case_id=existing[0])
            before = (case.get("state_json") or {}).get("answer")
            return {"status": "duplicate", "case_id": str(existing[0]),
                    "case_status": str(case["status"]),
                    "answer": f"같은 요청을 이미 받았어요.{chr(10) + str(before) if before else ''}"}
        # ★`[2026-09-29]` **사실 질문의 답은 분류 전에 규칙으로 만든다**(모델을 안 쓴다) — 그리고 Case 기록에 **처음부터**
        #   싣는다. 분류가 뒤에서 도는 동안 같은 요청이 다시 와도 앞의 답이 나간다(아래 중복 경로)
        fact = trip_facts.fact_question(message)
        fact_answer = (trip_facts.fact_reply(fact, message=message, items=items, now=at, place_source=place_source)
                       if fact is not None else None)
        with conn.transaction():
            case_id = repository.create_case(conn, tenant_id=tenant,
                                             customer_id=trip["customer_id"], subject=message,
                                             state_json={**marker, **({"answer": fact_answer[0]} if fact_answer else {})})
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                            event_type=EventType.CREATED,
                            payload={"channel": "trip_message", "message": message},
                            actor_type="api", actor_id=actor_id)
        # ★사실 질문 — 분류(모델)가 실패해도 답은 나간다(전에는 「분류하지 못해 처리하지 못했어요」로 끝났다, 2026-09-29).
        #   `defer` 가 있으면 분류·완료 기록을 응답 **뒤로** 미룬다. 없으면 여기서 끝까지 한다
        if fact_answer is not None:
            finish = lambda: _finish_fact_case(tenant=tenant, case_id=case_id, trip_id=trip_id,  # noqa: E731
                                               message=message, classifier=classifier, actor_id=actor_id,
                                               fact=fact, answer=fact_answer[0])
            if defer is not None:
                defer(finish)
                pending = True
            else:
                pending, classified = False, finish()
            case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
            return {"case_id": str(case_id), "case_status": str(case["status"]),
                    "classification": {"intent": case.get("intent"), "issue_code": case.get("issue_code")},
                    "status": "answered", "reason": "trip_fact_answered",
                    **({"classification_pending": True} if pending else
                       {} if classified else {"classification_failed": True}),
                    "report": {"type": "question", "fact": fact}, "answer": fact_answer[0], "basis": fact_answer[1]}
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
            return view({"status": "escalated", "reason": "classification_failed",
                         "answer": trip_replies.not_understood_reply("classification_failed")})
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        team = case_type_of(case.get("issue_code") or "", fallback="trip_desk") or "trip_desk"
        if team not in REGISTERED_TEAMS:
            team = "trip_desk"
        try:
            report = extract(message, chat) if chat is not None else None
            why = "no_extractor" if chat is None else "not_understood"
        except OllamaError as exc:
            report, why = None, f"extractor_failed: {exc}"[:120]
        if report is None:
            answer = trip_replies.not_understood_reply(why)
            # ★답은 실패 전이에도 Case 에 남긴다(`state_patch`) — 같은 요청이 다시 오면 그 답을 그대로 싣는다
            move(EventType.ROUTING_FAILED, {"failure_code": why, "state_patch": {"answer": answer}})
            return view({"status": "escalated", "reason": why, "report": None, "answer": answer})
        # ★`[2026-09-28]` 질문 · 그 밖 — 전에는 답 없이 escalated 로 끝났다(화면이 「담당자에게 넘겼어요」를 채웠다).
        #   질문은 **일정 사실 + 문턱을 넘은 규정 조각**으로 답한다(`*.itinerary_question` 과 같은 `question_answer`).
        #   그 밖(잡담 · 인사 · 모호한 말)은 할 수 있는 일과 이 여행의 사실로 답한다. ★일정은 바꾸지 않는다 —
        #   아래 「그 밖 = 다른 안으로 바꾸기」로 새지 않게 여기서 끝낸다.
        if report["type"] in ("question", "other"):
            if report["type"] == "question":
                status, answer, basis = trip_replies.question_reply(
                    message=message, items=items, tenant_id=tenant, policy_search=policy_search,
                    scopes=list(trip_replies.QUESTION_SCOPES),
                    min_score=float(get_guardrails().get("travel.question.min_policy_score")), now=at)
                reason = "question_answered" if status == "answered" else "question_needs_policy_answer"
            else:
                status, answer, basis = "answered", trip_replies.other_reply(items, at), {}
                reason = "not_a_trip_report"
            if status == "answered":
                move(EventType.ROUTED, {"owner_team_id": team, "capability": f"trip_desk.{report['type']}"})
                move(EventType.COMPLETED, {"answer_ref": f"trip:{trip_id}:{report['type']}",
                                           "state_patch": {"answer": answer}})
            else:
                move(EventType.ROUTING_FAILED, {"failure_code": reason, "state_patch": {"answer": answer}})
            return view({"status": status, "reason": reason, "report": report, "answer": answer,
                         "basis": basis})

        # ★분류가 `other` 여도(실측: 품절 문장) 처리는 추출값으로 간다 — 담당은 여행 창구로 적는다.
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
    elif report["type"] == "rollback":
        # ★`[2026-09-26]` 전에는 이 분기가 없어 「N번 일정으로 되돌려 주세요」가 아래 「다른 안으로 바꾸기」로
        #   떨어졌다 — 되돌리는 대신 **다른 장소로 바꿨다**(시험으로 확인, triPilot : RAG 세션이 코드를 읽고 찾았다).
        #   기준 버전은 지금 최신 — 그 사이 바뀌었으면 되돌리기가 `stale` 로 답한다.
        with get_connection() as conn:
            current, latest_items = store.latest(conn, trip_id)
        to_version, ask = ((int(report["to_version"]), None) if report.get("to_version")
                           else _rollback_target(store, trip_id, latest_items, message, selected_item_id, at))
        outcome = ({"status": "ask_rollback", "text": ask} if to_version is None else
                   desk.rollback(trip_id=trip_id, base_version=current["version"], to_version=to_version,
                                 message=message, request_id=request_id))
    elif report["type"] == "change":                 # 재요청 — 다른 안으로
        # ★`[2026-09-29 사용자 지적]` 들고 있던 「다른 안」이 없으면 **그 자리에서 찾는다**(`plan_fresh_alternate`).
        #   전에는 감시가 한 번 고친 항목만 봐서, 막 만든 일정은 늘 「바꿀 수 있는 다른 안이 없어요」였다.
        #   어느 항목인가: 화면에서 고른 일정 → 문장(번호 · 이름 · 끼니) → 들고 있던 안이 있는 항목 → 다음 일정
        with get_connection() as conn:
            current, latest_items = store.latest(conn, trip_id)
        target = _change_target(latest_items, message, selected_item_id, at)
        if target is None:
            _, target = _latest_changed_item(store, trip_id)
        if target is None:
            stops = sorted((i for i in latest_items if i.kind in ("dining", "activity")),
                           key=lambda i: (i.starts_at, i.seq))
            target = next((i for i in stops if i.starts_at >= at), stops[0] if stops else None)
        if target is None:
            outcome = {"status": "no_alternate", "reason": "바꿀 식사·활동 일정이 없다"}
        elif target.detail.get("alternates"):
            outcome = desk.swap_alternate(trip_id=trip_id, item_id=target.item_id, base_version=current["version"],
                                          message=message, request_id=request_id)
        else:
            outcome = desk.fresh_alternate(trip_id=trip_id, item_id=target.item_id, base_version=current["version"],
                                           message=message, request_id=request_id)
    else:
        # ★모르는 종류는 어떤 처리로도 떨어뜨리지 않는다 — 사람에게
        outcome = {"status": f"unhandled_{report['type']}"}
    with get_connection() as conn:
        def move2(event_type, payload):
            case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
            with conn.transaction():
                transition_case(conn, tenant_id=tenant, case_id=case_id,
                                expected_version=case["version"], event_type=event_type,
                                payload=payload, actor_type="api", actor_id=actor_id)
        # ★`asked` — 「먼저 물어봐줘」·「변경 안 할 일정」이라 바꾸지 않고 물었다(D-020). 처리한 것이다 —
        #   답은 묻는 문장이고, 고객은 계획서 링크·웹에서 고른다. 사람에게 넘길 일이 아니다.
        answer = trip_replies.outcome_reply(outcome.get("status"), outcome, message)
        # ★`[2026-09-28]` 「바꿀 것 없음」(오늘 일정 없음 · 그 뒤 식사 없음 · 영향 없음 · 이미 바뀜)도 **답**이다 —
        #   `ANSWERS` 머리 주석이 그렇게 말하는데 여기 목록에 없어 사람 대기로 떨어졌다(ui 세션 실서버 시험).
        #   「바꿀 다른 안이 없음」(`no_alternate`)도 오류가 아니라 답이다 — 사람 대기는 버그·오류 리포트에만(사용자 결정)
        if outcome.get("status") in ("adjusted", "answered", "still_fits", "asked", "rolled_back",
                                     "not_today", "no_meal", "clear", "gone", "no_alternate", "ask_rollback"):
            ref = f"trip:{trip_id}:" + (f"v{outcome['version']}" if outcome.get("version")
                                         else str(outcome.get("status")))
            # ★컨트롤러와 같은 모양 — 답은 `state_patch.answer` 로 Case 에 들어간다.
            # ★`[2026-09-29 ui 세션 지적]` 무엇을 봤고 왜 안 됐는지(반경 · 떨어진 후보와 이유)도 남긴다 — 「없어요」만 남아
            #   기록으로 원인을 알 수 없었다
            kept = {k: outcome[k] for k in ("status", "reason", "radius_m", "rejected", "version") if k in outcome}
            move2(EventType.COMPLETED, {"answer_ref": ref, "state_patch": {"answer": answer, "trip_outcome": kept}})
        else:
            # ★`[2026-09-28]` 답을 남긴다 — 전에는 완료 전이에만 남겨, 「바꿀 것 없음」(`no_meal` 등) 뒤 같은 요청이 오면
            #   「같은 요청을 이미 받았어요」만 나가고 앞의 답이 빠졌다(시험을 조여서 찾았다)
            move2(EventType.GUARDRAIL_ESCALATED, {"guardrail": "trip_desk",
                                                  "observed": str(outcome.get("status")),
                                                  "state_patch": {"answer": answer}})
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        return {"case_id": str(case_id), "case_status": str(case["status"]),
                "classification": {"intent": case.get("intent"),
                                   "issue_code": case.get("issue_code")},
                "status": outcome.get("status"), "report": report, "outcome": outcome, "answer": answer}


__all__ = ["TripNotFound", "handle_trip_message"]
