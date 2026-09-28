# -*- coding: utf-8 -*-
"""모의 실험 결과 요약 — 전환 횟수·점유율·전환당 여유 중 무엇이 취약성을 설명하나."""
from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from density_cascade_sim import spearman   # noqa: E402

data = json.loads(Path(os.environ.get("ACOP_SIM_OUT")
                       or Path(__file__).with_name("density_cascade_rows.json")).read_text(encoding="utf-8"))
rows = data["rows"]


def cell(subset, key):
    values = [row[key] for row in subset]
    return statistics.fmean(values), (statistics.pstdev(values) if len(values) > 1 else 0.0)


print("설정:", json.dumps(data["설정"], ensure_ascii=False))
print(f"판 {len(rows)}건 · 건너뜀 {len(data['skipped'])}건\n")

for delay in data["설정"]["delays"]:
    if delay not in (60, 120):
        continue
    subset = [row for row in rows if row["delay_min"] == delay]
    print(f"== 사건: 첫 활동 {delay}분 초과 ==")
    print("전환\\점유 |" + "".join(f"{r:>18.2f}" for r in data["설정"]["ratios"]))
    for metric, label in (("shifted_items", "밀린 항목 수"), ("overflow_min", "하루 창 초과(분)"), ("missed_reservations", "예약 놓침")):
        print(f"-- {label}")
        for t in data["설정"]["transitions"]:
            line = f"{t:>9} |"
            for r in data["설정"]["ratios"]:
                group = [row for row in subset if row["transitions"] == t and row["ratio"] == r]
                if not group:
                    line += f"{'—':>18}"
                    continue
                mean, sd = cell(group, metric)
                line += f"{mean:>12.1f}±{sd:<5.1f}"
            print(line)
    print()

print("== 무엇이 결과를 더 잘 설명하나 (순위 상관, 1에 가까울수록 같이 움직임) ==")
print(f"{'사건':>8} {'결과':>16} {'전환 횟수':>10} {'점유율':>10} {'전환당 여유':>12}")
for delay in data["설정"]["delays"]:
    subset = [row for row in rows if row["delay_min"] == delay]
    for metric, label in (("shifted_items", "밀린 항목 수"), ("overflow_min", "창 초과(분)")):
        ys = [row[metric] for row in subset]
        print(f"{delay:>6}분 {label:>16} "
              f"{spearman([row['transitions'] for row in subset], ys):>10.2f} "
              f"{spearman([row['ratio'] for row in subset], ys):>10.2f} "
              f"{spearman([row['slack_per_transition'] for row in subset], ys):>12.2f}")

print("\n== 전환당 여유 구간별 결과(사건 60분) ==")
subset = [row for row in rows if row["delay_min"] == 60]
buckets = [(0, 20), (20, 40), (40, 60), (60, 90), (90, 1000)]
print(f"{'전환당 여유(분)':>16} {'판수':>6} {'밀린 항목':>12} {'창 초과(분)':>14} {'예약 놓침률':>12} {'흡수한 비율':>12}")
for low, high in buckets:
    group = [row for row in subset if low <= row["slack_per_transition"] < high]
    if not group:
        continue
    shifted = statistics.fmean([row["shifted_items"] for row in group])
    overflow = statistics.fmean([row["overflow_min"] for row in group])
    absorbed = sum(1 for row in group if row["absorbed"]) / len(group)
    missed = sum(1 for row in group if row["missed_reservations"]) / len(group)
    print(f"{low:>7}~{high:<8} {len(group):>6} {shifted:>12.1f} {overflow:>14.1f} {missed:>11.0%} {absorbed:>11.0%}")

print("\n== 같은 전환 횟수 안에서 점유율만 바꿨을 때(사건 60분, 밀린 항목 수) ==")
for t in data["설정"]["transitions"]:
    parts = []
    for r in data["설정"]["ratios"]:
        group = [row for row in subset if row["transitions"] == t and row["ratio"] == r]
        parts.append(f"{r:.2f}:{statistics.fmean([row['shifted_items'] for row in group]):.1f}" if group else f"{r:.2f}:—")
    print(f"전환 {t}회 → " + "  ".join(parts))
