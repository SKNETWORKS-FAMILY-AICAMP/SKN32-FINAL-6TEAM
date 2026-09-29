# -*- coding: utf-8 -*-
"""여행 Case 의 **규정 질문** — 일정을 바꾸지 않고 규정 근거로 답한다. `[2026-09-25]`

★인계(triPilot : RAG 세션, 2026-09-25 실측): 여행을 가리키는 Case 는 전부 `*.itinerary`(규정 면제)로 갔고,
  고객 문장은 여섯 종류로만 읽혀
    「비 오면 오후 한강 카약 취소돼요? 위약금 있어요?」 → other  → 사람
    「저녁 식당에 아이 데려가도 되나요」                 → other  → 사람
    「내일 경복궁 휴관 아니에요?」                      → closed ← 질문이 「닫혔다」 신고로 둔갑
  규정 질문 셋 중 규정으로 간 것이 0건이었다. 여행 코퍼스에는 답이 있었다.
★이 시험의 「모델」은 그 실측 출력을 그대로 흉내 낸다 — 그 출력을 **실제 검증 규칙**(`trip_intake.validate`)이
  질문으로 돌리는지, 그다음 Case 가 규정을 읽고 근거를 달아 답하는지를 끝까지 본다.

재현:

    python -m pytest tests/scenario/test_case_question.py -v
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.context import PolicyChunk
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.case_engine import CaseEngine, cleanup_tenant
from app.modules.travel_ops.trip_intake import validate

from .test_case_version_day import Clock, _at, _latest, _seed, _sources

KAYAK = "비 오면 오후 한강 카약 취소돼요? 위약금 있어요?"
CHILD = "저녁 식당에 아이 데려가도 되나요"
PALACE = "내일 경복궁 휴관 아니에요?"
DELAY = "점심 식당 70분 늦을 것 같아요"
SWAP = "다른 식당으로 바꿔줘"

#: 실측한 모델 출력(triPilot : RAG, 2026-09-25) — 앞의 둘은 other, 경복궁은 closed 로 둔갑했다
MODEL = {KAYAK: {"type": "other"}, CHILD: {"type": "other"}, PALACE: {"type": "closed"},
         DELAY: {"type": "delay", "minutes": 70}, SWAP: {"type": "change"}}

#: 여행 코퍼스 모양의 규정 조각 — 문구는 시험용이다. 출처 id 가 답에 실리는지를 본다
CORPUS = [
    PolicyChunk("t_doc_04", 4, "비 때문에 업체가 운영을 중단하고 취소를 통지하면 고객에게 위약금을 물리지 않는다. "
                "고객이 먼저 취소하면 예약 조건의 기한을 따른다.", 0.82, "travel_cancellation"),
    PolicyChunk("t_doc_12", 2, "아이 동반 가능 여부는 식당이 밝힌 사실로만 안내한다. 확인되지 않았으면 가능하다고 말하지 않는다.",
                0.77, "travel_dining"),
    PolicyChunk("t_doc_08", 1, "궁궐·박물관의 정기 휴관일은 관리 기관 공지를 따른다. 휴관이면 같은 시간대 대체 활동을 제안한다.",
                0.74, "travel_activity"),
]
_KEYWORDS = {"t_doc_04": ("비", "취소", "위약금"), "t_doc_12": ("아이", "식당"), "t_doc_08": ("휴관", "경복궁")}


def _search(tenant_id, query, scopes):
    """질문과 겹치는 단어가 있는 조각만, 그 Team 의 scope 안에서."""
    found = [c for c in CORPUS if c.scope in scopes and any(w in query for w in _KEYWORDS[c.document_id])]
    return found


def _classifier(message: str) -> dict[str, str]:
    if "바꿔" in message:
        return {"intent": "adjust_reject", "issue_code": "other", "sentiment": "neutral"}
    code = "dining_hours" if ("식당" in message or "늦" in message) else "activity_other"
    return {"intent": "confirm_request", "issue_code": code, "sentiment": "neutral"}


@pytest.fixture()
def world():
    tenant = "question_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("08:00"))
    check, route_events = _sources(clock)
    engine = CaseEngine(tenant_id=tenant, check=check, route_events=route_events, classifier=_classifier,
                        report_extractor=lambda text: validate(MODEL.get(text, {"type": "other"}), text),
                        clock=clock, policy_search=_search)
    yield {"tenant": tenant, "store": store, "trip_id": trip_id, "customer": customer, "engine": engine}
    cleanup_tenant(tenant)


def _ask(world, text, request_id):
    return world["engine"].message(customer_id=world["customer"], trip_id=world["trip_id"], text=text,
                                   request_id=request_id)


def _reading(world, case_id) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT state_json FROM customer_cases WHERE tenant_id=%s AND case_id=%s",
                    (world["tenant"], case_id))
        return ((cur.fetchone()[0] or {}).get("interpretation") or {}).get("report") or {}


@pytest.mark.parametrize("text, team, source, item", [
    (KAYAK, "activity", "t_doc_04#c4", None),                 # 이 여행에 카약 항목은 없다 — 일반 답
    (CHILD, "dining", "t_doc_12#c2", "저녁"),                  # 「저녁 식당」 → 저녁 식사 항목
    (PALACE, "activity", "t_doc_08#c1", "경복궁"),             # ★closed 로 둔갑하던 문장
])
def test_a_rules_question_is_answered_from_the_rules_and_the_plan_stays(world, text, team, source, item):
    view = _ask(world, text, f"q-{source}")
    assert _reading(world, view["case_id"]) == {"type": "question"}          # ★질문으로 읽혔다
    assert view["case_status"] == "resolved" and view["owner_team_id"] == team, view
    # ★`[2026-09-29 사용자 지시]` 근거 id 는 고객 문장에 싣지 않는다 — 그 절의 **고객용 문장**이 실렸는지로 본다
    from app.modules.travel_ops.itinerary_team import customer_lines

    assert customer_lines()[source] in view["answer"] and "규정에서 찾은 내용" in view["answer"], view["answer"]
    assert "t_doc_" not in view["answer"]
    assert "일정은 바꾸지 않았어요" in view["answer"]
    if item:
        assert view["answer"].split(" — ")[0].find(item) >= 0, view["answer"]
    assert view["applied_actions"] == [] and _latest(world)[0]["version"] == 1   # ★일정을 안 바꿨다


def test_the_two_reports_stay_what_they_were(world):
    late = _ask(world, DELAY, "r-late")
    assert _reading(world, late["case_id"]) == {"type": "delay", "minutes": 70}
    assert "규정에서 찾은 내용" not in (late["answer"] or "")
    swap = _ask(world, SWAP, "r-swap")
    assert _reading(world, swap["case_id"]) == {"type": "change"}
    assert "규정에서 찾은 내용" not in (swap["answer"] or "")


def test_a_question_with_no_matching_rule_goes_to_a_person_not_to_a_guess(world):
    """규정이 0건이면 지어내지 않는다 — 근거 없는 Case 는 사람에게(degraded 또는 「모름」)."""
    MODEL["이 근처에 주차 되나요?"] = {"type": "other"}
    try:
        view = _ask(world, "이 근처에 주차 되나요?", "q-none")
    finally:
        MODEL.pop("이 근처에 주차 되나요?")
    assert _reading(world, view["case_id"]) == {"type": "question"}
    assert view["case_status"] == "escalated" and not view["answer"], view
    assert _latest(world)[0]["version"] == 1


def test_without_a_policy_search_a_question_is_escalated_not_answered():
    """시나리오 모드처럼 규정 검색을 안 넣은 조립 — 검색 실패는 degraded 로 사람에게 간다."""
    tenant = "question_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("08:00"))
    check, route_events = _sources(clock)
    engine = CaseEngine(tenant_id=tenant, check=check, route_events=route_events, classifier=_classifier,
                        report_extractor=lambda text: validate(MODEL.get(text, {"type": "other"}), text),
                        clock=clock)
    try:
        view = engine.message(customer_id=customer, trip_id=trip_id, text=PALACE, request_id="q-nopolicy")
        assert view["case_status"] == "escalated" and not view["answer"], view
        with get_connection() as conn:
            assert store.latest(conn, trip_id)[0]["version"] == 1
    finally:
        cleanup_tenant(tenant)
