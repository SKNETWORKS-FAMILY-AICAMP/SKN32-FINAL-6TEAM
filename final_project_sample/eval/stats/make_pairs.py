"""Build paired rows for McNemar and bootstrap from raw harness output."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--x", default=None)
    parser.add_argument("--y", default=None)
    args = parser.parse_args()

    grouped = defaultdict(dict)
    file_arms = []
    for input_path in args.input:
        arms_in_file = set()
        for line in Path(input_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                arms_in_file.add(row["arm"])
                grouped[(row["case_id"], row.get("repeat", 1))][row["arm"]] = row
        if len(arms_in_file) == 1:
            file_arms.append(next(iter(arms_in_file)))

    x_arm = args.x or (file_arms[0] if file_arms else "Proposed")
    y_arm = args.y or (file_arms[1] if len(file_arms) > 1 else "A")

    rows = []
    for (case_id, repeat), values in sorted(grouped.items()):
        if x_arm not in values or y_arm not in values:
            continue
        x_row, y_row = values[x_arm], values[y_arm]
        x_success, y_success = bool(x_row["success"]), bool(y_row["success"])
        paired = {
            "case_id": case_id, "repeat": repeat,
            "x_arm": x_arm, "y_arm": y_arm,
            "x_success": x_success, "y_success": y_success,
            # Backward-compatible aliases used by the original McNemar file.
            "a_success": y_success, "b_success": x_success,
        }
        for key, x_value, y_value in (
            ("score", x_row.get("score"), y_row.get("score")),
            ("grounding", x_row.get("judge", {}).get("policy_grounding"),
             y_row.get("judge", {}).get("policy_grounding")),
        ):
            if x_value is not None and y_value is not None:
                paired[f"x_{key}"] = float(x_value)
                paired[f"y_{key}"] = float(y_value)
        rows.append(paired)

    output = Path(args.output)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"output": args.output, "rows": len(rows), "x": x_arm, "y": y_arm}, ensure_ascii=False))


if __name__ == "__main__":
    main()
