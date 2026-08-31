"""결함 등록 게이트.

"결함을 하나 만들었다"와 "학습 문제로 쓸 수 있다"는 다르다. 아래를 통과한 것만
카탈로그에 넣는다. 특히 8번(실패 집합 구별)은 실측 없이는 알 수 없다 —
이 저장소에서 transition_case 와 _load_projection 은 실패 집합이 완전히 같다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import defects as defects_mod
from .sandbox import Sandbox


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def validate_all(target: Path, *, verbose: bool = True,
                 only: list[str] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {"baseline": None, "entries": {}, "collisions": []}
    with Sandbox(target) as sandbox:
        assert sandbox.root is not None
        if verbose:
            print("기준선을 확인한다 (결함 없는 상태에서 전부 통과해야 한다)")
        baseline = sandbox.pytest()
        sandbox.sweep()
        report["baseline"] = {"summary": baseline.summary, "failed": baseline.failed}
        if baseline.failed:
            print(f"  ✗ 기준선이 이미 깨져 있다: {baseline.failed}")
            return report
        if verbose:
            print(f"  ✓ {baseline.summary}")

        selected = [d for d in defects_mod.DEFECTS
                    if only is None or d.defect_id in only]
        for defect in selected:
            patch = defects_mod.PATCH_DIR / f"{defect.defect_id}.patch"
            entry: dict[str, Any] = {"title": defect.title, "invariant": defect.invariant,
                                     "path": defect.path, "gates": {}}
            if verbose:
                print(f"\n{defect.defect_id}  {defect.title}")

            before = (sandbox.root / defect.path).read_bytes()
            ok, message = sandbox.check(patch)
            entry["gates"]["applies"] = ok
            if not ok:
                entry["error"] = message
                report["entries"][defect.defect_id] = entry
                print(f"  ✗ 적용할 수 없다: {message}")
                continue
            applied, message = sandbox.apply(patch)
            entry["gates"]["applied"] = applied
            if not applied:
                entry["error"] = message
                report["entries"][defect.defect_id] = entry
                print(f"  X 적용이 실패했다: {message}")
                continue

            result = sandbox.pytest()
            sandbox.sweep()
            entry["failed"] = result.failed
            entry["summary"] = result.summary
            entry["gates"]["kills_tests"] = bool(result.failed)
            entry["gates"]["not_collection_error"] = not any(
                nodeid.endswith(".py") for nodeid in result.failed)
            if verbose:
                mark = "✓" if result.failed else "✗"
                print(f"  {mark} {result.summary}")
                for nodeid in result.failed[:6]:
                    print(f"      {nodeid}")
                if len(result.failed) > 6:
                    print(f"      … 외 {len(result.failed) - 6}개")

            reverted, message = sandbox.apply(patch, reverse=True)
            after = (sandbox.root / defect.path).read_bytes()
            entry["gates"]["reverts"] = reverted and after == before
            if not entry["gates"]["reverts"]:
                print(f"  ✗ 되돌리지 못했다: {message}")
            report["entries"][defect.defect_id] = entry

    ids = [d for d, e in report["entries"].items() if e.get("failed")]
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            score = jaccard(set(report["entries"][left]["failed"]),
                            set(report["entries"][right]["failed"]))
            if score >= 0.8:
                report["collisions"].append({"a": left, "b": right, "jaccard": round(score, 3)})
    for entry_id in ids:
        others: set[str] = set()
        for other_id in ids:
            if other_id != entry_id:
                others |= set(report["entries"][other_id]["failed"])
        unique = set(report["entries"][entry_id]["failed"]) - others
        report["entries"][entry_id]["unique_failures"] = sorted(unique)
        report["entries"][entry_id]["gates"]["distinguishable"] = bool(unique)
    return report
