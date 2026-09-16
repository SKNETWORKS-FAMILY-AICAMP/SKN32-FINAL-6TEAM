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


#: 처음부터 쌓아 보는 모드가 쓰는 저장소. 코어가 `acop_basement/` 한 패키지에 모여 있어
#: "빈 폴더에서 한 층씩" 이 성립한다. cs 는 코어와 도메인이 같은 `app/` 안에 섞여 있다.
BUILD_TARGET_REL = "final_project_sample"
BUILD_PACKAGE = "acop_basement"


def build_target_root() -> Path:
    override = os.environ.get("ACOP_DOJO_BUILD_TARGET")
    if override:
        return Path(override).resolve()
    return (WORKSPACE_ROOT / BUILD_TARGET_REL).resolve()


def build_workspace() -> Path:
    """학습자가 직접 쌓는 작업 폴더. git 에 올라가지 않는 곳에 둔다."""
    override = os.environ.get("ACOP_DOJO_BUILD_WORKSPACE")
    if override:
        return Path(override).resolve()
    return WORKSPACE_ROOT / ".acop_dojo" / "build" / BUILD_TARGET_REL


def data_dir() -> Path:
    return DOJO_ROOT / "data"


def progress_path() -> Path:
    """진행 상태 파일. 웹 지도가 읽는 유일한 입력이기도 하다."""
    override = os.environ.get("ACOP_DOJO_PROGRESS")
    if override:
        return Path(override).resolve()
    return WORKSPACE_ROOT / ".acop_dojo" / "progress.json"
