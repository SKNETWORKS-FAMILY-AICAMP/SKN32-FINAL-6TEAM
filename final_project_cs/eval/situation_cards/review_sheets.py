# -*- coding: utf-8 -*-
"""상황 카드 사람 작업 시트 — 0단계 카드 검토 시트 · 4단계 작성자 문장 합치기.

    review                     작성자마다 「상대가 쓸 카드」 검토 시트를 만든다(review_by_작성자N.csv)
    split                      3단계 배포 — 작성자 시트를 사람마다 자기 카드 40장만 담은 write_by_작성자N.csv 로 나눈다
    merge 시트.csv [시트.csv …]  작성자가 채운 시트를 검사해 responses_llm_bound_v0.csv 로 합친다

★`[2026-10-16 사용자 결정]` 작성자 2명이 카드 검토 · 문장 쓰기 · 라벨을 모두 한다. 그래서
  - 카드 검토는 **상대가 쓸 카드**만 한다 — 자기가 쓸 카드의 후보 · 설문을 쓰기 전에 보지 않게.
  - 검토 시트에는 **정답 키를 싣지 않는다**(묶음 · 이길 속성 · 기대 행동 · `acceptable_draft` · 속성 초안 · `needs_review` 문구).
    나중에 같은 사람이 80장 전부에 라벨을 붙이므로, 검토에서 정답 초안을 보면 라벨이 독립이 아니게 된다.
    검토는 「상황이 말이 되는가 · 후보가 이상하지 않은가」만 본다 — 결합 조건은 `bind_candidates.py` 가 이미 확인했다.
★합치기는 하나라도 틀리면 아무것도 쓰지 않는다(빈 문장 · 없는 카드 · 중복 · 상황 문장이 결합본과 다름 · 덮어쓰기).

실행(final_project_cs 에서): `python eval/situation_cards/review_sheets.py review`
                            `python eval/situation_cards/review_sheets.py merge 채운시트1.csv 채운시트2.csv`
다음 단계(라벨): `python -m eval.human_review export situation_cards --out 라벨시트_이름.csv`
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOUND = HERE / "cards_llm_bound_v0.jsonl"
SHEET = HERE / "sheet_llm_bound_v0.csv"
RESPONSES = HERE / "responses_llm_bound_v0.csv"
TEXT_COL = "고객이 보낼 말(1~2문장)"
NOTE_COL = "메모"
VERDICTS = ("괜찮음", "고침", "뺌")
VERDICT_COL = f"판정({' / '.join(VERDICTS)})"
WEEKDAY = "월화수목금토일"


#: ★`[2026-10-20]` 자료 묶음 — v0(holdout 80) · h2(holdout-2, `eval.alternative_pick.holdout2`)
SETS = {"v0": ("cards_llm_bound_v0.jsonl", "sheet_llm_bound_v0.csv", "responses_llm_bound_v0.csv"),
        "h2": ("cards_llm_bound_h2.jsonl", "sheet_llm_bound_h2.csv", "responses_llm_bound_h2.csv"),
        "h3": ("cards_llm_bound_h3.jsonl", "sheet_llm_bound_h3.csv", "responses_llm_bound_h3.csv")}


def use_set(name: str) -> None:
    global BOUND, SHEET, RESPONSES
    BOUND, SHEET, RESPONSES = (HERE / f for f in SETS[name])


def load_bound() -> dict[str, dict]:
    return {(c := json.loads(line))["card_id"]: c for line in BOUND.open(encoding="utf-8")}


def load_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def when(at: str) -> str:
    t = datetime.fromisoformat(at)
    return f"{t:%m-%d}({WEEKDAY[t.weekday()]}) {t:%H:%M}"


def candidate_text(c: dict) -> str:
    """후보 한 곳 — 이름 · 분류 코드 · 운영 코드가 낸 이유(거리 · 분류 · 휴무 여부). 속성 초안(`auto_tags`)은 싣지 않는다."""
    return f"{c['title']} ({c['class']}) — {c['code_reason']}"


def survey_text(survey: dict) -> str:
    """설문 — `priority` 는 뺀다(취향이 아니라 후보를 뽑는 범위다 · 계획서 1-1)."""
    parts = []
    for key, value in survey.items():
        if key == "priority":
            continue
        if isinstance(value, dict):
            value = ", ".join(f"{k}={v}" for k, v in value.items())
        elif isinstance(value, list):
            value = ", ".join(map(str, value))
        parts.append(f"{key}: {value}")
    return " / ".join(parts) or "(없음)"


def cmd_review(_args) -> None:
    cards = load_bound()
    rows = load_sheet(SHEET)
    writers = sorted({r["작성자"] for r in rows})
    targets = [HERE / f"review_by_{w}.csv" for w in writers]
    exists = [p.name for p in targets if p.exists()]
    if exists:
        raise SystemExit(f"이미 있다 — 덮어쓰지 않는다(채운 검토가 지워질 수 있다): {exists}. 옛 파일을 _backup 으로 옮긴다")
    for writer, out in zip(writers, targets):
        mine = [r for r in rows if r["작성자"] != writer]          # ★상대가 쓸 카드
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["카드", "검토자", "상황(작성자에게 보일 문장)", "원래 장소", "방문 시각", "설문(priority 뺌)",
                        "후보 1(코드 순서)", "후보 2", "후보 3", "원래 장소를 다시 고름", VERDICT_COL, NOTE_COL])
            for r in mine:
                c = cards[r["카드"]]
                shown = [candidate_text(x) for x in c["candidates"]] + [""] * (3 - len(c["candidates"]))
                w.writerow([c["card_id"], writer, c["situation"], c["origin"]["title"], when(c["at"]), survey_text(c["survey"]),
                            *shown[:3], "예" if c.get("origin_rebound_from") else "아니요", "", ""])
        print(f"{out.name} — {len(mine)}장({writer} 이(가) 검토, 상대가 쓸 카드)")


def cmd_split(_args) -> None:
    """`[2026-10-17]` 작성자마다 자기 행만 — 상대 카드 행을 잘못 채우는 일을 막는다. 열은 작성자 시트 그대로라 `merge` 가 그대로 받는다.
    카드 검토가 끝나지 않았으면(괜찮음이 아닌 판정이 남음) 나누지 않는다 — 상황 문장이 아직 바뀔 수 있다."""
    pending = [f"{p.name} {r['카드']}" for p in sorted(HERE.glob("review_by_*.csv")) for r in load_sheet(p)
               if (r.get(VERDICT_COL) or "").strip() != "괜찮음"]
    if pending:
        raise SystemExit(f"카드 검토가 덜 끝났다({len(pending)}장): {', '.join(pending[:10])}")
    cards = load_bound()
    rows = load_sheet(SHEET)
    stale = [r["카드"] for r in rows if r["상황"] != cards[r["카드"]]["situation"]]
    if stale:
        raise SystemExit(f"작성자 시트 상황 문장이 결합본과 다르다: {stale[:10]}")
    for writer in sorted({r["작성자"] for r in rows}):
        out = HERE / f"write_by_{writer}.csv"
        if out.exists():
            raise SystemExit(f"{out.name} 이(가) 이미 있다 — 덮어쓰지 않는다")
        mine = [r for r in rows if r["작성자"] == writer]
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(mine)
        print(f"{out.name} — {len(mine)}장")


def cmd_merge(args) -> None:
    cards = load_bound()
    expected = {r["카드"]: r for r in load_sheet(SHEET)}
    if RESPONSES.exists():
        raise SystemExit(f"{RESPONSES.name} 이(가) 이미 있다 — 덮어쓰지 않는다. 옛 파일을 _backup 으로 옮긴다")
    errors: list[str] = []
    got: dict[str, dict[str, str]] = {}
    for path in map(Path, args.sheets):
        for line, row in enumerate(load_sheet(path), start=2):
            cid = (row.get("카드") or "").strip()
            text = (row.get(TEXT_COL) or "").strip()
            if not cid and not text:
                continue
            if cid not in expected:
                errors.append(f"{path.name} {line}줄: 시트에 없는 카드 {cid!r}")
            elif not text:
                continue                                       # 다른 작성자 몫 — 한 파일에 둘이 같이 채워도 된다
            elif cid in got:
                errors.append(f"{path.name} {line}줄: {cid} 문장이 두 번 나온다")
            elif row.get("상황") and row["상황"].strip() != cards[cid]["situation"]:
                errors.append(f"{path.name} {line}줄: {cid} 상황 문장이 결합본과 다르다 — 옛 시트를 채운 것 같다")
            else:
                got[cid] = {"카드": cid, "작성자": expected[cid]["작성자"], TEXT_COL: text, NOTE_COL: (row.get(NOTE_COL) or "").strip()}
    missing = sorted(set(expected) - set(got))
    errors += [f"{cid}: 문장이 없다({expected[cid]['작성자']})" for cid in missing]
    if errors:
        raise SystemExit(f"합치지 않았다({len(errors)}건):\n  " + "\n  ".join(errors[:40]))
    with RESPONSES.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["카드", "작성자", TEXT_COL, NOTE_COL])
        w.writeheader()
        for r in expected:                                     # 작성자 시트 순서 그대로
            w.writerow(got[r])
    print(f"{RESPONSES.name} — {len(got)}/{len(expected)}장")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("review")
    sub.add_parser("split")
    mg = sub.add_parser("merge")
    mg.add_argument("sheets", nargs="+")
    mg.add_argument("--set", choices=tuple(SETS), default="v0",
                    help="h2 = holdout-2(`cards_llm_bound_h2.jsonl` · `sheet_llm_bound_h2.csv` → `responses_llm_bound_h2.csv`)")
    args = ap.parse_args(argv)
    if getattr(args, "set", "v0") != "v0":
        use_set(args.set)
    {"review": cmd_review, "split": cmd_split, "merge": cmd_merge}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
