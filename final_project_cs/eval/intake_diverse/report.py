# -*- coding: utf-8 -*-
"""채점 결과 → 표(마크다운). 칸 이름은 사람이 읽는 말로 바꾼다."""
from __future__ import annotations

from statistics import median
from typing import Any

from .score import pct

LABELS = [
    ("items", "일정 항목 찾음(재현율)"), ("items_tight", "그중 조각이 장소 말과 거의 같음"), ("items_precision", "읽은 항목 중 맞는 것(정밀도)"), ("time", "시작 시각"), ("end", "끝 시각"),
    ("date", "날짜"), ("kind", "종류(식사·숙소·활동)"), ("place_found", "찾은 장소 이름"), ("tamper", "값 변조(낮을수록 좋음)"),
    ("moves", "이동 수단"), ("moves_precision", "읽은 이동 수단 중 맞는 것"), ("conditions", "조건"), ("preferences", "성향"),
    ("requests", "요청 종류(라벨별)"), ("requests_exact", "요청 종류 전부 맞음(건)"), ("missing", "고객만 아는 빠진 값"),
    ("trip", "인원·기간"), ("cases", "읽기 성공(건)")]
SHAPES = ["mixed_list", "typo_line", "paragraph", "csv", "json", "excel_memo", "pasted_table", "multi_message", "mixed_request",
          "correction", "real"]
SHAPE_KO = {"mixed_list": "정형 목록+자유 문장", "typo_line": "말투·오타 한 줄", "paragraph": "문단 자유문", "csv": "CSV·TSV",
            "json": "JSON", "excel_memo": "메모식 엑셀", "pasted_table": "붙여 넣은 표", "multi_message": "나눠 보낸 메시지",
            "mixed_request": "계획+질문+짜기", "correction": "중간 정정", "real": "실제 접수"}
SHAPE_COLS = ["items", "items_tight", "items_precision", "time", "date", "tamper", "moves", "conditions", "preferences", "requests_exact", "missing"]


def _q(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else 0.0


def render(result: dict[str, Any], cases: list[dict[str, Any]], preds: dict[str, dict[str, Any]]) -> str:
    t = result["totals"]
    lines = ["## 칸별 점수", "", "| 칸 | 전체 | 합성 | 실제 |", "|---|---|---|---|"]
    for key, label in LABELS:
        lines.append(f"| {label} | {pct(t['전체'].get(key, [0, 0]))} | {pct(t.get('origin:synthetic', {}).get(key, [0, 0]))} "
                     f"| {pct(t.get('origin:real', {}).get(key, [0, 0]))} |")
    lines += ["", "## 형식별 점수", "", "| 형식 | 건 | " + " | ".join(dict(LABELS)[k] for k in SHAPE_COLS) + " |",
              "|---|---|" + "---|" * len(SHAPE_COLS)]
    for shape in SHAPES:
        row = t.get(f"shape:{shape}")
        if not row:
            continue
        lines.append(f"| {SHAPE_KO[shape]} | {row['cases'][1]} | " + " | ".join(pct(row.get(k, [0, 0])) for k in SHAPE_COLS) + " |")
    secs = [p.get("seconds", 0) for p in preds.values() if not p.get("error")]
    model = [p.get("model_seconds", 0) for p in preds.values() if p.get("model_calls")]
    if secs:
        lines += ["", "## 걸린 시간(한 건)", "", "| 무엇 | 건 | 가운데값 | 90% | 가장 긴 것 |", "|---|---|---|---|---|",
                  f"| 읽기 전체(규칙→모델→날짜→장소) | {len(secs)} | {median(secs):.1f}초 | {_q(secs, 0.9):.1f}초 | {max(secs):.1f}초 |"]
        if model:
            lines.append(f"| 그중 모델 호출(호출이 있던 건만) | {len(model)} | {median(model):.1f}초 | {_q(model, 0.9):.1f}초 | {max(model):.1f}초 |")
    errors = [(cid, p["error"]) for cid, p in preds.items() if p.get("error")]
    if errors:
        lines += ["", "## 읽기 실패", ""] + [f"- {cid}: {e}" for cid, e in errors]
    return "\n".join(lines) + "\n"


__all__ = ["render"]
