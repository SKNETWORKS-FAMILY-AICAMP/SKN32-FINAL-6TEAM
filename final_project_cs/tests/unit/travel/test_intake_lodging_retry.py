"""다른 장소 확정 뒤 바뀐 동선으로 숙소를 다시 본다. DB·모델·네트워크를 쓰지 않는다."""
from copy import deepcopy

from app.domains.travel_ops.components.intake import autofix, gaps, pipeline, prefill
from app.domains.travel_ops.components.intake.gaps import Gap, Proposal


def test_prefill_retries_both_hotel_breakfasts_after_a_meal_changes_the_route(monkeypatch):
    result, records, calls = _prefill(monkeypatch, resolve_meal=True)
    assert calls == [False, True], "식당 장소 확정 전·후의 동선으로 각각 추천한다"
    assert result["revision"] == 3
    assert {x["item"] for x in result["filled"]} == {"0-0", "0-1", "0-2"}
    hotels = [x for x in result["filled"] if x["gap"] == "lodging_place"]
    assert len(hotels) == 2 and {x["title"] for x in hotels} == {"공통 호텔"}
    assert result["kept"] == [] and result["questions"] == []
    assert len(result["rounds"]) == 2 and len(result["rounds"][0]["retried_gaps"]) == 2
    assert result["rounds"][0]["new_gaps"] == []
    assert len(records[0]["proposals"]) == 5, "첫 숙소 실패도 전체 시도 기록에 남는다"
    assert [p["candidates"] for p in records[0]["proposals"][:2]] == [[], []]


def test_prefill_reports_each_gap_the_recheck_and_the_end(monkeypatch):
    # `[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` 먼저 채우기가 알림 없이 돌았다 — 빈칸마다 · 다시 검사(`step: recheck`) · 끝(`done: total`)
    progress = []
    _prefill(monkeypatch, resolve_meal=True, progress=progress)
    assert progress[0] == {"done": 0, "total": 3, "current": None}
    asked = [p for p in progress if p.get("current")]
    assert {p["current"]["id"] for p in asked} == {"0-0", "0-1", "0-2"} and asked[0]["current"]["title"] in ("호텔", "식당")
    assert any(p.get("step") == "recheck" for p in progress)
    assert progress[-1] == {"done": 3, "total": 3, "current": None}
    dones = [p["done"] for p in progress]
    assert dones == sorted(dones)                                    # 줄지 않는다


def test_prefill_does_not_repeat_a_hotel_search_when_no_place_changed(monkeypatch):
    result, _records, calls = _prefill(monkeypatch, resolve_meal=False)
    assert calls == [False] and result["revision"] == 1
    assert len(result["rounds"]) == 1 and "retried_gaps" not in result["rounds"][0]
    assert {x["item"] for x in result["kept"]} == {"0-0", "0-1", "0-2"}


def test_default_settle_keeps_the_existing_no_repeat_contract():
    called = []
    hotel = Gap("lodging_place", {"item": "h"}, "숙소")
    meal = Gap("meal_place", {"item": "m"}, "식사")

    def owner(gap, draft):
        called.append(gap.kind)
        return Proposal(gap, gap.owner, [] if gap is hotel else [{"title": "식당"}])

    result, _used, rounds = gaps.settle({"revision": 1}, [hotel, meal],
                                      {"lodging_team": owner, "dining_team": owner},
                                      lambda draft, proposals: {"revision": 2}, lambda draft: [hotel])
    assert result["revision"] == 2 and called.count("lodging_place") == 1
    assert len(rounds) == 1


def test_usable_proposal_without_a_new_revision_does_not_trigger_retry():
    called = []
    hotel = Gap("lodging_place", {"item": "h"}, "숙소")
    meal = Gap("meal_place", {"item": "m"}, "식사")

    def owner(gap, draft):
        called.append(gap.kind)
        return Proposal(gap, gap.owner, [] if gap is hotel else [{"title": "기존 식당"}])

    _draft, _used, rounds = gaps.settle({"revision": 1}, [hotel, meal],
                                      {"lodging_team": owner, "dining_team": owner},
                                      lambda draft, proposals: draft, lambda draft: [hotel],
                                      retry_unfilled=lambda p: p.gap.kind == "lodging_place")
    assert called.count("lodging_place") == 1 and len(rounds) == 1


def test_lodging_retry_does_not_extend_the_two_round_limit():
    hotel = Gap("lodging_place", {"item": "h"}, "숙소")
    calls = []

    def owner(gap, draft):
        if gap.kind == "lodging_place":
            calls.append(draft["revision"])
            return Proposal(gap, gap.owner, [])
        return Proposal(gap, gap.owner, [{"title": "식당"}])

    draft, used, rounds = gaps.settle({"revision": 1}, [hotel, Gap("meal_place", {"item": "m1"}, "식사")],
                                     {"lodging_team": owner, "dining_team": owner},
                                     lambda draft, proposals: {"revision": draft["revision"] + 1},
                                     lambda draft: [hotel, Gap("meal_place", {"item": f"m{draft['revision']}"}, "새 식사")],
                                     retry_unfilled=lambda p: p.gap.kind == "lodging_place")
    assert calls == [1, 2] and len(rounds) == 2 and draft["revision"] == 3
    assert any(p.gap.key == hotel.key and p.owner == "ask_customer" for p in used)


def _prefill(monkeypatch, *, resolve_meal, progress=None):
    initial = {"items": [
        {"id": "0-0", "index": 0, "source_id": "s", "title": "호텔", "kind": "dining", "date": "2030-11-06",
         "place_state": "needs_choice", "place": None, "starts_at": "09:00", "ends_at": "10:00"},
        {"id": "0-1", "index": 1, "source_id": "s", "title": "호텔", "kind": "dining", "date": "2030-11-07",
         "place_state": "needs_choice", "place": None, "starts_at": "09:00", "ends_at": "10:00"},
        {"id": "0-2", "index": 2, "source_id": "s", "title": "식당", "kind": "dining", "date": "2030-11-06",
         "place_state": "needs_choice", "place": None, "starts_at": "12:00", "ends_at": "13:00"},
    ], "moves": []}
    views, records, calls = {1: initial}, [], []

    def plan(_conn, *, review, **kwargs):
        meal_ready = bool(review["items"][2]["place"])
        calls.append(meal_ready)
        targets = review["items"][:2] if meal_ready else review["items"][2:] if resolve_meal else []
        return {"changes": [{"id": item["id"], "source_id": "s", "index": item["index"], "title": item["title"],
                             "from": {"place": None}, "to": {"place": {"name": "공통 호텔" if meal_ready else "식당"}},
                             "edits": [{"field": "place", "value": {"name": "공통 호텔" if meal_ready else "식당"}}],
                             "hours_known": False} for item in targets],
                "kept": [{"id": item["id"], "reason": "no_fitting_time"} for item in review["items"] if item not in targets]}

    def edit(_conn, *, revision, edits, **kwargs):
        updated = deepcopy(views[revision])
        for edit in edits:
            number, field = edit["field"].removeprefix("items[").split("].")
            item = updated["items"][int(number)]
            item[field] = edit["value"]
            if field == "place":
                item["place_state"] = "customer"
        views[revision + 1] = updated
        return revision + 1

    monkeypatch.setattr(pipeline, "current_review", lambda conn, **kw: (None, views[kw["revision"]]))
    monkeypatch.setattr(pipeline, "_claims", lambda *args: [])
    monkeypatch.setattr(pipeline, "_trip_fields", lambda claims: {})
    monkeypatch.setattr(pipeline, "edit", edit)
    monkeypatch.setattr(autofix, "plan", plan)
    monkeypatch.setattr(prefill, "_store", lambda conn, **kw: records.append(kw["record"]))
    result = prefill.run(None, tenant_id="test", customer_id=None, intake_id=None, revision=1,
                         plan_slot=lambda gap, draft: [], on_progress=progress.append if progress is not None else None)
    return result, records, calls
