"""`config/project.yaml` 의 모듈 토글이 실제로 코드를 가르는지 검사한다.

계약: `docs/handoff/08_모듈_컴포넌트_목록.md`

  §2 ★모듈을 빼면 그것을 부르는 경로도 함께 빠져야 한다. 남아 있으면
     `RULE.md` §3.2(폴백 금지)에 따라 조용히 넘어가지 말고 명시적으로 실패해야 한다.
  §6 빌드 시 실패시켜야 할 것 4. 꺼진 모듈을 부르는 경로가 남아 있다

★2026-08-30 이전에는 여섯 모듈 중 `mcp` 와 `voc` 에 게이트가 아예 없었고,
  `graph_store` 는 게이트를 우회하는 경로가 관리자 화면에 남아 있었다. 화면에서
  꺼도 동작이 그대로였다. 이 파일은 그 상태로 되돌아가는 것을 막는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.composition import _MODULE_IMPLEMENTATIONS, build_classifier
from app.core.project_config import ProjectConfig, ProjectConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]


def _config(**overrides) -> ProjectConfig:
    modules = {
        "vector_rag": {"enabled": True}, "graph_store": {"enabled": True},
        "a2a_executor": {"enabled": False}, "mcp": {"enabled": True},
        "voc": {"enabled": True}, "ops_ui": {"enabled": True},
    }
    for name, enabled in overrides.items():
        modules[name] = {"enabled": enabled}
    return ProjectConfig.model_validate({
        "modules": modules,
        "ports": {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"},
        "teams": [{"team_id": "voc_store_manager", "active": True,
                   "implementation_ref": "app.modules.customer_ops:VocStoreManagerTeam"}],
    })


# ── voc ─────────────────────────────────────────────────────────────────────
def test_disabled_voc_refuses_the_inline_classifier():
    """★분류를 건너뛰지 않고 실패한다.

    조용히 넘어가면 `intent`·`sentiment` 가 빈 채로 Case 가 만들어지고
    그 빈 값이 근거 조합을 거쳐 고객 답변까지 간다(`CLAUDE.md` §1).
    """
    with pytest.raises(ProjectConfigError, match="voc.*disabled"):
        build_classifier(config=_config(voc=False))


def test_disabled_voc_refuses_the_daily_batch(monkeypatch):
    import app.core.project_config as project_config
    from app.application.feedback_job import run_daily_feedback

    monkeypatch.setattr(project_config, "load_project_config",
                        lambda *a, **k: _config(voc=False))
    with pytest.raises(ProjectConfigError, match="voc.*disabled"):
        # 연결은 쓰이지 않는다 — 게이트가 DB 를 건드리기 전에 막는다.
        run_daily_feedback(None, report_date=None, tenant_id="demo")


def test_disabled_voc_removes_the_voc_screen_and_its_menu():
    import app.presentation.ui.routes as routes
    from app.presentation.ui import mount_ui

    client = TestClient(mount_ui(FastAPI(), config=_config(voc=False)))
    try:
        assert client.get("/ui/voc").status_code == 404
        # 없는 화면으로 가는 링크를 남기면 눌렀을 때 404 가 뜨고 서버가 죽은 줄 안다.
        assert all(href != "/ui/voc" for href, _ in routes._NAV)
    finally:
        # ★메뉴는 모듈 전역이다. 되돌리지 않으면 다음 테스트가 잘린 메뉴를 본다.
        mount_ui(FastAPI(), config=_config())


def test_enabled_voc_keeps_the_screen_and_menu():
    import app.presentation.ui.routes as routes
    from app.presentation.ui import mount_ui

    client = TestClient(mount_ui(FastAPI(), config=_config()))
    assert client.get("/ui/voc").status_code != 404
    assert any(href == "/ui/voc" for href, _ in routes._NAV)


# ── mcp ─────────────────────────────────────────────────────────────────────
def test_disabled_mcp_refuses_every_tool(monkeypatch):
    """tool 세 개가 전부 `_mcp_principal` 을 지나므로 여기 하나만 막으면 된다."""
    import app.core.project_config as project_config
    from app.presentation.api import cases

    monkeypatch.setattr(project_config, "load_project_config",
                        lambda *a, **k: _config(mcp=False))
    for call in (lambda: cases._mcp_cases("c", 10),
                 lambda: cases._mcp_detail("c", "d"),
                 lambda: cases._mcp_open("c", "m", "mcp")):
        with pytest.raises(ProjectConfigError, match="mcp.*disabled"):
            call()


# ── graph_store ─────────────────────────────────────────────────────────────
def test_admin_page_does_not_build_the_graph_adapter_directly():
    """★관리자 화면이 조립 경계를 우회하면 모듈을 꺼도 Graph 줄이 그대로 뜬다.

    2026-08-30 이전 상태다. import 자체를 막아 되돌아가지 못하게 한다.
    """
    source = (REPO_ROOT / "app" / "presentation" / "ui" / "routes.py").read_text(encoding="utf-8")
    # 왜 그랬는지 적은 주석은 남겨야 한다(`CLAUDE.md` §3). import 와 생성만 막는다.
    assert "from app.infrastructure.graphstore" not in source
    assert "SqlGraphAdapter(" not in source, (
        "운영 화면은 composition.build_graph_store 를 거쳐야 한다 (handoff/08 §6-4)")


def test_admin_page_says_graph_module_is_off_instead_of_hiding_it(monkeypatch):
    """숨기지 않고 껐다고 적는다. 빈칸은 "껐다"와 "고장났다"를 구별해 주지 못한다."""
    import app.composition as composition
    import app.presentation.ui.routes as routes

    # ★composition 은 load_project_config 를 자기 이름공간으로 가져왔다.
    #   원본 모듈만 갈아 끼우면 이 경로는 여전히 진짜 선언을 읽는다.
    monkeypatch.setattr(composition, "load_project_config",
                        lambda *a, **k: _config(graph_store=False))
    assert routes._graph_port_name("demo") == "모듈 꺼짐 (graph_store)"


def test_admin_page_names_the_adapter_when_graph_module_is_on(monkeypatch):
    import app.composition as composition
    import app.presentation.ui.routes as routes

    monkeypatch.setattr(composition, "load_project_config", lambda *a, **k: _config())
    assert routes._graph_port_name("demo") == "SqlGraphAdapter"


# ── 회귀 방지 ────────────────────────────────────────────────────────────────
def test_every_declared_module_has_a_gate():
    """선언된 모듈 전부가 어딘가에서 실제로 검사돼야 한다.

    ★이 테스트가 이 파일의 핵심이다. 모듈을 새로 추가하면서 게이트를 안 다는
      실수가 `mcp` 와 `voc` 에서 실제로 일어났다(2026-08-30 발견). 이름만 늘고
      토글은 아무것도 안 하는 상태가 조용히 만들어진다.
    """
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPO_ROOT / "app").rglob("*.py"))
    # ★모듈 이름에 숫자가 들어간다(a2a_executor). [a-z_]+ 로 짜서 이 모듈만
    #   조용히 빠졌었다 — 검사기가 검사 대상을 못 보는 쪽이 더 위험하다.
    gated = set(re.findall(r'(?:require_module|module_enabled)\(\s*"([a-z0-9_]+)"', sources))
    missing = sorted(_MODULE_IMPLEMENTATIONS - gated)
    assert not missing, f"게이트가 없는 모듈: {', '.join(missing)}"
