"""결함을 적용할 사본을 만든다.

원본 저장소는 절대 건드리지 않는다. 학습자가 커밋 안 된 작업을 하고 있을 수 있고,
결함 실험 도중 프로세스가 죽으면 되돌릴 방법이 없기 때문이다.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

#: 사본에 넣지 않는 것. 이름만으로 거르면 docs/reports 까지 날아가므로 경로로 판단한다.
SKIP_NAMES = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
#: 대상 저장소 기준 상대 경로. 용량만 크고 테스트가 쓰지 않는다.
SKIP_PATHS = {"eval/reports"}
#: 대상 저장소 밖을 읽는 곳이 하나 있다 — scripts/seed.py 가 워크스페이스의 datasets 를
#: 참조한다. datasets 전체는 2.4GB 라 통째로 복사할 수 없어 필요한 파일만 옮긴다.
SIBLING_FILES = ("datasets/commerce/coupang_order_history/processed/orders.jsonl",)


def _ignore_factory(root: Path):
    """`legacy/` 는 제외하면 안 된다 — unit 테스트 두 개가 거기서 import 한다."""

    def ignore(directory: str, names: list[str]) -> set[str]:
        here = Path(directory)
        # .pytest-basetemp 류는 권한이 막혀 있어 복사 자체가 실패한다.
        dropped = {
            name for name in names
            if name in SKIP_NAMES or name.endswith(".pyc") or name.startswith(".pytest")
        }
        for name in names:
            try:
                rel = (here / name).resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            if rel in SKIP_PATHS:
                dropped.add(name)
        return dropped

    return ignore


@dataclass
class RunResult:
    returncode: int
    failed: list[str]
    summary: str
    stdout: str


class Sandbox:
    """대상 저장소의 사본. with 블록을 벗어나면 지운다."""

    def __init__(self, target: Path) -> None:
        self.target = target
        self.root: Path | None = None
        self._tmp: str | None = None

    def __enter__(self) -> "Sandbox":
        self._tmp = tempfile.mkdtemp(prefix="acop_dojo_")
        self.root = Path(self._tmp) / self.target.name
        shutil.copytree(self.target, self.root,
                        ignore=_ignore_factory(self.target.resolve()), symlinks=False)
        self._mirror_siblings()
        return self

    def _mirror_siblings(self) -> None:
        workspace = self.target.parent
        assert self.root is not None
        for rel in SIBLING_FILES:
            source = workspace / rel
            if not source.exists():
                continue
            destination = self.root.parent / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def __exit__(self, *exc: object) -> None:
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)

    def sweep(self) -> int:
        """pytest 가 사본 안에 만든 임시 디렉터리를 지운다.

        같은 사본에서 전체 테스트를 스무 번 넘게 돌리면 이게 쌓여 디스크를 채운다.
        실제로 21개 결함을 검증하다 'No space left on device' 로 멈춘 적이 있다.
        """
        freed = 0
        assert self.root is not None
        for child in self.root.iterdir():
            if child.is_dir() and (child.name.startswith(".pytest") or child.name == ".cache"):
                freed += 1
                shutil.rmtree(child, ignore_errors=True)
        return freed

    def apply(self, patch: Path, *, reverse: bool = False) -> tuple[bool, str]:
        # check 와 같은 옵션이어야 한다. 달라지면 check 는 통과하고 apply 는 조용히 실패한다.
        # autocrlf 를 꺼야 한다. 사본에 .git 이 없어 전역 설정이 적용되는데, 켜져 있으면
        # LF 파일을 통째로 CRLF 로 바꿔 되돌린 뒤 바이트가 달라진다.
        args = ["git", "-c", "core.autocrlf=false", "apply", "-p1", "--unsafe-paths"]
        if reverse:
            args.append("-R")
        args.append(str(patch.resolve()))
        proc = subprocess.run(args, cwd=self.root, capture_output=True, text=True, check=False)
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()

    def check(self, patch: Path) -> tuple[bool, str]:
        proc = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "apply", "-p1", "--unsafe-paths",
             "--check", str(patch.resolve())],
            cwd=self.root, capture_output=True, text=True, check=False)
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()

    def pytest(self, selection: list[str] | None = None, *, timeout: int = 900) -> RunResult:
        args = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                "--tb=no", "-rf"]
        args.extend(selection or [])
        proc = subprocess.run(args, cwd=self.root, capture_output=True, text=True,
                              timeout=timeout, check=False)
        failed = []
        for line in proc.stdout.splitlines():
            if line.startswith("FAILED ") or line.startswith("ERROR "):
                failed.append(line.split(" ", 1)[1].split(" - ")[0].strip())
        summary = ""
        for line in reversed(proc.stdout.splitlines()):
            if " passed" in line or " failed" in line or " error" in line:
                summary = line.strip()
                break
        return RunResult(proc.returncode, sorted(set(failed)), summary, proc.stdout)
