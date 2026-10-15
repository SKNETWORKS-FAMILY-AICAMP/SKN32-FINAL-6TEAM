# -*- coding: utf-8 -*-
"""접수 읽기 — 장소마다 「식사(dining)인가 활동(activity)인가」 판정을 세 방식으로 잰다. `[2026-10-15]`

    python -m eval.runners.intake_meal_kind [--holdout] [--repeats 3] [--model gpt-4o-mini] [--out REPORT.json]

★세 방식(같은 정답 자료 · 같은 모델 응답)
    rule       지금 코드 — 그 장소의 원문 구간(`span_segments.split_segments`)에 끼니 말이 있으면 식사(`rules.meal_mention`)
    rule_llm   rule 이 식사라고 하거나, 모델이 식사라고 하면서 **그 장소 구간 안의 조각**을 원문 그대로 인용하면 식사
    llm        모델 판정만 — 식사라고 하면서 인용한 조각이 원문에 글자 그대로 있으면 식사(없으면 활동으로 둔다)
  rule_llm · llm 은 문장마다 **같은 모델 응답 하나**로 계산한다 — 모델 차이가 아니라 방식 차이만 보이게.
★가장 나쁜 오류는 `false_dining`(활동을 식사로) — 장소 찾기가 그 이름의 식당을 고르고 시각이 식사 시간으로 간다(테스트 서버 「서촌」 → 「서촌닭갈비」).
★장소 위치는 정답으로 준다 — 이 평가는 장소 찾기가 아니라 종류 판정만 잰다.
★OpenAI 는 `.env` 의 `ACOP_OPENAI_API_KEY`(개발 평가용 개인 키). 키 값은 찍지 않는다. 온도 0.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domains.travel_ops.components.intake.rules import eat_mention, meal_mention
from app.domains.travel_ops.components.intake.span_segments import split_segments

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "eval" / "datasets" / "intake_meal_kind_v1.jsonl"
HOLDOUT = ROOT / "eval" / "datasets" / "intake_meal_kind_holdout_v1.jsonl"
MODES = ("rule", "rule_llm", "llm")

SYSTEM = (
    "You read one line of a traveller's Korean itinerary and the places named in it. For each place decide whether the "
    "traveller will eat or drink there (dining: a meal, snack, drink, café or a named restaurant/café) or only visit it "
    "(activity: sightseeing, walking, shopping, viewing, passing by). A meal word that only tells the time of day "
    "(e.g. 저녁 무렵, 점심쯤) is not eating. Eating that happens before leaving for the place (e.g. 아침 먹고 나와서) "
    "does not make that place dining.\n"
    "For dining, copy the shortest EXACT substring of the line that shows the eating (or the eatery name itself); never "
    "change, fix or translate characters. For activity the quote is \"\".\n"
    'Return JSON only: {"items": [{"place": "<as given>", "kind": "dining" | "activity", "quote": "..."}]}')


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def segments(text: str, names: list[str]) -> list[tuple[int, int, int, int]]:
    """정답 장소마다 (이름 시작, 이름 끝, 구간 시작, 구간 끝). 같은 이름이 두 번이면 차례로 찾는다."""
    spots, cursor = [], 0
    for name in names:
        at = text.find(name, cursor)
        if at < 0:
            raise ValueError(f"장소가 원문에 없다: {name!r} in {text!r}")
        spots.append((at, at + len(name)))
        cursor = at + len(name)
    return [(s, e, left, right) for (s, e), (left, right) in zip(spots, split_segments(text, spots))]


def rule_kind(text: str, seg: tuple[int, int, int, int]) -> str:
    start, _, left, right = seg
    mention = meal_mention(text[left:right], place_start=start - left)
    if mention and mention[2]:
        return "dining"
    # ★`[2026-10-15 (가)]` 끼니 말이 없어도 이름 뒤 「먹는다」 말이면 식사 — 접수 읽기(`llm_spans._line_items`)와 같은 규칙
    return "dining" if eat_mention(text[left:right], place_end=seg[1] - left) else "activity"


def ask(chat: Any, text: str, names: list[str]) -> dict[str, dict[str, str]]:
    """모델 응답 → 장소 이름마다 {kind, quote}. 모양이 다르면 그 장소는 비운다(활동으로 센다)."""
    user = json.dumps({"line": text, "places": names}, ensure_ascii=False)
    raw = chat.json(SYSTEM, user)
    out: dict[str, dict[str, str]] = {}
    for entry in (raw.get("items") if isinstance(raw, dict) else None) or []:
        if isinstance(entry, dict) and entry.get("place") in names:
            out[str(entry["place"])] = {"kind": str(entry.get("kind") or ""), "quote": str(entry.get("quote") or "")}
    return out


def llm_kind(text: str, answer: dict[str, str] | None, seg: tuple[int, int, int, int] | None = None) -> str:
    """모델이 식사라고 하고 인용이 원문에 글자 그대로 있으면 식사. `seg` 가 있으면 인용이 **그 장소 구간 안**이어야 한다."""
    if not answer or answer.get("kind") != "dining" or not answer.get("quote"):
        return "activity"
    quote = answer["quote"]
    if seg is None:
        return "dining" if quote in text else "activity"
    _, _, left, right = seg
    return "dining" if quote in text[left:right] else "activity"


def judge(case: dict[str, Any], answer: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    text = case["text"]
    names = [p["name"] for p in case["places"]]
    rows = []
    for place, seg in zip(case["places"], segments(text, names)):
        rule = rule_kind(text, seg)
        got = {"rule": rule,
               "rule_llm": "dining" if rule == "dining" or llm_kind(text, answer.get(place["name"]), seg) == "dining"
               else "activity",
               "llm": llm_kind(text, answer.get(place["name"]))}
        rows.append({"id": case["id"], "group": case["group"], "place": place["name"], "gold": place["label"],
                     "segment": text[seg[2]:seg[3]], "answer": answer.get(place["name"]), "got": got})
    return rows


def label(gold: str, got: str) -> str:
    if gold == got:
        return "correct"
    return "false_dining" if got == "dining" else "missed_dining"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mode in MODES:
        labels = Counter(label(r["gold"], r["got"][mode]) for r in rows)
        groups: dict[str, Counter] = defaultdict(Counter)
        for r in rows:
            groups[r["group"]][label(r["gold"], r["got"][mode])] += 1
        out[mode] = {"accuracy": f"{labels['correct']}/{len(rows)}", "pct": round(100 * labels["correct"] / len(rows), 1),
                     "false_dining": labels["false_dining"], "missed_dining": labels["missed_dining"],
                     "by_group": {g: f"{c['correct']}/{sum(c.values())}" for g, c in sorted(groups.items())}}
    return out


class _Replay:
    """한 번 받은 접수 모델 응답을 다시 준다 — `eat` 조각을 빼고 · 넣고 같은 응답으로 두 번 채점한다."""

    def __init__(self, raw: dict[str, Any], *, drop_eat: bool) -> None:
        self.raw, self.drop_eat = raw, drop_eat

    def json(self, system: str, user: str) -> dict[str, Any]:
        spans = [s for s in (self.raw.get("spans") or []) if not (self.drop_eat and isinstance(s, dict) and s.get("role") == "eat")]
        return {"spans": spans}


def judge_span(case: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    """★실제 접수 호출 모양(`llm_spans.label_lines` — 줄 번호 + 조각 역할)으로 채점. 모델이 장소를 못 가리켰으면 `place_missed`.
    span_rule = 모델이 가리킨 장소 + 규칙 끼니 판정(eat 조각 뺌) · span_rule_llm = 같은 응답 + eat 조각."""
    from app.domains.travel_ops.components.intake.llm_spans import label_lines

    text = case["text"]
    got: dict[str, Any] = {}
    for mode, drop in (("span_rule", True), ("span_rule_llm", False)):
        _, items, _ = label_lines([text], [1], _Replay(raw, drop_eat=drop))
        got[mode] = items
    rows, cursor = [], 0
    for place in case["places"]:
        at = text.find(place["name"], cursor)
        cursor = at + len(place["name"])
        row = {"id": case["id"], "group": case["group"], "place": place["name"], "gold": place["label"], "got": {}}
        for mode, items in got.items():
            hit = next((i for i in items if i.title.start < cursor and at < i.title.end), None)
            row["got"][mode] = "place_missed" if hit is None else ("dining" if hit.meal else "activity")
        rows.append(row)
    return rows


def make_chat(model: str) -> tuple[Any, dict[str, int]]:
    from openai import OpenAI

    from app.core.settings import get_settings
    from app.infrastructure.llm_failover import OpenAIChat
    from eval.runners.dining_alternatives import _CountingClient

    key = (getattr(get_settings(), "openai_api_key", "") or "").strip()
    if not key:
        raise SystemExit("ACOP_OPENAI_API_KEY 가 비어 있다")
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    client = _CountingClient(OpenAI(api_key=key, timeout=30.0, max_retries=1), usage)
    return OpenAIChat(api_key=key, model=model, timeout=30.0, client=client), usage


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--out")
    ap.add_argument("--shape", choices=("place_list", "span"), default="place_list",
                    help="place_list = 장소 목록을 주고 묻는 별도 프롬프트(첫 비교) · span = 실제 접수 호출(llm_spans.SYSTEM)")
    a = ap.parse_args()
    cases = load(HOLDOUT if a.holdout else DEV)
    chat, usage = make_chat(a.model)
    if a.shape == "span":
        return run_span(cases, chat, usage, a)
    runs, seconds, failures = [], [], 0
    for repeat in range(a.repeats):
        rows = []
        for case in cases:
            started = time.perf_counter()
            try:
                answer = ask(chat, case["text"], [p["name"] for p in case["places"]])
            except Exception as exc:   # noqa: BLE001 — 실패는 세고 그 문장은 모델 답 없이(활동으로) 센다
                failures += 1
                answer = {}
                print(f"[{case['id']}] 모델 호출 실패: {type(exc).__name__}", file=sys.stderr)
            seconds.append(time.perf_counter() - started)
            rows += judge(case, answer)
        runs.append({"repeat": repeat, "summary": summarize(rows), "rows": rows})
    seconds.sort()
    report = {"dataset": (HOLDOUT if a.holdout else DEV).name, "model": a.model, "repeats": a.repeats,
              "places": len(runs[0]["rows"]), "failures": failures, "usage": usage,
              "seconds": {"mean": round(sum(seconds) / len(seconds), 2), "p95": round(seconds[int(0.95 * (len(seconds) - 1))], 2)},
              "summary_by_repeat": [r["summary"] for r in runs],
              "env": {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
              "runs": runs}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dataset", "model", "places", "failures", "usage", "seconds")}, ensure_ascii=False))
    for i, s in enumerate(report["summary_by_repeat"]):
        print(f"repeat {i}:", json.dumps({m: {k: s[m][k] for k in ("accuracy", "pct", "false_dining", "missed_dining")}
                                           for m in MODES}, ensure_ascii=False))
    return 0


def run_span(cases: list[dict[str, Any]], chat: Any, usage: dict[str, int], a: Any) -> int:
    from app.domains.travel_ops.components.intake.llm_spans import SYSTEM as SPAN_SYSTEM

    runs, seconds, failures = [], [], 0
    for repeat in range(a.repeats):
        rows = []
        for case in cases:
            started = time.perf_counter()
            try:
                raw = chat.json(SPAN_SYSTEM, f"1: {case['text']}")
            except Exception as exc:   # noqa: BLE001 — 실패는 세고 그 문장은 모델 답 없이 센다(장소를 못 가리킨 것으로)
                failures += 1
                raw = {"spans": []}
                print(f"[{case['id']}] 모델 호출 실패: {type(exc).__name__}", file=sys.stderr)
            seconds.append(time.perf_counter() - started)
            rows += [{**r, "raw": raw} for r in judge_span(case, raw if isinstance(raw, dict) else {})]
        summary = {}
        for mode in ("span_rule", "span_rule_llm"):
            labels = Counter("place_missed" if r["got"][mode] == "place_missed" else label(r["gold"], r["got"][mode]) for r in rows)
            groups: dict[str, Counter] = defaultdict(Counter)
            for r in rows:
                groups[r["group"]][r["got"][mode] == r["gold"]] += 1
            summary[mode] = {"accuracy": f"{labels['correct']}/{len(rows)}", "pct": round(100 * labels["correct"] / len(rows), 1),
                             "false_dining": labels["false_dining"], "missed_dining": labels["missed_dining"],
                             "place_missed": labels["place_missed"],
                             "by_group": {g: f"{c[True]}/{sum(c.values())}" for g, c in sorted(groups.items())}}
        runs.append({"repeat": repeat, "summary": summary, "rows": rows})
    seconds.sort()
    report = {"dataset": (HOLDOUT if a.holdout else DEV).name, "shape": "span", "model": a.model, "repeats": a.repeats,
              "places": len(runs[0]["rows"]), "failures": failures, "usage": usage,
              "seconds": {"mean": round(sum(seconds) / len(seconds), 2), "p95": round(seconds[int(0.95 * (len(seconds) - 1))], 2)},
              "summary_by_repeat": [r["summary"] for r in runs],
              "env": {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, "runs": runs}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dataset", "shape", "model", "places", "failures", "usage", "seconds")}, ensure_ascii=False))
    for i, s in enumerate(report["summary_by_repeat"]):
        print(f"repeat {i}:", json.dumps({m: {k: s[m][k] for k in ("accuracy", "pct", "false_dining", "missed_dining", "place_missed")}
                                           for m in s}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
