"""고정된 새 경로를 재계산한다. 카카오 원값과 결과는 git 밖에만 쓴다.

브라우저 조회는 이 스크립트에서 하지 않는다. DOM으로 읽은 참조 파일을 받는다.
37%를 재추정하지 않으며 설계 시점의 요금 규칙 해시가 바뀌면 중단한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json"
RAW = ROOT.parent / "datasets/mobility/raw/kakao_golden"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--design", type=Path, default=RAW / "fresh_experiment_100_design.json")
    ap.add_argument("--references", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--modes", nargs="+", choices=["bus", "subway", "walk"])
    args = ap.parse_args()
    if not args.out.resolve().is_relative_to(RAW.resolve()):
        ap.error("원값을 포함한 결과는 datasets/mobility/raw/kakao_golden 아래에만 저장합니다")
    design = json.loads(args.design.read_text(encoding="utf-8"))
    frozen_hash = design["rules_sha256"]
    if hashlib.sha256(RULES.read_bytes()).hexdigest() != frozen_hash:
        ap.error("고정한 요금 규칙이 바뀌었습니다")
    sys.path.insert(0, str(ROOT))
    from app.domains.travel_ops.instances.mobility.engine.plan import Planner
    from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
    from scripts.mobility.compare_kakao_golden import KST, _planner_leg

    refs = {row[0]: row for row in json.loads(args.references.read_text(encoding="utf-8"))} if args.references else {}
    rt = build_verifier(quiet=True, local_router=True)
    svc = rt._v.car._service()
    print("자료 로딩 완료", flush=True)

    def run(p):
        started = time.monotonic()
        a = {"key": p["id"] + "a", "name": p["a"], "lat": p["alat"], "lon": p["alon"]}
        b = {"key": p["id"] + "b", "name": p["b"], "lat": p["blat"], "lon": p["blon"]}
        row = {"id": p["id"], "bucket": p["bucket"]}
        if refs:
            ref = refs[p["id"]]
            depart = datetime.fromisoformat(ref[1]).astimezone(KST)
            row["taxi"] = svc.leg((p["alon"], p["alat"]), (p["blon"], p["blat"]), depart, taxi=True)
            row["read_at"] = depart.isoformat()
        else:
            result, why = _planner_leg(rt, args.modes)(a, b, datetime(2026, 10, 8, 10, 30, tzinfo=KST))
            row["transit"] = result or {"failure": why}
            if p["bucket"] == "short" and args.modes is None:
                pl = Planner(rt, stage="planning", modes=None)
                distance, no_path = pl._walk_net(a, b, p["straight_m"])
                row["walk"] = {"m": distance, "no_path": no_path,
                               "min": distance / pl.speed / 60 if distance is not None else None,
                               "speed_m_s": pl.speed}
                row["bike"] = rt._v.bike_router.route("bike", p["alat"], p["alon"], p["blat"], p["blon"])
        row["elapsed_s"] = round(time.monotonic() - started, 2)
        return row

    checkpoint = args.out.with_suffix(".jsonl")
    rows = []
    with checkpoint.open("x", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as pool:
        for job in as_completed([pool.submit(run, p) for p in design["pairs"]]):
            row = job.result()
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{len(rows)}/{len(design['pairs'])} {row['id']} {row['elapsed_s']}s", flush=True)
    if hashlib.sha256(RULES.read_bytes()).hexdigest() != frozen_hash:
        raise RuntimeError("실험 도중 요금 규칙이 바뀌었습니다")
    with args.out.open("x", encoding="utf-8") as f:
        json.dump({"rules_sha256": frozen_hash, "reserve_rate": design["coefficient_locked"],
                   "arrive": "2026-10-08T10:30:00+09:00", "rows": sorted(rows, key=lambda r: r["id"])},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
