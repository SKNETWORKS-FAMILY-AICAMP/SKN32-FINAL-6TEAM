# -*- coding: utf-8 -*-
"""4차 v2 — 요청 종류·문제 코드 학습 결과를 `datasets/ml/` 의 JSON 에서 읽는다.

3차·4차 빌드의 규칙을 그대로 따른다(같은 실험 번호·같은 선정). 감정(쇼핑 리뷰) 실험은 읽지 않는다.
★실험 번호는 3차 문서와 이어지도록 EXP-06 부터 붙인다(EXP-01~05 는 감정 실험이라 이 판에서 뺐다).
"""
from __future__ import annotations

import json
from pathlib import Path

LABEL_MODELS = (("tfidf", "TF-IDF"), ("skt/A.X-Encoder-base", "A.X-Encoder-base"), ("jhu-clsp/mmBERT-base", "mmBERT-base"),
                ("kakaobank/kf-deberta-base", "kf-deberta-base"), ("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B"))
FIRST_EXP = 6


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _valid(m):
    if (m or {}).get("teacher_agreement_valid"):
        return m["teacher_agreement_valid"]["accuracy"]
    hist = [h for h in (m or {}).get("history") or [] if "valid_accuracy" in h]
    return hist[-1]["valid_accuracy"] if hist else None


def load(ml: Path):
    """→ {"intent": [...], "issue_code": [...], "first_run": {...}, "counts": {...}}"""
    base = ml / "intent_ko"
    runs = []
    for key, label, required in (("p1_real_only", "실제 글", True), ("p1b_real_tuned", "실제 글·가중 조정", False),
                                 ("p3_full", "실제+합성·가중 조정", False), ("p4_qwen3", "실제+합성·가중 조정", False)):
        folder = base / key
        if not folder.exists():
            if required:
                raise SystemExit(f"[멈춤] 근거 폴더가 없다: {folder}")
            continue
        data = {sub.name: json.loads((sub / "metrics.json").read_text(encoding="utf-8"))
                for sub in folder.iterdir() if (sub / "metrics.json").exists()}
        failed = {(r.get("field"), r.get("model")): r["failed"] for r in (_read(folder / "comparison.json") or []) if r.get("failed")}
        runs.append((key, label, data, failed))
    # ★선정된 kf-deberta 는 가중치를 저장하려고 같은 설정으로 다시 학습했다 — 표에는 저장판 결과를 쓰고 첫 실행은 재실행 기록으로 둔다.
    saved = base / "p3_kf_saved"
    first_run = {}
    for key, _label, data, _failed in runs:
        if key != "p3_full":
            continue
        for field in ("intent", "issue_code"):
            name = f"{field}__kakaobank__kf-deberta-base"
            m = _read(saved / name / "metrics.json")
            if m and name in data:
                first_run[field] = data[name]
                data[name] = m
    out = {"first_run": first_run}
    for field in ("intent", "issue_code"):
        rows = []
        for key, label, data, failed in runs:
            for model_id, short in LABEL_MODELS:
                m = data.get(f"{field}__{model_id.replace('/', '__')}")
                fail = failed.get((field, model_id))
                if m is None and fail is None:
                    continue
                speed = next((h["inference"] for h in (m or {}).get("history") or [] if "inference" in h), {})
                t = (m or {}).get("teacher_agreement_test") or {}
                rows.append({"model": model_id, "short": short, "run": label, "run_key": key, "kind": "Baseline" if model_id == "tfidf" else "DL",
                             "metrics": m, "valid": _valid(m), "acc": t.get("accuracy"), "ci": t.get("accuracy_ci95"), "f1": t.get("macro_f1"),
                             "speed": speed.get("sentences_per_second"), "failed": fail,
                             "train": (m or {}).get("train_real"), "synthetic": (m or {}).get("train_synthetic"), "n_test": t.get("n")})
        out[field] = rows
    # 선정: 기준선을 포함한 후보 중 검증 조각 점수 최고, 같으면 기준선, 인코더끼리 같으면 GPU 추론이 빠른 쪽(시험 조각은 선정에 쓰지 않는다)
    for field in ("intent", "issue_code"):
        ok = [r for r in out[field] if r["valid"] is not None and not r["failed"]]
        top = max(r["valid"] for r in ok)
        tied = [r for r in ok if abs(r["valid"] - top) < 1e-12]
        pick = next((r for r in tied if r["kind"] == "Baseline"), None) or max(tied, key=lambda r: r["speed"] or 0)
        pick["picked"] = True
    # 실험 번호: 요청 종류 먼저, 그다음 문제 코드(3차와 같은 순서)
    n = FIRST_EXP - 1
    for field in ("intent", "issue_code"):
        for r in out[field]:
            n += 1
            r["exp"] = n
    return out


def f4(x):
    return f"{x:.4f}"


def ci(pair):
    return f"[{pair[0]:.4f}, {pair[1]:.4f}]"


def result_text(r):
    if r["failed"]:
        return f"실패: {str(r['failed'])[:80]}"
    parts = [f"검증 {f4(r['valid'])}" if r["valid"] is not None else "검증 기록 없음", f"시험 교사 일치도 {f4(r['acc'])} {ci(r['ci']) if r['ci'] else ''}".rstrip(), f"F1 {f4(r['f1'])}"]
    if r.get("speed"):
        parts.append(f"GPU 추론 {r['speed']:,.0f}문장/s")
    return ", ".join(parts)
