# -*- coding: utf-8 -*-
"""실내·야외 조건이 붙은 장소 바꾸기의 되묻기 경로 — 어느 경로로 묻든 조건 선택지(`_setting_swap_choices`)를 거친다. `[2026-10-26 x600 c34bd376]`

☆x600(role-manager c34bd376 배포 뒤, 여행 db6f7452) 선택 없이 「실내를 야외로 바꿔줘」 →
  「말씀을 정확히 알아듣지 못했어요. 다음 중 하나인가요? 1) 북촌한옥마을 2) 광장시장(점심) 3) 국립중앙박물관」 (16.0초).
  선택지 칸이 label/message/action/item_id 뿐 = 대체 목록이다(모델 후보가 아니다). 팀 요청(`x-conversation.request`)에 `setting` 이 없고,
  다음 턴에 고른 박물관의 다른 안도 실내·야외로 걸러지지 않았다(CU · 올리브영) — 최종 해석의 `place_setting.want` 가 indoor/outdoor 가 아니었다.
  `place_setting` 은 스키마 필수(엄격 모드 포함)이고 indoor/outdoor 는 인용이 없으면 검증에서 실패하므로, 모델이 낸 값은 `want=any` 다.
  같은 문장에 로컬 E4B 는 `want=outdoor` 를 냈다(로컬 재현 안 됨) — x600 은 유료 넘김(gpt-6-luna) 경로로 보이나 `decision.model_path` 는 확인하지 않았다.
고친 것:
  - 스키마 칸 설명과 해석 지시에 「할 일과 무관하게(대상을 몰라 clarify 여도) 새 장소 조건을 적는다」를 둔다(모델이 칸을 비우는 원인 쪽).
  - 조건이 있는데 대상 없이 바꾸기를 고른 해석은 되묻기로 돌려 조건 선택지를 거친다(전에는 팀이 조건 없이 모든 활동을 물었다).
  - 조건이 있는데 바꿀 수 있는 활동이 하나도 없으면 식사가 든 대체 목록을 내지 않는다.
낱말을 보지 않는다 — 칸(`place_setting` 인용 확인) · 일정 종류 · 장소 기록만 본다. 모든 바깥 서비스는 메모리 대역이다.
"""
from __future__ import annotations

import pytest

from tests.unit.travel.test_chat_setting_swap_targets import ASK_OUTDOOR, _ask, _choice, _raw, _test12, _titles

MESSAGE = "실내를 야외로 바꿔줘"
ANY = {"want": "any", "evidence": ""}


# ── x600 응답이 나온 경로(재생) ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("over", [
    {"place_setting": ANY},                                                         # 대상 몰라 되묻기 · 후보 없음
    {"place_setting": ANY, "choices": [_choice("clarify", "i1")]},                  # 버려지는 후보만
    {"place_setting": ANY, "action": "apply_change", "target_item": "i1",           # 근처 기준 재확인이 후보를 지움
     "place_search": {"relation": "near", "anchor_item": "i3", "evidence": MESSAGE}},
])
def test_x600_reply_is_the_generic_list_of_an_interpretation_without_a_setting(over):
    """x600 응답 모양(머리말 · 식사 포함 대체 목록 · 칸 · 요청에 setting 없음)은 `want=any` 해석에서만 나온다 — 조건이 없으면 대체 목록 그대로가 계약이다."""
    items = _test12()
    _, request = _ask(_raw(**over), items, MESSAGE)
    assert "setting" not in request
    assert request["question"].startswith("말씀을 정확히 알아듣지 못했어요. 다음 중 하나인가요?")
    assert _titles(request, items) == ["북촌한옥마을", "광장시장", "국립중앙박물관"]
    assert all(sorted(c) == ["action", "item_id", "label", "message"] for c in request["choices"])


def test_same_reply_with_the_quoted_setting_asks_only_activities():
    """같은 해석에 인용 확인을 지난 `want=outdoor` 가 있으면(로컬 E4B) 활동만 묻는다 — 경로 차이는 칸 하나다."""
    items = _test12()
    _, request = _ask(_raw(), items, MESSAGE)
    assert request["setting"] == "outdoor" and request["question"].startswith(ASK_OUTDOOR)
    assert _titles(request, items) == ["북촌한옥마을", "국립중앙박물관", "N서울타워"]


# ── 모델이 칸을 비우는 원인 쪽: 스키마 · 지시 ───────────────────────────────────────────

def test_schema_and_prompt_ask_for_the_setting_whatever_the_action():
    """엄격 스키마(유료 넘김)는 칸 설명을 그대로 보낸다 — 대상을 몰라 clarify 여도 새 장소 조건을 적으라고 칸과 지시 둘 다 말한다."""
    from app.domains.travel_ops.components.conversation import edit_intent
    from app.infrastructure.llm_failover import strict_schema

    slot = edit_intent.schemas(["i1", "none"])["place_setting"]
    assert "clarify" in slot["description"]
    assert strict_schema({"type": "object", "properties": {"place_setting": slot}, "required": ["place_setting"]}
                         )["properties"]["place_setting"]["description"] == slot["description"]
    block = edit_intent.SYSTEM[edit_intent.SYSTEM.index("place_setting은 장소 교체"):]
    assert "clarify" in block and "action과 무관" in block


# ── 조건이 있으면 어느 되묻기든 조건 선택지 ──────────────────────────────────────────────

@pytest.mark.parametrize("action", ["apply_change", "propose_alternatives"])
def test_setting_swap_without_a_target_is_asked_with_activities_only(action):
    """조건은 있는데 대상 없이 바꾸기를 골랐다 — 팀이 조건 없이 모든 활동을 묻지 않게 되묻기로 돌려 조건 선택지를 거친다(할 일은 선택지에 남는다)."""
    items = _test12(first_setting=True)                                  # 북촌 = 이미 야외
    decision, request = _ask(_raw(action=action, target_item="none"), items, MESSAGE)
    assert decision.action == "clarify" and decision.item is None
    assert request["action"] == "clarify" and request["setting"] == "outdoor"
    assert request["question"].startswith(ASK_OUTDOOR)
    assert _titles(request, items) == ["국립중앙박물관", "N서울타워"]
    assert {c["action"] for c in request["choices"]} == {action}


def test_swap_without_a_target_and_without_a_setting_is_unchanged():
    items = _test12()
    decision, request = _ask(_raw(action="apply_change", target_item="none", place_setting=ANY), items, "바꿔줘")
    assert decision.action == "apply_change" and request["action"] == "apply_change" and "setting" not in request


def test_setting_clarify_with_no_activity_left_does_not_offer_meals():
    """바꿀 수 있는 활동이 하나도 없으면(모두 이미 야외) 식사가 든 대체 목록 대신 그렇게 말한다 — 선택지 없음."""
    items = _test12(third=("용산가족공원", True), first_setting=True, tower_setting=True)
    _, request = _ask(_raw(), items, MESSAGE)
    assert request["setting"] == "outdoor" and request["choices"] == []
    assert "광장시장" not in request["question"] and "알아듣지 못했어요" not in request["question"]
    assert "야외 장소로 바꿀 수 있는 활동 일정" in request["question"]
