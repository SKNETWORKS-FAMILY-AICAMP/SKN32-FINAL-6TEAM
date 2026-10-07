# -*- coding: utf-8 -*-
"""9호선 급행 — 열차 단위 운행표(서울 열린데이터광장 OA-101) 반영 (2026-10-07).

카카오맵 대조에서 나온 두 빈틈: ① 급행을 몰라 급행 구간이 늦게 나온다(여의도→코엑스 45분 · 카카오 38분)
② 통합 시간표에는 급행이 안 서는 역에도 급행이 선 것으로 들어 있어 그 역 배차가 절반으로 보였다(공항시장 평일 239편 · 실제 124편).
"""
from __future__ import annotations

import json
import statistics
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine import express as EX
from app.domains.travel_ops.instances.mobility.engine.verify_time import Dep, Timetable

NAMES = ["가", "나", "다", "라"]


def _run(express, seq, dir_="U"):
    return EX.Run("T1", express, dir_, seq, NAMES)


def test_a_run_serves_only_stations_it_stops_at_in_travel_order():
    r = _run(1, [(0, None, 600), (2, 660, 670), (3, 720, None)])        # 가 → 다 → 라 (나는 지나친다)
    assert r.serves("가", "다") and r.serves("다", "라") and r.serves("가", "라")
    assert not r.serves("가", "나"), "급행이 서지 않는 역에는 내릴 수 없다"
    assert not r.serves("다", "가"), "반대 순서는 아니다"
    assert not r.serves("라", "가") and r.dest == "라"


def test_ride_minutes_come_from_the_train_own_times_not_station_averages():
    r = _run(1, [(0, None, 600), (2, 660, 670), (3, 735, None)])
    assert r.ride_min("가", "다") == 1.0 and abs(r.ride_min("가", "라") - 2.25) < 1e-9
    assert r.ride_min("가", "나") is None


def test_ride_of_prefers_the_run_and_falls_back_to_the_path_average():
    lo = SimpleNamespace(travel_min_on_path=lambda line, path, target: 99.0)
    v = SimpleNamespace(path=["가", "다"])
    run = _run(1, [(0, None, 600), (2, 660, 670)])
    assert EX.ride_of(lo, "09호선", SimpleNamespace(run=run), v, "가", "다") == 1.0
    assert EX.ride_of(lo, "09호선", SimpleNamespace(run=None), v, "가", "다") == 99.0, "표가 없는 열차는 종전"
    assert EX.ride_of(lo, "09호선", SimpleNamespace(run=run), v, "가", "나") == 99.0, "표에 없는 구간도 종전(조용한 None 이 아니다)"


def test_the_shipped_line9_table_separates_express_from_general():
    assert sorted(EX.available()) == ["01호선", "09호선"]
    weekday = EX.load_line("09호선")["weekday"]
    runs = {id(r): r for _nm, _m, r in weekday}.values()
    assert sum(1 for r in runs if r.express) > 100 and sum(1 for r in runs if not r.express) > 100
    ex = [r.ride_min("여의도", "봉은사") for r in runs if r.express and r.dir == "U"]
    ge = [r.ride_min("여의도", "봉은사") for r in runs if not r.express and r.dir == "U"]
    ex, ge = [x for x in ex if x], [x for x in ge if x]
    assert ex and ge and statistics.median(ex) + 8 < statistics.median(ge), "급행이 일반보다 한참 빠르다(2026-10-07 실측 19.8 vs 31.5분)"
    assert all(not r.serves("여의도", "샛강") for r in runs if r.express), "급행은 샛강에 서지 않는다"


def _write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


def _row(line, nm, dest="중앙보훈병원"):
    return {"line": line, "station_nm": nm, "day_type": "weekday", "dep_time": "09:00:00", "dir": "U", "dest_nm": dest,
            "fetched_at": "2026-09-09"}


def test_timetable_replaces_a_line_with_its_run_table_only_for_a_real_full_timetable(tmp_path):
    real = [_row("09호선", nm) for nm in sorted(EX.stations_of("09호선"))] + [_row("02호선", "잠실", "성수")]
    p = _write(tmp_path, "t.jsonl", real)
    tt = Timetable.load(p, express=True)
    deps = tt.departures("09호선", "여의도", "weekday")
    assert len(deps) > 100 and all(isinstance(d, Dep) and d.run is not None for d in deps), "9호선은 열차 단위 표로 읽는다"
    assert [d.run for d in tt.departures("02호선", "잠실", "weekday")] == [None], "다른 노선은 그대로"
    assert tt.has_station("09호선", "샛강")
    assert len(Timetable.load(p).departures("09호선", "여의도", "weekday")) == 1, "기본은 꺼짐 — 시험용 축소 시간표를 건드리지 않는다"
    mini = _write(tmp_path, "mini.jsonl", [_row("09호선", "여의도")])
    assert len(Timetable.load(mini, express=True).departures("09호선", "여의도", "weekday")) == 1, "역이 80% 미만인 파일(시험용 축소판)에는 표를 끼우지 않는다"
    only2 = _write(tmp_path, "u.jsonl", [_row("02호선", "잠실", "성수")])
    assert not Timetable.load(only2, express=True).has_station("09호선", "여의도"), "그 노선이 없는 파일에 표를 끼워 넣지 않는다"


def test_non_express_station_headway_is_the_real_one(tmp_path):
    p = _write(tmp_path, "t.jsonl", [_row("09호선", nm) for nm in sorted(EX.stations_of("09호선"))])
    tt = Timetable.load(p, express=True)
    n = sum(1 for d in tt.departures("09호선", "공항시장", "weekday") if d.dir == "U")   # 한 방향
    assert 100 <= n <= 140, f"공항시장은 일반만 선다 — 통합 시간표는 한 방향 239편이었다, 실제는 약 124편(받은 값 {n})"


def test_line1_run_table_has_express_trains_that_skip_stations():
    runs = {id(r): r for _nm, _m, r in EX.load_line("01호선")["weekday"]}.values()
    assert sum(1 for r in runs if r.express) > 100 and len(runs) > 500
    skip = [r for r in runs if r.express and not r.serves("서울역", "남영") and r.serves("서울역", "용산")]
    assert skip, "1호선 급행은 남영 같은 작은 역을 지나친다"
    gen = [r.ride_min("서울역", "용산") for r in runs if not r.express and r.serves("서울역", "용산")]
    assert gen and min(gen) > 0
