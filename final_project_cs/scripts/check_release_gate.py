"""Run the local DoD-17 release gate as one reproducible command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN_FILES = (
    ROOT / "app" / "core" / "contracts.py",
    ROOT / "wiki" / "records" / "handoff" / "01_계약_Pydantic.md",
)


def _run(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode, output


def _pytest_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if " passed" in line or " failed" in line or " error" in line:
            return line
    return "출력 요약 없음"


def _git_root() -> Path | None:
    completed = subprocess.run(
        ["git", "-c", "safe.directory=*", "rev-parse", "--show-toplevel"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.returncode != 0:
        return None
    return Path(completed.stdout.strip()).resolve()


def _frozen_changes() -> list[str] | None:
    repository = _git_root()
    if repository is None:
        return ["git 저장소를 찾을 수 없음"]

    paths = [str(path.resolve().relative_to(repository)) for path in FROZEN_FILES]
    completed = subprocess.run(
        ["git", "-c", "safe.directory=*", "diff", "--name-only", "HEAD", "--", *paths],
        cwd=repository,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.returncode != 0:
        return [f"git diff 실행 실패 (exit {completed.returncode})"]
    changed = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return changed or None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("S-DOD17 automated release gate")
    results: list[tuple[str, bool, str]] = []

    # ★경로를 주지 않는다. `pytest tests` 로 부르면 **`eval/tests/` 14건이
    #   조용히 빠진다**(2026-09-02 실측: `pytest tests` 534 수집 vs `pytest` 548).
    #   빠지던 것 중에 `eval/tests/test_holdout_labeling.py` — DoD-15(RC 를 막고
    #   있는 바로 그 항목)의 라벨링 도구 테스트가 있었다. 게이트가 "통과"라고
    #   말하면서 정작 차단 항목의 테스트는 한 번도 안 돌린 셈이다.
    #   `CLAUDE.md` §6 이 정한 정본 전체 실행 명령도 경로 없는 `python -m pytest -q` 다.
    code, output = _run([sys.executable, "-m", "pytest", "-q", "-m", "not live"])
    results.append(("pytest -q -m 'not live' (저장소 전체)", code == 0, _pytest_summary(output)))

    code, output = _run([sys.executable, "-m", "scripts.verify_dod"])
    summary = next(
        (line.strip() for line in reversed(output.splitlines()) if "evidence 있음" in line),
        f"verify_dod exit {code}",
    )
    results.append(("python -m scripts.verify_dod", code == 0, summary))

    changed = _frozen_changes()
    if changed:
        detail = "변경: " + ", ".join(changed)
    else:
        detail = "최근 커밋(HEAD) 이후 동결 대상 변경 없음"
    results.append(("기능 동결 검사", not changed, detail))

    # ★커밋 ↔ Phase 매핑 (release_checklist §5-3 의 세 번째 미체크 항목).
    #   경로로 판정하므로 커밋 메시지를 사람이 읽어 대조하지 않아도 된다.
    #   `--strict` 는 Phase 를 못 정한 커밋이나 미매핑 경로가 있으면 실패한다 —
    #   새 디렉터리가 생겼는데 소유가 안 정해진 것을 조용히 넘기지 않기 위해서다.
    code, output = _run([sys.executable, "-m", "scripts.map_commits_to_phase",
                         "--count", "20", "--strict"])
    summary = next(
        (line.strip() for line in output.splitlines() if line.startswith("Phase 별 커밋 수")),
        f"map_commits_to_phase exit {code}",
    )
    results.append(("커밋↔Phase 자동 매핑 (최근 20개)", code == 0, summary))

    passed = sum(ok for _, ok, _ in results)
    failed = len(results) - passed
    print(f"결과: {passed} passed, {failed} failed")
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"- {status}: {name} — {detail}")
    if failed:
        print("실패 항목: " + ", ".join(name for name, ok, _ in results if not ok))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
