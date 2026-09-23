# -*- coding: utf-8 -*-
"""`intent`·`issue_code` 분류기 학습(GPU) — 교사(Gemma) 라벨을 학생 인코더로 증류한다.

    python train_labels_gpu.py --real labeled_real_v2.jsonl --synthetic synth_labeled.jsonl \
        --gold travel_intent_eval.jsonl --out-dir ... --models tfidf skt/A.X-Encoder-base

★**점수 이름을 바로 붙인다.** 시험 조각의 라벨은 교사가 붙였다. 그래서 여기 점수는
  「**교사 일치도**」다. 사람 정답과의 일치도가 아니다. 사람(작업 세션) 라벨과의
  비교는 `gold` 조각이 따로 잰다 — 51건이라 방향만 본다.

★**시험 조각은 실제 글로만 만든다.** 합성 글은 학습에만 넣는다. 교사가 쓴 글을 교사가
  가린 라벨로 시험하면 점수가 부풀려진다.

★**합성은 일관성 거름을 지난 것만 쓴다** — 쓰라고 한 라벨과 눈가림 재분류 라벨이
  같을 때만. 몇 건을 걸렀는지 결과에 남긴다.

★**조각에 한 건뿐인 라벨은 층화 분할에서 학습으로 보낸다.** 시험에만 있는 라벨은
  배운 적이 없어 점수를 깎기만 하고, 학습에만 있으면 시험에서 안 보일 뿐이다. 둘 다
  결과의 `label_counts` 에 남긴다.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score

FIELDS = ("intent", "issue_code")



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


def read_jsonl(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def filter_synthetic(rows: list[dict]) -> tuple[list[dict], dict]:
    kept, dropped = [], Counter()
    for row in rows:
        if row.get("intent") == row.get("intended_intent") and \
                row.get("issue_code") == row.get("intended_issue_code"):
            kept.append(row)
        else:
            dropped[f"{row.get('intended_intent')}/{row.get('intended_issue_code')}"] += 1
    return kept, {"input": len(rows), "kept": len(kept), "dropped": sum(dropped.values()),
                  "dropped_by_intended_pair": dict(dropped.most_common())}


def split_real(rows: list[dict], field: str, seed: int) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_label[row[field]].append(row)
    train, valid, test = [], [], []
    for label, items in sorted(by_label.items()):
        rng.shuffle(items)
        if len(items) < 3:
            train += items
            continue
        n = max(1, len(items) // 10)
        valid += items[:n]
        test += items[n:2 * n]
        train += items[2 * n:]
    for part in (train, valid, test):
        rng.shuffle(part)
    return train, valid, test


def bootstrap_ci(y_true, y_pred, n, seed):
    rng = np.random.default_rng(seed)
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    accs, f1s = [], []
    for _ in range(n):
        idx = rng.integers(0, len(y_true), len(y_true))
        accs.append(accuracy_score(y_true[idx], y_pred[idx]))
        f1s.append(f1_score(y_true[idx], y_pred[idx], average="macro", zero_division=0))
    return {"accuracy_ci95": [round(float(np.percentile(accs, 2.5)), 4), round(float(np.percentile(accs, 97.5)), 4)],
            "macro_f1_ci95": [round(float(np.percentile(f1s, 2.5)), 4), round(float(np.percentile(f1s, 97.5)), 4)],
            "bootstrap_n": n}


def scores(y_true, y_pred, labels, n_boot, seed):
    result = {
        "n": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)), 4),
        "per_label": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
    }
    if n_boot and len(y_true) >= 30:
        result.update(bootstrap_ci(y_true, y_pred, n_boot, seed))
    return result


# ── TF-IDF 기준선 ────────────────────────────────────────────
def run_tfidf(train, valid, test, gold, field, labels, args):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    model = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2, sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(C=8.0, max_iter=3000, class_weight="balanced")),
    ])
    started = time.perf_counter()
    model.fit([r["text"] for r in train], [r[field] for r in train])
    seconds = round(time.perf_counter() - started, 1)
    predict = lambda rows: list(model.predict([r["text"] for r in rows])) if rows else []  # noqa: E731
    return model, seconds, predict(valid), predict(test), predict(gold), None


# ── 인코더 파인튜닝 ─────────────────────────────────────────
def run_encoder(model_id, train, valid, test, gold, field, labels, args):
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(args.seed)
    index = {label: i for i, label in enumerate(labels)}

    class Texts(Dataset):
        def __init__(self, rows, tokenizer):
            self.enc = tokenizer([r["text"] for r in rows], truncation=True, max_length=args.max_len,
                                 padding="max_length", return_tensors="pt")
            self.y = torch.tensor([index[r[field]] for r in rows]) if rows and field in rows[0] else None

        def __len__(self):
            return self.enc["input_ids"].shape[0]

        def __getitem__(self, i):
            item = {k: v[i] for k, v in self.enc.items()}
            if self.y is not None:
                item["labels"] = self.y[i]
            return item

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id, num_labels=len(labels), id2label=dict(enumerate(labels)), label2id=index).to(device)
    if tokenizer.pad_token is None:                   # ★디코더 계열 백본(Qwen3 등)
        tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.pad_token_id
    params_million = sum(p.numel() for p in model.parameters()) / 1e6
    batch_size = args.batch_size if params_million <= 400 else min(args.batch_size, 16)

    # ★라벨이 크게 기운다(환불·취소가 대부분) — 손실에 가중을 준다.
    #   ☆2026-09-17 우선판: 빈도 역수(상한 20)를 줬더니 문제 코드 모델이 다수 라벨을 버리고 소수 라벨만
    #     찍었다(booking_cancel_request 재현율 0.26, 검증 정확도 0.33). 방식과 상한을 옵션으로 둔다.
    counts = Counter(r[field] for r in train)
    base = [len(train) / (len(labels) * max(1, counts.get(l, 0))) for l in labels]
    if args.class_weight == "sqrt":
        base = [w ** 0.5 for w in base]
    elif args.class_weight == "none":
        base = [1.0 for _ in base]
    weights = torch.clamp(torch.tensor(base, dtype=torch.float32, device=device), max=args.weight_cap)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)

    loader = DataLoader(Texts(train, tokenizer), batch_size=batch_size, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total = len(loader) * args.epochs
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.lr, total_steps=total, pct_start=0.1)

    @torch.no_grad()
    def predict(rows):
        if not rows:
            return []
        model.eval()
        out = []
        for batch in DataLoader(Texts([{"text": r["text"]} for r in rows], tokenizer), batch_size=128):
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=(device == "cuda")):
                logits = model(**batch).logits
            out += [labels[i] for i in logits.float().argmax(dim=-1).tolist()]
        return out

    started = time.perf_counter()
    history = []
    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            y = batch.pop("labels")
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=(device == "cuda")):
                logits = model(**batch).logits
            loss = loss_fn(logits.float(), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running += loss.item()
        valid_pred = predict(valid)
        history.append({"epoch": epoch + 1, "train_loss": round(running / len(loader), 4),
                        "valid_accuracy": round(float(accuracy_score([r[field] for r in valid], valid_pred)), 4)})
        print(f"[{model_id}/{field}] {history[-1]}", flush=True)
    seconds = round(time.perf_counter() - started, 1)
    if device == "cuda":
        torch.cuda.synchronize()
    speed_started = time.perf_counter()
    test_pred = predict(test)
    if device == "cuda":
        torch.cuda.synchronize()
    speed = {"sentences": len(test), "seconds": round(time.perf_counter() - speed_started, 3),
             "params_million": round(params_million, 1), "batch_size": batch_size}
    speed["sentences_per_second"] = round(len(test) / max(1e-9, speed["seconds"]), 1)
    history.append({"inference": speed})
    return (model, tokenizer), seconds, predict(valid), test_pred, predict(gold), history


def main():
    parser = argparse.ArgumentParser(description="intent·issue_code 학습")
    parser.add_argument("--real", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, default=None)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["tfidf", "skt/A.X-Encoder-base"])
    parser.add_argument("--fields", nargs="+", default=list(FIELDS))
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-len", type=int, default=96)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--class-weight", choices=("inverse", "sqrt", "none"), default="inverse")
    parser.add_argument("--weight-cap", type=float, default=20.0)
    parser.add_argument("--save-weights", action="store_true")
    parser.add_argument("--save-models", nargs="*", default=None,
                        help="이 모델만 가중치를 저장한다(디스크). 없으면 모두")
    args = parser.parse_args()
    _gpu_limit_gb = limit_gpu_memory()
    # ★실행 중인 순서 스크립트를 고치지 않고 설정을 바꾸는 자리 — 바꾼 값은 결과에 남긴다.
    overrides_path = Path(__file__).with_name("label_train_overrides.json")
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    for key, value in overrides.items():
        if key.startswith("_"):
            continue
        setattr(args, key, value)
    if overrides:
        print("설정 덮어쓰기:", overrides, flush=True)

    real = read_jsonl(args.real)
    synthetic_raw = read_jsonl(args.synthetic)
    synthetic, synthetic_stats = filter_synthetic(synthetic_raw)
    gold = read_jsonl(args.gold)
    print(f"실제 {len(real)} · 합성 {synthetic_stats} · 기준 조각 {len(gold)}", flush=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for field in args.fields:
        train_real, valid, test = split_real(real, field, args.seed)
        train = train_real + synthetic
        labels = sorted({r[field] for r in train + valid + test} |
                        {r[field] for r in gold if field in r})
        label_counts = {
            "train_real": dict(Counter(r[field] for r in train_real)),
            "train_synthetic": dict(Counter(r[field] for r in synthetic)),
            "valid": dict(Counter(r[field] for r in valid)),
            "test": dict(Counter(r[field] for r in test)),
            "gold": dict(Counter(r[field] for r in gold)),
            "never_in_train": sorted(set(labels) - {r[field] for r in train}),
        }
        for model_id in args.models:
            print(f"\n=== {field} · {model_id} ===", flush=True)
            try:
                if model_id == "tfidf":
                    trained, seconds, pv, pt, pg, history = run_tfidf(train, valid, test, gold, field, labels, args)
                else:
                    trained, seconds, pv, pt, pg, history = run_encoder(model_id, train, valid, test, gold,
                                                                        field, labels, args)
            except Exception as exc:                          # ★실패도 줄에 남긴다
                print(f"실패: {type(exc).__name__}: {exc}", flush=True)
                summary.append({"field": field, "model": model_id, "failed": f"{type(exc).__name__}: {exc}"[:300]})
                continue
            result = {
                "field": field, "model": model_id, "seed": args.seed, "epochs": args.epochs, "lr": args.lr,
                "class_weight": args.class_weight, "weight_cap": args.weight_cap, "overrides": overrides,
                "train_size": len(train), "train_real": len(train_real), "train_synthetic": len(synthetic),
                "synthetic_filter": synthetic_stats, "train_seconds": seconds, "history": history,
                "labels": labels, "label_counts": label_counts,
                # ★선정은 검증 조각으로 한다 — 시험 조각은 선정이 끝난 뒤 보고만 한다(코덱스 검수 2026-09-17 치명 1).
                "teacher_agreement_valid": scores([r[field] for r in valid], pv, labels, args.bootstrap, args.seed),
                "teacher_agreement_test": scores([r[field] for r in test], pt, labels, args.bootstrap, args.seed),
                "gold_author_labels": {
                    **scores([r[field] for r in gold], pg, labels, 0, args.seed),
                    "note": "작업 세션이 붙인 라벨 51건 · 사람 검수 없음 — 방향만 본다",
                    "predictions": [{"text": r["text"], "gold": r[field], "pred": p} for r, p in zip(gold, pg)],
                },
            }
            name = f"{field}__{model_id.replace('/', '__')}"
            out = args.out_dir / name
            out.mkdir(parents=True, exist_ok=True)
            (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            if args.save_weights and (not args.save_models or model_id in args.save_models):
                if model_id == "tfidf":
                    import joblib
                    joblib.dump(trained, out / "model.joblib")
                else:
                    trained[0].save_pretrained(out)
                    trained[1].save_pretrained(out)
            row = {"field": field, "model": model_id, "train_seconds": seconds,
                   "teacher_acc": result["teacher_agreement_test"]["accuracy"],
                   "teacher_macro_f1": result["teacher_agreement_test"]["macro_f1"],
                   "teacher_acc_ci95": result["teacher_agreement_test"].get("accuracy_ci95"),
                   "gold_acc": result["gold_author_labels"]["accuracy"],
                   "gold_macro_f1": result["gold_author_labels"]["macro_f1"]}
            summary.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            del trained
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass

    (args.out_dir / "comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 비교 ===\n" + json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
