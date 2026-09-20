# -*- coding: utf-8 -*-
"""감정 분류 학습셋 전처리 — 네이버쇼핑 리뷰(공개 말뭉치, Public Domain).

    python -m ml.preprocess

★**세어서 남긴다.** 단계마다 몇 건이 왜 빠졌는지 적고, 마지막에 산술 검사를 한다
  (들어온 건수 = 빠진 건수 합 + 남은 건수). 조용히 줄어든 데이터는 성공률을
  실제보다 좋아 보이게 만든다(`CLAUDE.md` §3 「조용한 스킵을 만들지 않는다」).

★**PII 는 학습 전에 가린다.** 제품이 쓰는 마스킹(`app/core/redaction.py`)을 그대로
  불러 쓴다 — 학습 때와 운영 때 **같은 모양의 글**을 보게 하려는 것이다. 여기서만
  쓰는 마스킹을 새로 만들면 두 쪽이 갈린다.

★**분할은 층화(stratified)한다.** 라벨 비율이 조각마다 같아야 시험 점수가 비교
  가능하다. 씨앗은 고정한다 — 같은 명령이 같은 분할을 낸다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.redaction import masked           # noqa: E402  ★제품과 같은 마스킹
from ml import REPO_ROOT, artifact_dir          # noqa: E402

#: 기본 입력 — 저장소 밖 데이터 폴더(루트 `.gitignore` 로 git 에 안 올라간다).
DEFAULT_SOURCE = (REPO_ROOT.parent / "datasets" / "voc" / "naver_shopping_sentiment"
                  / "processed" / "naver_shopping_sentiment.jsonl")

LABELS = ("negative", "positive")
MIN_CHARS = 2
MAX_CHARS = 300

#: 한국어 말뭉치에서 자주 나오는 개인정보 모양 — 제품 마스킹이 안 잡는 것만 더한다.
_EXTRA_PII = (
    (re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)"), "[REDACTED_RRN]"),      # 주민등록번호
    (re.compile(r"(?<!\d)01[016-9][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?<!\d)\d{2,3}-\d{2,6}-\d{2,6}(?!\d)"), "[REDACTED_ACCOUNT]"),  # 계좌번호 모양
)

#: ★3번 이상 반복하는 글자는 2번으로 줄인다(「좋아요ㅋㅋㅋㅋㅋㅋ」→「좋아요ㅋㅋ」).
#:  같은 말의 표기 차이를 줄이려는 것이다. 2번까지는 남긴다 — 강조는 뜻이 있다.
_REPEAT = re.compile(r"(.)\1{2,}")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """정규화 — 유니코드 통일 · 반복 축약 · 공백 정리 · PII 마스킹."""
    text = unicodedata.normalize("NFKC", text)
    text = masked(text)
    for pattern, replacement in _EXTRA_PII:
        text = pattern.sub(replacement, text)
    text = _REPEAT.sub(r"\1\1", text)
    return _SPACES.sub(" ", text).strip()


def read_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def preprocess(source: Path, *, seed: int, limit: int | None) -> tuple[dict[str, list[dict]], dict]:
    counts = Counter()
    removed_samples: list[dict] = []
    seen: set[str] = set()
    kept: list[dict] = []

    for row in read_rows(source):
        counts["read"] += 1
        if limit is not None and counts["read"] > limit:
            counts["read"] -= 1
            break
        raw = row.get("text")
        label = row.get("label")
        if not isinstance(raw, str) or label not in LABELS:
            counts["dropped_malformed"] += 1
            continue
        text = normalise(raw)
        if len(text) < MIN_CHARS:
            counts["dropped_too_short"] += 1
            continue
        if len(text) > MAX_CHARS:
            counts["dropped_too_long"] += 1
            if len(removed_samples) < 20:
                removed_samples.append({"reason": "too_long", "chars": len(text), "text": text[:120]})
            continue
        # ★정규화 **뒤** 중복을 본다. 원문이 달라도 표기만 다른 같은 글이 있다.
        key = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if key in seen:
            counts["dropped_duplicate"] += 1
            continue
        seen.add(key)
        if text != raw.strip():
            counts["normalised_changed"] += 1
        kept.append({"text": text, "label": label})

    # ── 층화 분할 8:1:1 ─────────────────────────────────────────
    rng = random.Random(seed)
    splits: dict[str, list[dict]] = {"train": [], "valid": [], "test": []}
    for label in LABELS:
        rows = [row for row in kept if row["label"] == label]
        rng.shuffle(rows)
        n_valid = len(rows) // 10
        n_test = len(rows) // 10
        splits["valid"] += rows[:n_valid]
        splits["test"] += rows[n_valid:n_valid + n_test]
        splits["train"] += rows[n_valid + n_test:]
    for rows in splits.values():
        rng.shuffle(rows)

    lengths = sorted(len(row["text"]) for row in kept)
    stats = {
        "source": str(source),
        "seed": seed,
        "read": counts["read"],
        "dropped": {
            "malformed": counts["dropped_malformed"],
            "too_short": counts["dropped_too_short"],
            "too_long": counts["dropped_too_long"],
            "duplicate": counts["dropped_duplicate"],
        },
        "normalisation_changed_text": counts["normalised_changed"],
        "kept": len(kept),
        "arithmetic_check": counts["read"] == sum(counts[k] for k in (
            "dropped_malformed", "dropped_too_short", "dropped_too_long", "dropped_duplicate")) + len(kept),
        "label_counts": {label: sum(1 for row in kept if row["label"] == label) for label in LABELS},
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_label_ratio": {
            name: {label: round(sum(1 for row in rows if row["label"] == label) / max(1, len(rows)), 4)
                   for label in LABELS}
            for name, rows in splits.items()
        },
        "char_length": {
            "min": lengths[0] if lengths else 0,
            "p50": lengths[len(lengths) // 2] if lengths else 0,
            "p95": lengths[int(len(lengths) * 0.95)] if lengths else 0,
            "max": lengths[-1] if lengths else 0,
        },
        "removed_samples": removed_samples,
    }
    return splits, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="감정 분류 학습셋 전처리")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--limit", type=int, default=None, help="앞에서 N 건만 읽는다(시험용)")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"입력이 없다: {args.source}", file=sys.stderr)
        return 2

    splits, stats = preprocess(args.source, seed=args.seed, limit=args.limit)
    out = artifact_dir("sentiment_ko", "data")
    for name, rows in splits.items():
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "preprocess_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in stats.items() if k != "removed_samples"},
                     ensure_ascii=False, indent=2))
    print(f"\n산출물: {out}")
    return 0 if stats["arithmetic_check"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
