# -*- coding: utf-8 -*-
"""이동 계산기 점검(2026-09-29) — 판정 본체(verify_time) 수정 회귀. 시간표 데이터 없이 작은 가짜 노선으로 돈다.

가짜 노선
  01호선  A — B — C — D      (역간 2분, 행선지 D)
  02호선  X — C — Y          (역간 2분, 행선지 Y)
  C 에서 갈아탄다. 환승 거리표에는 다른 역 쌍만 있다(C 는 없다).
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.domains.travel_ops.instances.mobility.engine.errors import CaseInputError
from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder
from app.domains.travel_ops.instances.mobility.engine.paths import RULES_DIR
from app.domains.travel_ops.instances.mobility.engine.timeutil import HolidayCalendar
from app.domains.travel_ops.instances.mobility.engine.transfer_walk import TransferWalk, ceil1
from app.domains.travel_ops.instances.mobility.engine.verify_time import Dep, Timetable, Verifier

RULES = json.loads((RULES_DIR / "rules_v0.3.json").read_text(encoding="utf-8"))


def _line(names, dest):
    return {"stations": [{"station_nm": n, "fr_order": i} for i, n in enumerate(names)],
            "edges": [{"a": a, "b": b, "grade": "확정", "travel_min": 2.0} for a, b in zip(names, names[1:])],
            "dir_label": {"reliable": True}, "is_loop": False}


def _net():
    return LineOrder({"built_at": "t", "dest_alias": {},
                      "lines": {"01호선": _line(["A", "B", "C", "D"], "D"),
                                "02호선": _line(["X", "C", "Y"], "Y")}})


def _tt(first_by_type=None, per_hour=6, until=23 * 60):
    """시간표 — 01호선은 A·B·C 에서 D 행, 02호선은 X·C 에서 Y 행. 요일형별 첫차를 바꿀 수 있다."""
    tt = Timetable()
    first_by_type = first_by_type or {"weekday": 5 * 60 + 30, "holiday": 5 * 60 + 30}
    for day_type, first in first_by_type.items():
        for line, stations, dest in (("01호선", ["A", "B", "C"], "D"), ("02호선", ["X", "C"], "Y")):
            for k, st in enumerate(stations):
                for m in range(first, until + 1, 60 // per_hour):
                    tt.by_key[(line, st, day_type)].append(Dep(m + 2 * k, "D", dest))
                tt.stations.add((line, st))
        tt.stations |= {("01호선", "D"), ("02호선", "Y")}
    for v in tt.by_key.values():
        v.sort(key=lambda d: d.min)
    tt.rows = sum(len(v) for v in tt.by_key.values())
    return tt


def _tw(pairs):
    return TransferWalk({"built_at": "t", "pairs": pairs, "stations": {}})


OTHER_PAIRS = {f"P{i}|01호선|02호선": {"distance_m": d} for i, d in enumerate([20, 60, 100, 150, 200, 250, 300, 320, 340, 400])}


def _v(tw=None, holidays=None, **kw):
    return Verifier(_tt(kw.pop("first_by_type", None)), _net(), RULES, holidays or set(), tw, **kw)


def _case(legs, **kw):
    return dict({"id": "t", "date": "2026-10-05", "depart_at": "10:00", "first_visit": False,
                 "no_alternatives": True, "legs": legs}, **kw)


TWO_LEGS = [{"line": "01호선", "from": "A", "to": "C"}, {"line": "02호선", "from": "C", "to": "Y"}]


# ── #2 올림 ──────────────────────────────────────────────────────────
def test_2_ceil1_never_shortens():
    assert ceil1(61 / 60) == 1.1 and ceil1(1.0) == 1.0 and ceil1(0.01) == 0.1
    tw = TransferWalk({"built_at": "t", "pairs": {"C|01호선|02호선": {"distance_m": 1.04 * 61}}, "stations": {}})
    w = tw.lookup("C", "01호선", "02호선")
    assert w.min == 1.1, "61초 걷기는 1.0 이 아니라 1.1 분 — 이후 올림하면 2분"


# ── #1 모르는 환승 도보 ─────────────────────────────────────────────
def test_1_unknown_transfer_uses_measured_p90_not_zero():
    res = _v(tw=_tw(OTHER_PAIRS)).verify_case(_case(TWO_LEGS))
    transfer = next(l for l in res.legs if l.label.startswith("환승"))
    assert "도보 0분" not in transfer.reason, "모르는 환승을 0분으로 채우지 않는다"
    p90 = _tw(OTHER_PAIRS).network_fallback()
    assert p90.basis == "network_p90" and p90.distance_m == 340
    assert f"도보 {p90.min:g}분" in transfer.reason
    assert any(w["code"] == "MOB_W_TRANSFER_WALK_NETWORK_P90" for w in transfer.warnings)


def test_1_no_transfer_table_at_all_is_no_data():
    res = _v(tw=None).verify_case(_case(TWO_LEGS))
    assert res.verdict == "unknown", "거리표가 없으면 대체 출처도 없다 — 판정 불가"
    assert res.out["verdict"] == "infeasible" and res.out.get("code") == "no_data"


def test_1_stop_station_walk_without_coords_is_unknown():
    v = _v()
    v.bus = type("B", (), {"route": lambda self, n: None})()
    got = v._stop_station_walk({"line": "01호선", "to": "C"}, {"mode": "bus", "route": "1", "from": "C정류장"}, {})
    assert got["verdict"] == "unknown" and got["walk_min"] is None, "좌표가 없으면 0분·성립이 아니다"


# ── #11 이어지지 않는 구간 ───────────────────────────────────────────
def test_11_disconnected_subway_legs_are_rejected():
    legs = [{"line": "01호선", "from": "A", "to": "B"}, {"line": "02호선", "from": "C", "to": "Y"}]
    with pytest.raises(CaseInputError, match="이어지지 않는다"):
        _v(tw=_tw(OTHER_PAIRS)).verify_case(_case(legs))


# ── #4 새벽 첫차는 다음 운행일의 요일형으로 ─────────────────────────
def test_4_rollover_first_train_uses_next_day_type():
    # 2026-10-02(금, 평일) 운행일의 03:50 요청 → 다음 날 10-03(토·개천절)은 휴일 시간표. 휴일 첫차를 늦게 둔다.
    cal = HolidayCalendar({"2026-10-03"}, [2026, 2027])
    v = _v(holidays=cal, first_by_type={"weekday": 5 * 60 + 30, "holiday": 4 * 60 + 20})
    v._case_date = date(2026, 10, 2)
    nd_type, nd_first = v._next_day_first("01호선", "A", "C", "weekday", 5 * 60 + 30)
    assert nd_type == "holiday" and nd_first == 4 * 60 + 20
    r = v.verify_leg(1, {"line": "01호선", "from": "A", "to": "C"}, 27 * 60 + 50, "weekday", False)
    assert r.code == "before_first" and "holiday" in r.reason and "04:20" in r.reason, r.reason


# ── #6 혼잡해서 다음 편을 타야 하는데 다음 편이 없다 ───────────────────
class _Crowd:
    def lookup(self, line, station, dir, day_type, d, minute, L, is_holiday=False):
        return 120, "매우혼잡", {"source_id": "cg", "fetched_at": "t", "slot": "10:00", "day_type": day_type}


def test_6_crowded_without_next_train_is_graded_down_and_told():
    v = Verifier(_tt(per_hour=1, until=10 * 60), _net(), RULES, set(), None, cg_data=_Crowd())
    v._case_date = date(2026, 10, 5)
    lv = RULES["congestion"]["levels"]["매우혼잡"]
    if lv.get("action") != "board_wait_extra_headway":
        pytest.skip("규칙에서 매우혼잡 가산이 꺼져 있다")
    party = {c: True for c in (lv.get("조건") or ["luggage"])}
    r = v.verify_leg(1, {"line": "01호선", "from": "A", "to": "C"}, 9 * 60 + 25, "weekday", False,
                     worst=True, party=party)
    codes = {w["code"] for w in r.warnings}
    assert "MOB_W_CONGESTION_NO_NEXT" in codes and "MOB_W_CONGESTION_NO_NEXT_BOARD" in codes
    assert r.grade != "확정", "다음 편이 없으면 확정 성립으로 두지 않는다"


# ── #7 지하철 후보가 없어도 다른 수단 후보는 본다 ──────────────────────
def test_7_multi_without_subway_candidate_is_no_data_only_when_nothing_else():
    v = _v(tw=_tw(OTHER_PAIRS))
    res = v.verify_case({"id": "m", "date": "2026-10-05", "depart_at": "10:00",
                         "multi": {"from": "A", "to": "없는역"}})
    assert res.verdict == "unknown" and "지하철·버스 직행·자전거" in res.reason
