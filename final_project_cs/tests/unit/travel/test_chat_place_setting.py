# -*- coding: utf-8 -*-
"""채팅 「실내를 야외로 바꿔줘」가 또 실내 장소로 바뀌던 결함 — 재현과 고친 동작. `[2026-10-25 QA]`

☆QA 2026-10-25(영상 채팅요청오류_261025): 등록된 여행 채팅에서 「실내를 야외로 바꿔줘」 · 「야외로 바꿔줘」 → 같은 실내 장소로만 바뀌었다.
  원인: 해석 결과에 「새 장소의 실내·야외」를 담을 칸이 없었고(`decision_unit._schema`), 팀에 넘기는 요청(`_dispatch_decision`)에도
  싣지 않았다. 팀은 등록 때 남긴 「다른 안」 첫째(`plan_swap` — `alternates[0]`)나 실내·야외를 보지 않는 새 후보 계산
  (`plan_fresh_alternate` — 날씨 사건일 때만 실내로 거른다)으로 바꿨다.
고친 것(D-025 — 모델이 읽고 코드는 인용 확인 · 조회 · 저장):
  - 해석 칸 `place_setting{want: any|indoor|outdoor, evidence}` — 인용(evidence)이 고객 문장에 그대로 있어야 받는다.
  - 팀 요청에 `setting` 을 싣고, 저장된 다른 안 · 새 후보 모두 장소 기록의 실내·야외(`attributes.indoor` → `weather_sensitive`)가
    요청과 같은 곳만 고른다. 모름은 고르지 않는다.
  - 맞는 곳이 없으면 다른 종류로 조용히 바꾸지 않고 그렇게 답한다(일정 그대로).

모든 바깥 서비스는 메모리 대역이다(mock 시험 — 실모델 확인은 보고서에 따로 적는다).
"""
from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, NextAction, TeamTask
from app.domains.travel_ops.components.conversation import edit_intent
from app.domains.travel_ops.components.conversation.decision_unit import Decision, DecisionFailed, _schema, decide, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item, item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange, plan_fresh_alternate
from app.domains.travel_ops.instances.activity.team import ActivityTeam

START = datetime(2030, 1, 1, 2, tzinfo=UTC)          # 서울 11:00


def _place(name, *, lat=37.5700, lon=126.9800, indoor=None, weather_sensitive=None):
    attributes = {"hours": ["00:00", "23:59"]}
    if indoor is not None:
        attributes["indoor"] = indoor
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": lat, "longitude": lon,
            "weather_sensitive": weather_sensitive, "attributes": attributes}


def _item(place, seq=1):
    return Item(item_id=uuid4(), seq=seq, kind="activity", title=place["name"], place_id=place["place_id"],
                starts_at=START, ends_at=START + timedelta(hours=2), place=place)


def _record(place):
    return {"key": place["place_id"], "name": place["name"], "place_id": place["place_id"],
            "starts_at": START.isoformat(), "ends_at": (START + timedelta(hours=2)).isoformat(), "walk_min": None}


# ── 해석: 실내·야외 조건을 담는 칸 ─────────────────────────────────────
def _raw(**over):
    raw = {"action": "apply_change", "target_item": "i1", "target_change": "none", "fact": "none", "minutes": 0,
           "choices": [], "reads": [], "social": "", "general_requests": [], "change_scope": "place",
           "destination_text": "", "condition_text": "", "anchor_kind": "none", "anchor_item": "none",
           "anchor_time": "", "at_day": "none", "relation": "at", "steps": 1,
           "place_setting": {"want": "outdoor", "evidence": "야외로"}}
    raw.update(over)
    return raw


def _decide(raw, message):
    museum = _item(_place("중앙박물관", indoor=True))
    model = SimpleNamespace(structured=lambda *a, **k: dict(raw))
    return decide(model, stops=stops_of([museum]), changes=[], history=[], selected_item_id=None,
                  message=message, now=START), museum


def test_schema_has_a_quoted_indoor_outdoor_slot_for_the_new_place():
    museum = _item(_place("중앙박물관", indoor=True))
    schema = _schema(stops_of([museum]), [])
    slot = schema["properties"]["place_setting"]
    assert slot["properties"]["want"]["enum"] == ["any", "indoor", "outdoor"]
    assert "place_setting" in schema["required"] and slot["additionalProperties"] is False
    assert "place_setting" in edit_intent.SYSTEM


def test_setting_guidance_keeps_place_search_empty_without_a_spoken_anchor():
    """☆실 E4B: place_setting 안내를 더한 뒤 조건 없는 교체 문장에 place_search=near(바꿀 일정)·evidence=""를 적어
    근거 검증(unquoted place_search)에서 해석 전체가 실패했다(수정 전 코드는 relation=none). 안내가 기본값을 다시 말해야 한다."""
    block = edit_intent.SYSTEM[edit_intent.SYSTEM.index("place_setting은 장소 교체"):]
    assert "place_setting은 place_search와 별개다" in block
    assert 'place_search는 relation=none,anchor_item=none,place_text="",evidence=""' in block


def test_unquoted_place_search_still_fails_closed():
    """검증기는 약화하지 않는다 — 실 E4B 가 낸 그대로의 칸(near·기준 일정·인용 없음)은 여전히 해석 실패다."""
    with pytest.raises(DecisionFailed, match="unquoted place_search"):
        _decide(_raw(place_search={"relation": "near", "anchor_item": "i1", "place_text": "", "evidence": ""},
                     place_setting={"want": "any", "evidence": ""}), "다른 곳으로 바꿔줘")


@pytest.mark.parametrize("message,want,evidence", [("실내를 야외로 바꿔줘", "outdoor", "야외로"),
                                                    ("야외로 바꿔줘", "outdoor", "야외로"),
                                                    ("실내로 바꿔줘", "indoor", "실내로")])
def test_quoted_setting_survives_decision_as_a_plain_change(message, want, evidence):
    got, museum = _decide(_raw(place_setting={"want": want, "evidence": evidence}), message)
    assert got.action == "apply_change" and got.item.item_id == museum.item_id
    assert got.raw["place_setting"] == {"want": want, "evidence": evidence}


def test_setting_word_copied_into_destination_is_not_searched_as_a_place_name():
    """☆모델이 「야외」를 목적지 칸에도 적으면 이름 찾기(`replace_named`)로 「야외」라는 장소를 찾았다 — 조건 칸의 인용과 같은 말이면 이름이 아니다."""
    got, _ = _decide(_raw(destination_text="야외"), "실내를 야외로 바꿔줘")
    assert got.action == "apply_change" and "named_destination" not in got.raw
    assert got.raw["destination_is_setting"] == {"text": "야외", "evidence": "야외로"}


def test_unquoted_setting_is_rejected_not_repaired():
    with pytest.raises(DecisionFailed):
        _decide(_raw(place_setting={"want": "outdoor", "evidence": "바깥 공기"}), "야외로 바꿔줘")
    with pytest.raises(ValueError):
        edit_intent.validate({"place_setting": {"want": "sky", "evidence": "야외로"}}, "야외로 바꿔줘", {"none", "i1"})


def test_no_setting_keeps_old_meaning():
    got, _ = _decide(_raw(place_setting={"want": "any", "evidence": ""}), "다른 곳으로 바꿔줘")
    assert got.action == "apply_change" and got.raw["place_setting"]["want"] == "any"
    legacy = _raw()
    legacy.pop("place_setting")                        # 저장된 옛 해석 · 옛 대역 — 칸이 없으면 조건 없음
    got, _ = _decide(legacy, "다른 곳으로 바꿔줘")
    assert got.action == "apply_change"


# ── 팀으로 넘기는 요청에 조건을 싣는다 ───────────────────────────────────
class _Store:
    def __init__(self, items):
        self.items = items

    def latest(self, conn, trip_id):
        return {"trip_id": str(trip_id), "version": 3, "customer_id": str(uuid4())}, self.items

    def versions(self, conn, trip_id):
        return [{"version": 3, "reason": "initial"}]


@pytest.mark.parametrize("want,expected", [("outdoor", "outdoor"), ("indoor", "indoor"), ("any", None)])
def test_dispatch_request_carries_the_quoted_setting(want, expected):
    from app.domains.travel_ops.components.conversation.trip_messages import _dispatch_decision

    museum = _item(_place("중앙박물관", indoor=True))
    decision = Decision(action="apply_change", item=museum, change=None, fact="none", minutes=None, question="",
                        raw={"place_setting": {"want": want, "evidence": "야외로" if want != "any" else ""}})
    plan = _dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(), message="야외로 바꿔줘",
                              at=START, store=_Store([museum]), items=[museum], decision=decision, selected=None,
                              actor_id="a", desk=None, prepare_only=True)
    assert plan["subject_ref"]["request"].get("setting") == expected


# ── 팀: 저장된 다른 안 · 새 후보를 조건으로 고른다 ───────────────────────
class _Tools:
    def __init__(self, view, catalog):
        self.view, self.catalog, self.calls = view, catalog, []

    def call(self, name, context, arguments, allowed_tools, seen, *, budget):
        self.calls.append(name)
        if name == "read.itinerary":
            return self.view
        if name == "read.place_catalog":
            return self.catalog
        if name == "read.disruptions":
            return {"verdict": "clear"}
        return None


def _team(request, item, catalog):
    trip_id = uuid4()
    view = {"trip": {"trip_id": str(trip_id), "version": 1}, "items": [item_to_dict(item)]}
    state = {"customer_id": str(uuid4()), "subject_ref": {
        "kind": "trip", "id": str(trip_id), "base_version": 1, "part_id": str(item.item_id),
        "request": {"type": "conversation", "at": (START - timedelta(days=1)).isoformat(), **request}}}
    case_id = uuid4()
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="activity", tenant_id="travel_unit",
                          knowledge_scope=[], current_state=state, estimated_input_tokens=0)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="activity",
                    capability="activity.itinerary", case_version=1, input_text="실내를 야외로 바꿔줘",
                    context=context, allowed_tools=ActivityTeam.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(minutes=1))
    return ActivityTeam(_Tools(view, catalog)), task


def _to(result):
    assert result.action_proposals, result.answer
    return result.action_proposals[0].arguments["replacements"][0]["item"]["place_id"]


def _stored_case():
    home = _place("중앙박물관", indoor=True)
    indoor_alt = _place("한빛전시관", lat=37.5720, indoor=True)          # 등록 때 첫째 다른 안 — ☆고치기 전 늘 이것
    outdoor_alt = _place("푸른공원", lat=37.5730, indoor=False)
    museum = _item(home)
    museum.detail = {"alternates": [_record(indoor_alt), _record(outdoor_alt)], "alternates_from": "intake"}
    return museum, [home, indoor_alt, outdoor_alt], indoor_alt, outdoor_alt


@pytest.mark.parametrize("want", ["outdoor", "indoor"])
def test_stored_alternates_follow_the_requested_setting(want):
    museum, catalog, indoor_alt, outdoor_alt = _stored_case()
    work, task = _team({"action": "apply_change", "setting": want}, museum, catalog)
    result = asyncio.run(work.execute(task))
    assert _to(result) == (outdoor_alt if want == "outdoor" else indoor_alt)["place_id"]


def test_without_setting_the_first_stored_alternate_is_kept():
    museum, catalog, indoor_alt, _ = _stored_case()
    work, task = _team({"action": "apply_change"}, museum, catalog)
    assert _to(asyncio.run(work.execute(task))) == indoor_alt["place_id"]


def test_fresh_search_picks_only_known_outdoor_places():
    home = _place("중앙박물관", indoor=True)
    near_indoor = _place("한빛미술관", lat=37.5710, indoor=True)          # 가장 가깝다 — ☆고치기 전 이것
    unknown = _place("모름터", lat=37.5720)
    by_weather = _place("솔숲산책로", lat=37.5750, weather_sensitive=True)
    work, task = _team({"action": "apply_change", "setting": "outdoor"}, _item(home), [home, near_indoor, unknown, by_weather])
    assert _to(asyncio.run(work.execute(task))) == by_weather["place_id"]


def test_propose_lists_only_matching_options():
    museum, catalog, _, outdoor_alt = _stored_case()
    work, task = _team({"action": "propose_alternatives", "setting": "outdoor"}, museum, catalog)
    result = asyncio.run(work.execute(task))
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert [o["name"] for o in result.decisions[0]["options"]] == [outdoor_alt["name"]]


def test_no_outdoor_candidate_says_so_and_keeps_the_plan():
    home = _place("중앙박물관", indoor=True)
    others = [_place("한빛미술관", lat=37.5710, indoor=True), _place("모름터", lat=37.5720)]
    work, task = _team({"action": "apply_change", "setting": "outdoor"}, _item(home), [home, *others])
    result = asyncio.run(work.execute(task))
    assert not result.action_proposals and result.next_action == NextAction.RESPOND
    assert "야외" in result.answer and "바꾸지 않았어요" in result.answer
    assert result.decisions[0]["itinerary"] == "no_alternate" and result.decisions[0]["setting"] == "outdoor"


def test_plan_fresh_alternate_setting_filter_is_direct():
    home = _place("중앙박물관", indoor=True)
    indoor_near = _place("한빛미술관", lat=37.5710, indoor=True)
    outdoor = _place("하늘정원", lat=37.5740, indoor=False)
    item = _item(home)
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[item],
                                places=[home, indoor_near, outdoor], item_id=item.item_id, message="야외로 바꿔줘",
                                request_id="r", setting="outdoor")
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "하늘정원" and "한빛미술관" not in plan.notice["other_options"]


# ── 실 E4B 관측(2026-10-25, 원래 프롬프트): condition_text=「야외로」 · 대상 2곳이라 되묻기 ─────────────
def test_setting_word_copied_into_condition_is_not_a_conditional_request():
    """☆실 E4B 기준 응답: 「실내를 야외로 바꿔줘」의 condition_text=「야외로」 → 조건부 막기(`condition_guard`)로 다른 안 묻기에 들었다."""
    got, _ = _decide(_raw(condition_text="야외로"), "실내를 야외로 바꿔줘")
    assert got.action == "apply_change" and "condition_guard" not in got.raw
    assert got.raw["condition_is_setting"] == {"text": "야외로", "evidence": "야외로"}
    real, _ = _decide(_raw(condition_text="비 오면", place_setting={"want": "indoor", "evidence": "실내로"}),
                      "비 오면 실내로 바꿔줘")
    assert real.action == "propose_alternatives" and real.raw["condition_guard"]["condition"] == "비 오면"


def test_clarify_keeps_the_setting_for_the_customers_pick():
    """대상이 둘 이상이라 되묻는 경우에도 조건을 잃지 않는다 — 고객이 고른 뒤 팀이 같은 요청(`setting`)으로 바꾼다."""
    from app.domains.travel_ops.components.conversation.trip_messages import _dispatch_decision

    museum = _item(_place("중앙박물관", indoor=True))
    park = _item(_place("솔숲산책로", lat=37.5750, indoor=False), seq=2)
    decision = Decision(action="clarify", item=None, change=None, fact="none", minutes=None, question="",
                        raw={"place_setting": {"want": "outdoor", "evidence": "야외로"}},
                        choices=[{"action": "apply_change", "item": museum, "change": None, "fact": "none"},
                                 {"action": "apply_change", "item": park, "change": None, "fact": "none"}])
    plan = _dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(), message="실내를 야외로 바꿔줘",
                              at=START, store=_Store([museum, park]), items=[museum, park], decision=decision, selected=None,
                              actor_id="a", desk=None, prepare_only=True)
    assert plan["subject_ref"]["request"]["setting"] == "outdoor"


def test_customer_pick_after_clarify_uses_the_kept_setting():
    museum, catalog, _, outdoor_alt = _stored_case()
    choices = [{"label": museum.title, "message": museum.title, "item_id": str(museum.item_id), "action": "apply_change"}]
    work, task = _team({"action": "clarify", "setting": "outdoor", "choices": choices}, museum, catalog)
    state = task.context.current_state
    state["subject_ref"].pop("part_id")
    state.update(required_input_schema={"required": ["message"], "choices": choices,
                                        "x-conversation": {"request": state["subject_ref"]["request"]}},
                 customer_input="1", customer_input_history=["1"])
    assert _to(asyncio.run(work.execute(task))) == outdoor_alt["place_id"]


# ── 실 E4B 관측(2026-10-25 live-8 · live-9, 최종 후보 코드): 야외 조건 원문을 근처 검색 칸에도 옮겨 적었다 ─────────────
#: 원출력(`raw_before_validation`) 그대로 — place_search=near · anchor_item=i1(바꿀 일정 중 하나) · evidence 가 place_setting 근거와 같은 원문 구간
_LIVE_COMMON = {"action": "apply_change", "target_item": "i1", "target_change": "none", "fact": "none", "destination_text": "",
                "anchor_kind": "item", "anchor_item": "i1", "anchor_time": "", "at_day": "today", "relation": "before", "steps": 0,
                "minutes": 0, "reads": [], "social": "", "general_requests": [],
                "choices": [{"action": "apply_change", "target_item": "i1", "target_change": "none", "fact": "none"}]}
_LIVE_TIME = {"boundary": "none", "scope": "item", "time": "", "duration_minutes": 0, "cascade": False, "continue_previous": False}
_LIVE_8 = {**_LIVE_COMMON, "time_edit": {**_LIVE_TIME, "evidence": "실내를 야외로"},
           "place_search": {"relation": "near", "anchor_item": "i1", "place_text": "", "evidence": "실내를 야외로"},
           "place_setting": {"want": "outdoor", "evidence": "야외로"}, "condition_text": ""}
_LIVE_9 = {**_LIVE_COMMON, "time_edit": {**_LIVE_TIME, "evidence": ""},
           "place_search": {"relation": "near", "anchor_item": "i1", "place_text": "", "evidence": "야외로 바꿔줘"},
           "place_setting": {"want": "outdoor", "evidence": "야외로 바꿔줘"}, "condition_text": "야외로 바꿔줘"}
_LIVE = [pytest.param("실내를 야외로 바꿔줘", _LIVE_8, id="live-8"), pytest.param("야외로 바꿔줘", _LIVE_9, id="live-9")]


def _day_trip():
    """박물관(실내 활동) · 점심(식사) · 남산공원(야외 활동) — i1 · i2 · i3."""
    def at(place, seq, start_h, hours, kind="activity"):
        return Item(item_id=uuid4(), seq=seq, kind=kind, title=place["name"], place_id=place["place_id"], place=place,
                    starts_at=START + timedelta(hours=start_h), ends_at=START + timedelta(hours=start_h + hours))
    lunch = {**_place("점심 식사", lat=37.5300), "kind": "dining"}
    return [at(_place("국립중앙박물관 관람", lat=37.5240, indoor=True), 1, -1, 2),
            at(lunch, 2, 1, 1, kind="dining"),
            at(_place("남산공원 산책", lat=37.5510, indoor=False), 3, 3, 2)]


def _decide_on(raw, message, items, selected=None):
    from app.domains.travel_ops.components.conversation.decision_unit import settle_near_search

    model = SimpleNamespace(structured=lambda *a, **k: copy.deepcopy(raw))
    got = decide(model, stops=stops_of(items), changes=[], history=[], selected_item_id=selected, message=message, now=START)
    return settle_near_search(got, items)


@pytest.mark.parametrize("message,raw", _LIVE)
def test_setting_quote_copied_into_place_search_still_asks_between_the_two_activities(message, raw):
    """☆live-8 · live-9: 복사된 근처 기준(i1)이 「기준으로 삼을 일정을 하나로 알려 주세요」(선택지 없음)로 되묻기를 덮어,
    고객에게는 식사 일정까지 끼운 대체 목록(박물관 · 점심 · 남산공원)이 나갔다. 근거 구간이 실내·야외 조건과 겹치면 근처 조건이 아니다."""
    from app.domains.travel_ops.components.conversation.trip_messages import _dispatch_decision

    items = _day_trip()
    got = _decide_on(raw, message, items)
    assert got.action == "clarify" and got.question != "기준으로 삼을 일정을 하나로 알려 주세요."
    assert [c["item"].title for c in got.choices] == ["국립중앙박물관 관람", "남산공원 산책"]
    assert got.raw["place_search"]["relation"] == "none" and got.raw["place_search"]["anchor_item"] == "none"
    assert got.raw["near_is_setting"]["was"] == raw["place_search"]
    assert got.raw["near_is_setting"]["evidence"] == raw["place_setting"]["evidence"]
    plan = _dispatch_decision(None, controller=None, tenant="t", trip_id=uuid4(), case_id=uuid4(), message=message,
                              at=START, store=_Store(items), items=items, decision=got, selected=None, actor_id="a",
                              desk=None, prepare_only=True)
    request = plan["subject_ref"]["request"]
    assert request["setting"] == "outdoor"
    assert [c["item_id"] for c in request["choices"]] == [str(items[0].item_id), str(items[2].item_id)]   # 식사 일정 빠짐


@pytest.mark.parametrize("message,raw", _LIVE)
def test_setting_quote_copied_into_place_search_does_not_block_the_park(message, raw):
    """대상이 i3(남산공원, 활동)인데 같은 복사(near i1)가 붙으면 「식사 일정이 아니라 ○○ 근처로 찾아 바꾸지는 못해요」로 막혔다(가정 입력 재현)."""
    items = _day_trip()
    picked = {**raw, "target_item": "i3",
              "choices": [{"action": "apply_change", "target_item": "i3", "target_change": "none", "fact": "none"}]}
    got = _decide_on(picked, message, items, selected=items[2].item_id)
    assert got.action == "apply_change" and got.item.item_id == items[2].item_id
    assert "near_guard" not in got.raw and "찾아 바꾸지는 못해요" not in got.question
    assert got.raw["place_setting"]["want"] == "outdoor" and got.raw["near_is_setting"]["was"]["anchor_item"] == "i1"


def _real_near(target):
    return {**_LIVE_COMMON, "target_item": target, "anchor_item": "none", "anchor_kind": "none",
            "choices": [{"action": "apply_change", "target_item": target, "target_change": "none", "fact": "none"}],
            "time_edit": {**_LIVE_TIME, "evidence": ""},
            "place_search": {"relation": "near", "anchor_item": "i3", "place_text": "", "evidence": "남산공원 근처"},
            "place_setting": {"want": "outdoor", "evidence": "야외로"}, "condition_text": ""}


def test_real_near_request_with_a_setting_keeps_the_near_search():
    """진짜 근처 요청(근거가 실내·야외 조건과 다른 구간)은 그대로다 — 식사는 그 근처로 찾고, 활동은 전처럼 근처로 못 바꾼다고 되묻는다."""
    message = "남산공원 근처 야외로 바꿔줘"
    items = _day_trip()
    lunch = _decide_on(_real_near("i2"), message, items, selected=items[1].item_id)
    assert lunch.action == "apply_change" and lunch.item.item_id == items[1].item_id
    assert lunch.raw["place_search"] == _real_near("i2")["place_search"] and "near_is_setting" not in lunch.raw
    museum = _decide_on(_real_near("i1"), message, items, selected=items[0].item_id)
    assert museum.action == "clarify" and museum.raw["near_guard"]["reason"] == "non_dining_near_other"
    assert "near_is_setting" not in museum.raw
