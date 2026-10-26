# -*- coding: utf-8 -*-
"""x600 74b2b232 결함(5) — 「실내를 야외로」가 방금 바꾼 식당을 대상으로 잡지 않는다. `[2026-10-26]`

증거: 보고서 `wiki/records/reports/2026-10-26_x600_74b2b232_실서버확인.md`, case 8f6055e0(다른 데로) → 2b9fa1d1(choice 누름 → 한일옥),
1cff6b55(실내를 야외로 → 식당 no_alternate, 원출력 target_item=i2 · target_change=c6 · place_setting outdoor), 1caa81bc · bcb1050d(trip_desk, model_path 없음).
모든 바깥 서비스는 메모리 대역이다(모델 호출 없음).
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.domains.travel_ops.components.conversation import trip_messages
from tests.unit.travel.test_chat_setting_swap_targets import ASK_OUTDOOR, _ask, _raw, _test12, _titles



# ── (5) 실내→야외: 변경 참조로 잡은 식당 대상은 활동 되묻기 ─────────────────────────────────

def test_x600_setting_swap_on_the_just_changed_meal_asks_activities():
    """x600 1cff6b55 원출력 모양: apply_change · target_item=i2(식당) · target_change=c1(방금 변경) · outdoor → 식당 팀이 아니라 활동 되묻기."""
    items = _test12()
    change = SimpleNamespace(alias="c1", version=2, target_item_id=items[2].item_id, line="광장시장 → 하나면옥")
    decision, request = _ask_with_change(_raw(action="apply_change", target_item="i2", target_change="c1"), items, change)
    assert decision.action == "clarify" and decision.item is None
    assert request["setting"] == "outdoor" and request["question"].startswith(ASK_OUTDOOR)
    assert _titles(request, items) == ["북촌한옥마을", "국립중앙박물관", "N서울타워"]


def test_setting_swap_on_a_meal_the_customer_picked_or_named_is_unchanged():
    """화면에서 고른 식당 · 변경 참조 없이 가리킨 식당은 그대로 식당 팀(팀이 실내·야외로 거른다)."""
    items = _test12()
    change = SimpleNamespace(alias="c1", version=2, target_item_id=items[2].item_id, line="광장시장 → 하나면옥")
    picked, _ = _ask_with_change(_raw(action="apply_change", target_item="i2", target_change="c1"), items, change,
                                 selected=items[2].item_id)
    named, request = _ask(_raw(action="apply_change", target_item="i2"), items, "점심 식당을 야외로 바꿔줘")
    assert picked.action == named.action == "apply_change" and picked.item is items[2] and named.item is items[2]
    assert request["setting"] == "outdoor"


def _ask_with_change(raw, items, change, *, selected=None):
    """`_ask` 와 같되 변경 목록에 c1 을 둔다(모델이 target_change 로 가리킬 수 있게)."""
    import copy
    from app.domains.travel_ops.components.conversation.decision_unit import decide, settle_near_search, stops_of
    from tests.unit.travel.test_chat_setting_swap_targets import NOW, _Store

    model = SimpleNamespace(structured=lambda *a, **k: copy.deepcopy(raw))
    decision = decide(model, stops=stops_of(items), changes=[change], history=[], selected_item_id=selected,
                      message="실내를 야외로 바꿔줘", now=NOW)
    decision = settle_near_search(decision, items)
    plan = trip_messages._dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(),
                                            message="실내를 야외로 바꿔줘", at=NOW, store=_Store(items), items=items,
                                            decision=decision, selected=selected, actor_id="a", desk=None, prepare_only=True)
    return decision, plan["subject_ref"]["request"]
