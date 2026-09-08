"""프로젝트 탐지.

★검사하는 것은 "찾는다" 가 아니라 **"아닌 것을 프로젝트라고 하지 않는다"** 다.
  목록이 틀리면 그 뒤의 모든 화면이 엉뚱한 폴더를 읽는다.

★테스트는 **이 저장소가 만든 임시 폴더만** 쓴다.
  실제 형제 프로젝트(`final_project_sample` 등)를 읽지 않는다 — 허가 없이 남의 폴더를
  여는 것은 이 저장소의 규칙 위반이다(`CLAUDE.md` §0.1).
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from console.discovery import discover, inspect_path, projects_only


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


def make_project(root: Path, name: str, *, evidence=False, reports=False) -> Path:
    path = root / name
    (path / "config").mkdir(parents=True)
    (path / "config" / "project.yaml").write_text("modules: {}\n", encoding="utf-8")
    if evidence:
        (path / "wiki" / "records" / "evidence").mkdir(parents=True)
    if reports:
        (path / "eval" / "reports").mkdir(parents=True)
    return path


# ── 찾아야 하는 것 ────────────────────────────────────────────────────────────
def test_a_folder_with_the_marker_is_a_project(root):
    path = make_project(root, "alpha")
    result = inspect_path(path)
    assert result.is_project
    assert result.name == "alpha"
    assert any("project.yaml" in reason for reason in result.reasons)


def test_siblings_are_discovered_from_the_root(root):
    make_project(root, "alpha")
    make_project(root, "beta")
    (root / "not-a-project").mkdir()
    names = {p.name for p in projects_only(discover(root))}
    assert names == {"alpha", "beta"}


def test_optional_sources_are_reported(root):
    path = make_project(root, "alpha", evidence=True)
    result = inspect_path(path)
    assert result.sources["evidence"] is True
    assert result.sources["eval_reports"] is False
    # ★없는 것도 이유에 적는다 — 화면이 "왜 비었나" 에 답해야 한다
    assert any("없는 자료" in reason for reason in result.reasons)


# ── 프로젝트라고 하면 안 되는 것 ───────────────────────────────────────────────
def test_a_plain_folder_is_not_a_project(root):
    (root / "docs").mkdir()
    result = inspect_path(root / "docs")
    assert not result.is_project
    assert result.reasons == ["config/project.yaml 가 없다"]


def test_a_missing_path_is_not_a_project(root):
    result = inspect_path(root / "nope")
    assert not result.is_project
    assert result.reasons == ["경로가 없다"]


def test_a_file_is_not_a_project(root):
    target = root / "file.txt"
    target.write_text("x", encoding="utf-8")
    result = inspect_path(target)
    assert not result.is_project
    assert result.reasons == ["폴더가 아니다"]


def test_non_projects_stay_in_the_listing(root):
    """★조용히 빼지 않는다. "왜 내 폴더가 안 보이나" 에 답할 수 있어야 한다."""
    make_project(root, "alpha")
    (root / "scratch").mkdir()
    names = {p.name: p.is_project for p in discover(root)}
    assert names == {"alpha": True, "scratch": False}


def test_noise_folders_are_skipped(root):
    make_project(root, "alpha")
    for noise in (".git", "node_modules", "__pycache__", ".venv"):
        (root / noise).mkdir()
    assert {p.name for p in discover(root)} == {"alpha"}


# ── 깨진 선언을 가진 프로젝트도 목록에 남는다 ─────────────────────────────────
def test_a_project_with_an_unreadable_declaration_is_still_listed(root):
    """★판별은 **파일 존재**로만 한다.

    내용을 파싱해 판단하면 깨진 선언을 가진 프로젝트가 목록에서 통째로 사라진다 —
    정작 그 프로젝트야말로 콘솔로 봐야 하는 것이다.
    """
    path = root / "broken"
    (path / "config").mkdir(parents=True)
    (path / "config" / "project.yaml").write_text("{{{ not yaml", encoding="utf-8")
    assert inspect_path(path).is_project


def test_depth_one_by_default_does_not_walk_into_projects(root):
    """깊게 훑으면 남의 하위 폴더까지 잡고 느려진다."""
    outer = make_project(root, "alpha")
    make_project(outer, "nested")
    assert {p.name for p in projects_only(discover(root))} == {"alpha"}
    assert {p.name for p in projects_only(discover(root, depth=2))} == {"alpha"}
