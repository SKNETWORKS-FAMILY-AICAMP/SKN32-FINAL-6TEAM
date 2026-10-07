# -*- coding: utf-8 -*-
"""우리 이동 도구를 카카오 기준 파일(시험 기준 세트)과 대조한다. `[2026-10-07 사용자 지시]`

실행(저장소 안에서):  python -m scripts.mobility.compare_kakao_golden [--arrive 2026-10-08T10:30] [--json out.json]

입력
  - 장소 쌍: `tests/unit/travel/mobility/golden_pairs_v1.json`(이름·좌표뿐 — 저장소에 있다)
  - 카카오 값: `datasets/mobility/raw/kakao_golden/kakao_routes_v1.json`(★저장소에 올리지 않는다 — `raw/` 는 .gitignore 가 막는다. 약관 · 팀 규칙)
대조
  - 대중교통: 우리 계획 수단의 소요(`eta_min` — 승차·환승 대기 포함, 정책 여유 제외) vs 카카오 최단안 · 추천안(총 소요에 **대기가 없다**)
  - 택시: 우리 택시 후보(`modes=[taxi]`)의 소요 · 요금 vs 카카오 자동차 길찾기의 소요 · 택시 요금
  - 걷기: 우리 보행 길 그래프의 거리 · 시간 vs 카카오 도보 최단(성인 4 km/h 환산)
출력: 요약 숫자(저장소에 적어도 되는 집계)와, 쌍별 표(카카오 값이 들어 있어 **로컬 파일로만** 쓴다).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAIRS = ROOT / "tests" / "unit" / "travel" / "mobility" / "golden_pairs_v1.json"
KAKAO = ROOT.parent / "datasets" / "mobility" / "raw" / "kakao_golden" / "kakao_routes_v1.json"
KST = timezone(timedelta(hours=9))


def _stats(diffs: list[float], tol: int = 5) -> dict:
    if not diffs:
        return {"n": 0}
    absd = [abs(x) for x in diffs]
    return {"n": len(diffs), "median": round(statistics.median(diffs), 1), "mean": round(statistics.mean(diffs), 1),
            "mae": round(statistics.mean(absd), 1), f"within_{tol}": round(sum(1 for x in absd if x <= tol) / len(diffs), 2),
            "ours_longer_than_5": sum(1 for x in diffs if x > tol), "ours_shorter_than_5": sum(1 for x in diffs if x < -tol)}


def load_pairs():
    return json.loads(PAIRS.read_text(encoding="utf-8"))["pairs"]


def load_kakao():
    return json.loads(KAKAO.read_text(encoding="utf-8"))["routes"]


def _planner_leg(rt, modes):
    """조립 없이 판정기만 있을 때의 구간 계산기 — `wiring.leg_planner` 가 돌려주는 것과 같은 모양(`{"route": …}`)."""
    from app.domains.travel_ops.instances.mobility.engine.plan import Planner, party_of

    planner = Planner(rt, stage="planning", modes=modes)
    party = party_of(None, {})

    def leg(a, b, arrive):
        got, why = planner.leg(a, b, arrive, party, True, case_id=f"{a['key']}_{b['key']}")
        return (None, why) if got is None else ({"route": got[0]}, None)
    return leg


def run(arrive: datetime, only: set[str] | None = None, log=print, direct: bool = False) -> dict:
    sys.path.insert(0, str(ROOT))
    from app.core.settings import get_settings
    from app.domains.travel_ops.instances.mobility import wiring
    from app.domains.travel_ops.instances.mobility.engine import runtime as ER
    from app.domains.travel_ops.instances.mobility.engine.plan import Planner

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
    taxi_t, taxi_f, taxi_km = [], [], []
    for r in rows:
        kc = (r.get("kakao") or {}).get("car") or {}
        ox = r.get("ours_taxi") or {}
        if "duration_s" in kc and "eta" in ox:
            taxi_t.append(ox["eta"] - kc["duration_s"] / 60)
            if ox.get("fare") is not None and kc.get("taxi_fare_krw"):
                taxi_f.append((ox["fare"] - kc["taxi_fare_krw"]) / kc["taxi_fare_krw"] * 100)
            if ox.get("km") is not None:
                taxi_km.append((ox["km"] - kc["distance_m"] / 1000) / (kc["distance_m"] / 1000) * 100)
    out["taxi_minutes_vs_kakao_car"] = _stats(taxi_t)
    out["taxi_fare_percent_vs_kakao_taxi_fare"] = _stats(taxi_f, tol=10) if taxi_f else {"n": 0}
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
        pathlib.Path(args.json).write_text(text + "\n", encoding="utf-8")
    print(json.dumps(got["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
