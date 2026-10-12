# -*- coding: utf-8 -*-
"""같은 여행의 문제 묶음 — 계산 쪽(`trip_watch_batch.WatchBatch`). 가짜 도구로 **한 초안 위의 차례 계산**을 본다. `[2026-10-03 사용자 지시]`

종단(진짜 Controller · 적용기 · DB)은 `tests/scenario/test_watch_batch.py` 가 본다. 여기서는 그 안쪽 규칙을 빠르게:

 ①뒤 항목은 **앞에서 고친 초안 기준** — 앞이 고른 곳을 뒤가 또 고르지 않는다(항목마다 따로 계산하던 때는 둘이 같은 곳을 골라 한 곳에 겹쳤다)
 ②「변경 안 할 일정」은 초안에 **안 넣는다**(바꾸지 않을 것이므로 뒤 항목의 기준이 되면 안 된다) — 적용기가 묻는다
 ③아무것도 못 바꿨으면 단일 Case 와 같게 escalate 하고 항목별 결과를 표지(`outcome:{항목}:{결과}`)로 남긴다. 점검 소스가 실패한 항목이 있으면 **다시 열 수 있는 사유**로 닫는다
 ④합친 결과를 마지막에 한 번 더 판정하고 걸리면 가장 나중 변경부터 뺀다(통째로 거절하지 않는다)
 ⑤날씨만이고 실내인지 모르면 바꾸지 않고 「바꿀까요?」 항목으로

재현:

    python -m pytest tests/unit/travel/activity/test_watch_batch_unit.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.watch import trip_watch_batch
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.components.itinerary.itinerary import Item, item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_checks import Violation
from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, WatchBatch, digest

from ..helpers import FakeTools, pack, task

KST = ZoneInfo("Asia/Seoul")
ALLOWED = ActivityTeam.manifest.allowed_tools
AT = datetime(2026, 10, 6, 10, 0, tzinfo=KST)
ROAD = {"verdict": "disrupted", "disruptions": [{"category": "traffic_control", "kind": "road_closed"}]}
CLEAR = {"verdict": "clear", "disruptions": []}
FATAL = {"verdict": "fatal", "disruptions": []}


def _place(name, index=0):
    # 0.001° ≈ 111m 씩 — 전부 600m 안. 이름 첫 낱말이 달라야 같은 곳(`same_site`)으로 묶이지 않는다
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5 + 0.001 * index, "longitude": 127.0,
            "weather_sensitive": False, "attributes": {"hours": ["09:00", "22:00"]}}


class _Tools(FakeTools):
    """장소 id 별 점검 결과 — 적힌 곳만 그 결과, 나머지는 `clear`."""

    def __init__(self, values, reports):
        super().__init__(values)
        self.reports = reports

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name != "read.disruptions":
            return super().call(name, context, arguments, allowed_tools, seen, budget)
        super().call(name, context, arguments, allowed_tools, seen, budget)            # 권한 · 중복 · 예산을 같은 순서로
        return self.reports.get(str(arguments.get("place_id")), CLEAR)


def _item(seq, kind, title, hour, place, minutes=60, **detail):
    start = AT.replace(hour=hour)
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=uuid4(), starts_at=start,
                ends_at=start + timedelta(minutes=minutes), place=place, detail=dict(detail))


def _world(items, candidates, reports, *, constraints=None):
    trip = {"trip_id": str(uuid4()), "version": 1, "customer_id": str(uuid4()), "constraints": constraints or {}, "party_size": 2}
    places = [i.place for i in items if i.place] + list(candidates)
    values = {"read.itinerary": {"trip": trip, "items": [item_to_dict(i) for i in items]}, "read.place_catalog": places}
    entries = [{"item_id": str(i.item_id), "base_id": f"watch:x:{i.item_id}:fp", "detected": "place", "issue_code": "activity_other",
                "categories": ["traffic_control"]} for i in items if str(i.place["place_id"]) in reports]
    context = pack("activity", state={"subject_ref": {"kind": "trip", "id": trip["trip_id"]}, "trigger_source": "schedule",
                                      "trigger": {"batch": entries, "at": AT.isoformat(), "detected": "batch"}})
    tools = _Tools(values, reports)
    return tools, task("activity", "activity.itinerary", context, ALLOWED)


async def _run(items, candidates, reports, **kw):
    tools, work = _world(items, candidates, reports, **kw)
    return await ActivityTeam(tools).execute(work), tools


def _replacements(result):
    [proposal] = result.action_proposals
    return {r["item"]["place"]["name"] for r in proposal.arguments["replacements"]}, proposal.arguments


# ── ① 뒤 항목은 앞 초안 기준 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_the_second_item_does_not_pick_what_the_first_one_already_took():
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)
    best, next_best, third = _place("아자 박물관", 2), _place("차카 갤러리", 3), _place("타파 공원", 4)
    result, _ = await _run([first, second], [best, next_best, third], {a1["place_id"]: ROAD, a2["place_id"]: ROAD})

    assert result.outcome == "completed"
    names, arguments = _replacements(result)
    assert len(arguments["replacements"]) == 2 and len(names) == 2                       # 서로 다른 두 곳이다(같은 곳에 겹치지 않았다)
    assert arguments["batch"]["applied"] and len(arguments["batch"]["applied"]) == 2
    assert result.answer.startswith("일정에 문제가 두 가지 겹쳐서 이렇게 처리했어요.")


@pytest.mark.asyncio
async def test_every_item_gets_its_own_tool_budget():
    """항목마다 `seen` 을 새로 쓴다 — 앞 항목이 도구 예산을 다 써서 뒤 항목이 「못 봤다」가 되지 않는다. 한 Case 의 호출 합은 한 항목 예산(`max_steps`)을 넘을 수 있다."""
    places = [_place(f"활동{chr(0x3131 + k)} 장소", k) for k in range(5)]
    items = [_item(k + 1, "activity", f"활동 {k}", 9 + 2 * k, places[k]) for k in range(5)]
    cands = [_place(f"{chr(0xAC00 + 7 * k)}후보", 0.5 + 0.5 * k) for k in range(10)]        # 55m 간격 — 다섯 항목 모두의 600m 안
    result, tools = await _run(items, cands, {p["place_id"]: ROAD for p in places})

    assert result.outcome == "completed"
    assert len(tools.calls) > ActivityTeam.manifest.max_steps                              # 한 항목 예산으로는 모자랄 호출 수다
    checked = {a["place_id"] for n, a in tools.calls if n == "read.disruptions"}
    assert all(p["place_id"] in checked for p in places)                                    # 마지막 항목까지 자기 점검을 했다
    _, arguments = _replacements(result)
    assert len(arguments["replacements"]) == 5                                              # 다섯 모두 바뀌었다(뒤 항목이 「못 봤다」로 밀리지 않았다)


# ── ② 변경 안 할 일정은 초안에 안 넣는다 ───────────────────────────

@pytest.mark.asyncio
async def test_a_pinned_item_is_left_out_of_the_draft_and_goes_to_the_applier_as_a_question():
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    pinned = _item(1, "activity", "전망대 관람", 10, a1, customer_pinned=True)
    plain = _item(2, "activity", "정원 산책", 13, a2)
    cands = [_place("아자 박물관", 2), _place("차카 갤러리", 3)]
    result, _ = await _run([pinned, plain], cands, {a1["place_id"]: ROAD, a2["place_id"]: ROAD})

    names, arguments = _replacements(result)
    assert len(arguments["replacements"]) == 2                                            # 묻는 항목의 안도 싣는다(적용기가 안 1·2·3 으로 묻는다)
    assert arguments["batch"]["applied"] == [str(plain.item_id)]                           # 판에 넣는 것은 평범한 항목뿐이다
    assert "변경하지 않기로 한 일정이라 바꾸지 않고" in result.answer and "전망대 관람" in result.answer


# ── ③ 못 바꿨으면 escalate + 표지 ─────────────────────────────────

@pytest.mark.asyncio
async def test_when_nothing_can_be_changed_it_escalates_with_one_token_per_unsolved_item():
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)
    result, _ = await _run([first, second], [], {a1["place_id"]: ROAD, a2["place_id"]: ROAD})        # 후보가 하나도 없다

    assert result.outcome == "escalated" and result.failure_code == "itinerary_unresolved" and not result.action_proposals
    assert f"outcome:{first.item_id}:no_alternate" in result.warnings and f"outcome:{second.item_id}:no_alternate" in result.warnings


@pytest.mark.asyncio
async def test_a_failed_source_closes_the_case_as_retryable_and_is_not_announced():
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)
    result, _ = await _run([first, second], [], {a1["place_id"]: FATAL, a2["place_id"]: ROAD})

    assert result.outcome == "escalated" and result.failure_code == "fatal_source_failure"      # 다시 열 수 있는 사유
    assert f"outcome:{second.item_id}:no_alternate" in result.warnings                          # 못 푼 것은 표지가 있다(감시가 알린다)
    assert not any(str(first.item_id) in w for w in result.warnings if w.startswith("outcome:"))  # 소스 실패 항목은 알리지 않는다


@pytest.mark.asyncio
async def test_one_failed_source_does_not_stop_the_healthy_items_from_being_applied():
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)
    result, _ = await _run([first, second], [_place("아자 박물관", 2)], {a1["place_id"]: FATAL, a2["place_id"]: ROAD})

    assert result.outcome == "completed" and result.action_proposals                              # 하나를 못 풀어도 나머지는 진행
    names, arguments = _replacements(result)
    assert names == {"아자 박물관"} and arguments["batch"]["applied"] == [str(second.item_id)]


# ── ④ 합친 결과를 한 번 더 — 걸리면 나중 것부터 뺀다 ───────────────

def test_the_merged_result_is_checked_once_more_and_the_latest_change_is_dropped_until_it_passes(monkeypatch):
    items = [_item(1, "activity", "가", 10, _place("가나다 전망대", 0)), _item(2, "activity", "나", 13, _place("마바사 정원", 1))]
    from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange

    def change(item, name):
        return ItineraryChange(reason="auto_adjusted", causes=[], notice={"text": f"{name}로 바꿨어요"},
                               replacements={item.item_id: item.replaced_by(place=_place(name, 5), title=name)}, summary={"to": name})

    outcomes = [Outcome(items[0], "applied", change=change(items[0], "아자 박물관")),
                Outcome(items[1], "applied", change=change(items[1], "차카 갤러리"))]
    seen = []

    def fake(trip, current, new_items):
        both = sum(1 for n in new_items if n.replaces_item_id is not None and n.kind == "activity")
        seen.append(both)
        return [Violation("overlap", (1, 2), "두 변경이 합치면 겹친다", "하나를 뺀다")] if both == 2 else []

    monkeypatch.setattr(trip_watch_batch, "introduced_violations", fake)
    out = WatchBatch(None, None, {})._final_recheck({}, items, outcomes)

    assert [o.kind for o in out] == ["applied", "recheck_failed"] and "겹친다" in out[1].reasons[0]      # 가장 나중 변경이 빠졌다
    assert seen == [2, 1]                                                                              # 합쳐서 보고 → 하나 빼고 다시 보고


# ── ⑤ 날씨만 + 실내인지 모름 → 바꿀까요? ──────────────────────────

@pytest.mark.asyncio
async def test_weather_only_with_unknown_indoor_is_asked_not_changed():
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    rainy = {"verdict": "disrupted", "indoor_unknown": True, "disruptions": [{"category": "forecast", "kind": "rain"}]}
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)
    result, _ = await _run([first, second], [_place("아자 박물관", 2)], {a1["place_id"]: rainy, a2["place_id"]: ROAD})

    names, arguments = _replacements(result)
    assert arguments["batch"]["consents"] == [{"item_id": str(first.item_id), "causes": rainy["disruptions"], "indoor_unknown": True}]
    assert names == {"아자 박물관"} and "바꿀지 따로 여쭤봤어요" in result.answer


# ── 알림 문장 ─────────────────────────────────────────────────────

def test_the_digest_puts_the_safety_line_first_and_never_promises_a_human():
    from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange

    plain = _item(1, "activity", "활동 가", 10, _place("가나다 전망대", 0))
    fire = _item(2, "dining", "점심", 12, _place("마바사 식당", 1))
    change = ItineraryChange(reason="auto_adjusted", causes=[], notice={"text": "활동 가를 아자로 바꿨어요.", "other_options": ["차카"]},
                             replacements={plain.item_id: plain})
    outcomes = [Outcome(plain, "applied", causes=[{"category": "traffic_control", "kind": "road_closed"}], change=change),
                Outcome(fire, "no_alternate", causes=[{"category": "disaster_msg", "kind": "fire"}])]
    payload = digest(outcomes, kind="change_notice")

    lines = [line for line in payload["text"].split("\n") if line.startswith("· ")]
    assert payload["type"] == "safety_alert" and payload["text"].startswith("⚠️ 안전 알림 — ")
    assert lines[0].startswith("· 점심") and lines[1].startswith("· 활동 가를 아자로 바꿨어요.")        # 안전 줄이 앞
    assert "다른 안: 차카." in lines[1] and "사람" not in payload["text"] and "담당자" not in payload["text"]
    assert payload["other_options"] == [] and payload["batch"] is True and len(payload["changes"]) == 1
    guidance = digest(outcomes, kind="guidance")                                                   # 안 바꾼 것만
    assert guidance["type"] == "safety_alert" and "활동 가" not in guidance["text"] and guidance["kind"] == "no_alternate"


# ── 적대 검토(2026-10-03) 반영 ───────────────────────────────────

@pytest.mark.asyncio
async def test_an_exception_in_one_item_does_not_block_the_others_and_that_item_is_kept_for_a_retry(monkeypatch):
    """★전에는 한 항목에서 예외가 나면 Team 전체가 실패해(`team_error`) 건강한 항목 · 안전 사건까지 같이 막혔다. 이제 그 항목만 `error` 로 남기고 나머지는 진행한다."""
    a1, _a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    meal = _place("바보 식당", 2)
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "dining", "점심 식사", 12, meal)
    real = trip_watch_batch._planner

    def planner(kind):
        if kind == "dining":
            def boom(*_a, **_k):
                raise RuntimeError("route data is broken")
            return boom
        return real(kind)

    monkeypatch.setattr(trip_watch_batch, "_planner", planner)
    result, _ = await _run([first, second], [_place("아자 박물관", 3)], {a1["place_id"]: ROAD, meal["place_id"]: ROAD})

    assert result.outcome == "completed" and result.action_proposals                            # 활동은 바뀌었다
    names, arguments = _replacements(result)
    assert names == {"아자 박물관"} and arguments["batch"]["retry"] == [str(second.item_id)]       # 식당은 다시 열 항목이다
    assert any("점심 식사" in w and "error" in w and "RuntimeError" in w for w in result.warnings)  # 운영자가 볼 수 있게 남는다
    assert "점심" not in result.answer                                                          # 고객에게는 알리지 않는다


def test_a_move_that_was_believed_replaced_but_is_still_there_after_the_change_was_dropped_is_retried(monkeypatch):
    """활동을 바꾸면 옆 이동이 새로 만들어져 그 이동 항목은 `gone`(이미 바뀜)으로 처리된다. 마지막 재판정에서 그 활동 변경이 빠지면 이동은 **그대로 남는다** — 아무도 계산한 적이 없으니 다시 연다."""
    from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange

    activity = _item(1, "activity", "활동", 10, _place("가나다 전망대", 0))
    move = _item(2, "mobility", "활동 → 식당", 11, None, minutes=15)
    change = ItineraryChange(reason="auto_adjusted", causes=[], notice={"text": "바꿨어요"},
                             replacements={activity.item_id: activity.replaced_by(place=_place("아자 박물관", 3), title="아자")}, summary={})
    outcomes = [Outcome(activity, "applied", change=change), Outcome(move, "nothing", reasons=["gone"])]
    monkeypatch.setattr(trip_watch_batch, "introduced_violations",
                        lambda trip, current, new_items: [Violation("overlap", (1,), "겹친다", "뺀다")] if any(
                            i.replaces_item_id for i in new_items) else [])
    out = WatchBatch(None, None, {})._final_recheck({}, [activity, move], outcomes)

    assert [o.kind for o in out] == ["recheck_failed", "retry"] and out[1].reasons == ["gone_but_unchanged"]


@pytest.mark.asyncio
async def test_the_options_of_a_question_are_checked_against_the_whole_itinerary_too():
    """묻는 항목의 안도 일정 전체 재판정을 통과한 것만 싣는다 — 안 맞는 안을 「안 1」로 보내 고르게 두지 않는다(단일 Case 는 판정 문 앞에서 이미 걸렀다)."""
    before = Item(item_id=uuid4(), seq=1, kind="activity", title="앞 활동", place_id=uuid4(), starts_at=AT.replace(hour=9),
                  ends_at=AT.replace(hour=10), place={**_place("앞 장소", 0), "attributes": {"hours": ["09:00", "22:00"], "district": "종로구"}})
    origin = {**_place("원래 장소", 0), "attributes": {"hours": ["09:00", "22:00"], "district": "종로구"}}
    pinned = _item(2, "activity", "원래 활동", 10, origin, customer_pinned=True)               # 앞 항목이 끝나자마자(간격 0분) 시작한다
    bad = {**_place("남산공원", 1), "attributes": {"hours": ["09:00", "22:00"], "district": "중구"}}        # 다른 구인데 이동 시간이 0분 → 안 맞는다
    good = {**_place("북촌길", 3), "attributes": {"hours": ["09:00", "22:00"], "district": "종로구"}}
    result, _ = await _run([before, pinned], [bad, good], {origin["place_id"]: ROAD})

    [proposal] = result.action_proposals
    [replacement] = proposal.arguments["replacements"]
    assert replacement["item"]["place"]["name"] == "북촌길"                                    # 안 맞는 1순위 대신 맞는 안이 「안 1」이다
    assert "남산공원" not in {a["name"] for a in replacement["item"]["detail"]["alternates"]}
    assert "변경하지 않기로 한 일정이라 바꾸지 않고" in result.answer


@pytest.mark.asyncio
async def test_when_the_time_runs_out_the_remaining_items_are_not_started_but_kept_for_a_retry(monkeypatch):
    """Team 코드는 동기라 시간 제한이 도중에 끊지 못한다 — 새 항목을 시작하기 전에 스스로 본다. 남은 항목은 알리지 않고 다음 회차에 다시 연다."""
    places = [_place(f"활동{chr(0x3131 + k)} 장소", k) for k in range(3)]
    items = [_item(k + 1, "activity", f"활동 {k}", 9 + 2 * k, places[k]) for k in range(3)]
    clock = iter([0.0, 0.0, 1000.0, 1000.0, 1000.0])                 # 시작 · 첫 항목 전(여유) · 둘째 항목 전(초과) …
    from types import SimpleNamespace

    # ★모듈 시계만 바꾼다 — `time.monotonic` 자체를 바꾸면 asyncio 이벤트 루프가 같이 흔들린다
    monkeypatch.setattr(trip_watch_batch, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    result, _ = await _run(items, [_place("아자 박물관", 0.5), _place("차카 갤러리", 1.5)], {p["place_id"]: ROAD for p in places})

    names, arguments = _replacements(result)
    assert len(names) == 1 and arguments["batch"]["applied"] == [str(items[0].item_id)]         # 첫 항목만 계산했다
    assert arguments["batch"]["retry"] == [str(items[1].item_id), str(items[2].item_id)]       # 나머지는 다시 열 항목이다
    assert any("deadline" in w for w in result.warnings)


def test_the_unchanged_notice_key_is_per_item_and_cause_so_a_later_safety_event_is_not_swallowed():
    """같은 항목 · 같은 원인이면 같은 키(두 번 안 알린다) — 같은 항목에 **다른 원인**(나중에 걸린 안전 사건)이 오면 다른 알림이다(전에는 키가 항목만 봐서 새 안전 안내가 사라질 수 있었다)."""
    item = _item(1, "activity", "활동", 10, _place("가나다 전망대", 0))
    road = digest([Outcome(item, "no_alternate", causes=[{"category": "traffic_control", "kind": "road_closed"}])], kind="guidance")
    road_again = digest([Outcome(item, "no_alternate", causes=[{"category": "traffic_control", "kind": "road_closed", "at": "다른 시각"}])], kind="guidance")
    fire = digest([Outcome(item, "no_alternate", causes=[{"category": "disaster_msg", "kind": "fire"}])], kind="guidance")
    assert trip_watch_batch.guidance_key(road) == trip_watch_batch.guidance_key(road_again)
    assert trip_watch_batch.guidance_key(road) != trip_watch_batch.guidance_key(fire)


@pytest.mark.asyncio
async def test_the_decision_record_keeps_the_time_and_tool_calls_of_every_item():
    """★`[2026-10-03]` 병목을 **재서** 찾으려고 항목마다 쓴 시간(초)과 도구 호출 수를 Case 결정 기록에 남긴다 — 호출 수 측정을 먼저 했더니 어디서 새는지 보였던 것과 같은 생각이다."""
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    first, second = _item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)
    result, tools = await _run([first, second], [_place("아자 박물관", 2), _place("차카 갤러리", 3)], {a1["place_id"]: ROAD, a2["place_id"]: ROAD})

    [decision] = result.decisions
    timing = decision["timing"]
    assert [row["item"] for row in timing["items"]] == ["전망대 관람", "정원 산책"]
    assert all(row["calls"] >= 1 and row["seconds"] >= 0 for row in timing["items"])
    # 항목별 호출 수의 합 = 도구가 실제로 받은 호출 수 − 항목 계산 전에 한 번 읽은 일정 조회(`read.itinerary`) — 센 값이 실제와 같다
    assert timing["total_calls"] == sum(row["calls"] for row in timing["items"]) == len(tools.calls) - 1
    assert timing["total_seconds"] == pytest.approx(sum(row["seconds"] for row in timing["items"]), abs=0.01)

