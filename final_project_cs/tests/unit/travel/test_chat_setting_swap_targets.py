# -*- coding: utf-8 -*-
"""실내·야외 조건이 붙은 장소 바꾸기 — 되묻기 선택지는 활동만, 이미 그 조건인 일정은 바로 바꾸지 않는다. `[2026-10-26 x600 재시험 da4ccd97]`

☆x600(role-manager da4ccd97 배포 뒤) 공개 예시 test12 「활동과 식사」:
  (1) 선택 없이 「실내를 야외로 바꿔줘」 → 머리말 「어느 일정을 야외 장소로 바꿀까요?」는 맞았으나 선택지
      「1) 북촌한옥마을 2) 광장시장 3) 국립중앙박물관 … 다른 곳으로 바꿔 줘」 — 식사(광장시장)가 남고 N서울타워가 빠졌다.
      선택지에 `fact` · `to_version` 칸이 있다 = 모델이 낸 되묻기 후보(`decision.choices`)를 문장화한 것이다(대체 목록이 아니다).
      da4ccd97 은 모델 후보에서 「이미 그 조건」만 뺐고 일정 종류는 보지 않았다 — 후보가 남아 있으면 활동 목록으로 가지 않았다.
  (3) 박물관 → 용산가족공원(야외)으로 바꾼 뒤 선택 없이 「야외로 바꿔줘」 → 되묻지 않고 이미 야외인 용산가족공원을 이촌한강공원으로 또 바꿨다
      (`reason=decision_apply_change` — 모델이 대상 i3 을 바로 냈고 직전 대화에 그 이름이 있어 대상 확인을 지났다).
  (4) 되돌린 판(v4)의 박물관 「운영시간 알려줘」 → 「모르겠어요 — 주소 조회 결과 없음, 운영시간 조회 결과 없음」.
      되돌리기는 옛 항목을 그대로 다시 쓴다(같은 item_id · place_id) — 장소 연결은 남는다(아래 시험). 그 문장은 관광공사 조회가
      둘 다 값을 돌려주지 못했을 때(속도 제한 · 하루 예산 · 공급자 실패)의 답과 같다.

모든 바깥 서비스는 메모리 대역이다. 원출력은 x600 응답 모양을 만드는 가정 입력이다(x600 해석 원출력은 조회하지 않았다).
"""
from __future__ import annotations

import copy
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation.decision_unit import decide, settle_near_search, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2030, 11, 2, tzinfo=KST)
NOW = datetime(2030, 10, 26, 4, 21, tzinfo=KST)
ASK_OUTDOOR = "어느 일정을 야외 장소로 바꿀까요?"


def _test12(*, third=("국립중앙박물관", False), first_setting=None, tower_setting=None):
    """test12 「활동과 식사」 — 별칭 i1 북촌 · i2 광장시장(점심) · i3 셋째 활동 · i4 N서울타워. 실내·야외는 `weather_sensitive`(True 야외)."""
    rows = [(1, "activity", "북촌한옥마을", (10, 0), (11, 30), first_setting),
            (2, "mobility", "지하철 3호선→1호선 21분 · 2.0km", (11, 30), (11, 51), None),
            (3, "dining", "광장시장", (12, 0), (13, 0), None),
            (4, "mobility", "지하철 1호선→4호선 32분 · 5.7km", (14, 12), (14, 44), None),
            (5, "activity", third[0], (15, 0), (16, 30), third[1]),
            (6, "mobility", "지하철 4호선 45분 · 3.4km", (18, 5), (18, 50), None),
            (7, "activity", "N서울타워", (19, 0), (20, 0), tower_setting)]
    items = []
    for seq, kind, title, (h1, m1), (h2, m2), sensitive in rows:
        place = None if kind == "mobility" else {"place_id": str(uuid4()), "name": title, "kind": kind,
                                                  "latitude": 37.55, "longitude": 126.98,
                                                  "weather_sensitive": sensitive, "attributes": {}}
        items.append(Item(item_id=uuid4(), seq=seq, kind=kind, title=title,
                          place_id=UUID(place["place_id"]) if place else None, place=place,
                          starts_at=DAY.replace(hour=h1, minute=m1), ends_at=DAY.replace(hour=h2, minute=m2)))
    return items


_BASE = {"time_edit": {"boundary": "none", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                       "continue_previous": False, "evidence": ""},
         "place_search": {"relation": "none", "anchor_item": "none", "place_text": "", "evidence": ""},
         "place_setting": {"want": "outdoor", "evidence": "야외로"}, "action": "clarify", "target_item": "none",
         "target_change": "none", "fact": "none", "destination_text": "", "condition_text": "", "anchor_kind": "none",
         "anchor_item": "none", "anchor_time": "", "at_day": "none", "relation": "at", "steps": 0, "minutes": 0,
         "reads": [], "social": "", "general_requests": [], "choices": []}


def _raw(**over):
    raw = copy.deepcopy(_BASE)
    for key, value in over.items():
        raw[key] = {**raw[key], **value} if isinstance(value, dict) and isinstance(raw.get(key), dict) else value
    return raw


def _choice(action, alias):
    return {"action": action, "target_item": alias, "target_change": "none", "fact": "none"}


class _Store:
    def __init__(self, items):
        self.items = items

    def latest(self, conn, trip_id):
        return {"trip_id": str(trip_id), "version": 1, "customer_id": str(uuid4())}, self.items

    def versions(self, conn, trip_id):
        return [{"version": 1, "reason": "created"}]


def _ask(raw, items, message, *, history=(), selected=None):
    """원출력 → 결정 단위 → 근처 정리 → 팀 요청(되묻기 문장 · 선택지 · 조건) — 고객이 받는 것과 같은 것."""
    from app.domains.travel_ops.components.conversation.trip_messages import _dispatch_decision

    model = SimpleNamespace(structured=lambda *a, **k: copy.deepcopy(raw))
    decision = decide(model, stops=stops_of(items), changes=[], history=list(history), selected_item_id=selected,
                      message=message, now=NOW)
    decision = settle_near_search(decision, items)
    plan = _dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(), message=message,
                              at=NOW, store=_Store(items), items=items, decision=decision, selected=selected,
                              actor_id="a", desk=None, prepare_only=True)
    return decision, plan["subject_ref"]["request"]


def _titles(request, items):
    return [next(i.title for i in items if str(i.item_id) == c["item_id"]) for c in request["choices"]]


# ── (1) 되묻기 선택지는 활동만 — 출처(모델 후보 · 대상 확인 · 대체)와 무관 ─────────────────────

def test_x600_case1_model_choices_with_lunch_become_the_activities_only():
    """x600 (1): 모델 되묻기 후보 = 북촌 · 광장시장(식사) · 박물관 → 식사는 빠지고 N서울타워가 들어온다(활동 셋)."""
    items = _test12()
    raw = _raw(choices=[_choice("apply_change", "i1"), _choice("apply_change", "i2"), _choice("apply_change", "i3")])
    decision, request = _ask(raw, items, "실내를 야외로 바꿔줘")
    assert decision.action == "clarify" and len(decision.choices) == 3          # 모델 후보 셋(식사 포함)이 결정에 남아 있다
    assert request["setting"] == "outdoor"
    assert _titles(request, items) == ["북촌한옥마을", "국립중앙박물관", "N서울타워"]
    assert "광장시장" not in request["question"]
    assert request["question"].startswith(ASK_OUTDOOR + "\n1) 1일차 10:00 북촌한옥마을 다른 곳으로 바꿔 줘")


def test_model_choices_stay_first_with_their_action_then_other_activities():
    """아직 그 조건이 아닌 모델 후보는 그 할 일 · 순서 그대로 앞에 둔다 — 나머지 자리는 바꿀 수 있는 다른 활동으로 채운다."""
    items = _test12()
    raw = _raw(choices=[_choice("propose_alternatives", "i3")])
    _, request = _ask(raw, items, "실내를 야외로 바꿔줘")
    assert [(c["action"], c["item_id"]) for c in request["choices"]][0] == ("propose_alternatives", str(items[4].item_id))
    assert _titles(request, items) == ["국립중앙박물관", "북촌한옥마을", "N서울타워"]


def test_one_stop_is_offered_once_even_if_the_model_gave_it_two_actions():
    items = _test12()
    raw = _raw(choices=[_choice("apply_change", "i3"), _choice("propose_alternatives", "i3")])
    _, request = _ask(raw, items, "실내를 야외로 바꿔줘")
    assert _titles(request, items) == ["국립중앙박물관", "북촌한옥마을", "N서울타워"]
    assert request["choices"][0]["action"] == "apply_change"


def test_model_choice_on_a_meal_is_dropped_even_when_only_meals_were_given():
    """모델 후보가 식사뿐이어도(비어 있지 않아도) 거른다 — 활동 목록을 묻는다."""
    items = _test12()
    raw = _raw(choices=[_choice("apply_change", "i2"), _choice("propose_alternatives", "i2")])
    _, request = _ask(raw, items, "실내를 야외로 바꿔줘")
    assert _titles(request, items) == ["북촌한옥마을", "국립중앙박물관", "N서울타워"]


def test_already_outdoor_activities_are_dropped_from_model_choices_and_the_filler():
    items = _test12(first_setting=True, tower_setting=True)               # 북촌 · N서울타워 = 야외 기록
    raw = _raw(choices=[_choice("apply_change", "i1"), _choice("apply_change", "i2"), _choice("apply_change", "i3")])
    _, request = _ask(raw, items, "실내를 야외로 바꿔줘")
    assert _titles(request, items) == ["국립중앙박물관"]


def test_no_setting_clarify_keeps_the_model_choices_as_given():
    """조건이 없는 되묻기(요청 종류 모름)는 모델 후보 그대로다 — 식사도 남는다(거르기는 실내·야외 바꾸기에만)."""
    items = _test12()
    raw = _raw(place_setting={"want": "any", "evidence": ""},
               choices=[_choice("apply_change", "i1"), _choice("apply_change", "i2")])
    _, request = _ask(raw, items, "바꿔줘")
    assert "setting" not in request
    assert _titles(request, items) == ["북촌한옥마을", "광장시장"]


# ── (3) 대상이 이미 요청한 조건이면 바로 바꾸지 않는다 ─────────────────────────────────────

_AFTER_SWAP = [{"role": "customer", "text": "1일차 15:00 국립중앙박물관 다른 곳으로 바꿔 줘"},
               {"role": "assistant", "text": "요청하신 대로 국립중앙박물관 대신 용산가족공원(으)로 바꿨습니다(15:00 시작)."}]


@pytest.mark.parametrize("action", ["apply_change", "propose_alternatives"])
def test_x600_case3_already_outdoor_target_is_asked_not_swapped(action):
    """x600 (3): 박물관 → 용산가족공원(야외) 뒤 「야외로 바꿔줘」 — 모델이 대상 i3(용산가족공원)을 바로 냈다.
    이미 야외 장소라고 말하고, 야외로 바꿀 다른 활동을 묻는다. 그 일정을 다른 야외 장소로 바꾸려는 뜻일 수도 있어 그 바꾸기도 마지막 선택지로 남긴다."""
    items = _test12(third=("용산가족공원", True))
    raw = _raw(action=action, target_item="i3", place_setting={"want": "outdoor", "evidence": "야외로"})
    decision, request = _ask(raw, items, "야외로 바꿔줘", history=_AFTER_SWAP)
    assert decision.action == "clarify" and decision.item is None
    assert decision.raw["setting_guard"]["item_id"] == str(items[4].item_id)
    assert request["action"] == "clarify" and request["setting"] == "outdoor"
    assert request["question"].startswith("용산가족공원은(는) 이미 야외 장소예요. " + ASK_OUTDOOR + "\n1) 1일차 10:00 북촌한옥마을")
    assert _titles(request, items) == ["북촌한옥마을", "N서울타워", "용산가족공원"]
    assert request["choices"][-1]["action"] == action


def test_already_outdoor_selected_target_is_asked_too():
    items = _test12(third=("용산가족공원", True))
    raw = _raw(action="apply_change", target_item="i3")
    decision, request = _ask(raw, items, "야외로 바꿔줘", selected=items[4].item_id)
    assert decision.action == "clarify"
    assert _titles(request, items)[-1] == "용산가족공원"
    assert request["question"].startswith("용산가족공원은(는) 이미 야외 장소예요.")


def test_already_outdoor_and_no_other_activity_offers_only_that_stop():
    items = _test12(third=("용산가족공원", True), first_setting=True, tower_setting=True)
    raw = _raw(action="apply_change", target_item="i3")
    _, request = _ask(raw, items, "야외로 바꿔줘", history=_AFTER_SWAP)
    assert _titles(request, items) == ["용산가족공원"]
    assert request["question"].startswith("용산가족공원은(는) 이미 야외 장소예요. " + ASK_OUTDOOR)


@pytest.mark.parametrize("third", [("국립중앙박물관", False), ("국립중앙박물관", None)])
def test_target_not_in_that_setting_or_unknown_is_still_changed(third):
    """장소 기록이 실내이거나 모르면 그대로 바꾸기로 간다(모름은 어느 쪽으로도 치지 않는다)."""
    items = _test12(third=third)
    raw = _raw(action="apply_change", target_item="i3")
    decision, request = _ask(raw, items, "박물관을 야외로 바꿔줘", selected=items[4].item_id)
    assert decision.action == "apply_change" and decision.item is items[4]
    assert request["action"] == "apply_change" and request["setting"] == "outdoor"
    assert "setting_guard" not in decision.raw


def test_no_setting_swap_of_an_outdoor_stop_is_unchanged():
    items = _test12(third=("용산가족공원", True))
    raw = _raw(action="apply_change", target_item="i3", place_setting={"want": "any", "evidence": ""})
    decision, _ = _ask(raw, items, "용산가족공원 다른 데로 바꿔줘", selected=items[4].item_id)
    assert decision.action == "apply_change"


def test_indoor_request_on_an_indoor_stop_is_asked():
    items = _test12()                                                    # 박물관 = 실내 기록
    raw = _raw(action="apply_change", target_item="i3", place_setting={"want": "indoor", "evidence": "실내로"})
    decision, request = _ask(raw, items, "실내로 바꿔줘", selected=items[4].item_id)
    assert decision.action == "clarify"
    assert request["question"].startswith("국립중앙박물관은(는) 이미 실내 장소예요. 어느 일정을 실내 장소로 바꿀까요?")


# ── (4) 되돌린 판의 장소 연결 ───────────────────────────────────────────────────────────

def _museum_place():
    return {"place_id": str(uuid4()), "name": "국립중앙박물관", "kind": "activity", "latitude": 37.5211, "longitude": 126.9803,
            "attributes": {"source_content_id": "129703", "source_content_type_id": "14"}}


class _Tour:
    """관광공사 대역 — 받은 식별자를 적고, `refuse` 면 값 없이 None(속도 제한 · 예산 · 공급자 실패와 같은 모양)."""

    def __init__(self, refuse=False):
        self.refuse, self.calls = refuse, []

    def by_content_id(self, content_id, type_id):
        self.calls.append(("common", content_id, type_id))
        return None if self.refuse else {"address": "서울특별시 용산구 서빙고로 137"}

    def operating(self, content_id, type_id):
        self.calls.append(("intro", content_id, type_id))
        return None if self.refuse else {"usetime_text": "09:30~17:30", "restdate_text": "1월 1일"}


def test_rollback_keeps_the_place_link_and_hours_lookup_uses_the_same_identity():
    """등록(v1) → 교체(v2 용산가족공원) → 교체(v3 이촌한강공원) → v1 로 되돌리기(v4) — 박물관 항목은 같은 item_id · place_id · 장소 기록으로 돌아오고,
    운영시간 조회는 v1 과 같은 관광공사 식별자로 나간다."""
    from app.domains.travel_ops.components.conversation import trip_facts
    from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, plan_rollback

    museum_place = _museum_place()
    v1 = _test12()
    museum = v1[4]
    museum.place, museum.place_id = museum_place, UUID(museum_place["place_id"])
    park = {**_museum_place(), "name": "용산가족공원", "attributes": {}}
    river = {**_museum_place(), "name": "이촌한강공원", "attributes": {}}
    v2 = [i if i is not museum else museum.replaced_by(place=park, title="용산가족공원") for i in v1]
    v3 = [i if i.seq != 5 else i.replaced_by(place=river, title="이촌한강공원") for i in v2]
    plan = plan_rollback(trip_version=3, base_version=3, current_items=v3, old_items=copy.deepcopy(v1), to_version=1,
                         message=None, request_id="qa-rb")
    assert isinstance(plan, ItineraryChange)
    restored = next(i for i in plan.full_items if i.seq == 5)
    assert (restored.item_id, restored.place_id, restored.place) == (museum.item_id, museum.place_id, museum_place)

    trip_facts._CACHE.clear()
    before, after = _Tour(), _Tour()
    text_v1, _ = trip_facts.fact_reply("hours", message="운영시간 알려줘", items=v1, now=NOW, place_source=before, item=museum)
    trip_facts._CACHE.clear()
    text_v4, _ = trip_facts.fact_reply("hours", message="운영시간 알려줘", items=plan.full_items, now=NOW,
                                       place_source=after, item=restored)
    assert before.calls == after.calls and ("intro", "129703", "14") in after.calls
    assert "09:30~17:30" in text_v1 and "09:30~17:30" in text_v4
    trip_facts._CACHE.clear()


def test_x600_case4_text_is_the_tour_lookup_returning_nothing():
    """x600 (4) 문장과 같은 답은 관광공사 두 조회(공통 · 소개)가 모두 값을 돌려주지 않을 때 나온다 — 장소 연결이 끊긴 경우의 답(식별자 찾기 실패)과 다르다."""
    from app.domains.travel_ops.components.conversation import trip_facts

    items = _test12()
    museum = items[4]
    museum.place = _museum_place()
    trip_facts._CACHE.clear()
    tour = _Tour(refuse=True)
    text, _ = trip_facts.fact_reply("hours", message="운영시간 알려줘", items=items, now=NOW, place_source=tour, item=museum)
    assert text == "국립중앙박물관의 운영시간은 모르겠어요 — 주소 조회 결과 없음, 운영시간 조회 결과 없음."
    assert [c[0] for c in tour.calls] == ["common", "intro"]
    trip_facts._CACHE.clear()
