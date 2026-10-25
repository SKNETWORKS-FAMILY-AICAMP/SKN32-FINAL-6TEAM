# -*- coding: utf-8 -*-
"""「실내를 야외로 바꿔줘」 첫 답이 「말씀을 정확히 알아듣지 못했어요」 대체 목록(식사 포함 · 활동 하나 빠짐)으로 나가던 결함. `[2026-10-26 x600 QA]`

☆x600(role-manager 2ce73990) 공개 예시 test12 「활동과 식사」(북촌한옥마을 · 광장시장 점심 · 국립중앙박물관 · N서울타워)에서
  선택 없이 「실내를 야외로 바꿔줘」 → 해석은 통과했고(`setting=outdoor` 가 팀 요청에 실렸다) 할 일은 되묻기였는데, 선택지가
  「1) 북촌한옥마을 2) 광장시장 3) 국립중앙박물관」 — `trip_messages._clarify_with_choices` 의 **후보 없음 대체 목록**(지금부터 가까운
  식사·활동 셋)이었다. 해석 실패(DecisionFailed)라면 「지금 요청을 해석하지 못했어요(해석 모델 응답 오류)」로 escalated 된다 — 이 길이 아니다.
원인(`decision_unit.decide` 끝의 기준 일정 확인): 근처 기준(`place_search.anchor_item`) 또는 뒤 일정 기준(`time_edit.scope=following`)이
  있으면 그 기준을 대상 확인(`guard_target`)에 한 번 더 넣고, 되묻기가 나오면 **선택지를 비운** 되묻기로 덮는다.
  - 근처 기준이 **바꿀 일정 자신**이면(모델이 바꿀 일정을 근처 기준으로도 적음) 같은 확인을 두 번 하는 것이다 — 첫 확인의 활동 3곳 되묻기가
    선택지 없는 되묻기로 덮여 대체 목록이 나갔다. 근거 원문이 실내·야외 조건과 겹치지 않으면(「실내를」) 앞 수정(near_is_setting)도 잡지 못한다.
  - 시각을 바꾸지 않는 해석(`time_edit.boundary=none` — 검증·실행 모두 무시하는 칸)의 `scope=following` 도 기준으로 썼다.
고친 것: 근처 기준이 바꿀 일정 자신이면 다시 확인하지 않는다(그 일정은 이미 확인했다 — `settle_near_search` 가 근처 조건을 뗀다).
  뒤 일정 기준은 시각 변경이 실제로 있을 때(boundary≠none)만 본다. 키워드를 보지 않는 구조 확인이다.

모든 바깥 서비스는 메모리 대역이다. 실 E4B 원출력은 `_LIVE_1` 만(2026-10-26 outdoor-diag live-1) — 나머지는 그 원출력의 칸 하나를 바꾼 가정 입력이다.
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
NOW = datetime(2030, 10, 26, 2, 40, tzinfo=KST)
MESSAGE = "실내를 야외로 바꿔줘"


def _test12():
    """test12 「활동과 식사」와 같은 제목·시각(x600 trip v1) — 이동 3개 포함. 별칭 i1 북촌 · i2 광장시장 · i3 박물관 · i4 N서울타워."""
    rows = [(1, "activity", "북촌한옥마을", (10, 0), (11, 30)), (2, "mobility", "지하철 3호선→1호선 21분 · 2.0km", (11, 30), (11, 51)),
            (3, "dining", "광장시장", (12, 0), (13, 0)), (4, "mobility", "지하철 1호선→4호선 32분 · 5.7km", (14, 12), (14, 44)),
            (5, "activity", "국립중앙박물관", (15, 0), (16, 30)), (6, "mobility", "지하철 4호선 45분 · 3.4km", (18, 5), (18, 50)),
            (7, "activity", "N서울타워", (19, 0), (20, 0))]
    items = []
    for seq, kind, title, (h1, m1), (h2, m2) in rows:
        place = None if kind == "mobility" else {"place_id": str(uuid4()), "name": title, "kind": kind,
                                                  "latitude": 37.55, "longitude": 126.98, "attributes": {}}
        items.append(Item(item_id=uuid4(), seq=seq, kind=kind, title=title,
                          place_id=UUID(place["place_id"]) if place else None, place=place,
                          starts_at=DAY.replace(hour=h1, minute=m1), ends_at=DAY.replace(hour=h2, minute=m2)))
    return items


#: 실 E4B(tripilot-pointer:e4b-ft, 127.0.0.1:11434, ctx 8192) 원출력 — role-manager 2ce73990 코드 · test12 일정 · 선택 없음
_LIVE_1 = {"time_edit": {"boundary": "none", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False,
                         "continue_previous": False, "evidence": ""},
           "place_search": {"relation": "near", "anchor_item": "i1", "place_text": "", "evidence": "실내를 야외로 바꿔줘"},
           "place_setting": {"want": "outdoor", "evidence": "야외로"}, "action": "apply_change", "target_item": "i1",
           "target_change": "none", "fact": "none", "destination_text": "", "condition_text": "", "anchor_kind": "item",
           "anchor_item": "i1", "anchor_time": "", "at_day": "none", "relation": "before", "steps": 0, "minutes": 0,
           "reads": [], "social": "", "general_requests": [], "choices": []}


#: 같은 조건 · 「야외로 바꿔줘」 실 E4B 원출력(후보 코드 live-3) — 근처 근거가 조건 원문과 같다(near_is_setting 이 뗀다)
_LIVE_3 = {**copy.deepcopy(_LIVE_1),
           "place_search": {"relation": "near", "anchor_item": "i1", "place_text": "", "evidence": "야외로 바꿔줘"},
           "place_setting": {"want": "outdoor", "evidence": "야외로 바꿔줘"},
           "choices": [{"action": "apply_change", "target_item": "i1", "target_change": "none", "fact": "none"}]}


def _variant(**over):
    raw = copy.deepcopy(_LIVE_1)
    for key, value in over.items():
        raw[key] = {**raw[key], **value} if isinstance(value, dict) and isinstance(raw.get(key), dict) else value
    return raw


_CASES = [
    pytest.param(MESSAGE, _LIVE_1, id="live-1-near-evidence-overlaps-setting"),
    pytest.param("야외로 바꿔줘", _LIVE_3, id="live-3-to-outdoor"),
    # 근처 근거가 실내·야외 조건 원문과 겹치지 않는다 — near_is_setting 이 잡지 못하고 기준(i1 = 바꿀 일정)이 남는다
    pytest.param(MESSAGE, _variant(place_search={"evidence": "실내를"}), id="near-anchor-is-target-evidence-silnae"),
    pytest.param(MESSAGE, _variant(place_search={"evidence": "바꿔줘"}), id="near-anchor-is-target-evidence-verb"),
    # 시각을 바꾸지 않는 해석(boundary=none)의 scope=following — 검증·실행 모두 무시하는 칸
    pytest.param(MESSAGE, _variant(place_search={"relation": "none", "anchor_item": "none", "evidence": ""},
                          time_edit={"scope": "following"}), id="inactive-time-edit-following"),
]


def _run(raw, items, message=MESSAGE):
    model = SimpleNamespace(structured=lambda *a, **k: copy.deepcopy(raw))
    got = decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=None, message=message, now=NOW)
    return settle_near_search(got, items)


class _Store:
    def __init__(self, items):
        self.items = items

    def latest(self, conn, trip_id):
        return {"trip_id": str(trip_id), "version": 1, "customer_id": str(uuid4())}, self.items

    def versions(self, conn, trip_id):
        return [{"version": 1, "reason": "created"}]


@pytest.mark.parametrize("message,raw", _CASES)
def test_ambiguous_outdoor_swap_asks_between_the_activities_not_the_fallback_list(message, raw):
    """고객이 보는 것: 되묻기 선택지가 활동 3곳(북촌 · 박물관 · N서울타워)이고 식사(광장시장)는 없다. 조건(setting=outdoor)도 실린다."""
    from app.domains.travel_ops.components.conversation.trip_messages import _dispatch_decision

    items = _test12()
    activities = [i for i in items if i.kind == "activity"]
    got = _run(raw, items, message)
    assert got.action == "clarify" and got.question != "기준으로 삼을 일정을 하나로 알려 주세요."
    assert [c["item"].title for c in got.choices] == [i.title for i in activities]
    assert got.raw["guard"]["ambiguous_target"] == "i1"
    plan = _dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(), message=message,
                              at=NOW, store=_Store(items), items=items, decision=got, selected=None, actor_id="a",
                              desk=None, prepare_only=True)
    request = plan["subject_ref"]["request"]
    assert request["setting"] == "outdoor"
    assert [c["item_id"] for c in request["choices"]] == [str(i.item_id) for i in activities]
    assert "광장시장" not in request["question"] and "N서울타워" in request["question"]


def test_near_anchor_on_another_ambiguous_stop_still_asks_for_the_anchor():
    """진짜 근처 기준이 바꿀 일정과 **다른** 일정이고 그 기준이 근거 없으면 — 전처럼 기준을 되묻는다(바꾸지 않는다)."""
    items = _test12()
    raw = _variant(action="apply_change", target_item="i2", place_setting={"want": "any", "evidence": ""},
                   place_search={"relation": "near", "anchor_item": "i3", "place_text": "", "evidence": "근처"},
                   choices=[{"action": "apply_change", "target_item": "i2", "target_change": "none", "fact": "none"}])
    got = _run(raw, items, message="근처로 바꿔줘")
    assert got.action == "clarify" and got.question == "기준으로 삼을 일정을 하나로 알려 주세요."


def test_active_following_shift_still_checks_its_anchor():
    """시각 변경이 실제로 있는 뒤 일정 옮기기(boundary=shift · scope=following)는 기준 확인을 그대로 거친다."""
    items = _test12()
    raw = _variant(action="change_time", target_item="none", anchor_item="i3", place_setting={"want": "any", "evidence": ""},
                   place_search={"relation": "none", "anchor_item": "none", "place_text": "", "evidence": ""},
                   time_edit={"boundary": "shift", "scope": "following", "evidence": "뒤 일정 30분 미뤄줘"},
                   choices=[])
    got = _run(raw, items, message="뒤 일정 30분 미뤄줘")
    assert got.action == "clarify" and got.question == "기준으로 삼을 일정을 하나로 알려 주세요."
