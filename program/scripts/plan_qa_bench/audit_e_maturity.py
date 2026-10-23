"""Read-only E/MX corpus audit; write a fresh evidence file without rebuilding data."""
import argparse
import collections
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def audit(root):
    data = root / "datasets/core/pointing/testset/requests_inside_chitchat_pairs_v1"
    files = [data / name for name in (
        "mx_all.json", "mx_main_prompts.json", "mx_disputes.json",
        "mx_human_check_sample.csv",
    )]
    all_rows, main, disputes = [json.loads(p.read_text(encoding="utf-8")) for p in files[:3]]
    with files[3].open(encoding="utf-8-sig", newline="") as stream:
        sample = list(csv.reader(stream))
    header, sample_rows = sample[0], sample[1:]
    # Exact Unicode header avoids terminal code-page display artifacts.
    judgement = header.index("사람 판정(번호/없음/애매)")
    pairs = collections.defaultdict(list)
    for row in main:
        pairs[row["pair"]].append(row)
    valid_pairs = sum(
        len(rows) == 2 and {r["kind"] for r in rows} == {"mixed", "control"}
        and rows[0]["gold"] == rows[1]["gold"] for rows in pairs.values()
    )
    mixed = [r for r in main if r["kind"] == "mixed"]
    expected_main = [r for r in all_rows if r["kind"] in ("mixed", "control") and not r.get("quarantine")]
    return {
        "recorded_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "scope": "Corpus structure and stored human-review cells; no model execution or human gold review",
        "files": [{"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
        "counts": {
            "all_rows": len(all_rows), "main_rows": len(main),
            "main_exactly_matches_unquarantined_pairs": main == expected_main,
            "pairs": len(pairs), "valid_same_gold_mixed_control_pairs": valid_pairs,
            "mixed": len(mixed), "control": sum(r["kind"] == "control" for r in main),
            "mixed_positive": sum(r["gold"] is not None for r in mixed),
            "mixed_null": sum(r["gold"] is None for r in mixed),
            "mixed_sources": dict(collections.Counter(r["src"] for r in mixed)),
            "mixed_categories": dict(collections.Counter(r["cat"] for r in mixed)),
            "itinerary_header_ids": len({r["itin"] for r in main}),
            "quarantined_pairs": len({r["pair"] for r in all_rows if r.get("quarantine")}),
            "challenge_rows_excluded_from_main": sum(r["kind"] == "challenge" for r in all_rows),
            "disagreements_excluded_before_main_construction": len(disputes),
            "disagreement_categories": dict(collections.Counter(r["cat"] for r in disputes)),
            "human_sample_rows": len(sample_rows),
            "human_judgements_filled": sum(bool(r[judgement].strip()) for r in sample_rows),
            "human_sample_all_rows_match_header_width": all(len(r) == len(header) for r in sample_rows),
        },
        "interpretation": {
            "more_advanced_for": "Mixed free-form single itinerary-item recognition and paired noise-effect diagnosis",
            "not_established": ["Human-validated final gold set", "Production readiness", "Overall travel intent or RAG answer correctness"],
            "limitations": [
                "Most mixed sentences are code concatenations; model-authored natural blends are not real customer messages",
                "Agreement-filtered labels can remove difficult cases; model-family label agreement is not human adjudication",
                "Two actual requested items are challenges outside the single-item score",
                "Header IDs are clustered contexts, not independent customer trips or independent accuracy samples",
                "Builder near-overlap filtering covers specified H train/test files, not every historical training source",
                "Repeatedly inspected development/regression scores do not replace a fresh fixed held-out set",
            ],
        },
        "source_builder": "program/scripts/plan_qa_bench/build_mx_set.py",
        "source_design": "program/research/시험세트_MX_설계_2026-10-07.md",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    result = audit(root)
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result["counts"], ensure_ascii=True))
