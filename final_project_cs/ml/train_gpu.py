# -*- coding: utf-8 -*-
"""여러 모델을 **같은 조건**으로 학습해 비교한다(GPU).

    python ml/train_gpu.py --models skt/A.X-Encoder-base klue/roberta-large ...

★**같은 조각·같은 지표·같은 씨앗**으로 잰다. 조건이 다르면 비교가 아니다
  (`CLAUDE.md` §6 — A/B 비교는 조건을 고정한다).
★**여행 조각도 같이 잰다.** 학습은 쇼핑 리뷰로 하고 제품은 여행 글을 받는다.
  그 차이를 숫자로 남긴다 — 리뷰 점수만 적으면 제품 성능을 과장하게 된다.
★**중립은 지어내지 않는다.** 학습 라벨은 둘뿐이라, 확신이 임계값 아래면 중립으로
  물러선다. 임계값을 훑어 커버리지와 정확도를 같이 적는다.
★**실패한 모델도 목록에 남긴다.** 조용히 빠지면 분모가 줄어 비교가 좋아 보인다.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

LABELS = ["negative", "positive"]



def limit_gpu_memory():
    """★빌려 쓰는 GPU다 — 이 프로세스가 쓸 메모리 상한을 건다(`ACOP_GPU_MEM_GB`, 기본 7GB).

    상한을 넘기면 조용히 느려지지 않고 메모리 부족 오류로 멈춘다 — 그 모델은 실패로
    기록되고 다음 모델로 넘어간다.
    """
    import os
    import torch
    if not torch.cuda.is_available():
        return None
    limit_gb = float(os.environ.get("ACOP_GPU_MEM_GB", "7"))
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    fraction = min(1.0, limit_gb / total_gb)
    torch.cuda.set_per_process_memory_fraction(fraction, 0)
    torch.set_num_threads(int(os.environ.get("ACOP_CPU_THREADS", "4")))
    print("GPU 메모리 상한 %.1fGB / 전체 %.1fGB · CPU 스레드 %d" % (limit_gb, total_gb, torch.get_num_threads()), flush=True)
    return limit_gb


def load_jsonl(path):
    texts, labels = [], []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def stratified_head(texts, labels, size):
    """★앞에서 자르지 않는다 — 라벨 비율을 지켜 고른다."""
    if size is None or size >= len(texts):
        return texts, labels
    per_label = size // len(LABELS)
    picked_texts, picked_labels = [], []
    for label in LABELS:
        idx = [i for i, value in enumerate(labels) if value == label][:per_label]
        picked_texts += [texts[i] for i in idx]
        picked_labels += [labels[i] for i in idx]
    return picked_texts, picked_labels


class Texts(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.encodings = tokenizer(texts, truncation=True, max_length=max_len,
                                   padding="max_length", return_tensors="pt")
        self.labels = None if labels is None else torch.tensor(
            [LABELS.index(label) for label in labels])

    def __len__(self):
        return self.encodings["input_ids"].shape[0]

    def __getitem__(self, idx):
        item = {key: value[idx] for key, value in self.encodings.items()}
        if self.labels is not None:
            item["labels"] = self.labels[idx]
        return item


@torch.no_grad()
def predict_probs(model, loader, device):
    model.eval()
    chunks = []
    for batch in loader:
        batch.pop("labels", None)
        batch = {key: value.to(device) for key, value in batch.items()}
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16,
                            enabled=(device == "cuda")):
            logits = model(**batch).logits
        chunks.append(torch.softmax(logits.float(), dim=-1).cpu().numpy())
    return np.concatenate(chunks)


def bootstrap_ci(y_true, y_pred, n, seed):
    """★점수 하나만 적지 않는다 — 다시 뽑아도 그 근처인지 본다."""
    rng = np.random.default_rng(seed)
    accs, f1s = [], []
    size = len(y_true)
    for _ in range(n):
        idx = rng.integers(0, size, size)
        accs.append(accuracy_score(y_true[idx], y_pred[idx]))
        f1s.append(f1_score(y_true[idx], y_pred[idx], average="macro"))
    return {"accuracy_ci95": [round(float(np.percentile(accs, 2.5)), 4),
                              round(float(np.percentile(accs, 97.5)), 4)],
            "macro_f1_ci95": [round(float(np.percentile(f1s, 2.5)), 4),
                              round(float(np.percentile(f1s, 97.5)), 4)],
            "bootstrap_n": n}


def coverage_table(probs, y_true, y_pred):
    """★임계값을 올리면 얼마나 답하고 그때 얼마나 맞나."""
    confidence = probs.max(axis=1)
    rows = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        mask = confidence >= threshold
        answered = int(mask.sum())
        rows.append({"threshold": threshold, "answered": answered,
                     "coverage": round(answered / len(y_true), 4),
                     "accuracy_on_answered":
                         round(float(accuracy_score(y_true[mask], y_pred[mask])), 4)
                         if answered else None})
    return rows


def travel_scores(probs, gold):
    """여행 조각 — 3분류(중립 포함). 임계값 아래는 중립으로 물러선 것이다."""
    confidence = probs.max(axis=1)
    predicted = np.array([LABELS[i] for i in probs.argmax(axis=1)])
    gold_arr = np.array(gold)
    polar = gold_arr != "neutral"
    rows = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        final = np.where(confidence >= threshold, predicted, "neutral")
        rows.append({
            "threshold": threshold,
            "accuracy_3class": round(float((final == gold_arr).mean()), 4),
            "macro_f1_3class": round(float(f1_score(
                gold_arr, final, average="macro",
                labels=["negative", "neutral", "positive"], zero_division=0)), 4),
            "abstain_rate": round(float((final == "neutral").mean()), 4),
            "accuracy_on_polar": round(float((final[polar] == gold_arr[polar]).mean()), 4),
        })
    return rows


def run_one(model_id, args, data, device):
    x_train, y_train, x_valid, y_valid, x_test, y_test, travel = data
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id, num_labels=len(LABELS),
        id2label={i: label for i, label in enumerate(LABELS)},
        label2id={label: i for i, label in enumerate(LABELS)}).to(device)
    # ★디코더 계열 백본(Qwen3 등)은 패딩 토큰이 없다 — 분류 머리가 마지막 토큰을 못 찾는다.
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.pad_token_id
    load_seconds = round(time.perf_counter() - started, 1)
    params_million = sum(p.numel() for p in model.parameters()) / 1e6
    # ★큰 백본은 12GB 에 안 들어간다 — 배치를 줄인다(줄였다는 사실을 결과에 남긴다).
    batch_size = args.batch_size if params_million <= 400 else min(args.batch_size, 16)

    train_loader = DataLoader(Texts(x_train, y_train, tokenizer, args.max_len),
                              batch_size=batch_size, shuffle=True, num_workers=0)
    valid_loader = DataLoader(Texts(x_valid, y_valid, tokenizer, args.max_len),
                              batch_size=args.eval_batch_size, num_workers=0)
    test_loader = DataLoader(Texts(x_test, y_test, tokenizer, args.max_len),
                             batch_size=args.eval_batch_size, num_workers=0)
    travel_loader = DataLoader(Texts(travel[0], None, tokenizer, args.max_len),
                               batch_size=args.eval_batch_size, num_workers=0)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=args.lr, total_steps=total_steps, pct_start=0.1)
    history = []
    train_started = time.perf_counter()
    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        for step, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16,
                                enabled=(device == "cuda")):
                output = model(**batch)
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running += output.loss.item()
            if step % 200 == 0:
                print("[%s] epoch %d step %d/%d loss %.4f (%.0fs)"
                      % (model_id, epoch + 1, step, len(train_loader), running / step,
                         time.perf_counter() - train_started), flush=True)
        valid_probs = predict_probs(model, valid_loader, device)
        valid_pred = np.array([LABELS[i] for i in valid_probs.argmax(axis=1)])
        history.append({"epoch": epoch + 1,
                        "train_loss": round(running / len(train_loader), 4),
                        "valid_accuracy": round(float((valid_pred == np.array(y_valid)).mean()), 4)})
        print("[%s] %s" % (model_id, json.dumps(history[-1], ensure_ascii=False)), flush=True)
    train_seconds = round(time.perf_counter() - train_started, 1)

    if device == "cuda":
        torch.cuda.synchronize()
    speed_started = time.perf_counter()
    test_probs = predict_probs(model, test_loader, device)
    if device == "cuda":
        torch.cuda.synchronize()
    test_seconds = time.perf_counter() - speed_started
    test_pred = np.array([LABELS[i] for i in test_probs.argmax(axis=1)])
    y_test_arr = np.array(y_test)
    inference_started = time.perf_counter()
    travel_probs = predict_probs(model, travel_loader, device)
    travel_seconds = round(time.perf_counter() - inference_started, 3)

    review = {
        "accuracy": round(float(accuracy_score(y_test_arr, test_pred)), 4),
        "macro_f1": round(float(f1_score(y_test_arr, test_pred, average="macro")), 4),
        "confusion_matrix": {"labels": LABELS,
                             "rows_true_cols_pred":
                                 confusion_matrix(y_test_arr, test_pred, labels=LABELS).tolist()},
        "per_label": classification_report(y_test_arr, test_pred, labels=LABELS,
                                           output_dict=True, zero_division=0),
        "coverage_by_threshold": coverage_table(test_probs, y_test_arr, test_pred),
    }
    review.update(bootstrap_ci(y_test_arr, test_pred, args.bootstrap, args.seed))
    result = {
        "model": model_id,
        "params_million": round(sum(p.numel() for p in model.parameters()) / 1e6, 1),
        "device": device, "seed": args.seed, "epochs": args.epochs,
        "batch_size": batch_size, "max_len": args.max_len, "lr": args.lr,
        "inference": {"test_sentences": len(x_test), "seconds": round(test_seconds, 2),
                      "sentences_per_second": round(len(x_test) / test_seconds, 1),
                      "eval_batch_size": args.eval_batch_size, "dtype": "bfloat16 autocast",
                      "gpu": torch.cuda.get_device_name(0) if device == "cuda" else "cpu"},
        "train_size": len(x_train), "valid_size": len(x_valid), "test_size": len(x_test),
        "load_seconds": load_seconds, "train_seconds": train_seconds, "history": history,
        "review_test": review,
        "travel_eval": {
            "n": len(travel[1]),
            "note": "소표본 41건 · 라벨은 작업 세션이 붙였고 사람 검수 안 받았다 — 방향만 본다",
            "by_threshold": travel_scores(travel_probs, travel[1]),
            "seconds_for_all": travel_seconds,
        },
    }
    out = Path(args.out_dir) / model_id.replace("/", "__")
    out.mkdir(parents=True, exist_ok=True)
    if args.save_weights and (not args.save_models or model_id in args.save_models):
        model.save_pretrained(out)
        tokenizer.save_pretrained(out)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def main():
    parser = argparse.ArgumentParser(description="여러 모델 비교 학습(GPU)")
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--travel-eval", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--train-size", type=int, default=None, help="없으면 전량")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--eval-batch-size", type=int, default=128)
    parser.add_argument("--max-len", type=int, default=96)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--save-weights", action="store_true")
    parser.add_argument("--save-models", nargs="*", default=None,
                        help="이 모델만 가중치를 저장한다(디스크). 없으면 모두")
    args = parser.parse_args()
    _gpu_limit_gb = limit_gpu_memory()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("장치: %s" % device, flush=True)

    x_train, y_train = stratified_head(*load_jsonl(args.data_dir / "train.jsonl"), args.train_size)
    x_valid, y_valid = load_jsonl(args.data_dir / "valid.jsonl")
    x_test, y_test = load_jsonl(args.data_dir / "test.jsonl")
    travel_texts, travel_labels = load_jsonl(args.travel_eval)
    data = (x_train, y_train, x_valid, y_valid, x_test, y_test, (travel_texts, travel_labels))

    summary = []
    for model_id in args.models:
        print("\n=== %s ===" % model_id, flush=True)
        try:
            result = run_one(model_id, args, data, device)
        except Exception as exc:
            print("[%s] 실패: %s: %s" % (model_id, type(exc).__name__, exc), flush=True)
            summary.append({"model": model_id,
                            "failed": ("%s: %s" % (type(exc).__name__, exc))[:300]})
            continue
        summary.append({
            "model": model_id, "params_million": result["params_million"],
            "review_accuracy": result["review_test"]["accuracy"],
            "review_macro_f1": result["review_test"]["macro_f1"],
            "review_accuracy_ci95": result["review_test"]["accuracy_ci95"],
            "train_seconds": result["train_seconds"],
            "sentences_per_second": result["inference"]["sentences_per_second"],
            "travel_best": max(result["travel_eval"]["by_threshold"],
                               key=lambda row: row["macro_f1_3class"]),
        })
        print(json.dumps(summary[-1], ensure_ascii=False, indent=2), flush=True)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(
        json.dumps({"models": summary, "train_size": len(x_train), "test_size": len(x_test)},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 비교 ===", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
