# -*- coding: utf-8 -*-
"""경로 대안의 요금 규칙 — 이동 계산기 문제목록(2026-09-29) #22·#23.

#22 요금을 모르는 경로 후보를 탈락시키지 않는다(버스를 섞어 갈아타는 대안은 요금 칸이 없다). 대신 아는 후보 뒤.
#23 원래 계획 요금을 모르면 0원으로 두지 않는다 — 추가 비용은 모름.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.travel_ops.replan import route_candidates

KST = timezone(timedelta(hours=9))
DEPART = datetime(2026, 10, 7, 10, 50, tzinfo=KST)


def _route(planned_fare, options):
    return {"planned": "planned", "options": [{"id": "planned", "label": "계획", "eta_min": 13, "uses": ["2호선:잠실"],
                                                **({"fare_krw": planned_fare} if planned_fare is not None else {})},
                                               *options]}


def _pick(cands):
    ok = [c for c in cands if not c.rejected]
    return min(ok, key=lambda c: c.rank()) if ok else None


def test_22_unknown_fare_option_is_kept_not_rejected():
    route = _route(1400, [{"id": "bus_mix", "label": "2호선→버스", "eta_min": 20, "uses": ["버스:2224"]}])
    cands = route_candidates(route=route, depart=DEPART, planned_arrival=DEPART + timedelta(minutes=13),
                             next_start=DEPART + timedelta(minutes=40),
                             events={"2호선:잠실": {"effect": "skip_station", "summary": "2호선 잠실 무정차"}})
    by = {c.key: c for c in cands}
    assert by["planned"].rejected, "사건이 걸린 계획 경로는 탈락"
    assert by["bus_mix"].rejected == [], "앞 판은 「요금을 몰라 추가 비용을 계산할 수 없다」로 탈락시켰다"
    assert _pick(cands).key == "bus_mix", "남은 대안이 요금 모름 하나뿐이면 그것을 고른다"


def test_22_known_fare_option_ranks_before_unknown():
    route = _route(1400, [{"id": "a_unknown", "label": "버스 섞임", "eta_min": 15, "uses": ["버스:1"]},
                          {"id": "b_known", "label": "지하철", "eta_min": 15, "uses": ["3호선:교대"], "fare_krw": 1500}])
    cands = route_candidates(route=route, depart=DEPART, planned_arrival=DEPART + timedelta(minutes=13),
                             next_start=DEPART + timedelta(minutes=40),
                             events={"2호선:잠실": {"effect": "skip_station", "summary": "무정차"}})
    assert _pick(cands).key == "b_known", "요금 모름을 0원(가장 쌈)으로 보고 앞세우지 않는다"


def test_23_unknown_planned_fare_is_not_zero():
    route = _route(None, [{"id": "alt", "label": "지하철", "eta_min": 15, "uses": ["3호선:교대"], "fare_krw": 1500}])
    cands = route_candidates(route=route, depart=DEPART, planned_arrival=DEPART + timedelta(minutes=13),
                             next_start=None, events={})
    alt = next(c for c in cands if c.key == "alt")
    assert alt.extra_cost_krw is None, "앞 판은 원래 요금을 0원으로 보고 추가 비용 1,500원을 지어냈다"
