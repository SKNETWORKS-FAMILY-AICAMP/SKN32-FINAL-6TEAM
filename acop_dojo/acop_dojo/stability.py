"""결함이 매번 같은 신호를 내는지 확인한다.

같은 문제를 두 번 풀었는데 다른 답이 나오면 학습 도구로 못 쓴다. 실제로
INV-STATE-001 은 세 번 중 두 번은 안 잡히고 한 번은 잡혔다.

두 가지를 구분한다.
- flaky: 같은 조건에서 반복해도 결과가 흔들린다.
- order-dependent: 혼자 돌리면 안 깨지는데 전체 안에서는 깨진다. 앞선 테스트가
  남긴 상태에 기대고 있다는 뜻이라, 결함이 아니라 테스트 격리의 문제다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import defect_stage
from . import defects as defects_mod
from .sandbox import Sandbox


def check(target: Path, *, repeats: int = 3, verbose: bool = True) -> dict[str, Any]:
    catalog = defects_mod.load_catalog()
    playable = defect_stage.playable(catalog)
    results: dict[str, Any] = {}

    with Sandbox(target) as sandbox:
        for defect_id in playable:
            defect = defects_mod.by_id(defect_id)
            patch = defects_mod.PATCH_DIR / f"{defect_id}.patch"
            expected = sorted(catalog["entries"][defect_id]["failed"])
            applied, message = sandbox.apply(patch)
            if not applied:
                results[defect_id] = {"verdict": "apply_failed", "detail": message}
                continue

            observed: list[list[str]] = []
            for _ in range(repeats):
                run = sandbox.pytest(expected)
                observed.append(sorted(run.failed))
                sandbox.sweep()
            sandbox.apply(patch, reverse=True)

            same = all(run == observed[0] for run in observed)
            if not same:
                verdict = "flaky"
            elif not observed[0]:
                verdict = "order_dependent"
            elif observed[0] == expected:
                verdict = "stable"
            else:
                verdict = "partial"
            results[defect_id] = {"verdict": verdict, "expected": expected,
                                  "observed": observed[0], "runs": repeats}
            if verbose:
                mark = {"stable": "✓", "partial": "~", "order_dependent": "!",
                        "flaky": "✗", "apply_failed": "✗"}[verdict]
                print(f"  {mark} {defect_id:20} {verdict:16} "
                      f"기대 {len(expected)}건 / 관측 {len(observed[0])}건")
    return results
