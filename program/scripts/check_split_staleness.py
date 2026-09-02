"""분할 스테이징이 원본보다 낡았는지 센다.

    python program/scripts/check_split_staleness.py

★스테이징을 서둘러 적용하지 않는 대신 이 검사를 둔다.
  원본이 바뀌면 분할을 다시 돌리면 된다 — 낡았는지만 알면 된다.

  program/wiki/_migration/datasets/index.md 참조.
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STAGE = "program/wiki/_migration/datasets"

#: 분할본 → 원본. codex 가 낸 파일명이 원본과 달라 손으로 맺는다.
PAIRS = {
    "voc/sources_catalog": "PLAN.md",
    "mt/olist_reviews_mt_bench": "REPORT.md",
    "commerce/naver_order_history": "REPORT.md",
    "commerce/courier_tracking": "REPORT.md",
    "voc/aihub_102_smb_order_qa": "REPORT.md",
    "voc/aihub_30716_callcenter_qa": "REPORT.md",
    "voc/aihub_71603_aspect_sentiment": "REPORT.md",
    "voc/aihub_71844_llm_instruction_tuning": "REPORT.md",
    "commerce/coupang_order_history/docs": "실제HTML_페이지네이션.md",
}


def main() -> int:
    stale, ok, missing = [], 0, []
    for rel, src_name in PAIRS.items():
        src = os.path.join("datasets", rel, src_name)
        stage_dir = os.path.join(STAGE, rel)
        if not os.path.exists(src):
            missing.append(src)
            continue
        outs = [os.path.join(stage_dir, f) for f in os.listdir(stage_dir)
                if f.endswith(".md")] if os.path.isdir(stage_dir) else []
        if not outs:
            missing.append(stage_dir)
            continue
        src_m = os.path.getmtime(src)
        oldest = min(os.path.getmtime(o) for o in outs)
        if src_m > oldest:
            stale.append((rel, src_name))
        else:
            ok += 1

    print(f"분할 스테이징 {len(PAIRS)}쌍")
    print(f"  최신 {ok}  ·  낡음 {len(stale)}  ·  짝 없음 {len(missing)}")
    for rel, name in stale:
        print(f"    ★낡음  {rel}/{name} 이 분할본보다 새롭다")
    for m in missing:
        print(f"    ★없음  {m}")
    if stale:
        print()
        print("  → 분할을 다시 돌린다. 서둘러 적용하지 않는다.")
        print("    program/wiki/_migration/datasets/index.md")
    return 1 if (stale or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
