# -*- coding: utf-8 -*-
"""이동 판정(`components/itinerary/move_judge.py`) — 두 장소 → 출발 시각 · 경로 · 소요 · 근거 등급. `[2026-10-06 사용자 요청 — MCP 읽기 도구]`

★지키려는 것
 ①판정기가 경로를 냈으면 `timetable`(시간표 기준 판정) — 출발 · 도착 시각 · 소요 · 경로(노선) · 대안 · 판정 근거(`basis`) · 확인 시각.
 ②판정기가 꺼져 있으면 `unavailable` + `estimate`(직선 어림 — 경로 · 시각은 없다). 판정기가 「갈 방법이 없다」고 하면 `no_route` + `none`(이유 그대로, **어림값을 덧붙이지 않는다**).
 ③서울 밖은 판정하지 않는다(`out_of_scope`). 좌표가 없으면 `InvalidPlace`. 출발 시각과 도착 시각을 같이 주면 오류.
 ④출발 시각을 주면 판정기를 두 번(넉넉한 목표 → 소요에 맞춘 목표), 도착 시각이면 한 번 부른다. 판정기는 부르는 쪽 시각을 그대로 받는다.

 ⑤`[코덱스 검토 반영]` 근거 등급은 **고른 경로**로 가른다 — 도보 · 택시는 시간표가 아니라 `estimate`(대안마다 `grade` 도). 판정기가 예외를 던지거나 이상한 모양을 주면 500 이 아니라 `unavailable`(`engine_error`).
    서울 밖은 판정기 · 근거에 닿기 전에 거른다. 출발 시각은 도착 목표를 90 → 180 → 360분으로 넓혀 찾고(못 찾으면 `searched`), `requested_depart_at` · `wait_min` 을 싣는다.

재현:

    python -m pytest tests/unit/travel/test_move_judge.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary import move_judge
from app.domains.travel_ops.components.team_hooks import legs

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=KST)
A = {"key": "o", "name": "경복궁", "kind": "activity", "lat": 37.5796, "lon": 126.9770, "weather_sensitive": None, "attributes": {}}
B = {"key": "d", "name": "시청", "kind": "activity", "lat": 37.5663, "lon": 126.9779, "weather_sensitive": None, "attributes": {}}
FAR = {**B, "name": "수원", "lat": 37.2636, "lon": 127.0286}


@pytest.fixture(autouse=True)
def _clean_hooks():
    saved = (legs._leg_planner, legs._disruptions_from_events, legs._walk_limit_m, legs._basis)
    legs.clear()
    yield
    legs._leg_planner, legs._disruptions_from_events, legs._walk_limit_m, legs._basis = saved       # 전역이라 되돌린다


class FakeLeg:
    """판정기 흉내 — 도착 목표에서 거꾸로 소요 15분 · 여유 5분을 뺀 출발을 낸다. 부른 인자를 남긴다."""

    def __init__(self, *, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, a, b, arrive_dt, not_before_dt=None):
        self.calls.append((arrive_dt, not_before_dt))
        if self.fail is not None:
            return None, self.fail
        route = {"from": a["name"], "to": b["name"], "planned": "subway", "options": [
            {"id": "subway", "label": "지하철 1호선", "eta_min": 15, "walk_m": 400, "fare_krw": 1550, "uses": [{"line": "1호선"}]},
            {"id": "walk", "label": "도보", "eta_min": 25, "walk_m": 1700}]}
        return {"route": route, "starts_at": arrive_dt - timedelta(minutes=20), "ends_at": arrive_dt - timedelta(minutes=5), "eta_min": 15, "left_out": []}, None


def _register(leg, basis=None):
    legs.register(leg_planner=lambda *a, **kw: leg, disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: 1500.0,
                  basis=basis or (lambda: {"mode": "enabled", "timetable_built_at": "2026-10-01T00:00:00+09:00", "rules_version": "v0.9.1", "timetable_stale": False}))


def test_an_arrival_time_asks_the_judge_once_and_reports_the_timetable_basis():
    leg = FakeLeg()
    _register(leg)
    arrive = NOW + timedelta(hours=1)
    out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=arrive)
    assert len(leg.calls) == 1 and leg.calls[0][0] == arrive
    assert out["status"] == "judged" and out["grade"] == "timetable" and out["grade_label"] == "시간표 기준 판정" and out["mode"] == "arrive_by"
    assert out["from"] == "경복궁" and out["to"] == "시청" and out["eta_min"] == 15
    assert out["depart_at"] == (arrive - timedelta(minutes=20)).isoformat() and out["arrive_at"] == (arrive - timedelta(minutes=5)).isoformat()
    assert out["route"]["label"] == "지하철 1호선" and out["route"]["uses"] == [{"line": "1호선"}] and out["alternatives"][0]["label"] == "도보"
    assert out["basis"]["rules_version"] == "v0.9.1" and out["basis"]["timetable_stale"] is False and out["checked_at"] == NOW.isoformat()      # ①


def test_a_departure_time_asks_twice_and_never_before_the_departure():
    leg = FakeLeg()
    _register(leg)
    out = move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW + timedelta(minutes=10))
    assert len(leg.calls) == 2 and all(call[1] == NOW + timedelta(minutes=10) for call in leg.calls)       # ④ 출발 하한은 늘 그 시각
    assert out["status"] == "judged" and out["mode"] == "depart_at"
    assert datetime.fromisoformat(out["depart_at"]) >= NOW + timedelta(minutes=10) - timedelta(minutes=1)
    default = FakeLeg()
    _register(default)
    assert move_judge.judge(origin=A, dest=B, now=NOW)["status"] == "judged" and default.calls[0][1] == NOW                # 시각을 안 주면 지금 출발


def test_a_judge_that_says_no_way_is_reported_as_it_said_and_gets_no_estimate():
    _register(FakeLeg(fail={"code": "no_service", "reason": "막차가 끝났다", "earliest": {"status": "found", "starts_at": "2026-10-07T05:30:00+09:00"}}))
    out = move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)
    assert out["status"] == "no_route" and out["grade"] == "none" and out["grade_label"] == "근거 없음"
    assert out["reason"]["code"] == "no_service" and "막차" in out["reason"]["reason"] and out["reason"]["earliest"]["status"] == "found"
    assert "estimate" not in out and "depart_at" not in out or out.get("depart_at") is None                 # ② 어림값 · 지어낸 시각이 없다


def test_a_disabled_judge_gives_only_a_straight_line_estimate_and_says_why():
    _register(FakeLeg(), basis=lambda: {"mode": "disabled"})
    legs.clear()                                                                                              # 판정기 자체가 없다(미등록)
    out = move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)
    assert out["status"] == "unavailable" and out["grade"] == "estimate" and out["basis"] is None
    assert out["reason"]["code"] == "engine_unavailable" and "알 수 없음" in out["reason"]["reason"]
    assert 1000 < out["estimate"]["straight_line_m"] < 2000 and out["estimate"]["walk_minutes_estimate"] >= 10 and "어림" in out["estimate"]["note"]
    assert "route" not in out and "depart_at" not in out                                                      # 경로 · 시각을 지어내지 않는다
    legs.register(leg_planner=lambda *a, **kw: None, disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: None, basis=lambda: {"mode": "disabled"})
    off = move_judge.judge(origin=A, dest=B, now=NOW)
    assert off["status"] == "unavailable" and "disabled" in off["reason"]["reason"]                           # 꺼져 있다고 그대로 말한다


def test_outside_seoul_is_not_judged():
    leg = FakeLeg()
    _register(leg)
    out = move_judge.judge(origin=A, dest=FAR, now=NOW)
    assert out["status"] == "out_of_scope" and out["grade"] == "none" and leg.calls == []


def test_places_need_coordinates_and_the_two_times_exclude_each_other():
    with pytest.raises(move_judge.InvalidPlace):
        move_judge.as_place({"name": "좌표 없음"}, key="o")
    with pytest.raises(move_judge.InvalidPlace):
        move_judge.as_place({"lat": 95, "lon": 126.9}, key="o")
    assert move_judge.as_place({"lat": "37.5", "lon": "127.0"}, key="o")["name"] == "이름 없음"
    with pytest.raises(ValueError):
        move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW, arrive_by=NOW + timedelta(hours=1))


def test_the_hook_without_basis_still_registers_the_old_way():
    legs.register(leg_planner=lambda *a, **kw: None, disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: None)         # 옛 호출 모양
    assert legs.basis() is None                                                                                  # 모른다 — 「꺼짐」이라 말하지 않는다


# ── ⑤ 코덱스 검토 반영 ────────────────────────────────────────────
class RouteLeg(FakeLeg):
    """고른 경로를 정할 수 있는 판정기 흉내."""

    def __init__(self, planned, options):
        super().__init__()
        self.planned, self.options = planned, options

    def __call__(self, a, b, arrive_dt, not_before_dt=None):
        self.calls.append((arrive_dt, not_before_dt))
        route = {"from": a["name"], "to": b["name"], "planned": self.planned, "options": self.options}
        return {"route": route, "starts_at": arrive_dt - timedelta(minutes=20), "ends_at": arrive_dt - timedelta(minutes=5), "eta_min": 15, "left_out": []}, None


def test_the_grade_follows_the_chosen_route_walk_and_taxi_are_not_the_timetable():
    walk = {"id": "walk", "label": "도보", "eta_min": 18, "walk_m": 1400}
    taxi = {"id": "taxi", "label": "택시", "eta_min": 9, "fare_krw": 9000}
    metro = {"id": "subway", "label": "지하철 1호선", "eta_min": 15, "uses": [{"line": "1호선"}]}
    for planned, expected in (("walk", "estimate"), ("taxi", "estimate"), ("subway", "timetable")):
        _register(RouteLeg(planned, [walk, taxi, metro]))
        out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
        assert out["status"] == "judged" and out["grade"] == expected and out["route"]["grade"] == expected, planned
        assert {o["id"]: o["grade"] for o in out["alternatives"]} == {k: v for k, v in (("walk", "estimate"), ("taxi", "estimate"), ("subway", "timetable")) if k != planned}
        assert ("grade_note" in out) == (expected == "estimate")                                # 어림이면 왜 시간표가 아닌지 말한다
        assert (out["grade_label"] == "시간표 기준 판정") == (expected == "timetable")


def test_an_engine_that_raises_or_returns_junk_becomes_unavailable_not_a_server_error():
    def boom(a, b, arrive_dt, not_before_dt=None):
        raise RuntimeError("내부 사정 — 이 문장은 새면 안 된다")

    _register(boom)
    out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
    assert out["status"] == "unavailable" and out["reason"]["code"] == "engine_error" and "estimate" in out and "내부 사정" not in str(out)
    _register(lambda a, b, arrive_dt, not_before_dt=None: ({"route": "이상한 모양"}, None))
    assert move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)["reason"]["code"] == "engine_error"
    legs.register(leg_planner=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("조립 실패")), disruptions_from_events=lambda e: ([], []),
                  walk_limit_m=lambda: None)
    assert move_judge.judge(origin=A, dest=B, now=NOW)["reason"]["code"] == "engine_error"        # 판정기를 못 만들어도 같다


def test_outside_seoul_is_refused_before_the_engine_or_its_basis_is_touched_and_an_unreadable_basis_does_not_stop_a_judgement():
    touched = []
    legs.register(leg_planner=lambda *a, **kw: touched.append("leg"), disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: None,
                  basis=lambda: touched.append("basis") or {})
    assert move_judge.judge(origin=A, dest=FAR, now=NOW)["status"] == "out_of_scope" and touched == []      # 범위 검사가 먼저다
    leg = FakeLeg()
    _register(leg, basis=lambda: (_ for _ in ()).throw(RuntimeError("런타임이 죽었다")))
    out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
    assert out["status"] == "judged" and out["basis"] is None                                             # 근거를 못 읽어도 판정은 한다(모른다고 적는다)


def test_a_departure_widens_the_arrival_target_in_steps_and_says_how_far_it_looked():
    class LateLeg(FakeLeg):
        """90분 안에 도착하는 목표로는 못 가고, 180분 목표부터 갈 수 있다."""

        def __call__(self, a, b, arrive_dt, not_before_dt=None):
            self.calls.append((arrive_dt, not_before_dt))
            if arrive_dt - not_before_dt < timedelta(minutes=150):
                return None, {"code": "arrive_late", "reason": "그 목표엔 늦는다"}
            return super().__call__(a, b, arrive_dt, not_before_dt)

    leg = LateLeg()
    _register(leg)
    out = move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)
    assert out["status"] == "judged" and [(c[0] - NOW).seconds // 60 for c in leg.calls][:2] == [90, 180]     # 90 에서 못 가면 180 으로
    assert out["requested_depart_at"] == NOW.isoformat() and isinstance(out["wait_min"], int) and out["wait_min"] >= 0
    nothing = FakeLeg(fail={"code": "no_service", "reason": "막차가 끝났다"})
    _register(nothing)
    gone = move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)
    assert gone["status"] == "no_route" and len(nothing.calls) == 3 and "360분" in gone["searched"]           # 어디까지 봤는지 말한다 — 6시간 넘는 길은 「없다」가 아니라 「안 찾았다」


def test_a_bus_route_is_an_estimate_and_a_train_route_is_the_timetable():
    metro = {"id": "subway", "label": "지하철 1호선", "eta_min": 15, "uses": ["01호선:서울역", "01호선:시청"]}
    bus = {"id": "bus", "label": "버스 7016", "eta_min": 20, "uses": ["버스:7016"]}
    mixed = {"id": "mixed", "label": "지하철+버스", "eta_min": 22, "uses": ["01호선:서울역", "버스:7016"]}
    _register(RouteLeg("subway", [metro, bus, mixed]))
    out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
    assert out["grade"] == "timetable" and {o["id"]: o["grade"] for o in out["alternatives"]} == {"bus": "estimate", "mixed": "estimate"}      # 버스는 노선 단위 배차 추정이다
    _register(RouteLeg("bus", [metro, bus]))
    assert move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))["grade"] == "estimate"


def test_a_judge_that_could_not_decide_is_not_reported_as_no_way():
    for code in ("no_data", "not_confirmed", "taxi_unavailable", "earliest_unconfirmed"):
        _register(FakeLeg(fail={"code": code, "reason": "자료가 없다"}))
        out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
        assert out["status"] == "undetermined" and out["grade"] == "none" and "갈 방법이 없다는 뜻이 아니에요" in out["reason"]["reason"], code
    _register(FakeLeg(fail={"code": "no_service", "reason": "막차가 끝났다"}))
    assert move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))["status"] == "no_route"             # 진짜 「없다」는 그대로


def test_internal_addresses_and_names_in_the_judges_texts_are_hidden():
    leaky = {"code": "taxi_unavailable", "reason": "GraphHopper 에 닿지 못했다 (http://10.1.2.3:8989): ACOP_MOBILITY_GH_URL 확인",
             "earliest": {"status": "unconfirmed", "reason": "C:\\data\\x 를 못 읽었다"}}
    _register(FakeLeg(fail=leaky))
    out = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
    text = str(out)
    assert "10.1.2.3" not in text and "ACOP_" not in text and "http://" not in text and "C:\\data" not in text and "<가림>" in text

    class Left(FakeLeg):
        def __call__(self, a, b, arrive_dt, not_before_dt=None):
            got, why = super().__call__(a, b, arrive_dt, not_before_dt)
            got["left_out"] = [{"label": "택시", "code": "taxi_no_route", "reason": "http://gh.internal:8989 불통", "_o": {"secret": 1}}]
            return got, why

    _register(Left())
    judged = move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW + timedelta(hours=1))
    assert judged["left_out"] == [{"label": "택시", "code": "taxi_no_route", "reason": "<가림> 불통"}]                           # 내부 칸을 걸러 낸다


def test_the_departure_fallback_is_flagged_as_not_the_earliest():
    class OnlyFirst(FakeLeg):
        """첫 부름만 성립하고 소요에 맞춘 둘째 부름은 못 한다."""

        def __call__(self, a, b, arrive_dt, not_before_dt=None):
            self.calls.append((arrive_dt, not_before_dt))
            if len(self.calls) > 1:
                return None, {"code": "arrive_late", "reason": "늦다"}
            return super().__call__(a, b, arrive_dt, not_before_dt)

    _register(OnlyFirst())
    out = move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)
    assert out["status"] == "judged" and out["earliest_not_guaranteed"] is True and out["wait_min"] > 0
    _register(FakeLeg())
    assert "earliest_not_guaranteed" not in move_judge.judge(origin=A, dest=B, now=NOW, depart_at=NOW)
