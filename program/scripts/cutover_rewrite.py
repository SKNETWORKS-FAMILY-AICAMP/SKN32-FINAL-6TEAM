"""(2026-09-07 전환 완료 — 이 파일은 계획만 냈다. 실행부는 cutover_apply.py) 전환 시 경로를 다시 쓴다 — 지금은 계획만 낸다.

    python program/scripts/cutover_rewrite.py              # 무엇이 바뀌는지만 본다
    python program/scripts/cutover_rewrite.py --layout docs-wiki

★기본은 dry-run 이다. 실제로 쓰려면 `--apply` 가 필요하고, 그건
  D-012 (중간발표 2026-09-15 이후) 전에는 쓰지 않는다.

무엇을 하나:
  wiki/                     → <저장소>/wiki/ 또는 <저장소>/docs/wiki/
  program/<저장소>/wiki/             → 그 저장소 안으로
  그러면서 상대경로 깊이가 바뀐다. 그걸 다시 계산한다.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 지금 위치 → 전환 후 위치. layout 에 따라 뒤가 바뀐다.
SOURCES = {
    "wiki": ("", "hub"),
    "final_project_cs/wiki": ("final_project_cs", "cs"),
    "final_project_sample/wiki": ("final_project_sample", "sample"),
    "datasets/wiki": ("datasets", "data"),
    "acop_dojo/wiki": ("acop_dojo", "dojo"),
}

LINK = re.compile(r"\]\((\.\./[^)]*?)\)")


def destination(src: str, layout: str) -> str:
    repo, _ = SOURCES[src]
    leaf = "docs/wiki" if layout == "docs-wiki" else "wiki"
    #: hub 은 저장소가 없다. 루트에 둔다.
    return f"{repo}/{leaf}" if repo else leaf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", choices=("wiki", "docs-wiki"), default="wiki",
                    help="wiki = <저장소>/wiki/ · docs-wiki = <저장소>/docs/wiki/")
    ap.add_argument("--apply", action="store_true",
                    help="★D-012 전에는 쓰지 않는다")
    args = ap.parse_args()

    if args.apply:
        print("★거부한다. 전환은 중간발표(2026-09-15) 이후다 — D-012.")
        print("  정말 할 때가 되면 이 가드를 지우고 다시 읽어라.")
        return 2

    print(f"배치안: {args.layout}\n")
    moves, link_counts = [], Counter()
    for src in SOURCES:
        dst = destination(src, args.layout)
        n = len(glob.glob(src + "/**/*.md", recursive=True))
        moves.append((src, dst, n))

    print(f"{'지금':38} {'전환 후':34} {'문서':>4}")
    print("-" * 80)
    for src, dst, n in moves:
        print(f"{src:38} {dst:34} {n:4}")
    print(f"{'':38} {'':34} {sum(m[2] for m in moves):4}")

    # 깊이가 바뀌는 링크를 센다
    print("\n다시 계산해야 하는 링크")
    for src, dst, _ in moves:
        cross = 0
        for f in glob.glob(src + "/**/*.md", recursive=True):
            body = open(f, encoding="utf-8", errors="replace").read()
            for m in LINK.finditer(body):
                target = m.group(1)
                #: 자기 트리 밖으로 나가는 것만 깊이가 바뀐다
                if target.count("../") >= 2:
                    cross += 1
                    link_counts[src] += 1
        if cross:
            print(f"  {src:38} {cross:4}곳")
    print(f"  {'합계':38} {sum(link_counts.values()):4}곳")

    print("\n코드·원본 문서를 가리키는 참조")
    code = 0
    for src in SOURCES:
        for f in glob.glob(src + "/**/*.md", recursive=True):
            body = open(f, encoding="utf-8", errors="replace").read()
            code += len(re.findall(r"(final_project_cs|final_project_sample|datasets)/[a-z]", body))
    print(f"  {code}곳 — 전환 후 같은 저장소 안이 되면 경로가 짧아진다")

    print("\n★dry-run 이다. 아무것도 안 바꿨다.")
    print("  전환 시점: 중간발표(2026-09-15) 이후 — wiki/decisions/D-012-cutover-timing.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
