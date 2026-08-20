"""Run the local DoD-17 release gate as one reproducible command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN_FILES = (
    ROOT / "app" / "core" / "contracts.py",
    ROOT / "docs" / "handoff" / "01_계약_Pydantic.md",
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

    code, output = _run([sys.executable, "-m", "pytest", "tests", "-q", "-m", "not live"])
    results.append(("pytest tests -q -m 'not live'", code == 0, _pytest_summary(output)))

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
