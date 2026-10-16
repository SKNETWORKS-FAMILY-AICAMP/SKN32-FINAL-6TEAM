# -*- coding: utf-8 -*-
"""여러 측정(`run.py` 의 `runs.jsonl`)을 합쳐 묶음 크기별 표를 다시 만든다. `[2026-10-16]`

    python -m eval.intake_chunking.merge <폴더1> <폴더2> … --out <폴더>

★이 실행의 유료 호출 상한(`--api-cap`)에 걸린 실행은 뺀다 — 모델이 답하지 못한 것이 아니라 시험 쪽이 막은 것이다(뺀 수를 표 위에 적는다).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from eval.intake_chunking.run import summarize

CAP = "이 실행의 유료 호출 상한을 넘었다"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folders", nargs="+")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    runs, dropped, backend = [], 0, ""
    for folder in args.folders:
        for line in (Path(folder) / "runs.jsonl").read_text(encoding="utf-8").splitlines():
            run = json.loads(line)
            backend = run["backend"]
            if any(CAP in (c.get("error") or "") for c in run["calls"]) or (run["report_error"] or "").find(CAP) >= 0:
                dropped += 1
                continue
            runs.append(run)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"합친 실행 {len(runs)} · 시험 쪽 호출 상한으로 뺀 실행 {dropped}")
    summarize(runs, out, f"{backend} (합침: {len(runs)} 실행, 상한으로 뺀 실행 {dropped})")


if __name__ == "__main__":
    main()
