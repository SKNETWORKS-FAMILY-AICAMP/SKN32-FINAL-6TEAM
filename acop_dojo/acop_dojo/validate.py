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


def _normalize(patch_text: str) -> str:
    """hunk 헤더의 줄 번호처럼 의미 없는 차이는 무시한다."""
    lines = []
    for line in patch_text.replace(chr(13) + chr(10), chr(10)).splitlines():
        lines.append("@@" if line.startswith("@@") else line)
    return chr(10).join(lines)


def check_patches(target: Path, *, verbose: bool = True) -> dict[str, Any]:
    """결함 patch 가 아직 유효한지만 본다. 테스트는 돌리지 않는다.

    patch 는 `app/` 이 바뀌면 **조용히** 낡는다. 실제로 `routes.py` 가 다른 작업으로
    14줄 늘면서 INV-UI-001 의 hunk 위치가 밀려 있었는데 아무도 몰랐다.
    전체 게이트는 20분이라 매번 돌릴 수 없어, 싼 검사를 따로 둔다.

    두 가지를 각각 본다. 실패 모드가 다르다.
    - anchor: `old` 문자열이 원본에 정확히 1회 나오는가. 0회면 코드가 바뀐 것이고,
      2회 이상이면 어디를 고칠지 정해지지 않는다. patch 를 **다시 만들 수 있는가**의 문제다.
    - apply: 지금 patch 파일이 그대로 적용되는가. context 3줄이 밀리면 여기서 걸린다.
      이미 만들어 둔 patch 가 **아직 쓸 수 있는가**의 문제다.
    """
    report: dict[str, Any] = {"ok": [], "anchor_broken": [], "apply_broken": [],
                              "drift": [], "missing": []}
    with Sandbox(target) as sandbox:
        assert sandbox.root is not None
        for defect in defects_mod.DEFECTS:
            patch = defects_mod.PATCH_DIR / f"{defect.defect_id}.patch"
            source = sandbox.root / defect.path
            if not patch.exists():
                report["missing"].append(defect.defect_id)
                continue
            with source.open(encoding="utf-8", newline="") as handle:
                original = handle.read()
            anchor = defect.old
            if anchor not in original:
                anchor = anchor.replace(chr(10), chr(13) + chr(10))
            count = original.count(anchor) if anchor else 0
            if count != 1:
                report["anchor_broken"].append((defect.defect_id, defect.path, count))
                continue
            ok, _ = sandbox.check(patch)
            if not ok:
                report["apply_broken"].append(defect.defect_id)
                continue
            # 적용은 되는데 생성기 관점에서는 이미 달라진 경우가 있다.
            # "저장된 patch 는 아직 붙지만 지금 만들면 다른 것이 나온다" 는 drift 다.
            try:
                regenerated = defects_mod.build_patch(defect, sandbox.root)
            except SystemExit:
                report["anchor_broken"].append((defect.defect_id, defect.path, -1))
                continue
            with patch.open(encoding="utf-8", newline="") as handle:
                stored = handle.read()
            if _normalize(regenerated) != _normalize(stored):
                report["drift"].append(defect.defect_id)
            else:
                report["ok"].append(defect.defect_id)

    if verbose:
        total = len(defects_mod.DEFECTS)
        print(f"결함 patch {total}개 검사 — 테스트는 돌리지 않는다")
        print(f"  ✓ 그대로 쓸 수 있다      {len(report['ok'])}")
        for defect_id, path, count in report["anchor_broken"]:
            found = "찾을 수 없다" if count == 0 else f"{count}번 나온다"
            print(f"  ✗ 기준 코드가 바뀌었다   {defect_id}  ({path} 에서 {found})")
        for defect_id in report["apply_broken"]:
            print(f"  ✗ patch 가 낡았다        {defect_id}  (context 가 밀렸다 — 재생성하면 된다)")
        for defect_id in report["drift"]:
            print(f"  ~ 생성 결과와 다르다     {defect_id}  (붙기는 하지만 재생성하면 달라진다)")
        for defect_id in report["missing"]:
            print(f"  ✗ patch 파일이 없다      {defect_id}")
    return report
