"""holdout 20건에 대한 사람 라벨링 템플릿을 만든다.

★DoD-15/17 의 유일한 차단 항목(judge agreement)은 사람 라벨이 있어야
  풀린다. 이 스크립트는 그 라벨을 채울 빈 자리를 만드는 것까지만 한다 —
  라벨 값 자체는 만들지 않는다(CLAUDE.md §1 "지어내지 않는다").

judge 가 채점에 쓴 candidate answer 를 사람도 그대로 보고 독립적으로
채점해야 agreement 가 의미 있다. `--predictions` 로 rescore 산출물
(`eval/reports/rescored_holdout_*.jsonl`)을 주면 후보 답변을 함께 보여준다.
아직 holdout 을 실행하지 않았다면(`--predictions` 생략) 케이스 정보만
채우고 candidate_answer 는 null 로 남긴다 — 그 상태로는 라벨링을 시작할
수 없다는 뜻이며, 조용히 빈 값을 채워 넣지 않는다.

    python -m eval.label_holdout_template \\
        --predictions eval/reports/rescored_holdout_proposed.jsonl \\
        --output eval/reports/holdout_human_labels_template.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "eval" / "datasets" / "holdout.jsonl"
RUBRIC_FIELDS = ("correctness", "policy_grounding", "next_action", "safety", "personalization")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_template(*, predictions_path: Path | None) -> list[dict]:
    cases = _load_jsonl(HOLDOUT)
    if not cases:
        raise ValueError(f"no holdout cases found at {HOLDOUT}")

    predictions_by_case: dict[str, dict] = {}
    if predictions_path is not None:
        for row in _load_jsonl(predictions_path):
            predictions_by_case[row["case_id"]] = row

    rows = []
    for case in cases:
        pred = predictions_by_case.get(case["case_id"])
        candidate = (pred or {}).get("prediction") or {}
        row = {
            "case_id": case["case_id"],
            "message": case["message"],
            "expected_intent": case.get("expected_intent"),
            "expected_next_action": case.get("expected_next_action"),
            "doc_ref": case.get("doc_ref"),
            "candidate_answer": candidate.get("answer"),
            "candidate_next_action": candidate.get("next_action"),
            "policy_evidence": (pred or {}).get("citations", {}).get("valid") if pred else None,
            # ★사람이 채운다 — judge 점수는 일부러 안 보여준다(앵커링 방지).
            #   같은 판정 기준(rubric.json)으로 judge 와 독립적으로 0~4점을 매긴다.
            "human_label": {field: None for field in RUBRIC_FIELDS} | {"total": None, "pass": None},
            "labeler": None,
            "notes": None,
        }
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the human-labeling template for the frozen holdout set")
    parser.add_argument("--predictions", default=None,
                         help="rescore 산출물(eval/reports/rescored_holdout_*.jsonl) — 있으면 candidate 답변을 함께 보여준다")
    parser.add_argument("--output", default=str(ROOT / "eval" / "reports" / "holdout_human_labels_template.jsonl"))
    args = parser.parse_args()

    predictions_path = Path(args.predictions) if args.predictions else None
    if predictions_path is not None and not predictions_path.exists():
        raise SystemExit(f"ERROR: predictions file not found: {predictions_path}")

    rows = build_template(predictions_path=predictions_path)
    missing_candidates = sum(1 for r in rows if r["candidate_answer"] is None)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps({"output": str(output_path), "rows": len(rows),
                       "missing_candidate_answer": missing_candidates}, ensure_ascii=False))
    if missing_candidates:
        print(f"경고: {missing_candidates}건은 candidate_answer 가 비어 있다. "
              f"holdout 을 먼저 실행(eval.runners.proposed --dataset eval/datasets/holdout.jsonl)하고 "
              f"eval.rescore 로 채점한 뒤 --predictions 로 다시 넘겨야 사람이 그 답을 보고 라벨링할 수 있다.")


if __name__ == "__main__":
    main()
