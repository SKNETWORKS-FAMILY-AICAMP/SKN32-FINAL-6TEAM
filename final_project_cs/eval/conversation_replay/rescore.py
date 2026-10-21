# -*- coding: utf-8 -*-
"""다시 채점 — 이미 돌린 재생 결과(`results.jsonl`)를 **정답 · 옮긴 조건만 바꿔** 다시 채점한다(모델을 다시 부르지 않는다). `[2026-10-19]`

    python -m eval.conversation_replay.rescore <run 폴더> --episodes <episodes_v*.jsonl> --targets <targets_v*.jsonl> \
        --compiled <compiled.jsonl> --name <scores 이름> [--judge-model gpt-4.1-mini --keys-file <키 파일>]

★사람 검수로 끝 상태 · 금지가 바뀌면 이것으로 다시 채점한다. 단 **대본(고객 줄 · 역할)이나 시작 상태가 바뀌면** 재생부터 다시 돌린다
  (갈림 판정 · B 잇기가 대본과 역할에 따라 달라지기 때문이다).
★판정 모델(`answer_judge`)은 있을 때와 없을 때를 따로 낸다 — 없으면 그 조건은 판정 불가.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--episodes", type=Path)
    ap.add_argument("--targets", type=Path)
    ap.add_argument("--compiled", type=Path)
    ap.add_argument("--name", default="scores_rescored")
    ap.add_argument("--judge-model")
    ap.add_argument("--keys-file", type=Path, action="append", default=[])
    ap.add_argument("--seed", type=int, default=20261019)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    from . import episodes as E
    from .runner import load_compiled, openai_judge
    from .score import score_episode

    eps = {e["episode_id"]: e for e in (E.load(args.episodes) if args.episodes else []) + (E.load(args.targets) if args.targets else [])}
    compiled = load_compiled(args.compiled, list(eps.values()))
    judge = None
    if args.judge_model:
        key = os.environ.get("ACOP_OPENAI_API_KEY", "")
        for path in args.keys_file:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("ACOP_OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"')
        judge = openai_judge(model=args.judge_model, seed=args.seed, api_key=key)
    out = args.run / f"{args.name}.jsonl"
    n = 0
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        last: dict[str, dict] = {}
        for line in (args.run / "results.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                last[row["episode_id"]] = row          # 이어 돌린 에피소드는 뒤 줄이 앞 줄을 대신한다
        for res in last.values():
            ep = eps.get(res["episode_id"])
            if ep is None:
                continue
            score = ({"episode_id": res["episode_id"], "crash": res["crash"]} if "crash" in res else
                     score_episode(res, compiled[res["episode_id"]], ep, judge=judge))
            fh.write(json.dumps(score, ensure_ascii=False, default=str) + "\n")
            n += 1
    print(f"다시 채점 {n}건 → {out}")


if __name__ == "__main__":
    main()
