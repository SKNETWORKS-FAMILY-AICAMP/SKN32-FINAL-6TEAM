"""Recount collected answers and verify immutable archive digests; no model calls."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "program/scripts/plan_qa_bench/results"
GPU = RESULTS / "gpu_backlog_20261008"
OUT = RESULTS / "heartbeat_20261009_0754/parent_results_verification.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    archive = GPU / "A_completed_hb0754_20261009"
    verification = read(archive / "archive_verification.json")
    for entry in verification["files"]:
        path = archive / entry["relative"]
        assert path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    answer_files = sorted(archive.glob("*/d_test_*.jsonl"))
    saved = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in answer_files)
    assert len(answer_files) == 13 and saved == 27555
    summaries = {}
    for suite, count_file in [
        ("d", "choice_counts"), ("d2", "choice_counts"),
        ("d3", "choice_counts"), ("h", "h_counts"), ("mx", "mx_counts"),
    ]:
        job = f"saluki_original_{suite}_a1"
        count = read(GPU / job / f"{count_file}.json")
        source = archive / job / f"d_test_{job}.jsonl"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == count["answer_sha256"]
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == count["saved"] == count["expected"]
        assert len({r["i"] for r in rows}) == len(rows)
        assert all(r.get("parsed") is True and not r.get("error") for r in rows)
        if suite == "mx":
            positive = [r for r in rows if r["type"].endswith("_mixed") and r["gold"] is not None]
            negative = [r for r in rows if r["type"].endswith("_mixed") and r["gold"] is None]
            expected = count["counts"]["mixed"]
            expected_positive = expected["request"]["correct"]
            expected_negative = expected["no_request"]["false_pick"]
        else:
            positive = [r for r in rows if r["gold"] is not None and r["type"] != "compound_intent"]
            negative = [r for r in rows if r["gold"] is None and r["type"] != "compound_intent"]
            expected_positive = count["positive"]["correct"]
            expected_negative = count["negative"]["false_pick"]
        correct = sum(r["pick"] == r["gold"] for r in positive)
        false_pick = sum(r["pick"] is not None for r in negative)
        assert correct == expected_positive and false_pick == expected_negative
        summaries[suite] = {
            "saved": len(rows), "expected": count["expected"],
            "positive_correct": correct, "positive_expected": len(positive),
            "null_false_pick": false_pick, "null_expected": len(negative),
            "failed_unparsed_missing": 0,
            "answer_sha256": count["answer_sha256"],
            "gold_sha256": count["gold_sha256"],
        }
    assert sum(s["saved"] for s in summaries.values()) == 9425
    result = {
        "scope": "Independent parent recount of collected row IDs, parsed flags, stored gold/pick and archive hashes; not human adjudication",
        "archive_files_verified": len(verification["files"]),
        "archive_files_expected": len(verification["files"]),
        "answer_files": len(answer_files), "saved_rows": saved,
        "saluki": summaries, "product_adoption": False,
    }
    assert not OUT.exists(), "Use a new output name or back up before rerunning"
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
