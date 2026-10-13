"""사용자가 채택한 지하철 웹 골든셋을 오프라인 제품 계산과 대조한다.

기존 결과를 덮어쓰지 않는다. 첫 승차 전 대기는 웹 승차~하차 소요에서
제외하되 원래 출발 안내 ETA와 환승 대기는 보존한다.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
import socket
import sys

CS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CS_ROOT))

from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(rt, row):
    case = {"id": row["id"], "date": row["service_date"],
            "depart_at": row["depart_at"], "stage": "planning",
            "first_visit": False, "no_alternatives": True, "legs": row["legs"]}
    result = rt.verify_case(case)
    rides = O.ride_results(row["legs"], result.legs)
    fare = O.fare_of(rt._v, row["legs"], result.legs)
    upper = O.fare_upper_of(rt._v, row["legs"], result.legs)
    first = rides[0].depart_min if rides else None
    duration = (result.arrive_min - first
                if first is not None and result.arrive_min is not None else None)
    services = []
    stops = []
    if rides:
        for leg, ride in zip(row["legs"], rides):
            ds = O.chosen_departures(rt._v, leg, ride, result.day_type)
            # 1/9호선 급행만 run 표를 사용한다. 나머지는 일반 운행이다.
            kinds = {"express" if getattr(getattr(d, "run", None), "express", False)
                     else "local" for d, _ in ds}
            services.append(sorted(kinds))
            patterns = []
            for d, verdict in ds:
                run = getattr(d, "run", None)
                path = list(run.order) if run else verdict.path
                if leg["from"] in path and leg["to"] in path:
                    patterns.append(path[path.index(leg["from"]):path.index(leg["to"]) + 1])
            stops.append(patterns)
    service_match = (len(services) == len(row["services"])
                     and all((bool(stops[i]) and all(pattern == row["observed_stops"][i]
                                                     for pattern in stops[i]))
                             if expected == "segment_stops" else kinds == [expected]
                             for i, (kinds, expected) in enumerate(zip(services, row["services"]))))
    diff = None if duration is None else duration - row["duration_min"]
    return {"id": row["id"], "fare_krw": fare, "fare_upper_krw": upper,
            "fare_estimated": O.fare_is_est(rt._v, row["legs"], result.legs),
            "fare_match": fare == row["fare_krw"],
            "duration_min": duration, "duration_diff_min": diff,
            "duration_scope": row["duration_scope"],
            "duration_within_tolerance": diff is not None and service_match
                and abs(diff) <= row["tolerance"]["duration_min"],
            "engine_services": services, "service_match": service_match,
            "engine_stop_patterns": stops,
            "initial_wait_min": rides[0].wait_min if rides else None,
            "departure_eta_min": result.eta_min,
            "result": dataclasses.asdict(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", choices=("none", "fare", "all"), default="all")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("기존 출력이 있습니다. 새 --out 이름을 사용하세요.")
    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    rows = golden["rows"]
    if not rows or len({r["id"] for r in rows}) != len(rows):
        parser.error("골든셋이 비었거나 ID가 중복됐습니다.")
    for row in rows:
        if (row["fare_basis"] != "adult_transport_card"
                or row["duration_scope"] != "first_boarding_to_final_alighting"
                or not row["sources"] or len(row["services"]) != len(row["legs"])):
            parser.error("비교 조건 또는 근거가 불완전합니다.")
    attempts = []

    def blocked(*_args, **_kwargs):
        attempts.append("blocked_network_attempt")
        raise RuntimeError("웹 골든셋 재생에서는 네트워크 호출을 허용하지 않습니다.")

    socket.socket.connect = blocked
    socket.create_connection = blocked
    rt = build_verifier(data_dir=str(args.data_dir), gh_url="", seoul_key="",
                        quiet=True, local_router=False)
    rt._v.lfd_enabled = False
    results = [compare(rt, row) for row in rows]
    engine = CS_ROOT / "app/domains/travel_ops/instances/mobility/engine"
    inputs = {str(p): sha(p) for p in sorted(engine.rglob("*.py"))
              if "_backup" not in p.parts}
    for path, _mtime in rt.source_mtimes.values():
        inputs[str(path)] = sha(path)
    totals = {"routes": len(rows),
              "fare_matches": sum(r["fare_match"] for r in results),
              "service_matches": sum(r["service_match"] for r in results),
              "duration_within_tolerance": sum(r["duration_within_tolerance"] for r in results),
              "blocked_network_attempts": len(attempts)}
    payload = {"golden_sha256": sha(args.golden), "rows": results,
               "totals": totals, "source_hashes": inputs,
               "runtime_stats": rt.stats,
               "tolerance_note": "시간 5분은 개발 진단 기준입니다. 도시 전체의 품질 보장은 아닙니다."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps(totals, ensure_ascii=False))
    for r in results:
        print(json.dumps({k: v for k, v in r.items() if k != "result"}, ensure_ascii=False))
    passed = not attempts
    if args.check in ("fare", "all"):
        passed &= totals["fare_matches"] == len(rows)
    if args.check == "all":
        passed &= totals["duration_within_tolerance"] == len(rows)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
