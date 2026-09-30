# -*- coding: utf-8 -*-
"""결정 단위 재생 시험 — **실제 모델**로 정답 표기된 문장을 돌려 정확도 · 지연을 잰다. `[2026-09-29]`

    python -m eval.decision_unit.replay eval/decision_unit/cases_ui25.jsonl

★서버 코드(`decision_unit.decide` — 지시문 · 스키마 · 검증)를 그대로 부른다. 여행은 파일에 적힌 모양(메모리 안)이라 DB 를 안 건드린다.
★합격선(계획서): 할 일 + 대상 동시 정답 95% 이상 · 엉뚱한 대상 변경 0건 · 지연 p95 5초 이하.
정답 한 줄: {"trip": 여행 이름, "history": [[역할, 문장]…], "selected": "i9"|null, "message": …,
            "action": 기대 할 일, "item": "i1"|null(상관없음)|"none", "change": "c2"|null, "fact": "detail"|null, "label_by": …}
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
CHANGING = ("apply_change", "propose_alternatives", "rollback", "redo", "report_closed")


@dataclass
class _Item:
    item_id: object
    seq: int
    kind: str
    title: str
    starts_at: datetime
    ends_at: datetime
    place: dict


def load_trips(path: Path) -> dict:
    """여행 파일 — {이름: {"items": [[날짜시각, 종류, 이름], …], "changes": [[id, 대상 순번(1부터)|null, 설명], …]}}."""
    from app.modules.travel_ops.decision_unit import Change

    raw = json.loads(path.read_text(encoding="utf-8"))
    trips = {}
    for name, trip in raw.items():
        items = []
        for n, (when, kind, title) in enumerate(trip["items"], start=1):
            start = datetime.fromisoformat(when).replace(tzinfo=KST)
            items.append(_Item(uuid4(), n, kind, title, start, start, {"name": title}))
        changes = [Change(alias, int(alias[1:]), "customer_request",
                          items[target - 1].item_id if target else None, line)
                   for alias, target, line in trip.get("changes", [])]
        trips[name] = (items, changes)
    return trips


def run(cases_path: Path, trips_path: Path) -> dict:
    from app.core.settings import get_settings
    from app.infrastructure.ollama_chat import from_settings
    from app.modules.travel_ops.decision_unit import DecisionFailed, decide, fact_first, stops_of

    chat = from_settings(get_settings())
    trips = load_trips(trips_path)
    rows, secs = [], []
    for line in cases_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        items, changes = trips[case["trip"]]
        stops = stops_of(items)
        alias_of = {s.item.item_id: s.alias for s in stops}
        selected = next((s.item.item_id for s in stops if s.alias == case.get("selected")), None)
        history = [{"role": "customer" if who == "고객" else "assistant", "text": text} for who, text in case.get("history", [])]
        started = time.monotonic()
        try:
            got = decide(chat, stops=stops, changes=changes, history=history, selected_item_id=selected,
                         message=case["message"])
            # ★`[2026-09-29]` 서버가 실제로 하는 것으로 잰다 — 후보가 모두 사실 질문인 되묻기는 첫 후보로 먼저 답한다(`fact_first`)
            got = fact_first(got)
            action, item = got.action, alias_of.get(getattr(got.item, "item_id", None), "none")
            change, fact = (got.change.alias if got.change else "none"), got.fact
            choices = [(c["action"], alias_of.get(getattr(c["item"], "item_id", None), "none")) for c in got.choices]
            error = None
        except DecisionFailed as exc:
            action = item = change = fact = None
            choices = []
            error = str(exc)
        secs.append(time.monotonic() - started)
        wanted = case["action"] if isinstance(case["action"], list) else [case["action"]]
        ok_action = action in wanted
        # ★대상은 바꾸는 할 일 · 사실 답일 때만 본다(되묻기로 답한 경우는 대상이 없어도 맞다)
        ok_item = case.get("item") is None or action == "clarify" or item == case["item"]
        ok_change = case.get("change") is None or change == case["change"]
        ok_fact = case.get("fact") is None or fact == case["fact"]
        good = ok_action and ok_item and ok_change and ok_fact
        # ★엉뚱한 대상 변경 — 바꾸는 할 일을 **다른 대상**에 냈다(정답이 바꾸는 할 일이 아니어도 바꾸면 위험)
        wrong_target_change = (action in CHANGING and case.get("item") not in (None, "none")
                               and item not in ("none", case.get("item")))
        # ★되물었지만 **후보 안에 정답**이 있었다 — 바꾸지 않고 고르게 했으니 안전하다(따로 센다)
        right_choice = action == "clarify" and any(a in wanted and (case.get("item") is None or i == case["item"])
                                                   for a, i in choices)
        rows.append({**case, "got": {"action": action, "item": item, "change": change, "fact": fact, "error": error,
                                     "choices": choices}, "clarify_with_right_choice": right_choice,
                     "good": good, "wrong_target_change": wrong_target_change, "seconds": round(secs[-1], 2)})
    secs_sorted = sorted(secs)
    p = lambda q: secs_sorted[min(len(secs_sorted) - 1, int(round(q * (len(secs_sorted) - 1))))]  # noqa: E731
    summary = {"cases": len(rows), "good": sum(r["good"] for r in rows),
               "accuracy": round(sum(r["good"] for r in rows) / max(1, len(rows)), 3),
               "wrong_target_changes": sum(r["wrong_target_change"] for r in rows),
               "clarify_with_right_choice": sum(r["clarify_with_right_choice"] for r in rows),
               "unnecessary_clarify": sum(1 for r in rows if r["got"]["action"] == "clarify"
                                          and "clarify" not in (r["action"] if isinstance(r["action"], list) else [r["action"]])),
               # ★`[2026-09-29 ui 세션 요청]` 질문 종류(fact)만 따로 — 할 일·대상이 맞아도 「어디 있어」에 전체 설명을 내면 틀린 답이다.
               #   분모 = 기대 fact 가 적힌 문장, 분자 = 모델이 고른 fact 가 기대와 같은 것
               "fact_labeled": sum(1 for r in rows if r.get("fact")),
               "fact_correct": sum(1 for r in rows if r.get("fact") and r["got"]["fact"] == r["fact"]),
               "p50": round(statistics.median(secs), 2) if secs else None, "p95": round(p(0.95), 2) if secs else None,
               "p99": round(p(0.99), 2) if secs else None, "max": round(max(secs), 2) if secs else None}
    return {"summary": summary, "rows": rows}


if __name__ == "__main__":
    cases = Path(sys.argv[1])
    trips = Path(sys.argv[2]) if len(sys.argv) > 2 else cases.with_name("trips.json")
    out = run(cases, trips)
    for r in out["rows"]:
        if not r["good"]:
            print("X", r["message"], "→", r["got"], "기대", {k: r.get(k) for k in ("action", "item", "change", "fact")})
    print(json.dumps(out["summary"], ensure_ascii=False))
    report = cases.with_name(f"report_{cases.stem}_{datetime.now(KST):%Y%m%d_%H%M}.json")
    report.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("리포트", report)
