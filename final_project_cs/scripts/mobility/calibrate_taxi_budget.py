"""시각을 맞춘 로컬 비교 자료로 예산 여유를 산정하고 별도 경로로 검증한다.

카카오 API 호출 없음. 개별 경로·기준값은 git 밖 raw 폴더에만 저장한다.
고정 거리층 분할과 P95를 사용하며 검증군으로 여유율을 다시 조정하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
from pathlib import Path

from app.modules.travel_ops.mobility.engine.car import taxi_planning_fare

SEED = "taxi-budget-20261008"
TRAIN_SHARE = 0.8
QUANTILE = 0.95
TARGET_COVERAGE = 0.9
RAW = Path(__file__).resolve().parents[3] / "datasets/mobility/raw"


def split_rows(rows):
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("중복 경로를 보정에 사용할 수 없습니다")
    valid, excluded = [], []
    for r in rows:
        if "excluded" in r:
            excluded.append({"id": r["id"], "reason": r["excluded"]})
            continue
        e = r["estimate"]
        if (r["bucket"] not in {"short", "mid", "long"}
                or e["fare_kind"] != "중형" or e["meter_won"] <= 0
                or r["reference_fare"] <= 0 or not r.get("time_basis")):
            raise ValueError(f"시각·차종·요금 조건이 부족합니다: {r['id']}")
        valid.append(r)
    train, validation = [], []
    for bucket in ("short", "mid", "long"):
        group = sorted((r for r in valid if r["bucket"] == bucket),
                       key=lambda r: hashlib.sha256(f"{SEED}:{r['id']}".encode()).hexdigest())
        cut = math.floor(len(group) * TRAIN_SHARE)
        train.extend(group[:cut])
        validation.extend(group[cut:])
    if not train or not validation:
        raise ValueError("계산군과 검증군이 모두 필요합니다")
    return train, validation, excluded


def fit_rate(train):
    # 통행료는 비율 보정 대상에서 제외한다.
    ratios = sorted(max(0, r["reference_fare"] - r["estimate"]["toll_won"])
                    / r["estimate"]["meter_won"] for r in train)
    index = min(len(ratios) - 1, math.ceil((len(ratios) + 1) * QUANTILE) - 1)
    factor = ratios[index]
    return max(0, math.ceil((factor - 1) * 100) / 100), factor


def evaluate(rows, rate, policy):
    diffs, covered = [], 0
    for r in rows:
        e = r["estimate"]
        total, _ = taxi_planning_fare(
            e["meter_won"], e["toll_won"], reserve_rate=rate,
            minimum_reserve_won=policy["minimum_reserve_won"]["value"],
            round_unit_won=policy["round_unit_won"]["value"])
        covered += total >= r["reference_fare"]
        diffs.append((total / r["reference_fare"] - 1) * 100)
    return {"n": len(rows), "at_or_above_reference": covered,
            "coverage": covered / len(rows), "median_difference_percent": statistics.median(diffs)}


def calibrate(rows, policy):
    train, validation, excluded = split_rows(rows)
    rate, factor = fit_rate(train)
    checks = evaluate(validation, rate, policy)
    return {"calibration_id": SEED, "quantile": QUANTILE, "factor": factor,
            "reserve_rate": rate, "target_coverage": TARGET_COVERAGE,
            "training": evaluate(train, rate, policy), "validation": checks,
            "training_ids": [r["id"] for r in train],
            "validation_ids": [r["id"] for r in validation],
            "excluded": excluded, "validated": checks["coverage"] >= TARGET_COVERAGE}


def raw_path(value):
    path = Path(os.path.abspath(value)).resolve()
    if not path.is_relative_to(RAW.resolve()):
        raise ValueError("개별 경로 자료는 git 밖 datasets/mobility/raw 안에만 둡니다")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aligned", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    source, output = raw_path(args.aligned), raw_path(args.out)
    rules_file = Path(__file__).resolve().parents[2] / "app/modules/travel_ops/mobility/engine/rules/rules_v0.3.json"
    policy = json.loads(rules_file.read_text(encoding="utf-8"))["taxi"]["planning_budget"]
    payload = source.read_bytes()
    result = calibrate(json.loads(payload)["rows"], policy)
    result["input_sha256"] = hashlib.sha256(payload).hexdigest()
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in {"training_ids", "validation_ids", "excluded"}},
                     ensure_ascii=False, indent=2))
    return 0 if result["validated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
