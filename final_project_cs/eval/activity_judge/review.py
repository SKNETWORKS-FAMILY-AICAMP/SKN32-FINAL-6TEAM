# -*- coding: utf-8 -*-
"""골든셋 라벨 사람 검토(구현 계획 WS-1.1) — 검토 시트를 뽑고, 채운 시트를 사람 라벨로 들인다.

    python -m eval.activity_judge.review export                     # 빈 검토 시트(labels_review.csv)
    python -m eval.activity_judge.review export --first-pass        # 1차 라벨(labels_first_pass.json)을 채운 시트
    python -m eval.activity_judge.review apply labels_review.csv --reviewer 이름
    python -m eval.activity_judge.build                             # 사람 라벨로 cases.jsonl · 매니페스트를 다시 만든다

★**시트에 작성자(Claude) 라벨을 싣지 않는다.** 라벨은 규칙 · LLM 결과도, 앞선 라벨도 보기 전에 고정한다
  (구현 계획 WS-1.1). 보면 거기에 맞추게 된다.
★사람 라벨은 `labels_human.json` 에 따로 둔다. `build` 가 코드 속 작성자 라벨 위에 덮어쓴다 —
  골든셋을 다시 만들어도 사람 라벨이 지워지지 않는다.
★`[2026-10-11 사용자 결정]` 1차 라벨(Claude) → 사람 검수도 허용한다(`--first-pass`). 1차 라벨은 `labels_first_pass.json`
  에 근거와 함께 남기고, 판단이 갈리는 건은 「확인 필요」로 표시한다 — 검수자는 그 건부터 본다. 빈 시트(기본)는 그대로 둔다.
★`live_status`(웹)는 원래 라벨이 없다(실제 공지를 사람이 확인하지 않는다 — `build.py`). 시트에서 뺀다.
★검토 시트(.csv)는 작업용이다 — 올리지 않는다. 올리는 것은 `labels_human.json` 이다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

from app.domains.travel_ops.instances.activity.judge.types import LIVE_STATUS, VALUES

HERE = Path(__file__).resolve().parent
SHEET = HERE / "labels_review.csv"
HUMAN_LABELS = HERE / "labels_human.json"
FIRST_PASS = HERE / "labels_first_pass.json"
WEEKDAYS = "월화수목금토일"

#: 종류별 판정 기준 — 라벨이 아니라 **무엇을 묻는가**다. 시트 행마다 싣는다.
CRITERIA: dict[str, str] = {
    "closure": "그 날짜가 원문상 정기휴무인가. 공휴일 여부는 입력에 없다 — 공휴일이어야 정해지는 경우는 unknown 도 허용 후보",
    "operating_hours": "그 시각이 원문상 운영시간 안인가. 입장 마감 뒤는 outside. 원문을 못 읽으면 unknown",
    "weather_sensitive": "날씨 영향을 받는 야외 활동인가(outdoor) 실내인가(indoor). 섞여 있으면 주된 쪽, 정할 수 없으면 unknown",
    "disaster_effect": ("유스케이스 수정본 §8 재해 분류표 기준(D2 — 분류표를 따른다). 지역 위험형: 문자에 걸린 구의 모든 활동을 막는다 · "
                        "야외 위험형: 야외 활동만 막는다 · 반영 안 함(「기타」 · 해제 · 실종 등): 막지 않는다 · "
                        "분류되지 않음: 막지 않고 경고만"),
}
HEADER = ["case_id", "종류", "방문 시각", "입력", "판정 기준", "고를 수 있는 값",
          "정답", "함께 맞다고 칠 값(; 로 구분)", "메모", "확인 필요", "1차 근거"]


def _when(text: str | None) -> str:
    if not text:
        return ""
    at = datetime.fromisoformat(text)
    return f"{at:%Y-%m-%d}({WEEKDAYS[at.weekday()]}) {at:%H:%M}"


def _inputs(case: dict) -> str:
    i = case["inputs"]
    kind = case["kind"]
    if kind == "closure":
        return f"휴무 원문: {i['restdate_text']}"
    if kind == "operating_hours":
        return f"운영시간 원문: {i['usetime_text']}"
    if kind == "weather_sensitive":
        return f"장소: {i['title']}" + (f" · 관광공사 중분류: {i['lclssystm2']}" if i.get("lclssystm2") else "")
    if kind == "disaster_effect":
        lines = [f"장소: {i['place_name']}"]
        for m in i["messages"] or []:
            lines.append(f"[{_when(m['created_at'])} · {m['step']} · {m['kind']} · {', '.join(m['regions'])}] {m['text']}")
        if not i["messages"]:
            lines.append("재난문자 없음")
        return "\n".join(lines)
    return json.dumps(i, ensure_ascii=False)


def load_cases() -> list[dict]:
    from .build import CASES
    return [c for c in CASES if c["kind"] != LIVE_STATUS]


def export(out: Path, first_pass: dict | None = None) -> None:
    cases = load_cases()
    labels = (first_pass or {}).get("labels", {})
    with out.open("w", encoding="utf-8-sig", newline="") as fh:     # BOM — 엑셀이 한글을 바로 읽는다
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        for c in cases:
            first = labels.get(c["case_id"]) or {}
            extra = ";".join(v for v in first.get("acceptable", []) if v != first.get("expected"))
            writer.writerow([c["case_id"], c["kind"], _when(c["inputs"].get("starts_at")), _inputs(c),
                             CRITERIA[c["kind"]], " / ".join(VALUES[c["kind"]]), first.get("expected") or "", extra, "",
                             "확인 필요" if first.get("check") else "", first.get("reason", "")])
    flagged = sum(1 for v in labels.values() if v.get("check"))
    print(f"{out} — {len(cases)}건. 「정답」 칸을 채운다(필요하면 「함께 맞다고 칠 값」 · 「메모」도)"
          + (f" · 1차 라벨을 채웠다 — 「확인 필요」 {flagged}건부터 본다" if labels else ""))


def read_sheet(path: Path) -> dict[str, dict]:
    """채운 시트를 읽어 검사한다. 하나라도 틀리면 아무것도 들이지 않는다."""
    kinds = {c["case_id"]: c["kind"] for c in load_cases()}
    labels: dict[str, dict] = {}
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            cid = (row.get("case_id") or "").strip()
            if cid not in kinds:
                errors.append(f"{cid or '(빈 칸)'}: 골든셋에 없는 case_id")
                continue
            allowed = VALUES[kinds[cid]]
            expected = (row.get("정답") or "").strip()
            if not expected:
                errors.append(f"{cid}: 정답이 비었다")
                continue
            extra = [v.strip() for v in (row.get(HEADER[7]) or "").split(";") if v.strip()]
            bad = [v for v in [expected, *extra] if v not in allowed]
            if bad:
                errors.append(f"{cid}: {bad} 는 고를 수 없는 값이다({' / '.join(allowed)})")
                continue
            labels[cid] = {"expected": expected,
                           "acceptable": [expected, *[v for v in extra if v != expected]],
                           "note": (row.get("메모") or "").strip()}
    missing = sorted(set(kinds) - set(labels) - {e.split(":")[0] for e in errors})
    errors += [f"{cid}: 시트에 행이 없다" for cid in missing]
    if errors:
        raise SystemExit("검토 시트에 문제가 있어 들이지 않았다:\n  " + "\n  ".join(errors))
    return labels


def apply(path: Path, reviewer: str) -> None:
    labels = read_sheet(path)
    first = FIRST_PASS.name if FIRST_PASS.exists() else None
    HUMAN_LABELS.write_text(json.dumps({"reviewer": reviewer, "reviewed_on": date.today().isoformat(),
                                        "first_pass": first, "labels": labels}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from .build import CASES
    claude = {c["case_id"]: c["expected"] for c in CASES}
    changed = sorted(cid for cid, label in labels.items() if label["expected"] != claude.get(cid))
    print(f"{HUMAN_LABELS.name} — {len(labels)}건 · 작성자 라벨과 정답이 다른 것 {len(changed)}건"
          + (f": {', '.join(changed)}" if changed else ""))
    print("→ python -m eval.activity_judge.build 로 골든셋을 다시 만든다")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--out", type=Path, default=SHEET)
    ex.add_argument("--first-pass", action="store_true", help="labels_first_pass.json 의 1차 라벨을 채운다")
    ap_apply = sub.add_parser("apply")
    ap_apply.add_argument("sheet", type=Path)
    ap_apply.add_argument("--reviewer", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "export":
        export(args.out, json.loads(FIRST_PASS.read_text(encoding="utf-8")) if args.first_pass else None)
    else:
        apply(args.sheet, args.reviewer)


if __name__ == "__main__":
    sys.exit(main())
