# -*- coding: utf-8 -*-
"""이동을 넣고 나서 생긴 영업시간 위반은 거절하지 않고 고쳐 본다 — 계획 생성기 「이동 뒤 보정 구멍」. `[2026-10-22 사용자 지시]`

실서버에서 「서울 1일」을 짰더니 `plan_infeasible`(422)로 거절됐다. 이동 시간을 넣으며 일정이 뒤로 밀려 식당이 닫는 시각을 넘었는데,
그 판정에서 걸리면 곧바로 거절했기 때문이다(장소를 바꾸면 풀리는 위반인데도). 또 고치는 함수가 못 고친 위반 하나에서 멈춰,
뒤의 고칠 수 있는 위반까지 안 고쳤다.

재현:

    python -m pytest tests/unit/travel/test_planner_post_move_repair.py -v
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.itinerary.itinerary_checks import Violation
from app.domains.travel_ops.components.planning import planner
from app.domains.travel_ops.components.planning.planner import Cand, PlanRequest

KST = timezone(timedelta(hours=9))
DAY = "2026-10-28"


def at(hm: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hm}:00+09:00")


def cand(key: str, kind: str, lat: float, hours=None, brk=None) -> Cand:
    attributes: dict = {}
    if hours:
        attributes["hours"] = hours
    if brk:
        attributes["break"] = brk
    return Cand(key=key, name=key, kind=kind, lat=lat, lon=127.0, attributes=attributes, origin="places")


def item(seq: int, kind: str, key: str, start: str, end: str) -> dict:
    return {"seq": seq, "kind": kind, "title": key, "place": key, "starts_at": at(start), "ends_at": at(end),
            "detail": {"planner": {"day": DAY, "origin": "places"}}}


def request() -> PlanRequest:
    return PlanRequest(city="서울", start_date=date.fromisoformat(DAY), days=1, party_size=2, constraints={})


@pytest.fixture(autouse=True)
def no_hours_lookup(monkeypatch):
    # 영업시간을 관광공사에서 읽는 자리 — 시험은 후보에 시간을 직접 실었다
    zero = {"asked": 0, "read": 0, "by_rule": 0, "by_model": 0, "unknown": 0, "failed": 0}
    monkeypatch.setattr(planner, "enrich_hours", lambda *a, **k: dict(zero))


def settle(items, chosen, spares=()):
    stats = {"asked": 0, "read": 0, "by_rule": 0, "by_model": 0, "unknown": 0, "failed": 0}
    used = {c.key for c in chosen.values()}
    fixed: list[str] = []
    out, routes, violations, rounds = planner._settle_moves(
        items, chosen, request(), engine=None, ledger=None, spares=list(spares), used=used, fixed=fixed,
        hours_stats=stats, tour_api=None, chat=None, now=at("09:00"))
    return out, routes, violations, rounds, fixed


def lunch_setup(spare: Cand | None):
    """활동 → 식당. 이동을 넣기 전엔 식당(12:10~13:10)이 닫는 시각 13:15 안이지만, 이동을 넣으면 10분 밀려 13:20 에 끝난다."""
    act = cand("관광지", "activity", 37.5000)
    lunch = cand("점심집", "dining", 37.5072, hours=["11:00", "13:15"])         # 약 800m — 도보 10분 + 여유 10분
    items = [item(1, "activity", "관광지", "10:30", "12:00"), item(2, "dining", "점심집", "12:10", "13:10")]
    chosen = {"관광지": act, "점심집": lunch}
    return items, chosen, ([spare] if spare else [])


def test_the_setup_really_breaks_only_after_moves_are_added():
    items, chosen, _ = lunch_setup(None)
    assert planner._check(items, chosen, request()) == [], "이동 전에는 판정을 통과한다"
    out, routes, _ = planner.add_moves(items, chosen)
    assert [v.code for v in planner._check(out, chosen, request(), routes)] == ["after_closing"], "이동을 넣으면 닫는 시각을 넘는다"


def test_a_violation_that_appears_after_moves_is_repaired_by_swapping_the_place_then_moves_are_added_again():
    spare = cand("여유집", "dining", 37.5072, hours=["09:00", "22:00"])
    items, chosen, spares = lunch_setup(spare)
    out, routes, violations, rounds, fixed = settle(items, chosen, spares)
    assert violations == []
    assert rounds == 1
    assert [i["title"] for i in out if i["kind"] == "dining"] == ["여유집"], "닫는 식당을 그날 그 시각에 여는 곳으로 바꿨다"
    assert sum(1 for i in out if i["kind"] == "mobility") == 1, "이동 항목은 걷었다가 한 번만 다시 들어갔다"
    assert [i["seq"] for i in out] == [1, 2, 3], "번호가 이어진다"
    assert any(line.startswith("이동을 넣은 뒤 after_closing") for line in fixed), "고친 내역이 남는다"


def test_when_nothing_can_replace_it_the_violation_is_returned_for_refusal_not_hidden():
    items, chosen, spares = lunch_setup(None)
    out, routes, violations, rounds, fixed = settle(items, chosen, spares)
    assert [v.code for v in violations] == ["after_closing"]
    assert rounds == 0
    assert out and any(i["kind"] == "mobility" for i in out), "거절에 쓰는 일정은 이동이 들어간 그대로"


def test_a_clean_plan_is_left_alone():
    items = [item(1, "activity", "관광지", "10:30", "12:00"), item(2, "dining", "점심집", "12:30", "13:30")]
    chosen = {"관광지": cand("관광지", "activity", 37.5000), "점심집": cand("점심집", "dining", 37.5072, hours=["11:00", "22:00"])}
    out, routes, violations, rounds, fixed = settle(items, chosen)
    assert violations == [] and rounds == 0
    assert not any(line.startswith("이동을 넣은 뒤") for line in fixed), "고칠 게 없으면 손대지 않는다"


def test_repair_keeps_going_after_a_violation_it_cannot_fix():
    # 앞 위반(바꿀 장소가 없다)이 뒤 위반(여는 시각까지 밀면 풀린다)을 막지 않는다
    stuck = cand("닫은집", "dining", 37.5000, hours=["11:00", "12:00"])
    early = cand("늦게여는집", "dining", 37.5000, hours=["13:00", "22:00"])
    items = [item(1, "dining", "닫은집", "12:30", "13:30"), item(2, "dining", "늦게여는집", "12:00", "13:00")]
    items[1]["starts_at"], items[1]["ends_at"] = at("14:00"), at("15:00")           # 이 항목은 영업 중
    items[1]["starts_at"], items[1]["ends_at"] = at("12:10"), at("12:50")           # 여는 시각(13:00) 전
    places = {"닫은집": stuck, "늦게여는집": early}
    violations = [Violation("after_closing", (1,), "닫은집이 닫은 뒤다", ""),
                  Violation("before_opening", (2,), "늦게여는집이 열기 전이다", "")]
    applied = planner.repair(items, places, violations, spares=[], used={"닫은집", "늦게여는집"},
                             constraints={}, party_size=2)
    assert any(line.startswith("before_opening(2)") for line in applied), applied
    assert items[1]["starts_at"] == at("13:00"), "여는 시각으로 밀었다"
