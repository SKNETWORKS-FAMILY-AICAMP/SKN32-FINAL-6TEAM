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
#: 대상 저장소 밖(워크스페이스의 datasets/)은 사본에 넣지 않는다. 그 폴더는 개인 구매기록이라
#: git 에서 뺐고, 그것을 읽던 scripts/seed.py 도 여행 전환 때 지워졌다(2026-09-14).


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
        # ★사본에 빈 git 저장소를 만든다. 원본의 .git 은 복사하지 않는다(무겁고, 사본에서
        #   커밋이 섞일 수 있다). 그런데 .git 이 아예 없으면 `git check-ignore` 를 부르는
        #   테스트가 사본에서만 실패해 기준선을 깬다 — 2026-09-14 test_api_key_file 이 그랬다.
        #   반대 방향 검사(템플릿이 무시되지 않는가)는 오히려 '저장소 아님' 오류로 우연히 통과했다.
        #   빈 저장소 하나로 둘 다 원본과 같게 돈다. git apply 도 그대로 된다(실측).
        subprocess.run(["git", "init", "-q"], cwd=self.root, capture_output=True, check=False)
        # ★색인에도 올린다(커밋은 안 한다). `git ls-files` 로 추적 파일을 훑는 검사가 있어서,
        #   빈 저장소면 "추적 파일을 하나도 못 읽었다" 로 사본에서만 실패한다(2026-09-21 실측).
        subprocess.run(["git", "-c", "core.autocrlf=false", "add", "-A"],
                       cwd=self.root, capture_output=True, check=False)
        return self

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
        proc = subprocess.run(args, cwd=self.root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=False)
        return proc.returncode == 0, (proc.stderr or proc.stdout or "").strip()

    def check(self, patch: Path) -> tuple[bool, str]:
        proc = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "apply", "-p1", "--unsafe-paths",
             "--check", str(patch.resolve())],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False)
        return proc.returncode == 0, (proc.stderr or proc.stdout or "").strip()

    def pytest(self, selection: list[str] | None = None, *, timeout: int = 900) -> RunResult:
        # ★-rfE — 실패(F)와 오류(E)를 둘 다 요약에 올린다. 예전엔 -rf 라 fixture·setup 오류가
        #   목록에 안 나와 판정에서 통째로 빠졌다(2026-09-14 게이트에서 한 회차 94건, 다른 회차 119건).
        args = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                "--tb=no", "-rfE"]
        args.extend(selection or [])
        try:
            proc = subprocess.run(args, cwd=self.root, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            # ★시간 초과를 예외로 터뜨리면 게이트가 통째로 죽는다(2026-09-21 cs 기준선에서 실제로 죽었다).
            #   결과로 말한다. 무엇을 돌리다 멈췄는지는 selection 이 들고 있다.
            return RunResult(124, sorted(selection or []),
                             f"{timeout}초 안에 끝나지 않았다 — 판정하지 못했다", "")
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
