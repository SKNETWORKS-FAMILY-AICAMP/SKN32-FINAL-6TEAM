# -*- coding: utf-8 -*-
"""여러 측정의 `scores.json` 을 나란히 놓는다.

    python -m eval.intake_diverse.compare 지금구조=<폴더> 시제품E4B=<폴더> 시제품Winnow=<폴더> > 비교.md
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from .report import LABELS, SHAPE_KO, SHAPES
from .score import pct

SHAPE_KEYS = ["items", "items_tight", "items_precision", "time", "date", "moves", "conditions", "preferences", "requests_exact", "missing"]


def main(argv: list[str]) -> int:
    runs = []
    for arg in argv:
        name, folder = arg.split("=", 1)
        runs.append((name, json.loads((Path(folder) / "scores.json").read_text(encoding="utf-8"))))
    lines = []
    for group, title in (("전체", "전체 69건"), ("origin:synthetic", "합성 49건"), ("origin:real", "실제 접수 20건")):
        lines += [f"### 칸별 — {title}", "", "| 칸 | " + " | ".join(n for n, _ in runs) + " |", "|---|" + "---|" * len(runs)]
        for key, label in LABELS:
            lines.append(f"| {label} | " + " | ".join(pct(r["totals"].get(group, {}).get(key, [0, 0])) for _, r in runs) + " |")
        lines.append("")
    for key in SHAPE_KEYS:
        label = dict(LABELS)[key]
        lines += [f"### 형식별 — {label}", "", "| 형식 | " + " | ".join(n for n, _ in runs) + " |", "|---|" + "---|" * len(runs)]
        for shape in SHAPES:
            g = f"shape:{shape}"
            if not any(g in r["totals"] for _, r in runs):
                continue
            lines.append(f"| {SHAPE_KO[shape]} | " + " | ".join(pct(r["totals"].get(g, {}).get(key, [0, 0])) for _, r in runs) + " |")
        lines.append("")
    sys.stdout.write("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
