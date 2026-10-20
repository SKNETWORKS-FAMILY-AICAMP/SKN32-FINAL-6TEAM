# -*- coding: utf-8 -*-
"""평가 판본 기록 — 어떤 코드로 잰 수치인지 남긴다. `[2026-10-20]`

☆`[2026-10-20 실측]` 커밋 전 작업 트리에서 여러 세션이 고치는 동안 잰 수치가 섞였다(gpt-4o-mini 실행 중 `customer_requests.py` 가 생겼다).
  git 커밋만으로는 커밋 전 변경이 안 보인다 — 결과에 영향을 주는 파일의 내용 해시를 함께 남긴다.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:   # noqa: BLE001
        return None


def code_version(paths: Iterable[str]) -> dict[str, object]:
    """파일(또는 폴더 안 .py)마다 내용 sha256 앞 16자리 · 묶음 해시 · git 커밋 · 커밋 전 변경 여부.

    줄 끝(CRLF/LF)은 해시 전에 맞춘다 — 내용이 같으면 같은 해시다.
    """
    files: dict[str, str] = {}
    for item in paths:
        target = ROOT / item
        found = sorted(target.rglob("*.py")) if target.is_dir() else [target]
        for path in found:
            if "__pycache__" in path.parts or not path.exists():
                continue
            data = path.read_bytes().replace(b"\r\n", b"\n")
            files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(data).hexdigest()[:16]
    bundle = hashlib.sha256("".join(f"{k}={v}\n" for k, v in sorted(files.items())).encode()).hexdigest()[:16]
    dirty = _git("status", "--porcelain", "--", *files)
    return {"bundle": bundle, "git_commit": _git("rev-parse", "--short", "HEAD"), "uncommitted": bool(dirty), "files": files}
