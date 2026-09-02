"""type 분류 검증용 층화 표본 추출.

governance/migration.md 의 검증 절차가 요구하는 표본을 만든다.
seed 를 고정해 **같은 표본이 다시 나온다.** 재현되지 않으면 재검증이 무의미하다.

    python program/scripts/sample_docs.py            # 표본 목록
    python program/scripts/sample_docs.py --summary  # 분류 판단용 요지까지

결과: program/scripts/_sample.txt
"""
from __future__ import annotations

import argparse
import glob
import os
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEED = 20260901          # ★고정. 바꾸면 이전 검증과 비교할 수 없다.
MIN_BYTES = 200          # 빈 파일·스텁 제외

#: ★seed 고정만으로는 부족하다.
#:  2026-09-01 에 수집 로직에 정렬을 넣었더니 같은 seed 인데 다른 표본이 나왔다.
#:  모집단 순서가 바뀌면 random.sample 결과도 바뀌기 때문이다.
#:  그래서 뽑은 목록 자체를 파일로 얼린다. 이 파일이 있으면 그대로 쓴다.
FROZEN = "program/scripts/sample_frozen.txt"

#: (층 이름, glob 패턴들, 뽑을 개수)
STRATA: list[tuple[str, list[str], int]] = [
    ("program/plan",     ["program/plan/*.md"], 8),
    ("program/research", ["program/research/*.md"], 6),
    ("cs/docs/plans",    ["final_project_cs/docs/plans/*.md"], 5),
    ("cs/docs/evidence", ["final_project_cs/docs/evidence/*.md"], 4),
    ("cs/docs/handoff",  ["final_project_cs/docs/handoff/*.md"], 5),
    ("cs/docs/reports",  ["final_project_cs/docs/reports/*.md"], 5),
    ("cs/docs/manuals",  ["final_project_cs/docs/manuals/*.md"], 2),
    ("cs/docs/vision",   ["final_project_cs/docs/vision/*.md"], 2),
    ("datasets REPORT",  ["datasets/**/REPORT.md"], 4),
    ("README/CLAUDE",    ["*/CLAUDE.md", "*/README.md", "CLAUDE.md"], 4),
]

OUT = "program/scripts/_sample.txt"


def collect(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for p in patterns:
        files += glob.glob(p, recursive=True)
    return sorted({f for f in files if os.path.getsize(f) > MIN_BYTES})


def summarize(path: str) -> tuple[str, str, list[str], int]:
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    h1 = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), "(제목없음)")
    body = next(
        (l.strip() for l in lines
         if l.strip() and not l.startswith(("#", "---", "|", "-", "*", ">", "```"))),
        "",
    )
    heads = [l.lstrip("#").strip() for l in lines if l.startswith("## ")][:5]
    return h1, body, heads, len(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true", help="분류 판단용 요지도 출력")
    args = ap.parse_args()

    sample: list[tuple[str, str]] = []

    if os.path.exists(FROZEN):
        # 얼린 목록이 있으면 그대로 쓴다. 다시 뽑지 않는다.
        for line in open(FROZEN, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                layer, _, path = line.partition("\t")
                sample.append((layer, path))
        missing = [f for _, f in sample if not os.path.exists(f)]
        print(f"얼린 표본 사용: {FROZEN}  ({len(sample)}건)")
        if missing:
            print(f"★ 사라진 파일 {len(missing)}건 — 재검증 결과가 이전과 달라진다")
            for m in missing:
                print(f"    {m}")
    else:
        random.seed(SEED)
        print(f"{'층':20} {'모집단':>6} {'표본':>4}")
        print("-" * 36)
        for name, patterns, quota in STRATA:
            files = collect(patterns)
            n = min(quota, len(files))
            picked = random.sample(files, n) if files else []
            sample += [(name, f) for f in picked]
            print(f"{name:20} {len(files):6} {n:4}")
        print("-" * 36)
        print(f"{'합계':20} {'':6} {len(sample):4}")
        print(f"\n★ {FROZEN} 이 없어서 새로 뽑았다.")
        print("  재검증하려면 이 결과를 그 경로로 복사해 얼려야 한다.")

    with open(OUT, "w", encoding="utf-8") as fh:
        for layer, f in sample:
            fh.write(f"{layer}\t{f}\n")
    print(f"\n→ {OUT}")

    if args.summary:
        print()
        for i, (layer, f) in enumerate(sample, 1):
            h1, body, heads, n = summarize(f)
            print(f"{i:2}. [{layer}] {os.path.basename(f)}")
            print(f"    제목: {h1[:70]}")
            print(f"    첫줄: {body[:100]}")
            print(f"    소제목: {' / '.join(heads)[:100]}")
            print(f"    {n}줄")
    return 0


if __name__ == "__main__":
    sys.exit(main())
