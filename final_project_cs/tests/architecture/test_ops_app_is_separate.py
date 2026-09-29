# -*- coding: utf-8 -*-
"""운영 앱은 고객 API 앱과 **갈라져 있다** — 완료 기준을 시험으로 강제한다. `[2026-09-29 사용자 지시]`

「외부에서 절대 접근 못 하게, 가능한 물리적으로 분리」(ui 세션 전달 · Codex 합의 1단계). 이 파일이 보는 것:
  ① 고객 API 앱(8042)의 경로 목록과 직접 요청에 운영 화면 · 관리 API · 시나리오가 **0개**(404)
  ② 운영 앱 코드가 고객 API 앱 객체를 **import 하지 않는다**
  ③ 운영 앱은 이 기계 안에서만 — 루프백이 아닌 요청 403 · 0.0.0.0 으로 띄우기 거부
  ④ 운영 화면이 스스로 scope 키를 만들지 않는다
★이것은 1단계(같은 기계의 다른 프로세스)다 — 「물리 분리 완료」가 아니다(2단계: 다른 기계 · 사설망 + VPN · SSH 터널).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
#: 고객 앱에 있으면 안 되는 경로 머리 — 운영 화면 · 로그인 · 관리 API · 시나리오 · 시연 화면
OPS_PREFIXES = ("/ui", "/ops", "/admin", "/scenario", "/tripilot", "/login", "/logout")


def _customer_app():
    from app.presentation.api.app import create_app

    return create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"})


def test_the_customer_app_has_no_ops_route_at_all():
    paths = sorted({getattr(r, "path", "") for r in _customer_app().routes})
    leaked = [p for p in paths if p == "/" or p.startswith(OPS_PREFIXES)]
    assert leaked == [], leaked


@pytest.mark.parametrize("method, path", [
    ("GET", "/ui/cases"), ("GET", "/ui/login"), ("POST", "/ui/login"), ("GET", "/ui/approvals"),
    ("GET", "/ui/delegations"), ("GET", "/ops/outbox"), ("GET", "/ui/admin"), ("GET", "/ui/scenario"),
    ("GET", "/admin/limits"), ("PATCH", "/admin/limits"), ("POST", "/admin/reload"),
    ("GET", "/scenario/status"), ("GET", "/tripilot"), ("GET", "/"),
])
def test_asking_the_customer_app_for_an_ops_path_is_404(method, path):
    assert TestClient(_customer_app()).request(method, path).status_code == 404


def test_the_ops_app_has_the_console_the_limits_api_and_the_scenario_mode():
    from app.ops_entrypoint import create_ops_app

    paths = {getattr(r, "path", "") for r in create_ops_app().routes}
    for needed in ("/ui/login", "/ui/cases", "/ui/approvals", "/ui/delegations", "/ops/outbox", "/ui/admin",
                   "/ui/scenario", "/admin/limits", "/admin/limits/events", "/scenario/status", "/tripilot"):
        assert needed in paths, needed


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found |= {f"{node.module}.{a.name}" for a in node.names}
    return found


def test_the_ops_app_code_never_imports_the_customer_app():
    files = [ROOT / "app/ops_entrypoint.py", *sorted((ROOT / "app/presentation/ui").glob("*.py"))]
    offenders = {str(f.relative_to(ROOT)): sorted(i for i in _imports(f) if i.startswith("app.presentation.api"))
                 for f in files}
    assert {k: v for k, v in offenders.items() if v} == {}


def test_the_ops_screens_never_mint_a_scope_key():
    """★전에는 운영 화면이 서버 비밀키로 scope 키를 **만들어** 같은 프로세스 안에서 API 를 불렀다(D-CS-007)."""
    for f in sorted((ROOT / "app/presentation/ui").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
                {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "_development_key" not in names and "ASGITransport" not in names, f.name


def test_the_ops_app_refuses_requests_from_outside_this_machine():
    from app.ops_entrypoint import create_ops_app

    assert TestClient(create_ops_app(routers=[])).get("/health").status_code == 200
    outside = TestClient(create_ops_app(routers=[]), client=("10.20.30.40", 50000))
    for path in ("/health", "/ui/login", "/admin/limits"):
        response = outside.get(path)
        assert response.status_code == 403 and response.json()["error"]["code"] == "ops_local_only", path


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.0.10"])
def test_the_ops_app_will_not_bind_outside_loopback(host, capsys):
    from app.ops_entrypoint import main

    assert main(["--host", host]) == 2
    assert "127.0.0.1" in capsys.readouterr().err


def test_the_ops_port_does_not_collide_with_ports_in_use():
    import app.core.settings as settings_module

    port = settings_module.Settings.model_fields["ops_port"].default
    assert port == 8070 and port not in {3100, 3102, 3200, 3300, 8041, 8042, 8044, 8060}
