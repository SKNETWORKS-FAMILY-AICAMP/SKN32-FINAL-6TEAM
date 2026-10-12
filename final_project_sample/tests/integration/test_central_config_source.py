"""대상이 중앙 저장소에서 자기 선언을 읽는다 — 결정 문서 3단계.

★핵심 성질 셋
  1. 설정이 `file` 이면 지금까지와 똑같다 (하위호환)
  2. 설정이 `central` 이면 중앙에서 읽는다
  3. 중앙에 못 붙거나 선언이 없으면 **기동을 거부한다**(fail-fast) —
     무엇이 켜져 있는지 모르는 채로 트래픽을 받지 않는다
"""
from __future__ import annotations

from uuid import uuid4

import pytest
import yaml

from acop_basement.core.config_store import PostgresConfigStore
from acop_basement.application.config_source import configured_store, load_active_config
from acop_basement.core.project_config import load_project_config
from acop_basement.core.settings import get_settings
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.tools.read_tools import ReadToolbox
from app.composition import build_registry


def _repo_declaration() -> dict:
    from pathlib import Path
    return yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))


@pytest.fixture()
def central(monkeypatch):
    """중앙 저장소에 이 테스트 전용 대상 하나를 등록한다."""
    deployment_id = "test-central-" + uuid4().hex
    declaration = _repo_declaration()
    PostgresConfigStore(get_connection, deployment_id).create(declaration)

    settings = get_settings()
    monkeypatch.setattr(settings, "config_source", "central")
    monkeypatch.setattr(settings, "deployment_id", deployment_id)
    try:
        yield deployment_id, declaration
    finally:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM project_configs WHERE deployment_id = %s",
                            (deployment_id,))


# ── 하위호환 ─────────────────────────────────────────────────────────
def test_file_mode_is_the_default_and_unchanged():
    settings = get_settings()
    assert settings.config_source == "file"
    assert configured_store() is None
    assert load_active_config().teams, "파일 모드가 지금까지처럼 읽혀야 한다"


# ── 중앙 모드 ────────────────────────────────────────────────────────
def test_central_mode_reads_the_declaration_from_the_store(central):
    _deployment_id, declaration = central

    config = load_active_config()

    assert [t.team_id for t in config.teams] == [t["team_id"] for t in declaration["teams"]]


def test_central_mode_sees_a_change_made_in_the_store(central):
    """★캐시하지 않는다 — 바꿨는데 그대로면 "왜 안 바뀌냐" 가 된다."""
    deployment_id, declaration = central
    store = PostgresConfigStore(get_connection, deployment_id)
    before = load_active_config().revision

    changed = {**declaration, "modules": {**declaration["modules"],
                                          "graph_store": {"enabled": False}}}
    # ★base_revision 은 지금 저장된 내용에서 계산된 값이다. 임의 문자열을 쓰면
    #   CAS 가 막는다 — 그게 이 설계가 의도한 동작이다(2026-08-30 실측).
    store.write(changed, base_revision=before, new_revision="rev-next")

    after = load_active_config()
    assert after.revision != before
    assert after.module_enabled("graph_store") is False


def test_explicit_path_still_wins_over_the_configured_source(central, tmp_path):
    """검증 도구·테스트가 특정 선언을 직접 지목할 수 있어야 한다."""
    _deployment_id, declaration = central
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")

    assert load_active_config(path).teams  # 중앙이 아니라 이 파일을 읽는다


def test_unregistered_deployment_refuses_to_start(monkeypatch):
    """★fail-fast — 선언이 없으면 기본값으로 도는 대신 멈춘다."""
    settings = get_settings()
    monkeypatch.setattr(settings, "config_source", "central")
    monkeypatch.setattr(settings, "deployment_id", "test-missing-" + uuid4().hex)

    with pytest.raises(Exception, match="선언이 없다"):
        load_active_config()


def test_central_mode_without_a_deployment_id_fails(monkeypatch):
    """어느 대상의 선언인지 모르는 채로 기동하면 안 된다."""
    settings = get_settings()
    monkeypatch.setattr(settings, "config_source", "central")
    monkeypatch.setattr(settings, "deployment_id", "")

    with pytest.raises(Exception, match="deployment_id"):
        configured_store()


# ── 조립까지 ─────────────────────────────────────────────────────────
def test_the_registry_assembles_from_the_central_declaration(central):
    """★읽기만으로 끝이 아니라 실제 조립이 돼야 의미가 있다."""
    registry = build_registry(
        tools=ReadToolbox(tool_functions={"read.policy": lambda _c, **_k: "정책"}),
        config=load_active_config())

    assert registry.manifests(), "중앙 선언으로 Team 이 조립돼야 한다"
