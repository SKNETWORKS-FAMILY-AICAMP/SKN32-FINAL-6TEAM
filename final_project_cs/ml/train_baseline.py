# -*- coding: utf-8 -*-
"""기준선 — TF-IDF + 로지스틱 회귀. 딥러닝이 이걸 못 이기면 딥러닝을 쓸 이유가 없다.

    python -m ml.train_baseline

★**기준선을 먼저 만든다.** 딥러닝 점수만 내면 그 점수가 좋은 건지 알 수 없다.
★**평균만 적지 않는다.** 부트스트랩 95% 신뢰구간을 같이 낸다(`CLAUDE.md` §4).
★**확률을 낸다.** 운영에서 「모르겠으면 중립」으로 물러설 임계값이 필요하다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import artifact_dir                      # noqa: E402

LABELS = ["negative", "positive"]


def load(split: str) -> tuple[list[str], list[str]]:
    path = artifact_dir("sentiment_ko", "data") / f"{split}.jsonl"
    texts, labels = [], []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def bootstrap_ci(y_true: np.ndarray, y_pred: np.ndarray, *, n: int, seed: int) -> dict:
    """★점수 하나만 적지 않는다 — 다시 뽑아도 그 근처인지 본다."""
    rng = np.random.default_rng(seed)
    accs, f1s = [], []
    size = len(y_true)
    for _ in range(n):
        idx = rng.integers(0, size, size)
        accs.append(accuracy_score(y_true[idx], y_pred[idx]))
        f1s.append(f1_score(y_true[idx], y_pred[idx], average="macro"))
    return {
        "accuracy_ci95": [round(float(np.percentile(accs, 2.5)), 4),
                          round(float(np.percentile(accs, 97.5)), 4)],
        "macro_f1_ci95": [round(float(np.percentile(f1s, 2.5)), 4),
                          round(float(np.percentile(f1s, 97.5)), 4)],
        "bootstrap_n": n,
    }


def coverage_table(probs: np.ndarray, y_true: np.ndarray, y_pred: np.ndarray) -> list[dict]:
    """★임계값을 올리면 얼마나 답하고 그때 얼마나 맞나.

    운영에서는 확신이 낮으면 **중립으로 물러선다**. 그 손익을 숫자로 둔다.
    """
    confidence = probs.max(axis=1)
    rows = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        mask = confidence >= threshold
        answered = int(mask.sum())
        rows.append({
            "threshold": threshold,
            "answered": answered,
            "coverage": round(answered / len(y_true), 4),
            "accuracy_on_answered": round(float(accuracy_score(y_true[mask], y_pred[mask])), 4)
            if answered else None,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="감정 분류 기준선 학습")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()

    x_train, y_train = load("train")
    x_valid, y_valid = load("valid")
    x_test, y_test = load("test")

    # ★한국어는 띄어쓰기가 흔들린다 — 글자 n-gram 을 같이 쓴다. 낱말만 쓰면
    #   「배송이빠르고」 같은 글이 통째로 미지 낱말이 된다.
    features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=3, sublinear_tf=True)),
    ])
    model = Pipeline([
        ("features", features),
        ("clf", LogisticRegression(C=4.0, max_iter=2000, n_jobs=-1, random_state=args.seed)),
    ])

    started = time.perf_counter()
    model.fit(x_train, y_train)
    train_seconds = round(time.perf_counter() - started, 1)

    result: dict = {"model": "tfidf+logreg", "seed": args.seed,
                    "train_seconds": train_seconds,
                    "train_size": len(x_train), "valid_size": len(x_valid), "test_size": len(x_test)}
    for name, (x, y) in {"valid": (x_valid, y_valid), "test": (x_test, y_test)}.items():
        pred = model.predict(x)
        result[name] = {
            "accuracy": round(float(accuracy_score(y, pred)), 4),
            "macro_f1": round(float(f1_score(y, pred, average="macro")), 4),
            "confusion_matrix": {"labels": LABELS,
                                 "rows_true_cols_pred": confusion_matrix(y, pred, labels=LABELS).tolist()},
            "per_label": classification_report(y, pred, labels=LABELS, output_dict=True, zero_division=0),
        }
    y_test_arr = np.array(y_test)
    pred_test = model.predict(x_test)
    result["test"].update(bootstrap_ci(y_test_arr, pred_test, n=args.bootstrap, seed=args.seed))
    result["test"]["coverage_by_threshold"] = coverage_table(
        model.predict_proba(x_test), y_test_arr, pred_test)

    out = artifact_dir("sentiment_ko", "baseline")
    import joblib
    joblib.dump(model, out / "model.joblib")
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "valid"}, ensure_ascii=False, indent=2)[:2500])
    print(f"\n산출물: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
