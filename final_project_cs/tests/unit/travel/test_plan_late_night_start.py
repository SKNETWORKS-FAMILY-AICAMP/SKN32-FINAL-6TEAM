# -*- coding: utf-8 -*-
"""오늘 남은 시간이 얼마 없을 때 지금부터 짜는 첫날 — 마감 뒤로 넘치게 짜서 거절하지 않는다. `[2026-10-22 사용자 지시]`

실서버에서 23:43 에 「서울 2일」(오늘 시작)을 요청하자 첫날 항목 4개가 다음 날 01:15~12:30 으로 밀려 `day_overflow` 로 거절됐다.
남은 창(23:45~23:59)에 들어가는 만큼만 첫날에 두고, 둘째 날부터는 평소 하루 창으로 짠다.

재현:

    python -m pytest tests/unit/travel/test_plan_late_night_start.py -v
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.domains.travel_ops.components.planning import planner
from app.domains.travel_ops.components.planning.planner import Cand, PlanRequest

KST = planner.KST
START = date(2026, 10, 22)


def act(name, lat):
    return Cand(key=f"k_{name}", name=name, kind="activity", lat=lat, lon=126.977,
                attributes={"hours": ["00:00", "23:59"], "district": "종로구"}, origin="places", rank_hint=0)


class Ledger:
    def shops(self):
        return [{"place_uid": f"p{i}", "name": f"가{i} 식당", "lat": 37.5795 + i * 0.0001, "lng": 126.9772,
                 "address": "서울특별시 종로구 1", "content_id": None, "badges": []} for i in range(10)]

    def verdicts(self, slots):
        return {s["seq"]: {"open_at_slot": True, "closed": False} for s in slots if s.get("place_uid")}

    def open_among(self, uids, at, until):
        return {uid: True for uid in uids}


@pytest.fixture(autouse=True)
def candidates(monkeypatch):
    monkeypatch.setattr(planner, "load_candidates", lambda conn, tenant_id, **kw: [
        act(f"장소{i}", 37.5796 + i * 0.001) for i in range(12)])
    zero = {"asked": 0, "read": 0, "by_rule": 0, "by_model": 0, "unknown": 0, "failed": 0}
    monkeypatch.setattr(planner, "enrich_hours", lambda *a, **k: dict(zero))
    from app.domains.travel_ops.components.team_hooks import legs
    monkeypatch.setattr(legs, "leg_planner", lambda *a, **k: None)       # 이동 계산기는 쓰지 않는다(어림값)


def plan(hour, minute, days=2, constraints=None):
    now = datetime(2026, 10, 22, hour, minute, 30, tzinfo=KST)
    out = planner.plan_trip(conn=None, tenant_id="t", ledger=Ledger(), start_at=now, search=lambda **kw: [], request=PlanRequest(
        city="서울", start_date=START, days=days, party_size=2, constraints=constraints or {}))
    return now, [item for item in out.as_dict()["draft"]["items"] if item["kind"] != "mobility"], out


def by_day(items):
    days: dict[str, list] = {}
    for item in items:
        days.setdefault(item["starts_at"][:10], []).append(item)
    return days


def test_a_request_just_before_midnight_is_not_refused_and_nothing_overflows_past_the_window():
    now, items, _ = plan(23, 43)
    days = by_day(items)
    assert all(datetime.fromisoformat(i["starts_at"]) >= now for i in days.get("2026-10-22", []))
    assert all(datetime.fromisoformat(i["ends_at"]) <= datetime(2026, 10, 22, 23, 59, tzinfo=KST) for i in days.get("2026-10-22", []))
    assert "2026-10-23" in days, "둘째 날은 평소처럼 짠다"


def test_the_second_day_keeps_the_usual_hours_when_the_first_day_is_cut_short():
    _, items, _ = plan(23, 43)
    second = by_day(items)["2026-10-23"]
    assert second[0]["starts_at"][11:16] <= "09:30", "둘째 날은 지금 시각으로 밀리지 않는다"


def test_an_afternoon_request_still_fills_the_rest_of_today():
    now, items, _ = plan(15, 10)
    today = by_day(items)["2026-10-22"]
    assert len(today) >= 2 and all(datetime.fromisoformat(i["starts_at"]) >= now for i in today)


def test_the_cut_is_reported_so_nothing_disappears_silently():
    _, _, out = plan(23, 43)
    first = out.planner["first_day"]
    assert first["from"] == "23:45" and first["until"] == "23:59" and first["dropped_items"] >= 1
