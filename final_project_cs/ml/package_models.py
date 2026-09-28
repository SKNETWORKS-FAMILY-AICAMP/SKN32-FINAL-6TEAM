# -*- coding: utf-8 -*-
"""제출용 모델 폴더를 만든다 — 과제별 하위 폴더 + README + SHA-256 목록.

    python -m ml.package_models --sentiment <폴더> --intent <폴더> --issue-code <폴더> \
        --baseline <감정 기준선 폴더> --out <출력 폴더>

★**받는 사람이 이 폴더만으로 쓸 수 있게** 만든다 — 로딩 코드, 라벨 목록, 지표, 파일 해시를
  README 에 같이 적는다. 파일이 전송 중에 깨졌는지는 SHA-256 으로 확인한다.
★**복사만 한다.** 원본 학습 산출물은 옮기거나 지우지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

KEEP = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
        "vocab.txt", "spm.model", "tokenizer.model", "added_tokens.json", "metrics.json", "model.joblib")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_model(src: Path, dst: Path) -> list[dict]:
    if not src.exists():
        raise SystemExit(f"[멈춤] 원본이 없다: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in KEEP:
        if (src / name).exists():
            shutil.copy2(src / name, dst / name)
            rows.append({"file": f"{dst.name}/{name}", "bytes": (dst / name).stat().st_size, "sha256": sha256(dst / name)})
    if not any(r["file"].endswith(("model.safetensors", "model.joblib")) for r in rows):
        raise SystemExit(f"[멈춤] 가중치 파일이 없다: {src}")
    return rows


def summary(metrics: dict) -> str:
    if "review_test" in metrics:
        t = metrics["review_test"]
        return f"리뷰 시험 {metrics['test_size']:,}건 정확도 {t['accuracy']:.4f} (95% 신뢰구간 {t['accuracy_ci95']})"
    if "teacher_agreement_test" in metrics:
        t = metrics["teacher_agreement_test"]
        return f"사건제목 시험 {t['n']:,}건 교사(Gemma) 일치도 {t['accuracy']:.4f}, macro F1 {t['macro_f1']:.4f} — 사람 정답 아님"
    if "test" in metrics:
        return f"리뷰 시험 정확도 {metrics['test']['accuracy']:.4f} (95% 신뢰구간 {metrics['test'].get('accuracy_ci95')})"
    return "[미확보]"


def main() -> int:
    parser = argparse.ArgumentParser(description="제출용 모델 폴더 만들기")
    parser.add_argument("--sentiment", type=Path, required=True)
    parser.add_argument("--intent", type=Path, required=True)
    parser.add_argument("--issue-code", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sentiment-threshold", type=float, required=True, help="여행 문장 조각에서 고른 감정 임계값")
    args = parser.parse_args()

    if args.out.exists():
        raise SystemExit(f"[멈춤] 출력 폴더가 이미 있다(덮어쓰지 않는다): {args.out}")
    parts = (("sentiment", args.sentiment, "감정(긍정·부정, 확신이 낮으면 중립)"),
             ("intent", args.intent, "요청 종류 5종"),
             ("issue_code", args.issue_code, "문제 코드 17종"),
             ("tfidf_baseline", args.baseline, "감정 기준선(TF-IDF + 로지스틱 회귀)"))
    files, lines = [], []
    for name, src, task in parts:
        files += copy_model(src, args.out / name)
        metrics = json.loads((src / "metrics.json").read_text(encoding="utf-8")) if (src / "metrics.json").exists() else {}
        cfg = json.loads((src / "config.json").read_text(encoding="utf-8")) if (src / "config.json").exists() else {}
        labels = list((cfg.get("id2label") or {}).values())
        lines.append(f"| `{name}/` | {task} | {metrics.get('model', 'TF-IDF')} | {', '.join(labels) if labels else '-'} | {summary(metrics)} |")

    readme = [
        "# 학습한 ML/DL 모델 — triPilot 인라인 분류(여행)",
        "",
        "6팀 데이터 전처리 단계 산출물 「학습한 ML/DL 모델」의 모델 파일이다. 문서의 수치는 각 폴더 `metrics.json` 에서 나왔다.",
        "",
        "| 폴더 | 과제 | 기반 모델 | 라벨 | 시험 결과 |",
        "|---|---|---|---|---|",
        *lines,
        "",
        "## 불러 쓰기",
        "",
        "```python",
        "from transformers import AutoModelForSequenceClassification, AutoTokenizer",
        "import torch",
        "",
        "path = \"sentiment\"   # intent, issue_code 도 같은 방식",
        "tokenizer = AutoTokenizer.from_pretrained(path)",
        "model = AutoModelForSequenceClassification.from_pretrained(path).eval()",
        "with torch.no_grad():",
        "    logits = model(**tokenizer(\"저녁 식당이 오늘 임시휴무래요\", truncation=True, max_length=96, return_tensors=\"pt\")).logits[0]",
        "probs = torch.softmax(logits, -1)",
        "print(model.config.id2label[int(probs.argmax())], float(probs.max()))",
        "```",
        "",
        "제품 안에서는 `app/infrastructure/ml/` 의 `LocalLabelModel`·`LocalSentiment`·`LocalCaseLabels`(확신이 낮으면 LLM 위임)로 부른다.",
        "기준선은 `joblib.load(\"tfidf_baseline/model.joblib\").predict_proba([문장])` 으로 부른다.",
        "",
        "## 주의",
        "",
        "- 요청 종류·문제 코드 점수는 교사 모델(Gemma 4 12B) 라벨과의 일치도다. 사람 정답과의 일치도가 아니다.",
        f"- 감정 모델은 쇼핑 리뷰로 학습했다. 여행 문장에서는 확신 임계값({args.sentiment_threshold} 권장, 여행 문장 41건 기준)으로 중립을 판단한다.",
        "- 입력은 개인정보를 마스킹한 뒤 넣는다(학습 데이터도 같은 규칙으로 마스킹했다).",
        "",
        "## 파일 무결성(SHA-256)",
        "",
        "| 파일 | 크기(byte) | SHA-256 |",
        "|---|---:|---|",
        *[f"| `{r['file']}` | {r['bytes']:,} | `{r['sha256']}` |" for r in files],
        "",
    ]
    (args.out / "README.md").write_text("\n".join(readme), encoding="utf-8")
    (args.out / "SHA256SUMS.txt").write_text("".join(f"{r['sha256']}  {r['file']}\n" for r in files), encoding="utf-8")
    total = sum(r["bytes"] for r in files)
    print(f"완료: {args.out} · 파일 {len(files)}개 · {total / 1024 / 1024:,.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
