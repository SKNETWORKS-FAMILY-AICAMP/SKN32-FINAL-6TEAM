"""잰 시간을 72% 절감 계산에 꽂아 본다.

    python -m eval.timing.report_review_time

★추정치를 실측으로 바꾸면 절감률이 얼마가 되는지 바로 보여준다.
  program/wiki/business/unit-economics.md §2 의 식을 그대로 쓴다.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "eval/timing/_review_times.jsonl")

#: unit-economics.md §2 — 골든셋 실측 비율. 시간만 추정이었다.
MIX = {"respond": 0.56, "wait_for_approval": 0.21, "wait_for_input": 0.18, "escalate": 0.05}
ESTIMATE = {"respond": 120.0, "wait_for_approval": 180.0, "wait_for_input": 60.0, "escalate": 514.2}
HUMAN_ONLY_SECONDS = 8.57 * 60      # 실가동 6시간 ÷ CPH 7
COST_PER_MINUTE = 4100 / (8.57)     # 건당 4,100원 ÷ 8.57분


def blended(times: dict[str, float]) -> float:
    return sum(MIX[k] * times[k] for k in MIX)


def main() -> int:
    if not os.path.exists(DATA):
        print("아직 잰 게 없다.")
        print("  python -m eval.timing.measure_review_time --n 20 --action respond")
        print("  python -m eval.timing.measure_review_time --n 20 --action wait_for_approval")
        return 1

    rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    rows = [r for r in rows if r["verdict"] != "skip"]
    if not rows:
        print("집계할 게 없다 (전부 보류).")
        return 1

    measured, by_who = {}, {}
    for action in ("respond", "wait_for_approval"):
        got = [r["seconds"] for r in rows if r["action"] == action]
        if got:
            measured[action] = statistics.median(got)
            by_who[action] = len(got)

    print(f"기록 {len(rows)}건\n")
    print(f"{'구간':20} {'추정':>8} {'실측 중앙값':>12} {'n':>4}")
    print("-" * 50)
    for action in MIX:
        est = ESTIMATE[action]
        if action in measured:
            m = measured[action]
            mark = "  ★" if abs(m - est) / est > 0.25 else ""
            print(f"{action:20} {est/60:7.2f}분 {m/60:11.2f}분 {by_who[action]:4}{mark}")
        else:
            print(f"{action:20} {est/60:7.2f}분 {'—':>12} {0:4}")

    if not measured:
        print("\n아직 어느 구간도 못 쟀다.")
        return 0

    #: 안 잰 구간은 추정치를 그대로 쓴다. 그것도 밝힌다.
    times = dict(ESTIMATE)
    times.update(measured)
    b = blended(times)
    saving = (HUMAN_ONLY_SECONDS - b) / HUMAN_ONLY_SECONDS * 100
    est_b = blended(ESTIMATE)
    est_saving = (HUMAN_ONLY_SECONDS - est_b) / HUMAN_ONLY_SECONDS * 100

    print(f"\n{'='*50}")
    print(f"{'':20} {'추정 기준':>12} {'실측 반영':>12}")
    print("-" * 50)
    print(f"{'건당 사람 시간':20} {est_b/60:11.2f}분 {b/60:11.2f}분")
    print(f"{'절감률':20} {est_saving:11.1f}% {saving:11.1f}%")
    print(f"{'건당 인건비':20} {est_b/60*COST_PER_MINUTE:10,.0f}원 {b/60*COST_PER_MINUTE:10,.0f}원")

    annual = 126_000 * (4100 - b / 60 * COST_PER_MINUTE)
    print(f"\n모델 조직 연간 절감 (126,000건)  {annual/1e8:.2f}억원")

    missing = [k for k in MIX if k not in measured]
    if missing:
        print(f"\n`[추정]` 아직 안 잰 구간: {', '.join(missing)}")
        print("  위 숫자는 그 구간에 추정치를 쓴 값이다.")
    else:
        print("\n★네 구간을 다 쟀다. unit-economics.md 의 [추정] 을 [실측] 로 바꿀 수 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
