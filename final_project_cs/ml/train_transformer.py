# -*- coding: utf-8 -*-
"""딥러닝 — KoELECTRA-small 파인튜닝(CPU). 기준선(TF-IDF)을 이기는지 본다.

    python -m ml.train_transformer --train-size 40000 --epochs 2

★**GPU 가 없다.** 이 기계는 `torch.cuda.is_available() == False` 다(실측). 그래서
  작은 모델(1,400만 파라미터)과 부분 표본으로 돈다. **부분 표본이라고 적는다** —
  전량 학습 결과가 아니다.
★**기준선과 같은 시험 조각·같은 지표**로 잰다. 조건이 다르면 비교가 아니다.
★**임계값 표를 같이 낸다.** 운영에서 확신이 낮으면 중립으로 물러선다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import artifact_dir                                          # noqa: E402
from ml.train_baseline import LABELS, bootstrap_ci, coverage_table, load   # noqa: E402

#: ★이름으로 부르면 transformers 가 **그때마다 허브에 묻는다** — 망이 막히면
#:  받아 둔 캐시가 있어도 실패한다(2026-09-17 실측: tokenizer 로드에서
#:  "Cannot send a request, as the client has been closed"). 그래서 **받아 둔
#:  스냅샷 폴더를 직접** 가리키고 오프라인으로 못박는다.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

BASE_MODEL_ID = "monologg/koelectra-small-v3-discriminator"


def _local_snapshot() -> str:
    """받아 둔 스냅샷 폴더. 없으면 이름 그대로 돌려준다(그때는 망이 필요하다)."""
    cache = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface")) / "hub"
    root = cache / ("models--" + BASE_MODEL_ID.replace("/", "--")) / "snapshots"
    if root.is_dir():
        snapshots = sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
        for snapshot in snapshots:
            if (snapshot / "config.json").exists():
                return str(snapshot)
    return BASE_MODEL_ID


BASE_MODEL = _local_snapshot()


class Reviews(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.encodings = tokenizer(texts, truncation=True, max_length=max_len,
                                   padding="max_length", return_tensors="pt")
        self.labels = torch.tensor([LABELS.index(label) for label in labels])

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: value[idx] for key, value in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def stratified_head(texts, labels, size):
    """★앞에서 잘라 쓰지 않는다 — 라벨 비율을 지켜 고른다."""
    if size is None or size >= len(texts):
        return texts, labels
    per_label = size // len(LABELS)
    picked_texts, picked_labels = [], []
    for label in LABELS:
        idx = [i for i, value in enumerate(labels) if value == label][:per_label]
        picked_texts += [texts[i] for i in idx]
        picked_labels += [labels[i] for i in idx]
    return picked_texts, picked_labels


@torch.no_grad()
def predict(model, loader):
    model.eval()
    probs = []
    for batch in loader:
        _labels = batch.pop("labels")
        logits = model(**batch).logits
        probs.append(torch.softmax(logits, dim=-1).cpu().numpy())
    return np.concatenate(probs)


def main() -> int:
    parser = argparse.ArgumentParser(description="감정 분류 딥러닝 학습(CPU)")
    parser.add_argument("--train-size", type=int, default=40000)
    parser.add_argument("--valid-size", type=int, default=4000)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-len", type=int, default=96)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(os.cpu_count() or 4)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(LABELS),
        id2label={i: label for i, label in enumerate(LABELS)},
        label2id={label: i for i, label in enumerate(LABELS)})

    x_train, y_train = stratified_head(*load("train"), args.train_size)
    x_valid, y_valid = stratified_head(*load("valid"), args.valid_size)
    x_test, y_test = load("test")

    train_loader = DataLoader(Reviews(x_train, y_train, tokenizer, args.max_len),
                              batch_size=args.batch_size, shuffle=True)
    valid_loader = DataLoader(Reviews(x_valid, y_valid, tokenizer, args.max_len),
                              batch_size=64)
    test_loader = DataLoader(Reviews(x_test, y_test, tokenizer, args.max_len), batch_size=64)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_steps = len(train_loader) * args.epochs
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.lr,
                                                    total_steps=total_steps, pct_start=0.1)
    started = time.perf_counter()
    history = []
    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        for step, batch in enumerate(train_loader, start=1):
            optimizer.zero_grad()
            output = model(**batch)
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running += output.loss.item()
            if step % 100 == 0:
                print(f"epoch {epoch + 1} step {step}/{len(train_loader)} "
                      f"loss {running / step:.4f} ({time.perf_counter() - started:.0f}s)", flush=True)
        valid_probs = predict(model, valid_loader)
        valid_pred = np.array([LABELS[i] for i in valid_probs.argmax(axis=1)])
        accuracy = float((valid_pred == np.array(y_valid)).mean())
        history.append({"epoch": epoch + 1, "train_loss": round(running / len(train_loader), 4),
                        "valid_accuracy": round(accuracy, 4)})
        print(json.dumps(history[-1], ensure_ascii=False), flush=True)
    train_seconds = round(time.perf_counter() - started, 1)

    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    test_probs = predict(model, test_loader)
    test_pred = np.array([LABELS[i] for i in test_probs.argmax(axis=1)])
    y_test_arr = np.array(y_test)
    result = {
        "model": BASE_MODEL, "task": "sentiment-binary", "device": "cpu",
        "seed": args.seed, "epochs": args.epochs, "batch_size": args.batch_size,
        "max_len": args.max_len, "lr": args.lr,
        "train_size": len(x_train), "train_size_note": "전량이 아니라 층화 부분표본",
        "valid_size": len(x_valid), "test_size": len(x_test),
        "train_seconds": train_seconds, "history": history,
        "test": {
            "accuracy": round(float(accuracy_score(y_test_arr, test_pred)), 4),
            "macro_f1": round(float(f1_score(y_test_arr, test_pred, average="macro")), 4),
            "confusion_matrix": {"labels": LABELS,
                                 "rows_true_cols_pred": confusion_matrix(
                                     y_test_arr, test_pred, labels=LABELS).tolist()},
            "per_label": classification_report(y_test_arr, test_pred, labels=LABELS,
                                               output_dict=True, zero_division=0),
            **bootstrap_ci(y_test_arr, test_pred, n=2000, seed=args.seed),
            "coverage_by_threshold": coverage_table(test_probs, y_test_arr, test_pred),
        },
    }
    out = artifact_dir("sentiment_ko", "koelectra")
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["test"], ensure_ascii=False, indent=2)[:1500], flush=True)
    print(f"\n산출물: {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
