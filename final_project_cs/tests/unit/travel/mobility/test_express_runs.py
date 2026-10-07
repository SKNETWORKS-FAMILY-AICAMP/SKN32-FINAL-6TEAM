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
    assert EX.available() == ["09호선"]
    weekday = EX.load_line("09호선")["weekday"]
    runs = {id(r): r for _nm, _m, r in weekday}.values()
    assert sum(1 for r in runs if r.express) > 100 and sum(1 for r in runs if not r.express) > 100
    ex = [r.ride_min("여의도", "봉은사") for r in runs if r.express and r.dir == "U"]
    ge = [r.ride_min("여의도", "봉은사") for r in runs if not r.express and r.dir == "U"]
    ex, ge = [x for x in ex if x], [x for x in ge if x]
    assert ex and ge and statistics.median(ex) + 8 < statistics.median(ge), "급행이 일반보다 한참 빠르다(2026-10-07 실측 19.8 vs 31.5분)"
    assert all(not r.serves("여의도", "샛강") for r in runs if r.express), "급행은 샛강에 서지 않는다"


def test_timetable_replaces_a_line_with_its_run_table_only_when_the_file_has_that_line(tmp_path):
    rows = [{"line": "09호선", "station_nm": "여의도", "day_type": "weekday", "dep_time": "09:00:00", "dir": "U", "dest_nm": "중앙보훈병원",
             "fetched_at": "2026-09-09"},
            {"line": "01호선", "station_nm": "서울역", "day_type": "weekday", "dep_time": "09:00:00", "dir": "U", "dest_nm": "소요산",
             "fetched_at": "2026-09-09"}]
    p = tmp_path / "t.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tt = Timetable.load(p)
    deps = tt.departures("09호선", "여의도", "weekday")
    assert len(deps) > 100 and all(isinstance(d, Dep) and d.run is not None for d in deps), "9호선은 열차 단위 표로 읽는다"
    assert [d.run for d in tt.departures("01호선", "서울역", "weekday")] == [None], "다른 노선은 그대로"
    assert tt.has_station("09호선", "샛강")
    plain = Timetable.load(p, express=False)
    assert len(plain.departures("09호선", "여의도", "weekday")) == 1, "스위치를 끄면 종전"
    only1 = tmp_path / "u.jsonl"
    only1.write_text(json.dumps(rows[1], ensure_ascii=False) + "\n", encoding="utf-8")
    assert not Timetable.load(only1).has_station("09호선", "여의도"), "그 노선이 없는 시간표 파일에 표를 끼워 넣지 않는다"


def test_non_express_station_headway_is_the_real_one():
    tt = Timetable.load(_empty_with_line9())
    n = sum(1 for d in tt.departures("09호선", "공항시장", "weekday") if d.dir == "U")   # 한 방향
    assert 100 <= n <= 140, f"공항시장은 일반만 선다 — 통합 시간표는 한 방향 239편이었다, 실제는 약 124편(받은 값 {n})"


def _empty_with_line9():
    import tempfile
    import pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "t.jsonl"
    p.write_text(json.dumps({"line": "09호선", "station_nm": "여의도", "day_type": "weekday", "dep_time": "09:00:00", "dir": "U",
                             "dest_nm": "중앙보훈병원", "fetched_at": "2026-09-09"}, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
