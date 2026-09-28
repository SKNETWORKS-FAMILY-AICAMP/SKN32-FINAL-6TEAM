"""judge 점수와 사람 라벨의 일치율 — DoD-15/17 의 유일한 차단 항목을 잰다.

v5 §15-4 는 judge agreement 를 "사람 라벨 20건과의 일치율"로 정의한다.
`eval/check_judge.py` 는 이것을 대신하지 못한다(judge 가 대놓고 틀리는
경우만 잡는다, 사람과 얼마나 맞는지는 모른다). 이 스크립트가 그 빈 자리다.

rubric 각 축(correctness/policy_grounding/next_action/safety/personalization,
0~4)마다 정확 일치율과 Cohen's kappa 를 낸다. `pass`(bool)는 별도로 잰다.
샘플 20건은 통계적으로 작다 — kappa 신뢰구간을 논하지 않고 점 추정치와
정확 일치율을 함께 보고한다(`CLAUDE.md` §4 "표본이 작으면 작다고 말한다").

    python -m eval.stats.agreement \\
        --judged eval/reports/rescored_holdout_proposed.jsonl \\
        --human eval/reports/holdout_human_labels_filled.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RUBRIC_FIELDS = ("correctness", "policy_grounding", "next_action", "safety", "personalization")


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _cohen_kappa(a: list, b: list) -> float | None:
    if len(a) < 2:
        return None
    from sklearn.metrics import cohen_kappa_score
    if len(set(a)) == 1 and set(a) == set(b):
        return 1.0  # 완전 일치 + 분산 0 이면 kappa 정의가 0/0 이 된다 — 완전 일치로 취급한다
    return float(cohen_kappa_score(a, b))


def compute_agreement(judged_rows: list[dict], human_rows: list[dict]) -> dict:
    human_by_case = {row["case_id"]: row for row in human_rows}
    missing = [row["case_id"] for row in judged_rows if row["case_id"] not in human_by_case]
    paired = [(row, human_by_case[row["case_id"]]) for row in judged_rows if row["case_id"] in human_by_case]
    unlabeled = [row["case_id"] for row, human in paired if human.get("human_label", {}).get(RUBRIC_FIELDS[0]) is None]

    result: dict = {"n_judged": len(judged_rows), "n_human": len(human_rows),
                     "n_paired": len(paired), "missing_human_label": missing,
                     "unlabeled_rows": unlabeled, "dimensions": {}}

    scored = [(j, h) for j, h in paired if h["case_id"] not in unlabeled]
    result["n_scored"] = len(scored)
    if not scored:
        result["note"] = "사람 라벨이 채워진 행이 0건이다 — agreement 를 낼 수 없다"
        return result

    for field in RUBRIC_FIELDS:
        judge_scores = [j["judge"][field] for j, _ in scored]
        human_scores = [h["human_label"][field] for _, h in scored]
        exact = sum(1 for a, b in zip(judge_scores, human_scores) if a == b) / len(scored)
        result["dimensions"][field] = {
            "exact_match_rate": round(exact, 4),
            "cohen_kappa": round(k, 4) if (k := _cohen_kappa(judge_scores, human_scores)) is not None else None,
        }

    judge_pass = [bool(j["judge"]["pass"]) for j, _ in scored]
    human_pass = [bool(h["human_label"]["pass"]) for _, h in scored]
    result["pass_agreement"] = {
        "exact_match_rate": round(sum(1 for a, b in zip(judge_pass, human_pass) if a == b) / len(scored), 4),
        "cohen_kappa": round(k, 4) if (k := _cohen_kappa(judge_pass, human_pass)) is not None else None,
    }
    if len(scored) < 20:
        result["sample_size_warning"] = (
            f"n={len(scored)} — 표본이 작다. 이 수치는 방향성만 말하며 모집단 일반화를 증명하지 않는다"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge-vs-human label agreement on the frozen holdout set")
    parser.add_argument("--judged", required=True, help="eval/reports/rescored_holdout_*.jsonl (judge 채점 포함)")
    parser.add_argument("--human", required=True, help="eval.label_holdout_template 출력에 사람이 human_label 을 채운 파일")
    args = parser.parse_args()

    judged_rows = _load_jsonl(Path(args.judged))
    human_rows = _load_jsonl(Path(args.human))
    result = compute_agreement(judged_rows, human_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
