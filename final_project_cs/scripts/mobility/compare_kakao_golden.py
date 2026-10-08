# -*- coding: utf-8 -*-
"""우리 이동 도구를 카카오 기준 파일(시험 기준 세트)과 대조한다. `[2026-10-07 사용자 지시]`

실행(저장소 안에서):  python -m scripts.mobility.compare_kakao_golden [--arrive 2026-10-08T10:30] [--json out.json]

입력
  - 장소 쌍: `tests/unit/travel/mobility/golden_pairs_v1.json`(이름·좌표뿐 — 저장소에 있다)
  - 카카오 값: `datasets/mobility/raw/kakao_golden/kakao_routes_reused_v5.json`(★git 밖 로컬 파일)
대조
  - 대중교통: 우리 계획 수단의 소요(`eta_min` — 승차·환승 대기 포함, 정책 여유 제외) vs 카카오 최단안 · 추천안(총 소요에 **대기가 없다**)
  - 택시: 우리 택시 후보(`modes=[taxi]`)의 소요 · 요금 vs 카카오 자동차 길찾기의 소요 · 택시 요금
  - 걷기: 우리 보행 길 그래프의 거리 · 시간 vs 카카오 도보 최단(성인 4 km/h 환산)
출력: 요약 숫자(저장소에 적어도 되는 집계)와, 쌍별 표(카카오 값이 들어 있어 **로컬 파일로만** 쓴다).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAIRS = ROOT / "tests" / "unit" / "travel" / "mobility" / "golden_pairs_v1.json"
KAKAO = ROOT.parent / "datasets" / "mobility" / "raw" / "kakao_golden" / "kakao_routes_reused_v5.json"
KST = timezone(timedelta(hours=9))


def _stats(diffs: list[float], tol: int = 5) -> dict:
    if not diffs:
        return {"n": 0}
    absd = [abs(x) for x in diffs]
    return {"n": len(diffs), "median": round(statistics.median(diffs), 1), "mean": round(statistics.mean(diffs), 1),
            f"within_{tol}_count": sum(1 for x in absd if x <= tol),
            "mae": round(statistics.mean(absd), 1), f"within_{tol}": round(sum(1 for x in absd if x <= tol) / len(diffs), 2),
            f"ours_longer_than_{tol}": sum(1 for x in diffs if x > tol), f"ours_shorter_than_{tol}": sum(1 for x in diffs if x < -tol)}


def load_pairs():
    return json.loads(PAIRS.read_text(encoding="utf-8"))["pairs"]


def load_kakao():
    return json.loads(KAKAO.read_text(encoding="utf-8"))["routes"]


def _planner_leg(rt, modes):
    """조립 없이 판정기만 있을 때의 구간 계산기 — `wiring.leg_planner` 가 돌려주는 것과 같은 모양(`{"route": …}`)."""
    from app.modules.travel_ops.mobility.engine.plan import Planner, party_of

    planner = Planner(rt, stage="planning", modes=modes)
    planner.trace = []
    party = party_of(None, {})

    def leg(a, b, arrive):
        planner.trace.clear()
        got, why = planner.leg(a, b, arrive, party, True, case_id=f"{a['key']}_{b['key']}")
        return (None, why) if got is None else ({"route": got[0], "comparison": planner.trace[-1]}, None)
    return leg


def run(arrive: datetime, only: set[str] | None = None, log=print, direct: bool = True) -> dict:
    sys.path.insert(0, str(ROOT))
    from app.core.settings import get_settings
    from app.modules.travel_ops.mobility import wiring
    from app.modules.travel_ops.mobility.engine import runtime as ER
    from app.modules.travel_ops.mobility.engine.plan import Planner

    if not direct:
        wiring.configure_from_settings(get_settings(), preload=True)
    if not direct and wiring._STATE.get("kw") is not None:
        leg = wiring.leg_planner(None, {})
        leg_taxi = wiring.leg_planner(None, {}, modes=["taxi"])
        rt = ER.get_verifier(**wiring._STATE["kw"])
    else:                                                      # direct(시험 환경 — 조립이 꺼져 있다): 판정기를 직접 올려 같은 계산기를 만든다
        rt = ER.build_verifier(quiet=True, local_router=True)
        leg, leg_taxi = _planner_leg(rt, None), _planner_leg(rt, ["taxi"])
    pl = Planner(rt, stage="planning", modes=None)
    kakao = load_kakao()
    rows = []
    for p in load_pairs():
        if only and p["id"] not in only:
            continue
        k = kakao.get(p["id"]) or {}
        a = {"key": "a", "name": p["a"], "lat": p["alat"], "lon": p["alon"]}
        b = {"key": "b", "name": p["b"], "lat": p["blat"], "lon": p["blon"]}
        row = {"id": p["id"], "a": p["a"], "b": p["b"], "bucket": p["bucket"], "straight_m": p["straight_m"]}
        t0 = time.time()
        res, why = leg(a, b, arrive) if leg else (None, {"code": "off"})
        if res is not None:
            r = res["route"]
            planned = next(o for o in r["options"] if o["id"] == r["planned"])
            row["ours_transit"] = {"id": planned["id"], "eta": planned["eta_min"], "min_option_eta": min(o["eta_min"] for o in r["options"]),
                                   "walk_m": planned.get("walk_m"), "label": planned["label"][:80]}
            trace_options = (res.get("comparison") or {}).get("options", [])
            trace = next((o for o in trace_options if o["id"] == planned["id"]), {})
            wait = trace.get("wait_min")
            row["ours_transit"]["wait_min"] = wait
            if wait is not None:
                row["ours_transit"]["eta_without_wait"] = planned["eta_min"] - wait
        else:
            row["ours_transit"] = {"none": str((why or {}).get("code"))}
        tx, _ = leg_taxi(a, b, arrive) if leg_taxi else (None, None)
        if tx is not None:
            o = tx["route"]["options"][0]
            km = re.search(r"([\d.]+)km", str(o.get("label")))
            row["ours_taxi"] = {"eta": o["eta_min"], "fare": o.get("fare_krw"), "km": float(km.group(1)) if km else None}
        try:
            straight = float(p["straight_m"])
            dist, no_path = pl._walk_net(a, b, straight)
            if dist is not None and not no_path:
                row["ours_walk"] = {"m": round(dist), "min": round(dist / pl.speed / 60, 1)}
        except Exception:                                    # noqa: BLE001
            pass
        row["kakao"] = k
        row["secs"] = round(time.time() - t0, 1)
        rows.append(row)
        log(f"{p['id']} {p['a']}→{p['b']} · 우리 {row['ours_transit'].get('eta', '—')} · {row['secs']}s")
    return {"arrive": arrive.isoformat(), "rows": rows, "summary": summarise(rows)}


def summarise(rows: list[dict]) -> dict:
    out: dict = {}
    tb, tr, tm = [], [], []
    by_bucket: dict[str, list[float]] = {}
    for r in rows:
        kt = (r.get("kakao") or {}).get("transit") or {}
        ot = r.get("ours_transit") or {}
        if "best" in kt and "eta" in ot:
            d = ot["eta"] - kt["best"]["min"]
            tb.append(d)
            tr.append(ot["eta"] - kt["rec"]["min"])
            tm.append(ot["min_option_eta"] - kt["best"]["min"])
            by_bucket.setdefault(r["bucket"], []).append(d)
    out["transit_vs_kakao_best"] = _stats(tb)
    out["transit_vs_kakao_recommended"] = _stats(tr)
    out["transit_our_fastest_option_vs_kakao_best"] = _stats(tm)
    out["transit_vs_kakao_best_by_bucket"] = {k: _stats(v) for k, v in by_bucket.items()}
    for name in ("best", "rec"):
        for field in ("eta", "eta_without_wait"):
            differences, percentages, our_values, reference_values = [], [], [], []
            for row in rows:
                reference = ((row.get("kakao") or {}).get("transit") or {}).get(name, {}).get("min")
                ours = (row.get("ours_transit") or {}).get(field)
                if reference is not None and reference > 0 and ours is not None:
                    differences.append(ours - reference)
                    percentages.append((ours - reference) / reference * 100)
                    our_values.append(ours)
                    reference_values.append(reference)
            out[f"transit_{field}_vs_{name}"] = {
                "minutes": _stats(differences), "percent": _stats(percentages, tol=10),
                "percent_denominator": "각 경로의 카카오 소요 분", "wait_known": len(differences),
                "ours_median_min": statistics.median(our_values) if our_values else None,
                "kakao_median_min": statistics.median(reference_values) if reference_values else None,
            }
    taxi_t, taxi_f, taxi_km = [], [], []
    for r in rows:
        kc = (r.get("kakao") or {}).get("car") or {}
        ox = r.get("ours_taxi") or {}
        if kc.get("source") in {"kakao_map_web", "legacy_api_user_reused"} and "duration_s" in kc and "eta" in ox:
            taxi_t.append(ox["eta"] - kc["duration_s"] / 60)
            if ox.get("fare") is not None and kc.get("taxi_fare_krw"):
                taxi_f.append((ox["fare"] - kc["taxi_fare_krw"]) / kc["taxi_fare_krw"] * 100)
            if ox.get("km") is not None:
                taxi_km.append((ox["km"] - kc["distance_m"] / 1000) / (kc["distance_m"] / 1000) * 100)
    out["taxi_minutes_vs_kakao_car"] = _stats(taxi_t)
    out["taxi_fare_percent_vs_kakao_taxi_fare"] = _stats(taxi_f, tol=10) if taxi_f else {"n": 0}
    out["taxi_fare_under_reference"] = {"n": len(taxi_f), "count": sum(x < 0 for x in taxi_f),
                                       "rate": sum(x < 0 for x in taxi_f) / len(taxi_f) if taxi_f else None}
    out["taxi_distance_percent_vs_kakao"] = _stats(taxi_km, tol=10) if taxi_km else {"n": 0}
    walk_m, walk_min = [], []
    for r in rows:
        kw = (r.get("kakao") or {}).get("walk") or {}
        ow = r.get("ours_walk") or {}
        if "shortest" in kw and "m" in ow:
            kmeters = kw["shortest"]["km"] * 1000
            walk_m.append((ow["m"] - kmeters) / kmeters * 100)
            walk_min.append(ow["min"] - kw["shortest"]["min"])
    out["walk_distance_percent_vs_kakao_shortest"] = _stats(walk_m, tol=10) if walk_m else {"n": 0}
    out["walk_minutes_vs_kakao_shortest"] = _stats(walk_min, tol=5)
    out["coverage"] = {"pairs": len(rows),
                       "web_car": sum(((r.get("kakao") or {}).get("car") or {}).get("source") == "kakao_map_web" for r in rows),
                       "car_reused_by_user": sum(((r.get("kakao") or {}).get("car") or {}).get("source") == "legacy_api_user_reused" for r in rows),
                       "car_excluded_legacy_api": sum(bool((r.get("kakao") or {}).get("car")) and
                           ((r.get("kakao") or {}).get("car") or {}).get("source") not in {"kakao_map_web", "legacy_api_user_reused"} for r in rows),
                       "wait_known": sum((r.get("ours_transit") or {}).get("wait_min") is not None for r in rows)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arrive", default="2026-10-08T10:30")
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    arrive = datetime.fromisoformat(args.arrive).replace(tzinfo=KST)
    got = run(arrive, set(args.only.split(",")) if args.only else None)
    text = json.dumps(got, ensure_ascii=False, indent=1)
    if args.json:
        output = pathlib.Path(os.path.abspath(args.json)).resolve()
        allowed = (ROOT.parent / "datasets" / "mobility" / "raw").resolve()
        if not output.is_relative_to(allowed):
            raise ValueError("쌍별 카카오 값은 git 밖 datasets/mobility/raw 안에만 저장합니다")
        with output.open("x", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(json.dumps(got["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
