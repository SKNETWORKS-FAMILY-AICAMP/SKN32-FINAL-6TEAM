# -*- coding: utf-8 -*-
"""실내·야외 조건이 붙은 장소 바꾸기의 대상 되묻기 — 선택지가 비면 일반 대체 목록 대신 바꿀 수 있는 활동을 묻는다. `[2026-10-26 x600 QA]`

☆x600(role-manager 53c3c273 배포 뒤) 공개 예시 test12 「활동과 식사」에서 선택 없이 「실내를 야외로 바꿔줘」 →
  `status=clarify` · `reason=decision_clarify` · 팀 요청 `setting=outdoor` 인데 선택지가 「1) 북촌한옥마을 2) 광장시장(점심) 3) 국립중앙박물관」
  — 선택지에 `fact` · `to_version` 칸이 없다 = `trip_messages._clarify_with_choices` 의 **후보 없음 대체 목록**(식사 포함 · 앞 3개)이다.
  53c3c273 은 그 길 하나(`decide()` 끝 기준 일정 재확인)만 막았다. 같은 화면이 되는 길은 더 있다:
  - 모델이 직접 `action=clarify` · `choices=[]` 를 냈다(검증은 지난다 — 되묻기는 대상이 없어도 된다)
  - 모델이 낸 후보가 모두 문장으로 만들 수 없는 것(`target_item=none` 의 바꾸기 등)이다
  - 진짜 다른 일정이 근처 기준인데 그 기준이 근거 없다(기준 재확인 — `choices=[]`)
  해석이 「실내·야외 조건이 붙은 장소 바꾸기(검증을 지난 `place_setting`) + 대상 미확정」으로 끝났다는 것은 칸으로 안다 —
  그때는 요청 종류를 모르는 대체 목록이 아니라 **바꿀 수 있는 활동**(장소 기록이 이미 그 조건인 일정은 뺀다)을 묻는다.
☆이어서 「야외로 바꿔줘」(이미 야외인 용산가족공원으로 바꾼 뒤) → 「1) 용산가족공원 다른 곳으로 바꿔 줘 2) 용산가족공원 대신 갈 곳 알아봐 줘」 —
  두 후보가 서로 다른 할 일로 같은 일정을 가리킨다 = 모델이 직접 낸 되묻기 후보(`guard_target` 은 한 할 일만 낸다).
  장소 기록이 이미 야외인 일정을 야외로 바꾸자는 후보는 빼고, 남는 것이 없으면 위와 같이 활동 후보를 묻는다.

요청 종류를 모를 때(실내·야외 조건 없음)의 대체 목록(2026-09-29 사용자 제안 — 식사·활동 앞 3개)은 그대로다(아래 시험).
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
NOW = datetime(2030, 10, 26, 3, 26, tzinfo=KST)
MESSAGE = "실내를 야외로 바꿔줘"
FALLBACK_HEAD = "말씀을 정확히 알아듣지 못했어요."


def _test12(*, third=("국립중앙박물관", False), first_setting=None):
    """test12 「활동과 식사」(x600 trip v1) — 별칭 i1 북촌 · i2 광장시장 · i3 셋째 활동 · i4 N서울타워. 실내·야외는 `weather_sensitive`(True 야외)."""
    rows = [(1, "activity", "북촌한옥마을", (10, 0), (11, 30), first_setting),
            (2, "mobility", "지하철 3호선→1호선 21분 · 2.0km", (11, 30), (11, 51), None),
            (3, "dining", "광장시장", (12, 0), (13, 0), None),
            (4, "mobility", "지하철 1호선→4호선 32분 · 5.7km", (14, 12), (14, 44), None),
            (5, "activity", third[0], (15, 0), (16, 30), third[1]),
            (6, "mobility", "지하철 4호선 45분 · 3.4km", (18, 5), (18, 50), None),
            (7, "activity", "N서울타워", (19, 0), (20, 0), None)]
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


class _Store:
    def __init__(self, items):
        self.items = items

    def latest(self, conn, trip_id):
        return {"trip_id": str(trip_id), "version": 1, "customer_id": str(uuid4())}, self.items

    def versions(self, conn, trip_id):
        return [{"version": 1, "reason": "created"}]


def _ask(raw, items, message=MESSAGE, *, history=(), changes=()):
    """원출력 → 결정 단위 → 근처 정리 → 팀 요청(되묻기 문장 · 선택지 · 조건) — 고객이 받는 되묻기와 같은 것."""
    from app.domains.travel_ops.components.conversation.trip_messages import _dispatch_decision

    model = SimpleNamespace(structured=lambda *a, **k: copy.deepcopy(raw))
    decision = decide(model, stops=stops_of(items), changes=list(changes), history=list(history), selected_item_id=None,
                      message=message, now=NOW)
    decision = settle_near_search(decision, items)
    plan = _dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(), message=message,
                              at=NOW, store=_Store(items), items=items, decision=decision, selected=None, actor_id="a",
                              desk=None, prepare_only=True)
    return decision, plan["subject_ref"]["request"]


_EMPTY_PATHS = [
    # x600 첫 턴과 같은 화면 — 모델이 직접 되묻기 · 후보 없음
    pytest.param(_raw(), MESSAGE, id="model-clarify-no-choices"),
    # 모델 후보가 모두 문장으로 만들 수 없다(대상 없는 바꾸기 · 시각 옮기기) → 같은 대체 목록
    pytest.param(_raw(choices=[{"action": "apply_change", "target_item": "none", "target_change": "none", "fact": "none"},
                               {"action": "change_time", "target_item": "i1", "target_change": "none", "fact": "none"}]),
                 MESSAGE, id="model-clarify-unrenderable-choices"),
    # 진짜 다른 일정(i3)이 근처 기준인데 근거가 없다 — 기준 재확인이 선택지를 비운다(53c3c273 이 남긴 길)
    pytest.param(_raw(action="apply_change", target_item="i1",
                      place_search={"relation": "near", "anchor_item": "i3", "place_text": "", "evidence": "실내를"}),
                 MESSAGE, id="anchor-recheck-other-stop"),
]


@pytest.mark.parametrize("raw,message", _EMPTY_PATHS)
def test_setting_swap_without_target_asks_activities_not_the_generic_fallback(raw, message):
    """고객이 보는 것: 「야외 장소로 바꿀 일정」 되묻기 — 활동 셋(북촌 · 박물관 · N서울타워), 식사(광장시장) 없음, 「알아듣지 못했어요」 아님."""
    items = _test12()
    activities = [i for i in items if i.kind == "activity"]
    decision, request = _ask(raw, items, message)
    assert decision.action == "clarify"
    assert request["setting"] == "outdoor"
    assert [c["item_id"] for c in request["choices"]] == [str(i.item_id) for i in activities]
    assert all(c["action"] == "apply_change" for c in request["choices"])
    assert "광장시장" not in request["question"]
    assert not request["question"].startswith(FALLBACK_HEAD)
    assert "야외" in request["question"]


def test_activities_already_in_the_wanted_setting_are_not_offered():
    """장소 기록이 이미 야외(weather_sensitive=True)인 활동은 「야외로 바꿀」 후보가 아니다 — 데이터로 뺀다(모름은 남긴다)."""
    items = _test12(first_setting=True)                     # 북촌 = 야외 기록
    decision, request = _ask(_raw(), items)
    titles = [next(i.title for i in items if str(i.item_id) == c["item_id"]) for c in request["choices"]]
    assert titles == ["국립중앙박물관", "N서울타워"]


def test_after_outdoor_swap_the_same_outdoor_stop_is_not_offered_again():
    """x600 셋째 턴: 박물관 → 용산가족공원(야외)으로 바꾼 뒤 「야외로 바꿔줘」 — 모델이 그 일정만 두 할 일로 되물었다.
    이미 야외인 일정을 야외로 바꾸자고 묻지 않는다 — 남은 활동(모르는 북촌 · N서울타워)을 묻는다."""
    items = _test12(third=("용산가족공원", True))
    park = "i3"
    raw = _raw(place_setting={"want": "outdoor", "evidence": "야외로"},
               choices=[{"action": "apply_change", "target_item": park, "target_change": "none", "fact": "none"},
                        {"action": "propose_alternatives", "target_item": park, "target_change": "none", "fact": "none"}])
    decision, request = _ask(raw, items, "야외로 바꿔줘")
    titles = [next(i.title for i in items if str(i.item_id) == c["item_id"]) for c in request["choices"]]
    assert titles == ["북촌한옥마을", "N서울타워"]
    assert "용산가족공원" not in request["question"]


def test_model_choices_that_still_fit_are_kept_as_the_model_gave_them():
    """모델 후보 중 아직 그 조건이 아닌 일정은 그대로 남는다(할 일 · 순서 그대로) — 활동 목록으로 덮어쓰지 않는다."""
    items = _test12()
    raw = _raw(choices=[{"action": "propose_alternatives", "target_item": "i3", "target_change": "none", "fact": "none"}])
    _, request = _ask(raw, items)
    assert [(c["action"], c["item_id"]) for c in request["choices"]] == [("propose_alternatives", str(items[4].item_id))]


#: 실 E4B(tripilot-pointer:e4b-ft, 127.0.0.1:11434, ctx 8192) 원출력 — x600 trip c3feb784 v1 과 같은 일정 · 선택 없음 (outdoor-diag2 live-1, 8.9초)
#   대상 i1 · 근처 기준 i1 — 대상 확인(guard_target)이 활동 셋을 낸다. 모델 후보는 비었다
_LIVE_X1 = _raw(action="apply_change", target_item="i1", anchor_kind="item", anchor_item="i1", relation="before",
                place_search={"relation": "near", "anchor_item": "i1", "place_text": "", "evidence": "실내를 야외로 바꿔줘"})


def test_live_guard_clarify_asks_which_stop_to_make_outdoor_not_not_understood():
    """실 E4B 원출력: 대상 확인 되묻기(활동 셋)도 「알아듣지 못했어요」가 아니라 「어느 일정을 야외 장소로 바꿀까요?」로 묻는다 — 무엇을 원하는지는 알아들었다."""
    items = _test12()
    decision, request = _ask(_LIVE_X1, items)
    assert decision.raw["guard"]["ambiguous_target"] == "i1"
    assert request["question"].startswith("어느 일정을 야외 장소로 바꿀까요?\n1) 1일차 10:00 북촌한옥마을")
    assert [c["item_id"] for c in request["choices"]] == [str(i.item_id) for i in items if i.kind == "activity"]


def test_unknown_request_kind_keeps_the_user_proposed_fallback():
    """요청 종류를 모르면(실내·야외 조건 없음) 2026-09-29 사용자 제안 대체 목록 그대로 — 지금부터 식사·활동 앞 3개, 기본 머리말."""
    items = _test12()
    _, request = _ask(_raw(place_setting={"want": "any", "evidence": ""}), items, "바꿔줘")
    assert "setting" not in request
    assert [c["item_id"] for c in request["choices"]] == [str(i.item_id) for i in items if i.kind != "mobility"][:3]
    assert request["question"].startswith(FALLBACK_HEAD)


def test_time_change_with_setting_quote_keeps_the_fallback():
    """시각을 바꾸는 해석(boundary≠none)에 남은 실내·야외 칸은 장소 바꾸기가 아니다 — 활동 후보로 돌리지 않는다."""
    items = _test12()
    raw = _raw(time_edit={"boundary": "shift", "scope": "item", "evidence": "바꿔줘"}, change_scope="time")
    _, request = _ask(raw, items)
    assert request["question"].startswith(FALLBACK_HEAD)
