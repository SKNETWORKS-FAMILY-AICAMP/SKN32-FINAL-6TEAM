# -*- coding: utf-8 -*-
"""이동 계산기 속도 개선(2026-10-19) — 결과는 그대로이고 일만 줄었는지 잠근다.

  ① 마지막 성립 출발 역산의 건너뛰기 — 버스 승차 소요 하한(`_bus_ride_floor`)이 worst 판정의 승차 소요보다 길지 않다(합성 프로파일 ·
     모든 시간대) · 실데이터에서 건너뛰기를 끈 판과 결과가 같다(mobility_full).
  ② 버스→버스 생성기 — 운행 시간 확인을 후보를 만들기 전에 해도 만든 후보와 같은 값을 본다 · 고른 후보가 확인을 끈 판과 같은 모양이다.
  ③ 요청 사이 재사용 · 잠금 · 여러 구간 한 번에 — 같은 입력이면 계산기를 다시 부르지 않고 같은 답(따로 복사) · 실시간 설정은 재사용 안 함 ·
     여러 스레드가 같이 불러도 구간끼리 출발 문맥이 섞이지 않는다 · `legs_many` 는 같은 순서 · 같은 구간 한 번.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from app.domains.travel_ops.components.team_hooks import legs as legs_hook
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import plan as P
from app.domains.travel_ops.instances.mobility.engine.bus_profile import BusSegProfile, Q
from app.domains.travel_ops.instances.mobility.engine.candidates import _ServiceView
from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg
from app.domains.travel_ops.instances.mobility.engine.verify_time import Verifier
from tests.unit.travel.mobility.test_bus_to_bus import A, B, _gen, _world

KST = timezone(timedelta(hours=9))


# ── ① 버스 승차 소요 하한 ──────────────────────────────────────────────────
def _profile(rows):
    """rows = [{(요일형, 시간): (날 수, p90 초)}] — 행마다 연속 정류장 구간 하나(노선 R · seq k → k+1)."""
    n = len(rows)
    arr = np.full((n, 2, 4, 24), np.nan, dtype=np.float32)
    arr[:, :, 0, :] = 0
    for i, cells in enumerate(rows):
        for (dt, h), (days, p90) in cells.items():
            j = 0 if dt == "weekday" else 1
            arr[i, j, 0, h] = days
            arr[i, j, Q["p10"], h] = p90 * 0.5
            arr[i, j, Q["p50"], h] = p90 * 0.8
            arr[i, j, Q["p90"], h] = p90
    index = {("R", k + 1): k for k in range(n)}
    ends = {k: (f"S{k + 1}", f"S{k + 2}", k + 2) for k in range(n)}
    return BusSegProfile(index, ends, arr, {"source_id": "synthetic"})


def test_min_cell_takes_the_shortest_usable_cell_only():
    prof = _profile([{("weekday", 8): (30, 600.0), ("weekday", 9): (2, 100.0), ("holiday", 3): (30, 450.0)}])
    assert prof.min_cell(0, "p90", 5) == 450.0              # 날 수 2 칸(100초)은 cell 이 안 쓰는 칸이라 빼고
    assert prof.min_cell(0, "p90", 31) is None              # 모두 날 수 미달이면 없음


def _floor_world(rows, dists, speed=12.0):
    stops = [{"seq": k + 1, "station_nm": f"정류장{k + 1}", "station_id": f"S{k + 1}", "route_id": "R",
              "sect_dist_m": (None if k == 0 else dists[k - 1])} for k in range(len(rows) + 1)]
    route = SimpleNamespace(route_id="R", route_nm="R", first_min=300, last_min=1400, term_min=10, route_type_nm="간선")
    bus = SimpleNamespace(stops={"R": stops}, by_id={"R": route}, route=lambda nm: route)
    prof = _profile(rows)
    fake = SimpleNamespace(bus=bus, bus_prof=prof, rv=lambda *k: 5, bus_speed=lambda r, d: (speed, "x", "추정", []))
    leg = bus_leg(route, stops[0], stops[-1])
    return fake, leg, prof, stops


def test_bus_ride_floor_never_exceeds_worst_walk_at_any_hour():
    rows = [{("weekday", h): (30, 300.0 + 40 * (h % 5)) for h in range(6, 23)},           # 낮만 칸 — 밤은 종전 모델
            {("weekday", h): (30, 120.0) for h in range(24)} | {("holiday", 2): (30, 60.0)},
            {}]                                                                            # 칸 없음 — 종전 모델만
    fake, leg, prof, stops = _floor_world(rows, dists=[900, 500, 700])
    floor = Verifier._bus_ride_floor(fake, leg, "weekday")
    assert floor > 0
    old = lambda d: d / 1000 / 12.0 * 60                                                   # noqa: E731 — 판정기 종전 모델과 같은 식
    for start in range(0, 2 * 1440 - 200, 7):
        for days in (lambda t: ("weekday",), lambda t: ("weekday", "holiday")):
            w = prof.walk("R", stops, 1, len(stops), start, days, "p90", 5, old)
            if w.minutes is not None:
                assert floor <= w.minutes + 1e-9, (start, floor, w.minutes)


def test_bus_ride_floor_is_zero_when_unknown():
    fake, leg, _prof, _stops = _floor_world([{}], dists=[None])
    fake.bus_speed = lambda r, d: (None, "x", "근거없음", [])
    assert Verifier._bus_ride_floor(fake, leg, "weekday") == 0          # 하한을 못 내면 건너뛰지 않는다
    fake.bus_prof = None
    assert Verifier._bus_ride_floor(fake, leg, "weekday") == 0


def test_subway_candidates_are_remembered_per_line_stations_daytype_and_closed_edges(monkeypatch):
    import collections
    from app.domains.travel_ops.instances.mobility.engine import verify_time as VT
    v = Verifier.__new__(Verifier)
    v.disr = []
    made = []

    def fake(line, origin, target, day_type, closed):
        made.append((line, origin, target, day_type, frozenset(closed)))
        return [("편성", len(made))], collections.Counter({"종착열차": 1}), False

    monkeypatch.setattr(v, "_candidates_uncached", fake)
    out, drop, _ = v.candidates("2호선", "잠실", "강남", "weekday")
    out.append("부른 쪽이 덧붙임")
    drop["종착열차"] += 5
    again, drop2, _ = v.candidates("2호선", "잠실", "강남", "weekday")
    assert len(made) == 1 and again == [("편성", 1)] and drop2["종착열차"] == 1      # 기억한 답 · 고친 것이 새지 않음
    v.candidates("2호선", "잠실", "강남", "holiday")
    v.disr = [{"kind": "edge_closed", "line": "2호선", "between": ["성수", "건대입구"]}]
    v.candidates("2호선", "잠실", "강남", "weekday")                                 # 끊긴 구간이 생기면 다시 만든다
    v.disr = [{"kind": "edge_closed", "line": "5호선", "between": ["가", "나"]}]
    v.candidates("2호선", "잠실", "강남", "weekday")                                 # 다른 노선의 사고는 이 목록과 무관
    assert len(made) == 3
    monkeypatch.setattr(VT, "CAND_CACHE_MAX", 3)
    v.candidates("3호선", "가", "나", "weekday")                                     # 상한에 닿으면 비우고 다시
    assert len(v._cand_cache) == 1


# ── ② 버스→버스 생성기: 확인을 먼저 해도 같은 값 ─────────────────────────────
def test_service_view_carries_the_values_of_the_candidate_it_becomes():
    seen = []

    def record(view):
        seen.append((view.shape, view.est_min, tuple(map(tuple, view.bus_board_offsets and [view.bus_board_offsets])),
                     tuple((r.route_id, x["seq"]) for r, x in view.bus_boards), tuple(map(str, view.legs))))
        return True

    g = _gen(_world())
    g.service_check = record
    out = g.bus_to_bus(*A, *B, 800)
    assert out and seen
    for c in out:
        key = ("C", c.est_min, tuple(map(tuple, [c.bus_board_offsets])), tuple((r.route_id, x["seq"]) for r, x in c.bus_boards),
               tuple(map(str, c.legs)))
        assert key in seen, key


def test_bus_to_bus_result_without_check_is_unchanged_by_the_precheck():
    plain = _gen(_world()).bus_to_bus(*A, *B, 800)
    g = _gen(_world())
    g.service_check = lambda view: True
    checked = g.bus_to_bus(*A, *B, 800)
    assert [(c.legs, c.est_min, c.bus_board_offsets) for c in plain] == [(c.legs, c.est_min, c.bus_board_offsets) for c in checked]


def test_service_view_legs_are_built_on_demand():
    r = SimpleNamespace(route_id="7", route_nm="7")
    x, y = {"seq": 1, "station_nm": "가"}, {"seq": 3, "station_nm": "나"}
    v = _ServiceView("C", 12.3, [(r, x)], [1.0], "7", x, (y,))
    assert v.legs == [bus_leg(r, x, y)]


def test_in_service_remembers_boards_only_for_the_same_bus_legs():
    p = P.Planner.__new__(P.Planner)
    r = SimpleNamespace(route_id="1", route_nm="1", first_min=300, last_min=1300)
    rows = [{"seq": 1, "station_nm": "가", "route_id": "1"}, {"seq": 2, "station_nm": "나", "route_id": "1"}]
    bus = SimpleNamespace(stops={"1": rows}, by_id={"1": r})
    p.v = SimpleNamespace(bus=bus)
    p._ride_est = lambda *a: 0.0
    mc = SimpleNamespace(legs=[bus_leg(r, rows[0], rows[1])], est_min=10.0)
    assert p._in_service(mc, 600, 610)
    assert mc._service_boards[0]                                         # 기억했다
    assert not p._in_service(mc, 100, 110)                               # 같은 승차 정보로 다른 시각도 맞게
    mc.legs = [dict(mc.legs[0], from_sequence=2, to_sequence=3)]         # 버스 구간이 바뀌면 다시 찾는다(기억을 쓰지 않는다)
    p._in_service(mc, 600, 610)
    assert mc._service_boards[0][0][4] == 2


# ── ③ 요청 사이 재사용 · 잠금 · 여러 구간 ────────────────────────────────────
class _FakePlanner:
    calls = 0
    delay = 0.0

    def __init__(self, rt, *, stage="planning", modes=None, **kw):
        self.stage, self.modes, self.trace, self.disruptions = stage, set(modes) if modes else None, None, ()
        self.departure_context = None

    def leg(self, a, b, arrive_dt, party, first_visit, case_id, not_before_dt=None):
        type(self).calls += 1
        self.trace.append({"options": [{"id": "walk", "margin_min": 5}]})
        time.sleep(self.delay)
        self.departure_context = {"from_place": dict(a), "to_place": dict(b), "options": {}}
        time.sleep(self.delay)
        route = {"from": a["name"], "to": b["name"], "planned": "walk",
                 "options": [{"id": "walk", "label": "도보", "eta_min": 7, "uses": [], "walk_m": 500}]}
        return (route, 600, 607, arrive_dt.date(), []), None


@pytest.fixture()
def fake_engine(monkeypatch):
    rt = SimpleNamespace(timetable_built_at="2026-10-19", rules_version="t", _v=SimpleNamespace(rv=lambda *k: 5))
    monkeypatch.setitem(wiring._STATE, "mode", "enabled")
    monkeypatch.setitem(wiring._STATE, "kw", {})
    monkeypatch.setattr(wiring.engine_runtime, "get_verifier", lambda **kw: rt)
    monkeypatch.setattr(P, "Planner", _FakePlanner)
    monkeypatch.setattr(P, "party_of", lambda size, c: {"adults": size or 1})
    _FakePlanner.calls, _FakePlanner.delay = 0, 0.0
    wiring.clear_leg_cache()
    yield rt
    wiring.clear_leg_cache()


def _pl(key, lat):
    return {"key": key, "name": f"장소{key}", "kind": "activity", "lat": lat, "lon": 127.0, "weather_sensitive": None, "attributes": {}}


AT = datetime(2026, 10, 21, 14, 0, tzinfo=KST)


def test_same_inputs_reuse_the_answer_as_a_separate_copy(fake_engine):
    eng = wiring.leg_planner(2, {})
    a, b = _pl("a", 37.50), _pl("b", 37.51)
    first, _ = eng(a, b, AT, None)
    first["route"]["planned"] = "망가뜨림"                                 # 부른 쪽이 고쳐도 다음 답에 새지 않는다
    second, _ = wiring.leg_planner(2, {})(a, b, AT, None)                 # 다른 요청(새 계산기)이어도 다시 쓴다
    assert _FakePlanner.calls == 1
    assert second["route"]["planned"] == "walk"
    assert second["departure_context"]["from_place"]["key"] == "a"


def test_different_inputs_or_live_settings_are_not_reused(fake_engine):
    a, b = _pl("a", 37.50), _pl("b", 37.51)
    wiring.leg_planner(2, {})(a, b, AT, None)
    wiring.leg_planner(3, {})(a, b, AT, None)                             # 일행이 다르다
    wiring.leg_planner(2, {})(a, b, AT + timedelta(minutes=1), None)      # 시각이 다르다
    wiring.leg_planner(2, {})(a, dict(b, name="다른 이름"), AT, None)     # 이름이 결과(경로 끝 이름 · 출발 문맥)에 들어간다
    assert _FakePlanner.calls == 4
    bike = wiring.leg_planner(2, {}, modes=["bike"])
    bike(a, b, AT, None)
    bike(a, b, AT, None)                                                  # 따릉이 대여 가능 대수는 실시간 — 다시 쓰지 않는다
    quoted = wiring.leg_planner(2, {"taxi_call_quotes": [{"x": 1}]})
    quoted(a, b, AT, None)
    quoted(a, b, AT, None)                                                # 사전 견적 유효 시간은 지금 시각으로 본다
    assert _FakePlanner.calls == 8


def test_reuse_expires_and_configure_clears(fake_engine, monkeypatch):
    a, b = _pl("a", 37.50), _pl("b", 37.51)
    monkeypatch.setattr(wiring, "LEG_CACHE_TTL_S", -1)
    wiring.leg_planner(2, {})(a, b, AT, None)
    wiring.leg_planner(2, {})(a, b, AT, None)
    assert _FakePlanner.calls == 2                                        # 시간이 지나면 다시 센다
    monkeypatch.setattr(wiring, "LEG_CACHE_TTL_S", 300)
    wiring.leg_planner(2, {})(a, b, AT, None)
    wiring.clear_leg_cache()
    wiring.leg_planner(2, {})(a, b, AT, None)
    assert _FakePlanner.calls == 4


def test_one_engine_shared_by_threads_keeps_each_legs_context(fake_engine):
    _FakePlanner.delay = 0.01
    eng = wiring.leg_planner(2, {})
    places = [(_pl(f"a{i}", 37.50 + i / 1000), _pl(f"b{i}", 37.60 + i / 1000)) for i in range(8)]
    out = [None] * len(places)

    def run(i):
        out[i] = eng(*places[i], AT, None)

    ts = [threading.Thread(target=run, args=(i,)) for i in range(len(places))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    for i, (got, _why) in enumerate(out):
        assert got["departure_context"]["from_place"]["key"] == f"a{i}"
        assert got["route"]["from"] == f"장소a{i}"


def test_legs_many_keeps_order_and_counts_each_leg_once(fake_engine):
    eng = wiring.leg_planner(2, {})
    a, b, c = _pl("a", 37.50), _pl("b", 37.51), _pl("c", 37.52)
    jobs = [(a, b, AT, None), (b, c, AT, None), (a, b, AT, None)]
    got = legs_hook.legs_many(eng, jobs)
    assert [g[0]["route"]["to"] for g in got] == ["장소b", "장소c", "장소b"]
    assert _FakePlanner.calls == 2
    assert got[0][0] is not got[2][0]                                     # 같은 구간이어도 따로 복사


def test_legs_many_works_with_engines_without_the_batch_entry():
    seen = []

    def plain(a, b, arrive, not_before):
        seen.append(a)
        return {"a": a}, None

    assert legs_hook.legs_many(plain, [(1, 2, 3, None), (4, 5, 6, None)]) == [({"a": 1}, None), ({"a": 4}, None)]
    assert seen == [1, 4]
    off = legs_hook.legs_many(None, [(1, 2, 3, None)])
    assert off[0][0] is None and off[0][1]["code"] == "engine_off"


# ── 실데이터(mobility_full) — 건너뛰기를 끈 판과 같다 ──────────────────────────
_PAIRS = [  # (출발 lat, lon, 도착 lat, lon, 도착 목표) — 서울 장소 목록에서 고른 구간(버스 직행 · 혼합 · 지하철이 섞이게)
    (37.5796, 126.9770, 37.4979, 127.0276, "2026-10-21T14:00:00+09:00"),     # 경복궁 → 강남
    (37.5445, 127.0560, 37.5665, 126.9780, "2026-10-21T11:30:00+09:00"),     # 성수 → 시청
    (37.5512, 126.9882, 37.5345, 126.9946, "2026-10-21T16:15:00+09:00"),     # 남산 → 이태원
    (37.6006, 127.0247, 37.5826, 127.0019, "2026-10-21T10:45:00+09:00"),     # 성북 → 혜화
    (37.5140, 127.1050, 37.5400, 127.0700, "2026-10-21T19:00:00+09:00"),     # 잠실 → 건대
]


@pytest.mark.mobility_full
def test_full_last_feasible_depart_skip_changes_nothing(monkeypatch):
    from tests.unit.travel.mobility.test_mixed_v1 import _runtime
    rt = _runtime()
    party = P.party_of(None, {})

    def run():
        out = []
        for i, (la, lo, lb, lob, at) in enumerate(_PAIRS):
            pl = P.Planner(rt, stage="planning")
            a = {"key": f"a{i}", "name": f"출발{i}", "kind": "activity", "lat": la, "lon": lo}
            b = {"key": f"b{i}", "name": f"도착{i}", "kind": "activity", "lat": lb, "lon": lob}
            got, why = pl.leg(a, b, datetime.fromisoformat(at), party, True, f"case{i}")
            out.append((got[0], got[1], got[2], got[4]) if got else ("none", why))
        return out

    with_skip = run()
    monkeypatch.setattr(Verifier, "_bus_ride_floor", lambda self, leg, day_type: 0)
    without_skip = run()
    assert with_skip == without_skip
