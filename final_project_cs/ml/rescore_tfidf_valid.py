# -*- coding: utf-8 -*-
"""TF-IDF 기준선의 **검증 조각 점수**를 다시 계산하고 모델 파일을 저장한다.

    python -m ml.rescore_tfidf_valid

★왜 필요한가. 모델 선정은 검증 조각으로 해야 한다(시험 조각은 선정 뒤 보고만). 원격 학습의 첫 판은
  TF-IDF 검증 점수를 저장하지 않았고 모델 파일도 남기지 않았다.
★**재현을 먼저 확인한다.** 같은 데이터·같은 seed 로 분할·학습해 **시험 점수가 원격 결과와 같을 때만**
  검증 점수를 metrics.json 에 더한다. 다르면 멈춘다 — 다른 모델의 점수를 섞지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import artifact_dir                                                   # noqa: E402
from ml.train_labels_gpu import filter_synthetic, read_jsonl, run_tfidf, scores, split_real   # noqa: E402

RUNS = (("p1_real_only", False), ("p3_full", True), ("p4_qwen3", True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    root = artifact_dir("intent_ko")
    real = read_jsonl(root / "data" / "labeled_real_v2.jsonl")
    synthetic, synth_stats = filter_synthetic(read_jsonl(root / "data" / "synth_labeled.jsonl"))
    gold = read_jsonl(Path(__file__).resolve().parent / "data" / "travel_intent_eval.jsonl")
    print(f"실제 {len(real)} · 합성 {synth_stats}")
    for run, use_synth in RUNS:
        for field in ("intent", "issue_code"):
            target = root / run / f"{field}__tfidf" / "metrics.json"
            if not target.exists():
                continue
            metrics = json.loads(target.read_text(encoding="utf-8"))
            train_real, valid, test = split_real(real, field, args.seed)
            train = train_real + (synthetic if use_synth else [])
            labels = metrics["labels"]
            model, seconds, pv, pt, pg, _ = run_tfidf(train, valid, test, gold, field, labels, args)
            test_now = scores([r[field] for r in test], pt, labels, 0, args.seed)["accuracy"]
            test_then = metrics["teacher_agreement_test"]["accuracy"]
            if abs(test_now - test_then) > 1e-9 or len(train) != metrics["train_size"]:
                raise SystemExit(f"[멈춤] 재현 실패 {run}/{field}: 시험 {test_then} vs {test_now}, 학습 {metrics['train_size']} vs {len(train)}")
            metrics["teacher_agreement_valid"] = scores([r[field] for r in valid], pv, labels, args.bootstrap, args.seed)
            metrics["valid_rescored_locally"] = "원격 결과와 시험 점수·학습 건수가 같음을 확인한 뒤 같은 seed 로 다시 계산"
            target.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            joblib.dump(model, target.parent / "model.joblib")
            print(f"{run}/{field}: 시험 {test_now:.4f}(재현) · 검증 {metrics['teacher_agreement_valid']['accuracy']:.4f} · 모델 저장")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
