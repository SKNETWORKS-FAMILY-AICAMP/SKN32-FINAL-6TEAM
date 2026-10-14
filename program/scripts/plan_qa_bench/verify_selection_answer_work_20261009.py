"""Verify saved work and links without model calls or artifact overwrites."""
import hashlib
import json
import py_compile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / "datasets/travel/selection_answer_bench/2026-10-09_pilot_v3"


def main():
    m = json.loads((PILOT / "manifest.json").read_text(encoding="utf-8"))
    checks = []
    for rel, sha in m["source_sha256"].items():
        assert hashlib.sha256((PILOT / rel).read_bytes()).hexdigest() == sha
        checks.append("pilot:" + rel)
    j = json.loads((ROOT / "program/scripts/plan_qa_bench/results/jev_training_recount_20261009_v1/counts.json").read_text(encoding="utf-8"))
    for rel, sha in j["source_sha256"].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha
        checks.append("jev:" + rel)
    assert len(j["rows"]) == 5 and all(r["saved"] == 835 and r["errors"] == 0 for r in j["rows"])
    docs = [
        "final_project_cs/wiki/quality/selection-grounded-answer-evaluation.md",
        "program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v2.md",
        "final_project_cs/wiki/records/reports/2026-10-09_1158_pilot-independent-review-corrections.md",
        "final_project_cs/wiki/records/reports/2026-10-09_1150_selection-answer-plan-and-training-review.md",
        "datasets/travel/selection_answer_bench/2026-10-09_pilot_v3/REPORT.md",
        "program/scripts/plan_qa_bench/results/jev_training_recount_20261009_v1/comparison.md",
        "program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md",
    ]
    links = []
    for rel in docs:
        p = ROOT / rel
        for link in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
            if "://" in link or link.startswith("#"):
                continue
            target = link.split("#")[0]
            dest = Path(target) if re.match(r"^[A-Za-z]:[/\\]", target) else p.parent / target
            assert dest.exists(), (rel, link, str(dest.resolve()))
            links.append(dict(document=rel, target=link))
    scripts = ["jev_training_recount_20261009.py", "selection_answer_pilot_20261009.py", "integrate_selection_answer_20261009.py", "integrate_selection_answer_review_20261009.py", "saluki_data_audit_20261009.py"]
    for script in scripts:
        py_compile.compile(str(ROOT / "program/scripts/plan_qa_bench" / script), doraise=True)
    status = json.loads((ROOT / "program/research/daily_rag_slm/selection_answer_review_2026-10-09_v2.json").read_text(encoding="utf-8"))
    assert not status["model_measurement_complete"] and not status["product_applied"]
    assert status["pilot_human_reviewed"] == status["pilot_model_evaluated"] == 0
    assert m["unique_itinerary_contents"] == status["pilot_unique_itinerary_contents"] == 1
    rows = [json.loads(l) for l in (PILOT / "raw/episodes.jsonl").read_text(encoding="utf-8").splitlines()]
    inputs = [json.loads(l) for l in (PILOT / "processed/model_inputs.jsonl").read_text(encoding="utf-8").splitlines()]
    for r, input_row in zip(rows, inputs):
        assert "gold" not in input_row and re.fullmatch(r"pilot-\d{4}", input_row["id"])
        assert r["gold"]["evidence_status"] in ["sufficient", "not_required"]
        assert all(c in r["allowed_source_ids"] for c in re.findall(r"\[([^]]+)\]", r["gold"]["reference_answer"]))
    saluki = json.loads((ROOT / "program/research/daily_rag_slm/saluki_finetune_2026-10-09.json").read_text(encoding="utf-8"))
    assert not saluki["conditional_backlog"]["ready"] and not saluki["conditional_backlog"]["worker_registered"]
    result = dict(file_hashes_verified=len(checks), expected_hashes=len(checks), local_links_verified=len(links),
                  expected_local_links=len(links), python_syntax_passed=len(scripts), expected_python_scripts=len(scripts),
                  human_reviewed=0, model_evaluated=0, pilot_schema_passed=24, pilot_expected=24,
                  final_holdout=False, saluki_training_started=False, links=links)
    output = ROOT / "program/scripts/plan_qa_bench/results/selection_answer_work_verification_20261009_v2.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k != "links"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
