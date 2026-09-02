"""stage3 학습 데이터를 합치고 train/holdout 으로 **층화 분할**한다.

★v8 까지는 이 단계를 즉석으로 했고 스크립트가 없었다. 그 결과 v7 에서
  holdout 에 mismatch 가 **1건**만 들어가는 일이 벌어졌다(무작위 분리의 불운).
  n=1 로는 "echo 했다/안 했다"밖에 못 말한다. v8 은 4건이었고 그것도
  "50% → 통계적 결론 불가"로 끝났다.

  그래서 **층화 분할**한다 — mismatch 행과 나머지를 각각 같은 비율로 쪼갠다.
  holdout 의 mismatch 표본 수가 실험 설계상 가장 중요한 수치이므로, 그것을
  운에 맡기지 않고 보장하고 **그 수를 출력해 기록에 남긴다**.

★mismatch 판정은 `case_id` 의 `-mismatch` 접미사로 한다 —
  `build_stage3_mismatch_dataset.py` 가 evidence 를 실제로 조작한 행에만
  붙이는 표식이다. 조작하지 않은 대조군(consistent)은 접미사가 없어
  일반 행과 함께 층화된다. 그게 맞다 — 대조군은 "일관된 예시"이므로.

    python -m eval.finetune.build_stage3_split \\
        --source eval/finetune/sft_stage3.jsonl \\
        --source eval/finetune/sft_stage3_mismatch_v9.jsonl \\
        --train-out eval/finetune/sft_stage3_train_v9.jsonl \\
        --holdout-out eval/finetune/sft_stage3_holdout_v9.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MISMATCH_SUFFIX = "-mismatch"


def _load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _is_mismatch(row: dict) -> bool:
    return str(row.get("case_id", "")).endswith(MISMATCH_SUFFIX)


def _split(rows: list[dict], holdout_ratio: float, rng: random.Random) -> tuple[list[dict], list[dict]]:
    shuffled = rows[:]
    rng.shuffle(shuffled)
    cut = round(len(shuffled) * holdout_ratio)
    return shuffled[cut:], shuffled[:cut]


def main() -> int:
    parser = argparse.ArgumentParser(description="stage3 데이터 합치기 + 층화 train/holdout 분할")
    parser.add_argument("--source", action="append", required=True,
                        help="합칠 jsonl (여러 번 지정)")
    parser.add_argument("--train-out", required=True)
    parser.add_argument("--holdout-out", required=True)
    parser.add_argument("--holdout-ratio", type=float, default=0.163,
                        help="v8 의 33/202 를 기본값으로 둔다 — 세대 간 비교 가능성 유지")
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()

    rows: list[dict] = []
    per_source: list[tuple[str, int]] = []
    seen_case_ids: set[str] = set()
    duplicates = 0
    for source in args.source:
        path = ROOT / source if not Path(source).is_absolute() else Path(source)
        loaded = _load(path)
        kept = []
        for row in loaded:
            case_id = str(row.get("case_id", ""))
            # ★같은 case_id 가 두 소스에 있으면 학습·평가 양쪽에 새어 들어갈 수 있다.
            #   조용히 덮어쓰지 않고 세어 보고한다.
            if case_id and case_id in seen_case_ids:
                duplicates += 1
                continue
            seen_case_ids.add(case_id)
            kept.append(row)
        per_source.append((source, len(kept)))
        rows.extend(kept)

    mismatch = [row for row in rows if _is_mismatch(row)]
    rest = [row for row in rows if not _is_mismatch(row)]

    rng = random.Random(args.seed)
    train_m, hold_m = _split(mismatch, args.holdout_ratio, rng)
    train_r, hold_r = _split(rest, args.holdout_ratio, rng)

    train = train_m + train_r
    holdout = hold_m + hold_r
    rng.shuffle(train)
    rng.shuffle(holdout)

    for path_str, data in ((args.train_out, train), (args.holdout_out, holdout)):
        path = ROOT / path_str if not Path(path_str).is_absolute() else Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in data:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "sources": per_source,
        "duplicate_case_ids_dropped": duplicates,
        "total": len(rows),
        "mismatch_total": len(mismatch),
        "mismatch_ratio": round(len(mismatch) / len(rows), 4) if rows else 0.0,
        "train": len(train),
        "holdout": len(holdout),
        # ★이 값이 이번 실험의 성패를 가른다 — v7 은 1, v8 은 4였다.
        "holdout_mismatch": len(hold_m),
        "train_mismatch": len(train_m),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
