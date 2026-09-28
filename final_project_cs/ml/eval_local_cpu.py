# -*- coding: utf-8 -*-
"""학습한 감정 모델을 **제품 어댑터 그대로** 불러 CPU 에서 잰다 — 여행 조각 판정 + 추론 속도.

    python -m ml.eval_local_cpu --model-dir ../datasets/ml/sentiment_ko/skt__A.X-Encoder-base

★**GPU 점수로 제품을 말하지 않는다.** 제품 서버에는 GPU 가 없다(이 저장소의 개발
  서버도 CPU). 그래서 제품 자리(`app/infrastructure/ml/sentiment.py`)로 불러 CPU 에서
  한 문장씩 걸리는 시간을 잰다.

★**어댑터를 거쳐서 잰다.** 모델을 직접 부르면 어댑터의 물러섬(중립)·계약이 빠진다.
  속도만 따로, 묶음 처리(배치) 기준으로 한 번 더 잰다 — 두 수는 뜻이 다르다.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.infrastructure.ml.sentiment import LocalSentiment   # noqa: E402  ★제품 자리
from ml import REPO_ROOT, artifact_dir                        # noqa: E402

LABELS3 = ("negative", "neutral", "positive")


def macro_f1(gold: list[str], pred: list[str]) -> float:
    scores = []
    for label in LABELS3:
        tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def main() -> int:
    parser = argparse.ArgumentParser(description="어댑터로 CPU 평가")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--latency-n", type=int, default=200)
    parser.add_argument("--batch-n", type=int, default=1000)
    args = parser.parse_args()

    travel = [json.loads(line) for line in
              (REPO_ROOT / "ml" / "data" / "travel_sentiment_eval.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    test = [json.loads(line)["text"] for line in
            (artifact_dir("sentiment_ko", "data") / "test.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]

    adapter = LocalSentiment(args.model_dir)
    started = time.perf_counter()
    adapter("준비")                                   # 적재 시간은 따로 잰다
    load_seconds = round(time.perf_counter() - started, 2)
    assert adapter.kind == "transformer", adapter.kind

    # ── 여행 조각 — 임계값별(어댑터가 물러서는 기준) ────────────────
    raw = [adapter._probabilities(row["text"]) for row in travel]   # 한 번만 계산해 임계값을 훑는다
    by_threshold = []
    for threshold in (0.5, 0.7, 0.8, 0.9, 0.95):
        pred = []
        for probs in raw:
            best = max(probs, key=probs.get)
            pred.append("neutral" if probs[best] < threshold else best)
        gold = [row["label"] for row in travel]
        by_threshold.append({
            "threshold": threshold,
            "accuracy_3class": round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 4),
            "macro_f1_3class": round(macro_f1(gold, pred), 4),
            "abstain_rate": round(pred.count("neutral") / len(pred), 4),
        })

    # ── 한 문장씩(제품이 메시지 하나를 받을 때) ─────────────────────
    latencies = []
    for text in test[:args.latency_n]:
        tick = time.perf_counter()
        adapter(text)
        latencies.append((time.perf_counter() - tick) * 1000)
    latencies.sort()

    # ── 묶음(배치 32) 처리량 ─────────────────────────────────────
    import torch
    tokenizer, model = adapter._tokenizer, adapter._model
    tick = time.perf_counter()
    with torch.no_grad():
        for start in range(0, args.batch_n, 32):
            chunk = test[start:start + 32]
            encoded = tokenizer(chunk, truncation=True, max_length=96, padding=True, return_tensors="pt")
            model(**encoded)
    batch_seconds = time.perf_counter() - tick

    result = {
        "model_dir": str(args.model_dir), "adapter": "app.infrastructure.ml.sentiment.LocalSentiment",
        "device": "cpu", "cpu": platform.processor(), "torch_threads": torch.get_num_threads(),
        "load_seconds": load_seconds,
        "travel_eval": {"n": len(travel), "note": "작업 세션 라벨 41건 — 방향만 본다",
                        "by_threshold": by_threshold},
        "latency_single_ms": {"n": len(latencies), "p50": round(statistics.median(latencies), 1),
                              "p95": round(latencies[int(len(latencies) * 0.95) - 1], 1),
                              "mean": round(statistics.mean(latencies), 1)},
        "batch32_throughput": {"sentences": args.batch_n, "seconds": round(batch_seconds, 2),
                               "sentences_per_second": round(args.batch_n / batch_seconds, 1)},
    }
    (args.model_dir / "cpu_eval.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
