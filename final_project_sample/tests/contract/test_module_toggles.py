"""`config/project.yaml` 의 모듈 토글이 실제로 코드를 가르는지 검사한다.

★2026-08-31 이전에는 여섯 모듈 중 `mcp` 와 `voc` 에 게이트가 아예 없었다.
  화면에서 꺼도 개인 AI 의 read-only 접근과 인라인 분류와 VOC 화면이 그대로였다.
  같은 결함을 `final_project_cs` 에서 먼저 찾아 고쳤고(2026-08-30) 여기로 이식했다.
  이 파일은 그 상태로 되돌아가는 것을 막는다.

★게이트를 다는 자리가 cs 와 다르다. 이 저장소는 `acop_basement` 가 product(`app`)를
  import 할 수 없다(단독 설치 계약). 그래서 basement 안의 게이트는 basement 자신의
  로더(`acop_basement.application.config_source.load_active_config`)로 묻는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from acop_basement.core.project_config import ProjectConfig, ProjectConfigError
from app.composition import _MODULE_IMPLEMENTATIONS, build_classifier

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
        # ★이 저장소의 선언 스키마는 Team 을 최소 하나 요구한다(min_length=1).
        #   cs 에서 그대로 옮겨 오다 빈 목록으로 두어 ValidationError 를 봤다.
        "teams": [{"team_id": "feedback_analytics", "active": True,
                   "implementation_ref":
                       "app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam"}],
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
    import acop_basement.application.config_source as config_source
    from acop_basement.application.feedback_job import run_daily_feedback

    monkeypatch.setattr(config_source, "load_active_config",
                        lambda *a, **k: _config(voc=False))
    with pytest.raises(ProjectConfigError, match="voc.*disabled"):
        # 연결은 쓰이지 않는다 — 게이트가 DB 를 건드리기 전에 막는다.
        run_daily_feedback(None, report_date=None, tenant_id="demo")


def test_disabled_voc_removes_the_voc_screen_and_its_menu():
    from acop_basement.presentation.ui import mount_ui
    import acop_basement.presentation.ui.routes as routes

    client = TestClient(mount_ui(FastAPI(), config=_config(voc=False)))
    try:
        assert client.get("/ops/voc").status_code == 404
        # 없는 화면으로 가는 링크를 남기면 눌렀을 때 404 가 뜨고 서버가 죽은 줄 안다.
        assert all(href != "/ops/voc" for href, _ in routes._NAV)
    finally:
        # ★메뉴는 모듈 전역이다. 되돌리지 않으면 다음 테스트가 잘린 메뉴를 본다.
        mount_ui(FastAPI(), config=_config())


def test_enabled_voc_keeps_the_screen_and_menu():
    from acop_basement.presentation.ui import mount_ui
    import acop_basement.presentation.ui.routes as routes

    client = TestClient(mount_ui(FastAPI(), config=_config()))
    assert client.get("/ops/voc").status_code != 404
    assert any(href == "/ops/voc" for href, _ in routes._NAV)


# ── mcp ─────────────────────────────────────────────────────────────────────
def test_disabled_mcp_refuses_every_tool(monkeypatch):
    """tool 세 개가 전부 `_mcp_principal` 을 지나므로 여기 하나만 막으면 된다."""
    import acop_basement.application.config_source as config_source
    from acop_basement.presentation.api import cases

    monkeypatch.setattr(config_source, "load_active_config",
                        lambda *a, **k: _config(mcp=False))
    for call in (lambda: cases._mcp_cases("c", 10),
                 lambda: cases._mcp_detail("c", "d"),
                 lambda: cases._mcp_open("c", "m", "mcp")):
        with pytest.raises(ProjectConfigError, match="mcp.*disabled"):
            call()


# ── graph_store ─────────────────────────────────────────────────────────────
def test_ui_does_not_reach_for_the_graph_adapter():
    """★cs 와 달리 여기 화면은 그래프를 쓰지 않는다. 쓰지도 않는 import 만 남아 있었다.

    관리자 화면이 `final_project_ui` 로 나가면서 생긴 잔재다. 남겨 두면 다음 사람이
    조립 경계를 건너뛰고 그것을 쓰게 된다 — cs 에서 실제로 그렇게 됐다.
    """
    source = (REPO_ROOT / "acop_basement" / "presentation" / "ui" / "routes.py").read_text(
        encoding="utf-8")
    assert "SqlGraphAdapter" not in source


# ── 계층 경계 ────────────────────────────────────────────────────────────────
def test_basement_never_imports_the_product_at_module_level():
    """★basement 는 product(`app`)를 **최상위에서** import 할 수 없다.

    함수 안 지연 import 는 허용된 설계다 — `acop_basement` 는 cs 가 설치하는
    pip 패키지이고, product 조립 루트는 실제로 필요할 때만 부른다
    (`presentation/api/app.py` 주석, 2026-08-19 버그헌팅 라운드9). 최상위 import 는
    그 계약을 깬다. 패키지를 단독 설치하면 import 자체가 실패하기 때문이다.

    ★이 테스트를 처음에 "app 을 아예 import 하지 않는다" 로 짰다가 6건이 걸렸다.
      전부 의도된 지연 import 였다. 검사기가 규칙을 잘못 적으면 멀쩡한 코드를
      결함으로 만든다.
    """
    offenders = []
    for path in (REPO_ROOT / "acop_basement").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("from app.", "from app import", "import app.")):
                offenders.append("%s: %s" % (path.relative_to(REPO_ROOT), line.strip()))
    assert not offenders, "basement 최상위 import: " + " / ".join(offenders)


# ── 회귀 방지 ────────────────────────────────────────────────────────────────
def test_every_declared_module_has_a_gate():
    """선언된 모듈 전부가 어딘가에서 실제로 검사돼야 한다.

    ★이 테스트가 이 파일의 핵심이다. 모듈을 새로 추가하면서 게이트를 안 다는
      실수가 `mcp` 와 `voc` 에서 실제로 일어났다. 이름만 늘고 토글은 아무것도
      안 하는 상태가 조용히 만들어진다.
    ★모듈 이름에 숫자가 들어간다(a2a_executor). 정규식을 `[a-z_]+` 로 짜면 이 모듈만
      조용히 빠진다 — cs 에서 실제로 그랬다. 검사기가 검사 대상을 못 보는 쪽이 더 위험하다.
    """
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for root in ("acop_basement", "app")
        for path in (REPO_ROOT / root).rglob("*.py"))
    gated = set(re.findall(r'(?:require_module|module_enabled)\(\s*"([a-z0-9_]+)"', sources))
    missing = sorted(_MODULE_IMPLEMENTATIONS - gated)
    assert not missing, f"게이트가 없는 모듈: {', '.join(missing)}"
