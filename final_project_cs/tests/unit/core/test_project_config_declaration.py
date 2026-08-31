"""구성 선언 조회 — 2026-08-31 추가.

선언되지 않은 모듈을 물었을 때 `True` 를 돌려주도록 바꿔도 전체 424개가 전부
통과했다. 그러면 끈 줄 알았던 기능이 실제로는 돌아가고, 구성 선언이 실제 조립을
지배하지 못한다.
"""

from __future__ import annotations

import pytest

from app.core.project_config import ProjectConfigError, load_project_config


def test_undeclared_module_raises_instead_of_defaulting() -> None:
    config = load_project_config()
    with pytest.raises(ProjectConfigError, match="not declared"):
        config.module_enabled("module_that_is_not_declared")


def test_require_module_on_undeclared_module_also_raises() -> None:
    """require_module 은 module_enabled 를 거치므로 같은 곳에서 막혀야 한다."""
    config = load_project_config()
    with pytest.raises(ProjectConfigError):
        config.require_module("module_that_is_not_declared", "any_operation")


def test_declared_modules_answer_a_boolean() -> None:
    config = load_project_config()
    assert config.modules, "project.yaml 에 선언된 모듈이 하나도 없다"
    for module_id in config.modules:
        assert isinstance(config.module_enabled(module_id), bool)
