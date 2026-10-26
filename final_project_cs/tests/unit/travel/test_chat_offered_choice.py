# -*- coding: utf-8 -*-
"""x600 74b2b232 결함(3) — 「다른 안」 선택지를 누르면 모델 없이 고른 안으로. `[2026-10-26]`

증거: 보고서 `wiki/records/reports/2026-10-26_x600_74b2b232_실서버확인.md`, case 8f6055e0(다른 데로) → 2b9fa1d1(choice 누름 → 한일옥),
1cff6b55(실내를 야외로 → 식당 no_alternate, 원출력 target_item=i2 · target_change=c6 · place_setting outdoor), 1caa81bc · bcb1050d(trip_desk, model_path 없음).
모든 바깥 서비스는 메모리 대역이다(모델 호출 없음).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import case_dispatch, offered_choice, trip_messages
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import plan_swap

KST = ZoneInfo("Asia/Seoul")
TRIP = uuid4()


# ── (3) 「다른 안」 선택지 → 모델 없이 고른 안 ─────────────────────────────────────────────

def _dining(name):
    return {"place_id": str(uuid4()), "name": name, "kind": "dining", "latitude": 37.57, "longitude": 126.99, "attributes": {}}


def _alt(place, note=None):
    return {"key": place["place_id"], "name": place["name"], "place_id": place["place_id"], "option": None, "option_label": None,
            "starts_at": "2030-11-02T13:00:00+09:00", "ends_at": "2030-11-02T14:00:00+09:00", **({"note": note} if note else {})}


def _after_fresh_swap():
    """x600 43 응답 뒤 판: 광장시장 → 하나면옥, 하나면옥이 다른 안(조선옥 · 순라길비비 · 인사동 옥정 + 원래 광장시장)을 들고 있다."""
    hana, joseon, sunra, okjeong, market = (_dining(n) for n in ("하나면옥", "조선옥", "순라길비비", "인사동 옥정", "광장시장"))
    more = [_alt(joseon), _alt(sunra), _alt(okjeong, "13:30으로 늦추면")]
    item = Item(item_id=uuid4(), seq=3, kind="dining", title="하나면옥", place_id=UUID(hana["place_id"]), place=hana,
                starts_at=datetime(2030, 11, 2, 13, tzinfo=KST), ends_at=datetime(2030, 11, 2, 14, tzinfo=KST),
                detail={"alternates": more + [_alt(market)]})
    places = {p["place_id"]: p for p in (hana, joseon, sunra, okjeong, market)}
    return item, places, more


def _team_state(more, trip_id=TRIP):
    """팀 경로 Case 기록(x600 8f6055e0 모양) — 마지막 결정에 to · kind · more_options, 적용 기록 있음."""
    return {"trip_message": {"trip_id": str(trip_id)}, "applied_actions": [{"result_ref": f"trip:{trip_id}:v4"}],
            "decisions": [{"itinerary": "customer_request", "from": "광장시장", "to": "하나면옥", "kind": "dining", "more_options": more}]}


def _turns(case_id):
    return [{"role": "customer", "text": "다른 데로 바꿔줘", "case_id": str(case_id)},
            {"role": "assistant", "text": "요청하신 대로 …", "case_id": str(case_id)}]


@pytest.fixture
def cases(monkeypatch):
    store: dict[str, dict] = {}
    from app.infrastructure.db import repository
    monkeypatch.setattr(repository, "get_case", lambda conn, *, tenant_id, case_id: store.get(str(case_id)))
    return store


def test_x600_choice_message_resolves_to_the_offered_alternate_without_the_model(cases):
    item, places, more = _after_fresh_swap()
    case_id = uuid4()
    cases[str(case_id)] = {"state_json": _team_state(more)}
    shown = [c for c, _ in case_dispatch.offered_alternates(cases[str(case_id)]["state_json"])]
    assert shown[0] == {"label": "식당 조선옥", "message": "하나면옥 대신 조선옥(으)로 바꿔 줘"}      # 공개 선택지 모양 그대로
    decision = offered_choice.decide(None, tenant="t", trip_id=TRIP, items=[item], message="하나면옥 대신 조선옥(으)로 바꿔 줘",
                                     turns=_turns(case_id))
    assert decision is not None and decision.action == "apply_change" and decision.item is item
    assert decision.raw == {"source": "offered_choice", "model_called": False, "choice": more[0]["key"],
                            "offered_case_id": str(case_id)}
    # 기존 팀 계산(plan_swap)이 그 key 로 고른 곳으로 바꾼다 — 한일옥 같은 새 후보로 가지 않는다
    plan = plan_swap(trip_version=4, base_version=4, items=[item], places_by_id=places, item_id=item.item_id,
                     choice=decision.raw["choice"], message="m", request_id="r", check=None, customer_pick=True)
    assert plan.summary["to"] == "조선옥"


def test_choice_request_carries_the_key_to_the_team(cases):
    item, _, more = _after_fresh_swap()
    case_id = uuid4()
    cases[str(case_id)] = {"state_json": _team_state(more)}
    decision = offered_choice.decide(None, tenant="t", trip_id=TRIP, items=[item], message="하나면옥 대신 순라길비비(으)로 바꿔 줘",
                                     turns=_turns(case_id))

    class Store:
        def latest(self, conn, trip_id):
            return {"trip_id": str(trip_id), "version": 4, "customer_id": str(uuid4())}, [item]

        def versions(self, conn, trip_id):
            return [{"version": 4, "reason": "customer_request"}]

    plan = trip_messages._dispatch_decision(None, controller=None, tenant="t", trip_id=TRIP, case_id=uuid4(),
                                            message="하나면옥 대신 순라길비비(으)로 바꿔 줘", at=datetime(2030, 11, 1, tzinfo=KST),
                                            store=Store(), items=[item], decision=decision, selected=None, actor_id="a",
                                            desk=None, prepare_only=True)
    assert plan["team_id"] == "dining" and plan["subject_ref"]["part_id"] == str(item.item_id)
    assert plan["subject_ref"]["request"]["choice"] == more[1]["key"]


@pytest.mark.parametrize("case", ["not_offered", "older_turn", "other_trip", "selected_other", "no_holder", "proposal"])
def test_anything_else_goes_to_the_interpreter_as_before(cases, case):
    item, _, more = _after_fresh_swap()
    case_id = uuid4()
    state = _team_state(more, trip_id=uuid4() if case == "other_trip" else TRIP)
    if case == "proposal":
        state["applied_actions"] = [{"result_ref": f"trip:{TRIP}:proposal:{uuid4()}"}]
    cases[str(case_id)] = {"state_json": state}
    turns = _turns(case_id)
    if case == "older_turn":
        turns = turns + [{"role": "customer", "text": "운영시간", "case_id": None}, {"role": "assistant", "text": "…", "case_id": str(uuid4())}]
    message = "하나면옥 대신 조선옥으로 바꿔줘" if case == "not_offered" else "하나면옥 대신 조선옥(으)로 바꿔 줘"
    items = [replace(item, detail={})] if case == "no_holder" else [item]
    got = offered_choice.decide(None, tenant="t", trip_id=TRIP, items=items, message=message, turns=turns,
                                selected=uuid4() if case == "selected_other" else None)
    assert got is None


def test_trip_desk_adjusted_outcome_with_other_options_offers_choices_and_records_them():
    """팀 밖 결과(이름 말한 곳 · 근처 식당)도 같은 계산 — 공개 선택지 {label, message} · 기록 `offered` 에 key."""
    _, _, more = _after_fresh_swap()
    offers = case_dispatch.alternate_offers({"to": "한일옥", "kind": "dining", "more_options": more})
    assert [c["label"] for c, _ in offers] == ["식당 조선옥", "식당 순라길비비", "식당 13:30으로 늦추면 인사동 옥정"]
    assert all(sorted(c) == ["label", "message"] for c, _ in offers)
    state = {"trip_outcome": {"offered": [{**c, "choice": k} for c, k in offers]}}
    assert case_dispatch.offered_alternates(state) == offers
