"""Create a blank human-label worksheet from the frozen holdout dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


FIELDS = ("human_intent", "human_issue_code", "human_sentiment", "human_pass", "human_notes")


def make_template(rows: list[dict]) -> list[dict]:
    """Preserve case IDs/messages and leave every human field blank."""
    return [
        {
            "case_id": row["case_id"],
            "message": row["message"],
            "human_intent": None,
            "human_issue_code": None,
            "human_sentiment": None,
            "human_pass": None,
            "human_notes": "",
        }
        for row in rows
    ]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="eval/datasets/holdout.jsonl")
    parser.add_argument("--output", default="eval/reports/holdout_human_labels_template.jsonl")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = make_template(load_jsonl(Path(args.input)))
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} blank labels to {output}")


if __name__ == "__main__":
    main()
