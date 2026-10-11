"""Paired percentile bootstrap for repeated case-level evaluation results."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def paired_deltas(rows, arm_x="Proposed", arm_y="A", metric="score"):
    """Return x-y deltas from make_pairs output or raw arm rows."""
    if rows and any(f"x_{metric}" in row for row in rows):
        return [float(row[f"x_{metric}"]) - float(row[f"y_{metric}"])
                for row in rows if f"x_{metric}" in row and f"y_{metric}" in row]
    grouped = defaultdict(dict)
    for row in rows:
        grouped[(row["case_id"], row.get("repeat", 1))][row["arm"]] = float(row[metric])
    return [values[arm_x] - values[arm_y] for values in grouped.values()
            if arm_x in values and arm_y in values]


def paired_bootstrap_delta(deltas, n=10000, seed=7):
    if not deltas:
        raise ValueError("no paired observations for requested arms and metric")
    rng = random.Random(seed)
    draws = [sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(n)]
    ordered = sorted(draws)
    quantile = lambda p: ordered[min(len(ordered) - 1, int(p * len(ordered)))]
    return sum(deltas) / len(deltas), (quantile(0.025), quantile(0.975))


def format_result(mean, ci, arm_x, arm_y, paired_n):
    significance = "유의하다" if ci[0] > 0 or ci[1] < 0 else "유의하지 않다 (CI가 0을 포함)"
    return (f"paired_n={paired_n}; {arm_x}-{arm_y} mean diff={mean:.6f} "
            f"[{ci[0]:.6f}, {ci[1]:.6f}]; {significance}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--arm-x", default="Proposed")
    parser.add_argument("--arm-y", default="A")
    parser.add_argument("--metric", default="score")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    if rows:
        args.arm_x = rows[0].get("x_arm", args.arm_x)
        args.arm_y = rows[0].get("y_arm", args.arm_y)
    deltas = paired_deltas(rows, args.arm_x, args.arm_y, args.metric)
    mean, ci = paired_bootstrap_delta(deltas, args.n, args.seed)
    print(format_result(mean, ci, args.arm_x, args.arm_y, len(deltas)))


if __name__ == "__main__":
    main()
