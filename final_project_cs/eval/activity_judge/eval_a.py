# -*- coding: utf-8 -*-
"""유스케이스 수정본 EVAL-A 채점기 — 지금은 정의를 확인한 두 항목만(A1 · A4). `[2026-10-12]` 구현 계획 4.5.

    A1  판정 순서 — 방문 시각 → 재난문자 → 정기휴무 → 운영시간. 문제가 겹치면 **가장 앞선 사유**로 답해야 한다.
        팀(`ActivityTeam`)을 가짜 도구로 돌려 겹친 시나리오마다 사유를 본다. LLM · DB · 네트워크를 쓰지 않는다.
    A4  재난 판정은 §8 분류표대로 채점한다 — 골든셋 재난 사례마다 **분류표가 내는 답**(`disaster_impact.assess`)을 계산해
        ① 골든셋 라벨과 다른 사례(1.1 사람 검수 거리) ② (결과 파일을 주면) 규칙 · LLM 답이 분류표와 맞는 비율을 낸다.

★A2 · A3 · A5~A8 은 정의 문서(유스케이스 수정본 10-06)를 확인하지 못해 만들지 않았다 — 지어낸 기준으로 채점하지 않는다.
★분류표 답은 장소의 구로 문자를 먼저 거른다(`read.disaster` 가 실제로 하는 일) — 골든셋 문자에는 다른 지역 문자도 섞여 있다.
  구 · 실내외는 활동 CSV 목록(`csv_places`)에서 읽고, 모르면 분류표 답도 `unknown` 이다(짐작하지 않는다).

사용법
    python -m eval.activity_judge.eval_a a1
    python -m eval.activity_judge.eval_a a4 [--results eval/reports/activity_judge/<run>/results.jsonl]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .build import DATASET

KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)      # 화요일 14시
A1_ORDER = ("time_unknown", "disaster_blocks", "closed_weekday", "outside_hours")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ── A1 판정 순서 ───────────────────────────────────────────────────

class _Tools:
    """`ReadToolbox` 와 같은 모양의 가짜 — 이름 → 값."""

    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        from app.core.contracts import ToolNotAllowed

        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        seen.add(name + ":" + repr(sorted(arguments.items())))
        value = self.values.get(name)
        return value(**arguments) if callable(value) else value


def _scenario_values(problems: set[str]) -> dict[str, Any]:
    week = {d: {"open": "09:00", "close": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    if "closed_weekday" in problems:
        week["tue"] = "closed"
    elif "outside_hours" in problems:
        week["tue"] = {"open": "09:00", "close": "12:00"}           # 14시 방문 — 운영시간 밖
    if "closed_weekday" in problems and "outside_hours" in problems:
        week["tue"] = "closed"                                      # 둘이 겹치면 휴무가 앞선다(같은 날 닫혀 있다)
    message = {"kind": "교통통제", "step": "안전안내", "text": "[종로구] 사직로 일대 전면 통제",
               "created_at": "2026-11-10T09:00:00+09:00", "regions": ["서울특별시 종로구"], "serial": "a1",
               "category": "disaster_msg", "weather": False}
    blocked = "disaster_blocks" in problems
    report = {"verdict": "disrupted" if blocked else "clear", "advisories": [], "failed_categories": [],
              "not_connected": [], "indoor_unknown": False,
              "disruptions": [message] if blocked else [],
              "checks": [{"category": "disaster_msg", "status": "ok", "unclassified": []}]}
    starts = None if "time_unknown" in problems else TUESDAY
    return {"read.booking": {"booking_id": "a1", "place_id": "p1", "starts_at": starts, "party_size": 2, "capacity": 4},
            "read.policy": [],
            "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5796,
                           "longitude": 126.9770, "address": "서울특별시 종로구 사직로 161", "source_content_id": None},
            "read.disruptions": report,
            "read.disaster": {"for_region": report["disruptions"], "unclassified": [], "covered": True},
            "read.place_hours": {"known": True, "attributes": {"hours_week": week}, "source": "eval_a1",
                                 "why_unknown": None, "conditions": [], "usetime_text": None, "restdate_text": None},
            "read.place_class": None, "read.holiday": None, "read.place_candidates": None}


def _reason(result: Any) -> str | None:
    decision = (result.decisions or [{}])[0]
    return decision.get("reason") or result.failure_code


def run_a1() -> dict[str, Any]:
    """겹치는 문제 조합 전부(1~4개) — 사유가 A1 순서에서 가장 앞선 것인가."""
    from itertools import combinations

    from app.core.contracts import ContextPack, TeamTask
    from app.domains.travel_ops.instances.activity import ActivityTeam

    allowed = list(ActivityTeam.manifest.allowed_tools)
    rows = []
    for size in range(1, len(A1_ORDER) + 1):
        for combo in combinations(A1_ORDER, size):
            problems = set(combo)
            expected = next(p for p in A1_ORDER if p in problems)
            context = ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id="activity", tenant_id="eval-a1",
                                  knowledge_scope=["travel_activity"], current_state={"status": "running"},
                                  estimated_input_tokens=10)
            task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=context.case_id, team_id="activity",
                            capability="activity.check_feasible", case_version=1, input_text="EVAL-A1",
                            context=context, allowed_tools=allowed,
                            deadline_at=datetime.now(timezone.utc) + timedelta(seconds=90))
            result = asyncio.run(ActivityTeam(_Tools(_scenario_values(problems))).execute(task))
            got = _reason(result)
            rows.append({"problems": list(combo), "expected": expected, "got": got, "pass": got == expected})
    passed = sum(r["pass"] for r in rows)
    return {"item": "EVAL-A1", "passed": passed, "total": len(rows), "rows": rows}


# ── A4 재난 분류표 채점 ─────────────────────────────────────────────

def _place_facts(name: str | None) -> tuple[str | None, bool | None]:
    """(구, 실외 여부) — 규칙 판정(`judge.rule`)과 같은 장소 목록 · 같은 분류 규칙. 모르면 None."""
    from app.domains.travel_ops.instances.activity.judge.rule import _outdoor_from_class, place_facts

    facts = place_facts(name)
    return facts.get("district"), _outdoor_from_class(facts.get("lcls1"), facts.get("lcls2")) if facts else None


def reaches(message: dict[str, Any], district: str | None) -> bool | None:
    """문자가 그 장소의 구에 닿나 — 규칙 판정과 같은 함수."""
    from app.domains.travel_ops.instances.activity.judge.rule import reaches as rule_reaches

    return rule_reaches(message, district)

def table_answer(case: dict[str, Any]) -> tuple[str, str]:
    """(분류표가 내는 답, 이유) — `blocks` · `no_effect` · `unknown`."""
    from app.domains.travel_ops.instances.activity.disaster_impact import ImpactRules, assess

    inputs = case["inputs"]
    district, outdoor = _place_facts(inputs.get("place_name"))
    kept, unsure = [], False
    for message in inputs.get("messages") or []:
        hit = reaches(message, district)
        if hit is None:
            unsure = True
        elif hit:
            kept.append(message)
    at = datetime.fromisoformat(inputs["starts_at"]) if inputs.get("starts_at") else None
    impact = assess(kept, outdoor, ImpactRules.load(), at=at, place_name=inputs.get("place_name"))
    if impact.blocks:
        return "blocks", ", ".join(sorted({m["impact"] for m in impact.blocks}))
    if impact.ask:
        return "unknown", "야외 위험형인데 실내외를 모름"
    if unsure:
        return "unknown", "장소의 구를 몰라 구 단위 문자가 닿는지 모름"
    return "no_effect", "닿는 문자 없음" if not kept else ", ".join(sorted({m["impact"] for m in impact.no_effect
                                                                            + impact.unclassified}))


def run_a4(results: Path | None = None) -> dict[str, Any]:
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    disaster = [c for c in cases if c["kind"] == "disaster_effect"]
    rows = []
    for case in disaster:
        answer, why = table_answer(case)
        rows.append({"case_id": case["case_id"], "table": answer, "why": why, "label": case["acceptable"],
                     "label_agrees": answer in case["acceptable"]})
    out: dict[str, Any] = {"item": "EVAL-A4", "cases": len(rows),
                           "label_agrees": sum(r["label_agrees"] for r in rows), "rows": rows}
    if results is not None:
        table = {r["case_id"]: r["table"] for r in rows}
        scored: dict[str, list[bool]] = {"rule": [], "llm": []}
        for line in results.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") != "disaster_effect" or row.get("case_id") not in table:
                continue
            for side in scored:
                if row.get(side) is not None:
                    scored[side].append(row[side] == table[row["case_id"]])
        out["agreement_with_table"] = {side: {"agree": sum(v), "total": len(v)} for side, v in scored.items()}
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("item", choices=["a1", "a4"])
    parser.add_argument("--results", type=Path, default=None, help="run.py 결과(results.jsonl) — A4 에서 규칙 · LLM 채점")
    args = parser.parse_args(argv)
    if args.item == "a1":
        report = run_a1()
        for r in report["rows"]:
            print(f"{'통과' if r['pass'] else '실패'}  {'+'.join(r['problems']):60}  기대 {r['expected']:16} 실제 {r['got']}")
        print(f"\nEVAL-A1 판정 순서: {report['passed']}/{report['total']}")
    else:
        report = run_a4(args.results)
        for r in report["rows"]:
            mark = "같음" if r["label_agrees"] else "다름"
            print(f"{mark}  {r['case_id']:13} 분류표 {r['table']:9} 라벨 {','.join(r['label']):18} ({r['why']})")
        print(f"\nEVAL-A4 라벨이 분류표와 같은 사례: {report['label_agrees']}/{report['cases']}")
        for side, s in (report.get("agreement_with_table") or {}).items():
            print(f"  {side}: 분류표와 일치 {s['agree']}/{s['total']}")


if __name__ == "__main__":
    main()
