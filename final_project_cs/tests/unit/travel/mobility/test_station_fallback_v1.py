# -*- coding: utf-8 -*-
"""사고 대안 역(83 E1 · 문제목록 #38 · 85번 방 2026-09-30) — 장소마다 도보 상한 안 역을 **가까운 순 여럿** 보고,
사고로 막힌 역만 뺀다. 앞 판은 가장 가까운 역 하나(near[0])만 봐서 성수역 무정차 때 뚝섬·서울숲을 안 봤다.

두 층:
  게이트(데이터 없음) — 막힌 역 판정·후보 역 목록을 작은 역표로 잠근다.
  전체층(실데이터 · mobility_full) — 83 흐름 사례(아쿠아리움 → 성수 11:30) 그대로:
    「가장 가까운 역이 무정차일 때 다음 역 경로가 나온다」 · 「막힌 역만 있으면 no_service」 ·
    「사고가 없으면 가장 가까운 역 그대로(앞 판과 같다)」.
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.travel_ops.mobility.engine import plan as P
from app.modules.travel_ops.mobility.engine.paths import RULES_DIR
from app.modules.travel_ops.mobility.engine.runtime import Runtime
from app.modules.travel_ops.mobility.engine.verify_time import Timetable, Verifier

RULES = json.loads((RULES_DIR / "rules_v0.3.json").read_text(encoding="utf-8"))

# 83 흐름의 두 장소(재생 시나리오 좌표) — 아쿠아리움(롯데월드타워 지하) · 성수동 쇼룸 거리
AQUARIUM = {"key": "aquarium", "name": "아쿠아리움", "lat": 37.5131, "lon": 127.1033}
SEONGSU = {"key": "seongsu", "name": "성수동 팝업·향수 쇼룸 거리", "lat": 37.5445, "lon": 127.056}
ARRIVE = datetime.fromisoformat("2026-09-23T11:30:00+09:00")
SKIP_SEONGSU = ({"kind": "station_skip", "line": "02호선", "station": "성수"},)


# ── 게이트 — 데이터 없이 ───────────────────────────────────────────────
class _Stations:
    """작은 역표 — stations_near 는 가까운 순 (m, 레코드). 노선군은 레코드의 lines."""
    def __init__(self, rows):
        self.rows = rows

    def stations_near(self, lat, lng, within_m):
        rows = self.rows.get(lat, []) if isinstance(self.rows, dict) else self.rows
        return [(d, r) for d, r in rows if d <= within_m]

    def group_lines(self, rec):
        return frozenset(rec["lines"])

    def is_ambiguous(self, nm):
        return False


def _planner(rows, disruptions=()):
    v = Verifier(Timetable(), None, RULES, set())
    v.sc, v.ex = _Stations(rows), None
    pl = P.Planner(Runtime(v, timetable_built_at="t", rules_version="v", stats={}))
    pl.disruptions = tuple(disruptions)
    return pl


ROWS = [(14.0, {"station_nm": "성수", "line": "02호선", "lines": ["02호선"]}),
        (400.0, {"station_nm": "건대입구", "line": "02호선", "lines": ["02호선", "07호선"]}),
        (815.0, {"station_nm": "뚝섬", "line": "02호선", "lines": ["02호선"]}),
        (1003.0, {"station_nm": "서울숲", "line": "수인분당선", "lines": ["수인분당선"]})]
PLACE = {"lat": 0.0, "lon": 0.0}


def test_no_disruption_keeps_nearest_first():
    pl = _planner(ROWS)
    assert [s[0] for s in pl._near_stations(PLACE, 1200, 3)] == ["성수", "건대입구", "뚝섬"]
    assert pl._near_station(PLACE, 1200)[0] == "성수", "사고가 없으면 가장 가까운 역 — 앞 판과 같다"


def test_skipped_station_is_dropped_and_next_comes_in():
    pl = _planner(ROWS, SKIP_SEONGSU)
    assert [s[0] for s in pl._near_stations(PLACE, 1200, 3)] == ["건대입구", "뚝섬", "서울숲"]
    assert pl._near_station(PLACE, 1200)[0] == "건대입구"


def test_transfer_station_with_one_line_skipped_is_not_blocked():
    """환승역은 한 노선만 무정차면 막힌 역이 아니다 — 판정기가 그 노선만 뺀다."""
    one = _planner(ROWS, ({"kind": "station_skip", "line": "02호선", "station": "건대입구"},))
    assert "건대입구" in [s[0] for s in one._near_stations(PLACE, 1200, 4)]
    both = _planner(ROWS, ({"kind": "station_skip", "line": "02호선", "station": "건대입구"},
                           {"kind": "line_closed", "line": "07호선"}))
    assert "건대입구" not in [s[0] for s in both._near_stations(PLACE, 1200, 4)]


def test_skip_at_other_station_does_not_block():
    pl = _planner(ROWS, ({"kind": "station_skip", "line": "02호선", "station": "강남"},))
    assert pl._near_station(PLACE, 1200)[0] == "성수", "다른 역의 무정차는 이 역을 막지 않는다"


def test_station_k_uses_proposal_until_rule_lands():
    pl = _planner(ROWS)
    has_rule = "장소_역_후보_최대" in RULES.get("candidates", {})
    assert pl._station_k() == (RULES["candidates"]["장소_역_후보_최대"]["value"] if has_rule else P.STATION_K_PROPOSED)


# ── 전체층 — 실데이터(83 사례) ─────────────────────────────────────────
_RT = None


def _runtime():
    global _RT
    if _RT is None:
        from app.modules.travel_ops.mobility.engine.runtime import build_verifier
        try:
            _RT = build_verifier(quiet=True)
        except RuntimeError as e:
            _RT = e
    if isinstance(_RT, Exception):
        pytest.skip("시간표 없음(DATA_DIR) — 데이터 축 SKIP")
    return _RT


def _leg(disruptions=(), not_before=None):
    pl = P.Planner(_runtime(), stage="planning")
    pl.disruptions = tuple(disruptions)
    got, why = pl.leg(AQUARIUM, SEONGSU, ARRIVE, P.party_of(None, {}), True, "aq_to_ss", not_before_dt=not_before)
    if got is None:
        return None, why
    route = got[0]
    return next(o for o in route["options"] if o["id"] == route["planned"]), why


@pytest.mark.mobility_full
def test_full_no_disruption_is_unchanged():
    planned, why = _leg()
    assert planned is not None, why
    assert planned["uses"] == ["2호선:잠실", "2호선:성수"], "사고가 없으면 가장 가까운 역끼리 — 앞 판과 같다"


@pytest.mark.mobility_full
def test_full_nearest_skipped_gives_next_station_route():
    """83 E1 — 성수역 무정차에서 앞 판은 「잠실→성수 후보 1개 중 성립 0개」였다."""
    planned, why = _leg(SKIP_SEONGSU)
    assert planned is not None, f"다음 역 경로가 나와야 한다 — {why}"
    assert "2호선:성수" not in planned["uses"], planned
    assert planned["uses"][-1].split(":")[1] in ("뚝섬", "서울숲", "건대입구"), planned


@pytest.mark.mobility_full
def test_full_only_blocked_stations_is_no_service():
    closed = ({"kind": "line_closed", "line": "02호선"}, {"kind": "line_closed", "line": "수인분당선"})
    planned, why = _leg(closed)
    assert planned is None or not planned["uses"], "막힌 역만 있으면 대중교통 경로를 내지 않는다"
    if planned is None:
        assert why["code"] == P.STATION_BLOCKED_CODE and SEONGSU["name"] in why["reason"], why


def test_blocked_code_matches_room_spec():
    assert P.STATION_BLOCKED_CODE == "no_service"


def test_blocked_only_gate_synthetic():
    """게이트판 — 목적지 쪽 역이 전부 막히면 판정기를 부르지 않고 no_service 로 끝난다(작은 역표)."""
    dest = [r for r in ROWS if r[1]["station_nm"] != "건대입구"]          # 목적지 쪽 = 성수·뚝섬·서울숲
    src = [(200.0, {"station_nm": "잠실", "line": "08호선", "lines": ["02호선", "08호선"]})]
    pl = _planner({0.0: src, 0.05: dest},
                  ({"kind": "line_closed", "line": "02호선"}, {"kind": "line_closed", "line": "수인분당선"}))
    pl._vc = lambda case: pytest.fail("막힌 역만 있으면 판정기를 부르지 않는다")
    pl.modes = {"subway"}
    got, why = pl.leg(dict(PLACE, key="a", name="출발"), dict(PLACE, key="b", name="도착", lat=0.05),
                      ARRIVE, {}, True, "a_to_b")
    assert got is None and why["code"] == "no_service" and "도착" in why["reason"], why


# ── 게이트 — GPT 85 대조로 더한 축 ─────────────────────────────────────
def test_ambiguous_station_skip_blocks_only_that_physical_station():
    """동명이역(양평 5호선 ↔ 경의중앙선 양평) — 실제 StationCoords 로. 5호선 양평 무정차는 5호선 양평만 막는다."""
    from app.modules.travel_ops.mobility.engine.geo import StationCoords
    sc = StationCoords({"stations": {
        "양평|05호선": {"station_key": "양평|05호선", "station_nm": "양평", "line": "05호선", "lat": 37.5343, "lng": 126.8859},
        "양평|경의선": {"station_key": "양평|경의선", "station_nm": "양평", "line": "경의선", "lat": 37.4925, "lng": 127.4917}}},
        ambig_m=1000)
    assert sc.is_ambiguous("양평")
    pl = _planner([], ({"kind": "station_skip", "line": "05호선", "station": "양평"},))
    pl.v.sc = sc
    recs = {r["line"]: r for r in sc.by_key.values()}
    assert pl._blocked_station(recs["05호선"]) is True
    assert pl._blocked_station(recs["경의선"]) is False, "같은 이름의 다른 물리적 역은 막지 않는다"


def _opt(pi, start, uses=("1호선:가", "1호선:나"), n=1, key=None):
    legs = [{"line": "01호선", "from": "가", "to": "나"}]
    return {"eta_min": 20, "uses": list(uses), "_legs": legs, "_route": f"짝{pi}", "_start": start,
            "_transfers": 0, "_n": 1000 * pi + n, "_key": key or ("rail", pi, n), "_margin": 0, "_slack": 0,
            "_walk_min": 0, "_walk_m": None, "_fare": None, "_severe": [], "_covered": False,
            "_check": {"date": "2026-09-23", "legs": legs, "off": 0, "walk_place_in": 0, "walk_place_out": 0,
                       "walk_stop_in": 0, "walk_stop_out": 0, "by_station": 690}}


def _pair_planner(per_pair, revive=lambda o, start: None):
    """역 짝 3개(짝0 = 가장 가까운 짝) · 짝마다 per_pair[pi] 후보. 판정기는 부르지 않는다. 본 짝 순번을 seen 에."""
    pl = _planner([])
    pl.modes = {"subway"}
    pl._near_stations = lambda place, limit, k=None: ([("A1", 100.0, None), ("A2", 300.0, None)] if place["key"] == "a"
                                                      else [("B1", 100.0, None), ("B2", 300.0, None)])
    seen = []

    def tp(xa, xb, pi, *a):
        seen.append(pi)
        return [dict(o) for o in per_pair.get(pi, [])], SimpleNamespace(candidates=[1], out={"code": "no_data", "reason": "짝 실패"},
                                                                         reason="짝 실패"), 1
    pl._transit_pair = tp
    pl._recheck_at = lambda o, start, *a: ((revive(o, start), None) if revive(o, start) else (None, "infeasible"))
    return pl, seen


A_, B_ = dict(PLACE, key="a", name="출발"), dict(PLACE, key="b", name="도착", lat=0.05)
NB = datetime.fromisoformat("2026-09-23T10:45:00+09:00")          # 645분
ARR = datetime.fromisoformat("2026-09-23T11:30:00+09:00")          # 690분


def test_pair_search_stops_at_first_pair_when_it_works():
    pl, seen = _pair_planner({0: [_opt(0, 650)], 1: [_opt(1, 660)]})
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b", not_before_dt=NB)
    assert got is not None and seen == [0], "첫 짝으로 답이 나오면 다음 짝을 안 본다(앞 판과 같다)"


def test_pair_search_goes_on_when_first_pair_leaves_before_prev_end():
    """83 사례 모양 — 첫 짝은 앞 일정 끝(10:45)보다 1분 일찍 떠나야 하고 재판정도 안 된다 → 다음 짝."""
    pl, seen = _pair_planner({0: [_opt(0, 644)], 1: [_opt(1, 650)]})
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b", not_before_dt=NB)
    assert got is not None and seen[:2] == [0, 1], (seen, why)
    assert got[1] == 650, "다음 짝의 후보(10:50 출발)가 계획 수단"


def test_pair_search_stops_when_first_pair_revives_at_prev_end():
    """첫 짝이 nb 에서 재판정으로 살아나면 거기서 멈춘다 — 뒤 선택 로직(nb 재판정)과 같은 기준."""
    pl, seen = _pair_planner({0: [_opt(0, 644)], 1: [_opt(1, 650)]},
                             revive=lambda o, start: dict(o, _start=start) if o["_key"][1] == 0 else None)
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b", not_before_dt=NB)
    assert got is not None and seen == [0] and got[1] == 645, (seen, got and got[1])


def test_pair_search_skips_pair_whose_candidates_fail_uses_check():
    """GPT 85 #2 — 첫 짝 후보가 모두 uses 표기 검사에서 탈락하면 멈추지 않고 다음 짝을 본다."""
    pl, seen = _pair_planner({0: [_opt(0, 650, uses=("엉뚱",))], 1: [_opt(1, 650)]})
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b", not_before_dt=NB)
    assert got is not None and seen[:2] == [0, 1], (seen, why)
    assert all(o["uses"] != ["엉뚱"] for o in got[0]["options"])


def test_all_pairs_fail_reason_names_the_pairs():
    """GPT 85 #3 — 여러 짝이 모두 실패하면 첫 짝 이유를 전체 원인처럼 내지 않는다."""
    pl, seen = _pair_planner({})
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b", not_before_dt=NB)
    assert got is None and len(seen) > 1
    assert why["reason"].startswith(f"검토한 역 짝 {len(seen)}개") and "A1→B1: 짝 실패" in why["reason"], why


def test_revive_keys_do_not_collide_on_same_sort_number():
    """GPT 85 #4 — _n 이 같아도(버스 100+901 = 짝1 후보 1001) 재판정 되돌림은 _key 로 가려 후보를 덮어쓰지 않는다."""
    bus = dict(_opt(0, 640, uses=("버스:101",)), _n=1001, _key=("bus", 0, 901), _route="버스", eta_min=25,
               _legs=[{"mode": "bus", "route": "101", "from": "가", "to": "나"}])
    pl, seen = _pair_planner({0: [_opt(0, 640, n=1)], 1: [_opt(1, 640, n=1)]},
                             revive=lambda o, start: dict(o, _start=start))
    pl._bus_direct = lambda *a, **k: [bus]
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b", not_before_dt=NB)
    assert got is not None
    labels = sorted(o["label"] for o in got[0]["options"])
    assert any("버스" in x for x in labels) and len(labels) == len(set(labels)), labels


def test_same_nearest_station_still_walk_only():
    """앞 판 정책 유지(사각지대로 기록) — 막힌 역을 뺀 뒤 양쪽 첫 역이 같으면 다른 짝을 보지 않는다."""
    pl, seen = _pair_planner({0: [_opt(0, 650)]})
    pl._near_stations = lambda place, limit, k=None: [("같은역", 100.0, None), ("B2", 300.0, None)]
    got, why = pl.leg(A_, B_, ARR, {}, True, "a_to_b")
    assert got is None and seen == [] and "가장 가까운 역이 같다" in why["reason"], why


@pytest.mark.parametrize("bad", [0, -1, 2.5, True, "3"])
def test_station_k_rule_value_must_be_positive_int(bad):
    pl = _planner([])
    pl.v.R = dict(pl.v.R, candidates=dict(pl.v.R["candidates"], 장소_역_후보_최대={"value": bad}))
    with pytest.raises(ValueError, match="장소_역_후보_최대"):
        pl._station_k()
