"""결함 등록 게이트.

"결함을 하나 만들었다"와 "학습 문제로 쓸 수 있다"는 다르다. 아래를 통과한 것만
카탈로그에 넣는다. 특히 8번(실패 집합 구별)은 실측 없이는 알 수 없다 —
이 저장소에서 transition_case 와 _load_projection 은 실패 집합이 완전히 같다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import defects as defects_mod
from .config import data_dir
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
        if baseline.returncode == 124:
            # 기준선이 끝나지 않으면 무엇이 새 실패인지 알 수 없다. 여기서 멈춘다.
            print(f"  ✗ 기준선이 {baseline.summary}. 결함 판정을 시작하지 않는다.")
            print("    대상 저장소에서 끝나지 않는 테스트를 먼저 찾는다 — pytest -v 로 마지막 줄을 본다.")
            report["baseline"] = {"summary": baseline.summary, "failed": []}
            return report
        if " passed" not in baseline.summary:
            # 시험이 하나도 안 돌았다(불러오기에서 멈춤 등). 이 상태로는 무엇이 새 실패인지 모른다.
            # 2026-10-06 — 이걸 모르고 진행해 결함 8개를 「안 잡힘」으로 저장했다.
            print(f"  ✗ 기준선에서 시험이 돌지 않았다: {baseline.summary}. 결함 판정을 시작하지 않는다.")
            report["baseline"] = {"summary": baseline.summary, "failed": []}
            return report
        sandbox.sweep()
        report["baseline"] = {"summary": baseline.summary, "failed": baseline.failed}
        # ★기준선의 실패는 결함 판정에서 뺀다. 공유 저장소는 다른 작업 때문에 늘 몇 건이
        #   깨져 있을 수 있고, 사본에는 .git 이 없어 git 을 묻는 테스트는 원래 실패한다.
        #   예전에는 여기서 멈추고 빈 결과를 돌려줘 카탈로그가 통째로 지워졌다.
        #   대가 — 기준선에서 이미 깨진 테스트가 지키는 규칙은 이번 판정에서 보이지 않는다.
        known_broken = set(baseline.failed)
        # ★미리 알고 있는 환경 의존 실패(data/known_baseline.json)와 그 밖의 것을 가른다.
        #   그 밖의 것도 판정에서는 빼지만 게이트는 실패로 끝낸다 — 다른 작업이 깨뜨린
        #   무결성 검사를 '환경 탓' 으로 묻어 두지 않으려고.
        prefixes = [e["prefix"] for e in json.loads(
            (data_dir() / "known_baseline.json").read_text(encoding="utf-8"))["entries"]]
        unexpected = sorted(n for n in known_broken if not n.startswith(tuple(prefixes)))
        report["unexpected_baseline"] = unexpected
        if verbose:
            if known_broken:
                print(f"  ! 결함 없이도 {len(known_broken)}건이 실패한다 — 판정에서 뺀다")
                for nodeid in sorted(known_broken):
                    mark = "✗ 모르는 실패" if nodeid in unexpected else "  알려진 실패"
                    print(f"    {mark}  {nodeid}")
                print(f"    {baseline.summary}")
            else:
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
            if " passed" not in result.summary and " failed" not in result.summary:
                # 시험이 하나도 안 돌았으면 「안 잡힘」이 아니라 「판정 못 함」이다. 카탈로그에 넣지 않는다.
                print(f"  ? 시험이 돌지 않아 판정하지 못했다: {result.summary}")
                sandbox.apply(patch, reverse=True)
                continue
            new_failures = sorted(set(result.failed) - known_broken)
            entry["failed"] = new_failures
            entry["summary"] = result.summary
            entry["gates"]["kills_tests"] = bool(new_failures)
            entry["gates"]["not_collection_error"] = not any(
                nodeid.endswith(".py") for nodeid in new_failures)
            if verbose:
                mark = "✓" if new_failures else "✗"
                print(f"  {mark} {result.summary}")
                for nodeid in new_failures[:6]:
                    print(f"      {nodeid}")
                if len(new_failures) > 6:
                    print(f"      … 외 {len(new_failures) - 6}개")

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


def _runnable(nodeid: str, root: Path) -> bool:
    """지금 코드에 아직 있는 시험인가. 없는 이름을 넘기면 pytest 가 통째로 멈춘다."""
    file_part = nodeid.split("::")[0]
    path = root / file_part
    if not path.is_file() or "::" not in nodeid:
        return False
    name = nodeid.split("::")[-1].split("[")[0]
    return f"def {name}(" in path.read_text(encoding="utf-8", errors="replace")


def recheck_all(target: Path, *, only: list[str] | None = None) -> dict[str, Any]:
    """결함마다 지난번에 그 결함을 잡은 시험만 다시 돌려, 지금 코드에서도 우는지 본다.

    전체 관문은 결함마다 cs 시험 전체를 돌린다. 시험이 4,005개로 늘자 한 바퀴가 11분,
    43개면 8시간쯤 걸린다(2026-10-06 실측 656초 × 43, 예상). 재확인은 빠른 대신 보는 것이 좁다 —
    새로 생긴 다른 시험이 그 결함을 잡는지는 보지 않는다. 카탈로그의 전체 관문 결과는 바꾸지 않고
    entries[id]["recheck"] 에만 적는다.
    """
    catalog = defects_mod.load_catalog()
    entries = catalog.get("entries", {})
    report: dict[str, Any] = {"entries": {}, "baseline": None}
    with Sandbox(target) as sandbox:
        assert sandbox.root is not None
        plan: dict[str, list[str]] = {}
        dropped: dict[str, int] = {}
        for defect in defects_mod.DEFECTS:
            if only is not None and defect.defect_id not in only:
                continue
            old = entries.get(defect.defect_id, {}).get("failed", [])
            keep = [n for n in old if _runnable(n, sandbox.root)]
            plan[defect.defect_id] = keep
            dropped[defect.defect_id] = len(old) - len(keep)
        union = sorted({n for ids in plan.values() for n in ids})
        print(f"재확인 — 결함 {len(plan)}개, 다시 돌릴 시험 {len(union)}개(지난번에 결함을 잡은 시험 중 지금도 있는 것)")
        baseline = sandbox.pytest(union) if union else None
        if baseline is None or (" passed" not in baseline.summary and " failed" not in baseline.summary):
            print(f"  ✗ 기준선에서 시험이 돌지 않았다: {baseline.summary if baseline else '돌릴 시험 없음'}")
            return report
        sandbox.sweep()
        known_broken = set(baseline.failed)
        report["baseline"] = {"summary": baseline.summary, "failed": sorted(known_broken)}
        print(f"  기준선 {baseline.summary}" + (f" — 결함 없이도 {len(known_broken)}건 실패, 판정에서 뺀다"
                                              if known_broken else ""))
        for defect_id, selection in plan.items():
            defect = defects_mod.by_id(defect_id)
            patch = defects_mod.PATCH_DIR / f"{defect_id}.patch"
            usable = [n for n in selection if n not in known_broken]
            if not usable:
                print(f"\n{defect_id}  ? 다시 돌릴 시험이 없다(사라졌거나 결함 없이도 실패) — 전체 관문으로만 판정할 수 있다")
                report["entries"][defect_id] = {"state": "no_tests", "dropped": dropped[defect_id]}
                continue
            applied, message = sandbox.apply(patch)
            if not applied:
                print(f"\n{defect_id}  X 적용 실패: {message}")
                report["entries"][defect_id] = {"state": "apply_failed", "error": message}
                continue
            result = sandbox.pytest(usable)
            sandbox.sweep()
            sandbox.apply(patch, reverse=True)
            if " passed" not in result.summary and " failed" not in result.summary:
                print(f"\n{defect_id}  ? 시험이 돌지 않았다: {result.summary}")
                report["entries"][defect_id] = {"state": "not_run", "summary": result.summary}
                continue
            caught = sorted(set(result.failed) & set(usable))
            mark = "✓" if caught else "✗"
            print(f"\n{defect_id}  {mark} 다시 돌린 {len(usable)}개 중 {len(caught)}개가 울었다  {defect.title}")
            report["entries"][defect_id] = {"state": "caught" if caught else "missed",
                                             "ran": len(usable), "caught": len(caught),
                                             "dropped": dropped[defect_id], "summary": result.summary}
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
                              "drift": [], "missing": [], "source_missing": []}
    with Sandbox(target) as sandbox:
        assert sandbox.root is not None
        for defect in defects_mod.DEFECTS:
            patch = defects_mod.PATCH_DIR / f"{defect.defect_id}.patch"
            source = sandbox.root / defect.path
            if not patch.exists():
                report["missing"].append(defect.defect_id)
                continue
            # 겨누는 파일 자체가 없으면 앵커를 볼 수도 없다. 죽지 말고 보고한다 —
            # 도메인이 바뀌어 Team 코드가 통째로 지워졌을 때 실제로 여기서 죽었다.
            if not source.exists():
                report["source_missing"].append((defect.defect_id, defect.path))
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
        for defect_id, path in report["source_missing"]:
            print(f"  ✗ 겨누는 파일이 없다     {defect_id}  ({path} — 지워졌거나 옮겨졌다)")
        for defect_id in report["missing"]:
            print(f"  ✗ patch 파일이 없다      {defect_id}")
    return report
