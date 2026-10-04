# -*- coding: utf-8 -*-
"""선로 길이 추정 요금망 검증(#21 · 2026-10-04) — 공표 거리를 일부러 가리고(추정만) 낸 요금이 공표로 낸 요금과 얼마나 같은가.

실행(final_project_cs 에서): python scripts/mobility/validate_fare_estimate.py
자료: ../datasets/mobility/processed/mobility/rail_edge_track_v1.jsonl.gz (datasets/mobility/scripts/build_rail_edge_distance_v1.py 가 만든다)"""
import copy, gzip, json, math, random, sys
sys.path.insert(0, ".")
from app.modules.travel_ops.mobility.engine import options as O
from app.modules.travel_ops.mobility.engine.line_order import LineOrder
from app.modules.travel_ops.mobility.engine.geo import StationCoords
from pathlib import Path
D = Path("../datasets/mobility/processed/mobility")
lo = LineOrder.load(str(D / "line_station_order_v1.json"))
sc = StationCoords.load(str(D / "station_coords.json")) if hasattr(StationCoords, "load") else None
rule = json.load(open("app/modules/travel_ops/mobility/engine/rules/rules_v0.3.json", encoding="utf-8"))["fare"]
tau = rule["subway"]["distance_estimate"]["value"]["tolerance"]
# 추정 간선(공표 행 포함) — 검증용으로 공표 간선도 선로 길이로
est_all = {}
floor = {}
for l in gzip.open(D / "rail_edge_track_v1.jsonl.gz", "rt", encoding="utf-8"):
    r = json.loads(l)
    t, st = r.get("track_m"), r.get("straight_m")
    if t is None or st is None or t > st * 1.5 + 150:
        if st is not None:
            floor[(r["line"], r["a"], r["b"])] = int(st * 0.75)
        continue
    est_all[(r["line"], r["a"], r["b"])] = int(t)
cfg = {"연결_반경_m": 300}
F = rule
net_off = O.FareNet(lo, sc, None, cfg)                      # 공표만
doc2 = copy.deepcopy(lo.doc)
for ln, d in doc2["lines"].items():
    for e in d["edges"]:
        e["distance_m"] = None
lo2 = LineOrder(doc2)
net_est = O.FareNet(lo2, sc, None, cfg, est_all, tau, set(rule["subway"]["distance_estimate"]["value"]["lines"]), floor)           # 추정만(공표 가림)
random.seed(7)
tot = same = none_est = diff = 0
diffs = []
for ln in ("01호선", "02호선", "03호선", "04호선", "05호선", "06호선", "07호선", "08호선"):
    names = lo.stations(ln)
    for _ in range(120):
        a, b = random.sample(names, 2)
        legs = [{"line": ln, "from": a, "to": b}]
        if net_off.ridden_m(legs) is None:
            continue
        ub = net_off.upper_m(legs); lb = min(net_off.lower_m(legs) or 0, ub)
        f_off = O.subway_fare_at(F, ub, 700) if O.subway_fare_at(F, lb, 700) == O.subway_fare_at(F, ub, 700) else None
        if f_off is None:
            continue
        tot += 1
        if net_est.ridden_m(legs) is None:
            none_est += 1; continue
        ub2 = net_est.upper_m(legs); lb2 = min(net_est.lower_m(legs) or 0, ub2)
        f1, f2 = O.subway_fare_at(F, lb2, 700), O.subway_fare_at(F, ub2, 700)
        if f1 != f2:
            none_est += 1; continue
        if f2 == f_off: same += 1
        else:
            diff += 1; diffs.append((ln, a, b, f_off, f2, ub))
print(f"공표로 요금이 나오는 같은 노선 쌍 {tot}")
print(f"  추정만으로 값이 안 나옴(괄호가 한 요금으로 안 모임/선로 못 얻음) {none_est} = {none_est/tot*100:.0f}%")
print(f"  추정이 값을 냄 {same+diff} = {(same+diff)/tot*100:.0f}% 중 공표와 같음 {same} · 다름 {diff}")
for d in diffs[:8]: print("   다름:", d)
