"""공유 원본에서는 읽기와 fetch만 허용하는 Git 진입점. 자료를 삭제하거나 복원하지 않는다."""
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
READ_COMMANDS = {"status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "ls-remote", "for-each-ref", "check-ignore", "cat-file", "merge-base", "rev-list", "describe", "fetch", "version"}
ALWAYS_DENY = {"clean", "reset", "restore", "sparse-checkout", "read-tree", "update-index", "prune", "rm"}


def permitted(args: list[str], original: bool) -> bool:
    if not args or args[0].startswith("-"):
        return False  # -C, -c, --git-dir로 검사 대상을 바꾸지 못하게 한다.
    if any(arg in {"-f", "--force", "--force-with-lease"} or arg.startswith(("--output", "--work-tree", "--git-dir", "--exec-path")) for arg in args):
        return False
    verb = args[0]
    if verb in ALWAYS_DENY:
        return False
    if verb == "worktree":
        return args[1:] == ["list"]
    if original:
        return verb in READ_COMMANDS
    return verb in READ_COMMANDS | {"add", "commit", "push", "merge", "cherry-pick", "checkout", "switch"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf8")
    args = sys.argv[1:]
    if args == ["--self-test"]:
        cases = [(["status"], True, True), (["fetch", "team"], True, True), (["checkout", "main"], True, False), (["pull"], True, False), (["reset", "--hard"], False, False), (["clean", "-fdx"], False, False), (["-C", "elsewhere", "status"], True, False), (["worktree", "remove", "x"], False, False), (["commit", "-m", "x"], False, True), (["restore", "."], True, False), (["diff", "--output=datasets/file"], True, False), (["checkout", "-f", "main"], False, False)]
        for argv, original, wanted in cases:
            assert permitted(argv, original) == wanted, argv
        print(f"삭제 없는 Git 명령 판정 시험 {len(cases)}/{len(cases)}")
        return 0
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, env=env)
    if repo.returncode:
        print("로컬 자료 보호: Git 작업 폴더를 확인하지 못해 중단했습니다.", file=sys.stderr)
        return 2
    original = Path(repo.stdout.strip()).resolve() == ROOT
    if not permitted(args, original):
        print("로컬 자료 보호: 이 Git 명령은 차단했습니다. 원본 동기화·삭제는 하지 않습니다.", file=sys.stderr)
        return 2
    return subprocess.run(["git", *args], env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
