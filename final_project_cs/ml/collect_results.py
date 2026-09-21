# -*- coding: utf-8 -*-
"""학습 결과를 표로 모은다 — 리포트 작성자가 그대로 인용할 수 있게.

    python -m ml.collect_results

★**지표는 지어내지 않는다.** `metrics.json`·`cpu_eval.json` 에 있는 값만 옮긴다.
  없으면 「—」로 두고, 왜 없는지는 표 아래 주석에 적는다.
★**실패한 모델도 줄에 남긴다**(`comparison.json` 의 `failed`). 빠뜨리면 분모가 줄어
  비교가 실제보다 좋아 보인다.
★**점수의 이름을 표에 적는다.** 감정의 「리뷰 정확도」는 사람 라벨(별점) 기준이고,
  intent·issue_code 의 「교사 일치도」는 Gemma 라벨 기준이다. 섞어 읽으면 안 된다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import artifact_dir                      # noqa: E402


def _load(path: Path) -> dict | list | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, list):
        return f"[{value[0]}, {value[1]}]" if len(value) == 2 else str(value)
    return str(value)


def _table(headers: list[str], rows: list[dict]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines += ["| " + " | ".join(_fmt(row.get(h)) for h in headers) + " |" for row in rows]
    return "\n".join(lines)


def sentiment_rows() -> list[dict]:
    root = artifact_dir("sentiment_ko")
    rows = []
    baseline = _load(root / "baseline" / "metrics.json")
    if baseline:
        rows.append({"모델": "TF-IDF + 로지스틱 회귀", "크기": "—", "학습 장치": "CPU",
                     "학습 초": baseline.get("train_seconds"),
                     "리뷰 정확도": baseline["test"]["accuracy"],
                     "95% 신뢰구간": baseline["test"].get("accuracy_ci95"),
                     "GPU 추론 문장/초": None, "여행 3분류 최고 F1(임계값)": None,
                     "CPU 한 문장 p50 ms": None})
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        metrics = _load(directory / "metrics.json")
        if not metrics or "review_test" not in metrics:
            continue
        travel = metrics.get("travel_eval", {}).get("by_threshold") or []
        best = max(travel, key=lambda r: r["macro_f1_3class"]) if travel else None
        cpu = _load(directory / "cpu_eval.json") or {}
        rows.append({
            "모델": metrics["model"], "크기": f"{metrics.get('params_million')}M",
            "학습 장치": (metrics.get("inference") or {}).get("gpu") or metrics.get("device"),
            "학습 초": metrics.get("train_seconds"),
            "리뷰 정확도": metrics["review_test"]["accuracy"],
            "95% 신뢰구간": metrics["review_test"].get("accuracy_ci95"),
            "GPU 추론 문장/초": (metrics.get("inference") or {}).get("sentences_per_second"),
            "여행 3분류 최고 F1(임계값)": f"{best['macro_f1_3class']} ({best['threshold']})" if best else None,
            "CPU 한 문장 p50 ms": (cpu.get("latency_single_ms") or {}).get("p50"),
        })
    return rows


def intent_rows() -> list[dict]:
    root = artifact_dir("intent_ko")
    rows = []
    for run in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in ("data",)):
        for directory in sorted(p for p in run.iterdir() if p.is_dir()):
            metrics = _load(directory / "metrics.json")
            if not metrics or "teacher_agreement_test" not in metrics:
                continue
            speed = next((h["inference"] for h in (metrics.get("history") or []) if "inference" in h), {})
            teacher, gold = metrics["teacher_agreement_test"], metrics["gold_author_labels"]
            rows.append({
                "실행": run.name, "축": metrics["field"], "모델": metrics["model"],
                "학습(실제+합성)": f"{metrics.get('train_real')}+{metrics.get('train_synthetic')}",
                "교사 일치도": teacher["accuracy"], "교사 macro F1": teacher["macro_f1"],
                "95% 신뢰구간": teacher.get("accuracy_ci95"),
                "작업세션 라벨 51건 정확도": gold["accuracy"],
                "GPU 추론 문장/초": speed.get("sentences_per_second"),
                "학습 초": metrics.get("train_seconds"),
            })
        comparison = _load(run / "comparison.json") or []
        for item in comparison if isinstance(comparison, list) else []:
            if item.get("failed"):
                rows.append({"실행": run.name, "축": item.get("field"), "모델": item.get("model"),
                             "교사 일치도": f"실패: {item['failed'][:60]}"})
    return rows


def main() -> int:
    parts = []
    s_rows = sentiment_rows()
    if s_rows:
        parts.append("## 감정 (긍정·부정 → 제품 3분류)\n\n" + _table(
            ["모델", "크기", "학습 장치", "학습 초", "리뷰 정확도", "95% 신뢰구간", "GPU 추론 문장/초",
             "여행 3분류 최고 F1(임계값)", "CPU 한 문장 p50 ms"], s_rows) +
            "\n\n- 리뷰 정확도: 네이버쇼핑 리뷰 시험 조각 19,988건, 별점 라벨 기준\n"
            "- 여행 3분류: 작업 세션 라벨 41건 — 방향만 본다\n")
    i_rows = intent_rows()
    if i_rows:
        parts.append("## intent · issue_code\n\n" + _table(
            ["실행", "축", "모델", "학습(실제+합성)", "교사 일치도", "교사 macro F1", "95% 신뢰구간",
             "작업세션 라벨 51건 정확도", "GPU 추론 문장/초", "학습 초"], i_rows) +
            "\n\n- 교사 일치도: 시험 조각(실제 상담 제목)의 라벨을 Gemma 가 붙였다 — 사람 정답과의 일치도가 아니다\n"
            "- 작업세션 라벨 51건: 사람 검수 없음 — 방향만 본다\n")
    if not parts:
        print("모은 결과가 없다", file=sys.stderr)
        return 1
    text = "\n".join(parts)
    out = artifact_dir() / "results_table.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n산출물: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
