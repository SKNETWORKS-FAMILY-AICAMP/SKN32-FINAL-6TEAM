"""불변식 원장.

새 규칙이 생긴 것을 기계가 **발견**하려 하지 않는다. 자연어에서 무엇이 정책이고
무엇이 구현 세부인지 안정적으로 가려낼 방법이 없어서, grep 으로 찾겠다는 시도는
오탐과 미탐을 동시에 만든다. 대신 **선언을 강제한다.**

규칙은 여기 산다. 결함 카탈로그는 그 규칙을 어기는 방법의 목록이다.
`defects` 가 빈 규칙은 "문서에는 있는데 세는 곳이 없다" 는 뜻이고, 검사에서 실패한다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import defects as defects_mod
from .config import data_dir, target_root

REGISTRY_PATH = data_dir() / "invariants.json"


def load() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["entries"]


# ── 정본 원장과의 대조 ─────────────────────────────────────────────────────────
# ★원장이 둘이다. cs 의 `wiki/quality/invariants.md`(INV-CS-*)가 정본이고, 이 파일의
#  R-* 는 도장이 결함을 묶으려고 만든 것이다. 둘을 사람이 문장끼리 짝지으면 해석이
#  섞인다 — 그래서 **실행 증거로** 잇는다. 정본 규칙마다 판정 테스트가 적혀 있고,
#  도장 결함마다 실제로 깨뜨린 테스트가 카탈로그에 있다. 겹치면 그 결함이 그 규칙을 어긴다.
#  대가 — 정본의 판정 테스트가 아닌 다른 테스트로만 잡히는 결함은 이어지지 않는다.
_CANON_ROW = re.compile(
    r"^\|\s*`(INV-CS-[A-Z]+-\d+)`\s*\|\s*(.+?)\s*\|\s*(automated|manual|review)\s*\|\s*(.+?)\s*\|\s*$")


def canonical() -> dict[str, dict[str, Any]]:
    """정본 원장의 표를 읽는다. 표 밖의 서술은 읽지 않는다.

    실행 위치가 `::test_x` 로 시작하면 바로 위 행과 같은 파일이다 — 문서가 그렇게 줄여 쓴다.
    """
    path = target_root() / "wiki" / "quality" / "invariants.md"
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    last_file = None
    for line in path.read_text(encoding="utf-8").splitlines():
        matched = _CANON_ROW.match(line)
        if not matched:
            continue
        canon_id, rule, kind, where = matched.groups()
        test = None
        if kind == "automated":
            where = where.strip().strip("`")
            if where.startswith("::") and last_file:
                where = last_file + where
            last_file = where.split("::")[0]
            test = where
        rows.setdefault(canon_id, {"rule": rule, "kind": kind, "test": test})
    return rows


def canonical_links(catalog: dict[str, Any]) -> dict[str, list[str]]:
    """정본 ID → 그 판정 테스트를 실제로 깨뜨린 도장 결함."""
    entries = catalog.get("entries", {})
    links: dict[str, list[str]] = {}
    for canon_id, row in canonical().items():
        test = row["test"]
        if not test:
            continue
        hit = sorted(d for d, e in entries.items()
                     if any(n == test or n.startswith(test + "[") for n in e.get("failed", [])))
        if hit:
            links[canon_id] = hit
    return links


def canonical_summary(separator: str) -> None:
    rows = canonical()
    if not rows:
        print("정본 원장(wiki/quality/invariants.md)을 찾지 못해 대조하지 않았다.")
        return
    automated = [c for c, r in rows.items() if r["kind"] == "automated"]
    links = canonical_links(defects_mod.load_catalog())
    print("")
    print(f"정본 원장 대조 — INV-CS-* {len(rows)}개 · 자동 판정 {len(automated)}개")
    print(separator)
    print(f"  도장 결함이 판정 테스트를 실제로 깨뜨리는 정본 규칙 "
          f"{len(links)}/{len(automated)} = {len(links) * 100 // max(len(automated), 1)}%")
    for canon_id in sorted(links):
        print(f"    {canon_id:<16} ← {', '.join(links[canon_id])}")


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

    # 중지한 결함 참조도 본다. 되살릴 때 오타 난 id 가 조용히 사라지면 안 된다.
    parked = {d.defect_id for d in defects_mod.PARKED}
    for rule_id, entry in sorted(entries.items()):
        for defect_id in entry.get("parked_defects", []):
            if defect_id not in parked:
                problems["unknown_defect"].append((rule_id, defect_id))

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
    # 대조는 정보다. 정본 규칙에 도장 결함이 없는 것은 도장의 결함 목록 문제가 아니라
    # 아직 안 만든 가설이라 실패로 치지 않는다.
    canonical_summary(separator)
    return 1 if total else 0
