"""불변식 원장.

새 규칙이 생긴 것을 기계가 **발견**하려 하지 않는다. 자연어에서 무엇이 정책이고
무엇이 구현 세부인지 안정적으로 가려낼 방법이 없어서, grep 으로 찾겠다는 시도는
오탐과 미탐을 동시에 만든다. 대신 **선언을 강제한다.**

규칙은 여기 산다. 결함 카탈로그는 그 규칙을 어기는 방법의 목록이다.
`defects` 가 빈 규칙은 "문서에는 있는데 세는 곳이 없다" 는 뜻이고, 검사에서 실패한다.
"""
from __future__ import annotations

import json
from typing import Any

from . import defects as defects_mod
from .config import data_dir

REGISTRY_PATH = data_dir() / "invariants.json"


def load() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["entries"]


def check() -> dict[str, Any]:
    """원장과 카탈로그의 참조 무결성을 본다. 테스트는 돌리지 않는다."""
    entries = load()
    known = {d.defect_id for d in defects_mod.DEFECTS}
    excluded = {d.defect_id for d in defects_mod.DEFECTS if getattr(d, "excluded", "")}

    seen: dict[str, str] = {}
    problems: dict[str, list[Any]] = {
        "no_defect": [], "unknown_defect": [], "double_mapped": [],
        "orphan_defect": [], "no_reason": [],
    }
    for rule_id, entry in sorted(entries.items()):
        status = entry.get("status", "active")
        ids = entry.get("defects", [])
        if status != "active" and not entry.get("reason"):
            problems["no_reason"].append(rule_id)
        for defect_id in ids:
            if defect_id not in known:
                problems["unknown_defect"].append((rule_id, defect_id))
            if defect_id in seen:
                problems["double_mapped"].append((defect_id, seen[defect_id], rule_id))
            seen[defect_id] = rule_id
        if status == "active" and not [d for d in ids if d not in excluded]:
            problems["no_defect"].append((rule_id, entry["rule"], entry.get("source", "")))

    problems["orphan_defect"] = sorted(known - set(seen))
    return {"entries": entries, "problems": problems,
            "active": sum(1 for e in entries.values() if e.get("status") == "active"),
            "covered": sum(1 for e in entries.values()
                           if e.get("status") == "active"
                           and [d for d in e.get("defects", []) if d not in excluded])}


def report(outcome: dict[str, Any], *, separator: str) -> int:
    problems = outcome["problems"]
    print(f"불변식 원장 {len(outcome['entries'])}개 · 활성 {outcome['active']}개 · "
          f"세는 곳이 있는 것 {outcome['covered']}개")
    print(separator)

    for defect_id, first, second in problems["double_mapped"]:
        print(f"  X 결함 하나가 두 규칙에 붙었다   {defect_id}  ({first}, {second})")
    for rule_id, defect_id in problems["unknown_defect"]:
        print(f"  X 없는 결함을 참조한다           {rule_id} -> {defect_id}")
    for defect_id in problems["orphan_defect"]:
        print(f"  X 어느 규칙에도 안 붙은 결함     {defect_id}")
    for rule_id in problems["no_reason"]:
        print(f"  X 비활성인데 사유가 없다         {rule_id}")

    if problems["no_defect"]:
        print("")
        print(f"  규칙은 있는데 세는 곳이 없다 — {len(problems['no_defect'])}건")
        print("  문서에 적힌 규칙이 깨져도 아무 테스트가 울지 않는다는 뜻이다.")
        print("")
        for rule_id, rule, source in problems["no_defect"]:
            print(f"    {rule_id:<14} {rule}")
            if source:
                print(f"    {'':<14} 출처: {source}")

    total = sum(len(v) for v in problems.values())
    print("")
    print(separator)
    if total:
        print(f"{total}건이 걸렸다.")
        print("규칙을 지우지 말고 그 규칙을 어기는 결함을 카탈로그에 넣는다 —")
        print("결함이 테스트에 안 잡히면 그게 바로 메워야 할 자리다.")
    else:
        print("원장과 카탈로그가 맞는다.")
    return 1 if total else 0
