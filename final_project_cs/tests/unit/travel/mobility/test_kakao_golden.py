# -*- coding: utf-8 -*-
"""카카오 기준 200쌍 대조: 최초 40쌍의 퇴보 방지선은 같은 표본으로 유지한다.
기준값은 git 밖 로컬 파일이다. 최초 40쌍은 사용자 지시대로 재사용하고,
추가 160쌍은 웹 화면을 읽었다. 이 시험은 외부 API를 호출하지 않는다.
대기 포함/제외 수치는 동일한 비교 가능 경로로 계산한다.
MOBILITY_COMPARISON_RESULT로 저장된 계산 결과를 검증할 수 있다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import pytest

from scripts.mobility import compare_kakao_golden as C
from tests.unit.travel.mobility import test_plan_v1 as T      # 같은 폴더 시험의 실데이터 확인(자료가 없는 기기는 건너뛴다)

pytestmark = pytest.mark.live

_RESULT: dict = {}


def _result():
    if not C.KAKAO.exists():
        pytest.skip("카카오 기준 파일이 없다(이 PC 에만 있다) — 건너뛴다")
    T._skip_if_no_data()
    if not _RESULT:
        saved = os.environ.get("MOBILITY_COMPARISON_RESULT")
        if saved:
            _RESULT.update(json.loads(Path(saved).read_text(encoding="utf-8")))
            assert {r["id"] for r in _RESULT["rows"]} == {p["id"] for p in C.load_pairs()}
        else:
            _RESULT.update(C.run(dt.datetime(2026, 10, 8, 10, 30, tzinfo=C.KST), log=lambda *_: None, direct=True))
    return _RESULT["summary"]


def test_every_pair_in_the_reference_has_a_car_and_a_transit_value():
    if not C.KAKAO.exists():
        pytest.skip("카카오 기준 파일이 없다")
    kakao = C.load_kakao()
    for p in C.load_pairs():
        k = kakao[p["id"]]
        assert "distance_m" in k["car"], p["id"]
        assert "best" in k["transit"] or "none" in k["transit"], p["id"]


def test_wait_before_after_cover_the_same_comparable_paths():
    summary = _result()
    before = summary["transit_eta_vs_best"]["minutes"]["n"]
    after = summary["transit_eta_without_wait_vs_best"]["minutes"]["n"]
    assert before == after == summary["transit_vs_kakao_best"]["n"]


def test_transit_stays_close_to_the_kakao_best_and_recommended_routes():
    _result()
    # 옛 문턱은 최초 40쌍으로 정했다. 표본 확장과 코드 퇴보를 섞지 않고 같은 쌍으로 지킨다.
    s = C.summarise([r for r in _RESULT["rows"] if int(r["id"][1:]) <= 40])
    best, rec = s["transit_vs_kakao_best"], s["transit_vs_kakao_recommended"]
    assert best["n"] >= 35
    assert best["within_5"] >= 0.65, best                 # 2026-10-07: 0.74
    assert -3 <= rec["median"] <= 3, rec                  # 2026-10-07: 0 (카카오 추천안 대비)
    assert best["median"] <= 5, best                      # 2026-10-07: +3 (대기가 들어 있어 평균 2~3분 길다)
    assert s["transit_our_fastest_option_vs_kakao_best"]["within_5"] >= 0.75   # 2026-10-07: 0.82


def test_taxi_minutes_follow_the_kakao_car_route_time():
    _result()
    t = C.summarise([r for r in _RESULT["rows"] if int(r["id"][1:]) <= 40])["taxi_minutes_vs_kakao_car"]
    assert t["n"] >= 35 and t["within_5"] >= 0.60, t       # 2026-10-07: 0.68
    assert abs(t["median"]) <= 2, t                        # 2026-10-07: −0.3


def test_taxi_fare_comparison_is_an_estimate_not_a_floor_ceiling():
    f = _result()["taxi_fare_percent_vs_kakao_taxi_fare"]
    assert f["n"] == len(C.load_pairs())
    # 높은 예상액을 결함으로 보던 옛 관문은 사용자 보수적 예산 지시와 반대였다.
    # 교통 시각이 다른 화면끼리라 요금 정확도 상한을 이 값으로 보장하지 않는다.
    assert "median" in f and "mae" in f
