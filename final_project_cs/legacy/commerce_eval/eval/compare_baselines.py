# -*- coding: utf-8 -*-
"""채점자를 바꾼 뒤 **같은 채점자 안에서** 군을 비교한다.

★재기준선(re-baseline)의 요점은 "점수가 올랐다/내렸다" 가 아니다.
  채점자를 바꾸면 모든 점수가 같이 움직이므로 **v1 점수와 v3 점수를 직접
  비교하는 것은 의미가 없다.** 의미가 있는 것은 **같은 채점자 안에서 군끼리의
  관계가 보존되는가** 다.

      v1 에서  Proposed > B > A  였다면
      v3 에서도 Proposed > B > A  인가?

  보존되면 "채점자를 바꿔도 결론은 같다" 고 말할 수 있고, 그때 비로소
  grounding 축을 고친 값으로 갈아탈 수 있다. 뒤집히면 **결론 자체가 채점자에
  달려 있었다**는 뜻이라 훨씬 큰 문제다.

★grounding 축은 따로 본다. 이 축을 고치는 것이 재기준선의 목적이었으므로
  "변별하게 됐는가" 를 값의 종류 수와 최빈값 비중으로 확인한다.

    python -m eval.compare_baselines
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUBRIC_FIELDS = ("correctness", "policy_grounding", "next_action", "safety", "personalization")

#: (군, judge-v1 산출물, judge-v3 산출물)
DEFAULT_ARMS = [
    ("A", "eval/reports/2026-08-24_reeval_A.jsonl",
          "eval/reports/2026-09-06_rebaseline_A_judgev3.jsonl"),
    ("B", "eval/reports/2026-08-24_reeval_B.jsonl",
          "eval/reports/2026-09-06_rebaseline_B_judgev3.jsonl"),
    ("Proposed", "eval/reports/2026-08-28_reeval_Proposed_v3.jsonl",
                 "eval/reports/2026-09-06_rebaseline_Proposed_judgev3.jsonl"),
]


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _summary(rows: list[dict]) -> dict:
    judged = [r["judge"] for r in rows if r.get("judge")]
    if not judged:
        return {}
    grounding = [j["policy_grounding"] for j in judged]
    counts = collections.Counter(grounding)
    return {
        "n": len(judged),
        "pass_rate": sum(1 for j in judged if j.get("pass")) / len(judged),
        "total_mean": statistics.mean([j["total"] for j in judged]),
        "fields": {f: round(statistics.mean([j[f] for j in judged]), 3) for f in RUBRIC_FIELDS},
        "grounding_distinct": len(counts),
        "grounding_dominant_share": max(counts.values()) / len(grounding),
        "grounding_dist": dict(sorted(counts.items())),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="채점자 교체 전후, 같은 채점자 안에서의 군 비교")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report: dict = {"arms": {}, "judge_versions": {}}
    missing = []
    for arm, v1_path, v3_path in DEFAULT_ARMS:
        p1, p3 = ROOT / v1_path, ROOT / v3_path
        if not p3.exists():
            missing.append(v3_path)
            continue
        rows3 = _load(p3)
        report["judge_versions"][arm] = (rows3[0].get("rescore") or {}).get("judge_prompt_version")
        report["arms"][arm] = {"judge_v1": _summary(_load(p1)), "judge_v3": _summary(rows3)}

    if missing:
        print("아직 없는 산출물:", *missing, sep="\n  ")
        return 1

    print("=" * 78)
    print("같은 채점자 안에서의 군 비교 — 채점자를 바꿔도 순위가 보존되는가")
    print("=" * 78)
    for key, label in (("judge_v1", "judge-v1 (기존)"), ("judge_v3", "judge-v3 (재기준선)")):
        print(f"\n[{label}]")
        print(f"  {'군':<10} {'n':>4} {'pass':>7} {'total평균':>9}   grounding(종류·최빈)")
        order = []
        for arm in report["arms"]:
            s = report["arms"][arm][key]
            order.append((s["pass_rate"], arm))
            print(f"  {arm:<10} {s['n']:>4} {s['pass_rate']:>6.1%} {s['total_mean']:>9.2f}"
                  f"   {s['grounding_distinct']}종 · 최빈 {s['grounding_dominant_share']:.0%}"
                  f"  {s['grounding_dist']}")
        ranking = [a for _, a in sorted(order, reverse=True)]
        report.setdefault("ranking", {})[key] = ranking
        print(f"  → pass 기준 순위: {' > '.join(ranking)}")

    same = report["ranking"]["judge_v1"] == report["ranking"]["judge_v3"]
    report["ranking_preserved"] = same
    print("\n" + "-" * 78)
    if same:
        print("★순위가 보존됐다 — 채점자를 바꿔도 군 사이의 결론은 같다.")
        print("  그러므로 grounding 축을 고친 judge-v3 값으로 갈아타도 결론이 흔들리지 않는다.")
    else:
        print("★순위가 뒤집혔다 — 결론 자체가 채점자에 달려 있었다는 뜻이다.")
        print("  이건 grounding 축 하나의 문제가 아니다. 갈아타기 전에 원인을 찾아야 한다.")
    print("-" * 78)

    if args.output:
        out = ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"기록: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
