# -*- coding: utf-8 -*-
"""4차 v4 — 이동(mobility) 팀 값. 세 문서가 같은 값을 쓰도록 한곳에 둔다.

출처: 이동 팀 보고 1차(2026-09-16 결과서 두 건), 2차(2026-09-28, 브랜치 role-mobility 94dd707 의 결과서 v3·ML 학습결과서 v2 를 옮긴 파일).
★전부 팀 보고다(이번 작성에서 재실행하지 않았다). 개인 통근 동선은 노선·정류장을 옮기지 않고 개수로만 적는다.
"""
MOB = dict(
    timetable=463_326, judged=444_915, no_departure=18_411,
    airport=(8_949, 180), bus_routes=717, bus_stops=41_820, edges=777, stations=793, transfer=(213, 74), congestion=65_169, holidays=46,
    dest_filled=20_548, profile=(40_776, 41_103), profile_days=100, fare=(243, 432),
    regression=[("09-16", 85), ("09-20", 97), ("09-23", 123), ("09-24", 140), ("09-25", 168)],      # 마지막 값이 2차 보고서의 잠근 값
    reg_later=171, probes_later=15_792,                                                              # 이후 커밋(PR_NOTE, 42구간)
    probes=12_032, probe_detail=dict(infeasible=3_998, feasible=6_859, unknown=1_175), probes_prev=8_648,
    rules="v0.9.1", warn_codes=48, bus_names=59,
    field=dict(commute=5, tags_trips=29, tags=90, fare_sum=44_100),
    profile_rows=8_743_191, transfer_car=(1_017, 528, 227), station_keys=793,
    ml=dict(majority=0.678, logreg=(0.808, 0.118), mlp=(0.823, 0.122), hgb=(0.848, 0.120), hgb_v2=(0.893, 0.078), subway=0.992, bus=0.405,
            regress=("71/85", "73/85"), no_evidence=("376/376", "56/376", "275/3,342"), probes=8_648, probes_v2=11_656, feats=(27, 33)),
)
SRC = ("이동 팀 보고 2차(2026-09-28) 기준이다. 브랜치 role-mobility(94dd707, 2026-09-27)의 이동 모듈 결과서(데이터 전처리 결과서 v3, ML 학습결과서 v2)를 인용하며, "
       "이번 문서 작성에서 재실행하지 않았다. 판정 회귀 168건·규칙 v0.9.1은 이동 팀이 기기에서 재실행해 잠근 값이다. 1차 기준선은 2026-09-16 결과서다.")


