"""도장이 바라보는 대상 저장소와 경로."""
from __future__ import annotations

import os
from pathlib import Path

#: 학습 대상. 워크스페이스 루트 기준 상대 경로.
TARGET_REL = "final_project_cs"

DOJO_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = DOJO_ROOT.parent
WORKSPACE_ROOT = PACKAGE_ROOT.parent


def target_root() -> Path:
    """학습 대상 저장소의 절대 경로. ACOP_DOJO_TARGET 으로 덮어쓸 수 있다."""
    override = os.environ.get("ACOP_DOJO_TARGET")
    if override:
        return Path(override).resolve()
    return (WORKSPACE_ROOT / TARGET_REL).resolve()


def data_dir() -> Path:
    return DOJO_ROOT / "data"


def progress_path() -> Path:
    """진행 상태 파일. 웹 지도가 읽는 유일한 입력이기도 하다."""
    override = os.environ.get("ACOP_DOJO_PROGRESS")
    if override:
        return Path(override).resolve()
    return WORKSPACE_ROOT / ".acop_dojo" / "progress.json"
