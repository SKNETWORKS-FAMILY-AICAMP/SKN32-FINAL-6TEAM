# -*- coding: utf-8 -*-
"""카카오 기준 세트 대조 — 우리 이동 도구가 카카오 값에서 얼마나 벌어졌는지 **숫자로 지킨다**. `[2026-10-07 사용자 지시]`

★기준 값(카카오가 준 값)은 저장소에 없다 — `datasets/mobility/raw/kakao_golden/kakao_routes_v1.json`(이 PC 안에서만 · `raw/` 는 .gitignore). 파일이 없으면 이 시험은 건너뛴다.
  장소 쌍 40개(이름·좌표뿐)는 `golden_pairs_v1.json` 에 있다. 값을 다시 받는 법: `scripts/mobility/collect_kakao_car_golden.py`(자동차 — API) · 카카오맵 웹 화면 읽기(대중교통·도보).
★느린 시험이다(쌍마다 이동 계산기를 돌린다 · 4~6분) — `live` 표시라 기본 시험에서 빠진다: `python -m pytest tests/unit/travel/mobility/test_kakao_golden.py -m live`.
★문턱은 2026-10-07 측정값에서 조금 여유를 둔 **퇴보 방지선**이다(정답 기준이 아니다): 대중교통 카카오 최단 대비 ±5분 74% · 추천 대비 중앙 0분 · 택시 소요 ±5분 68%.
  카카오 총 소요에는 대기가 없고 우리에게는 있다 — 그래서 우리가 평균 2~3분 길게 나오는 것이 정상이다.
"""
from __future__ import annotations

import datetime as dt
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
        try:
            _RESULT.update(C.run(dt.datetime(2026, 10, 8, 10, 30, tzinfo=C.KST), log=lambda *_: None, direct=True))
        except Exception as exc:                                  # 이동 자료가 없는 기기
            pytest.skip(f"이동 계산기를 못 올렸다 — {str(exc)[:80]}")
    return _RESULT["summary"]


def test_every_pair_in_the_reference_has_a_car_and_a_transit_value():
    if not C.KAKAO.exists():
        pytest.skip("카카오 기준 파일이 없다")
    kakao = C.load_kakao()
    for p in C.load_pairs():
        k = kakao[p["id"]]
        assert "distance_m" in k["car"], p["id"]
        assert "best" in k["transit"] or "none" in k["transit"], p["id"]


def test_transit_stays_close_to_the_kakao_best_and_recommended_routes():
    s = _result()
    best, rec = s["transit_vs_kakao_best"], s["transit_vs_kakao_recommended"]
    assert best["n"] >= 35
    assert best["within_5"] >= 0.65, best                 # 2026-10-07: 0.74
    assert -3 <= rec["median"] <= 3, rec                  # 2026-10-07: 0 (카카오 추천안 대비)
    assert best["median"] <= 5, best                      # 2026-10-07: +3 (대기가 들어 있어 평균 2~3분 길다)
    assert s["transit_our_fastest_option_vs_kakao_best"]["within_5"] >= 0.75   # 2026-10-07: 0.82


def test_taxi_minutes_follow_the_kakao_car_route_time():
    t = _result()["taxi_minutes_vs_kakao_car"]
    assert t["n"] >= 35 and t["within_5"] >= 0.60, t       # 2026-10-07: 0.68
    assert abs(t["median"]) <= 2, t                        # 2026-10-07: −0.3


def test_the_taxi_fare_is_never_far_above_the_kakao_estimate_because_it_is_a_floor():
    f = _result()["taxi_fare_percent_vs_kakao_taxi_fare"]
    assert f["median"] <= 5, f                             # 2026-10-07: −10.9 (하한이라 낮은 쪽 — 위로 크게 벗어나면 결함)
    assert f["ours_longer_than_5"] <= 8, f                 # 2026-10-07: 2
