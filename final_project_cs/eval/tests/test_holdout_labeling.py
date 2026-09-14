"""label_holdout_template / agreement 를 합성 데이터로 검증한다.

★사람 라벨 값 자체는 여기서 지어내지 않는다 — 도구가 올바르게 동작하는지만
  합성(fixture) 데이터로 검증한다. 진짜 라벨은 사람만 채울 수 있다.
"""
import json
from pathlib import Path

from eval.label_holdout_template import build_template, RUBRIC_FIELDS as TEMPLATE_FIELDS
from eval.stats.agreement import compute_agreement, RUBRIC_FIELDS

ROOT = Path(__file__).resolve().parents[2]


def test_template_without_predictions_leaves_candidate_answer_null():
    rows = build_template(predictions_path=None)
    assert len(rows) == 24
    assert all(row["candidate_answer"] is None for row in rows)
    assert all(set(row["human_label"]) == set(TEMPLATE_FIELDS) | {"total", "pass"} for row in rows)
    assert all(value is None for row in rows for value in row["human_label"].values())


def test_template_with_predictions_fills_candidate_answer(tmp_path):
    holdout_ids = [json.loads(line)["case_id"]
                   for line in (ROOT / "eval/datasets/holdout.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    predictions = tmp_path / "rescored_holdout_proposed.jsonl"
    with predictions.open("w", encoding="utf-8") as out:
        out.write(json.dumps({"case_id": holdout_ids[0],
                               "prediction": {"answer": "test answer", "next_action": "respond"},
                               "citations": {"valid": ["doc_01#c1"]}}) + "\n")

    rows = build_template(predictions_path=predictions)
    matched = next(r for r in rows if r["case_id"] == holdout_ids[0])
    assert matched["candidate_answer"] == "test answer"
    assert matched["policy_evidence"] == ["doc_01#c1"]
    others_missing = [r for r in rows if r["case_id"] != holdout_ids[0]]
    assert all(r["candidate_answer"] is None for r in others_missing)


def _judged_row(case_id: str, **scores) -> dict:
    judge = {field: 3 for field in RUBRIC_FIELDS} | {"total": 15, "pass": True} | scores
    return {"case_id": case_id, "judge": judge}


def _human_row(case_id: str, labeled: bool = True, **scores) -> dict:
    if not labeled:
        label = {field: None for field in RUBRIC_FIELDS} | {"total": None, "pass": None}
    else:
        label = {field: 3 for field in RUBRIC_FIELDS} | {"total": 15, "pass": True} | scores
    return {"case_id": case_id, "human_label": label}


def test_perfect_agreement_scores_kappa_one_and_exact_match_one():
    judged = [_judged_row(f"h-{i}") for i in range(5)]
    human = [_human_row(f"h-{i}") for i in range(5)]
    result = compute_agreement(judged, human)
    assert result["n_scored"] == 5
    for field in RUBRIC_FIELDS:
        assert result["dimensions"][field]["exact_match_rate"] == 1.0
        assert result["dimensions"][field]["cohen_kappa"] == 1.0
    assert result["pass_agreement"]["exact_match_rate"] == 1.0


def test_disagreement_lowers_exact_match_rate():
    judged = [_judged_row("h-0", correctness=4), _judged_row("h-1", correctness=1)]
    human = [_human_row("h-0", correctness=1), _human_row("h-1", correctness=1)]
    result = compute_agreement(judged, human)
    assert result["dimensions"]["correctness"]["exact_match_rate"] == 0.5


def test_unlabeled_human_rows_are_excluded_and_reported():
    judged = [_judged_row("h-0"), _judged_row("h-1")]
    human = [_human_row("h-0"), _human_row("h-1", labeled=False)]
    result = compute_agreement(judged, human)
    assert result["n_scored"] == 1
    assert "h-1" in result["unlabeled_rows"]


def test_missing_human_row_entirely_is_reported():
    judged = [_judged_row("h-0"), _judged_row("h-missing")]
    human = [_human_row("h-0")]
    result = compute_agreement(judged, human)
    assert result["missing_human_label"] == ["h-missing"]
    assert result["n_scored"] == 1


def test_no_labeled_rows_returns_note_instead_of_crashing():
    judged = [_judged_row("h-0")]
    human = [_human_row("h-0", labeled=False)]
    result = compute_agreement(judged, human)
    assert "note" in result
    assert "dimensions" not in result or result["dimensions"] == {}
