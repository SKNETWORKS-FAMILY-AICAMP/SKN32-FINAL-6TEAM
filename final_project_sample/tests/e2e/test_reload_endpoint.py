"""`POST /admin/reload` — 재기동 없이 바뀐 선언을 반영한다.

★2026-08-19 설계검토는 후보 3(재기동 요구)을 골랐고, 재검토 트리거로
  "대상과 Composer 가 같은 durable config store 를 쓰기로 정해진 때" 를 남겼다.
  중앙 설정 저장소(2026-08-30)로 그 조건이 충족돼 후보 2(관리자 신호)를 넣는다.

★검사하는 것: 인증·scope 분리, 성공 시 active 가 실제로 옮겨가는가,
  **실패 시 옛 조립이 살아남는가**, 그리고 그 실패가 200 뒤에 숨지 않는가.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from acop_basement.core.settings import get_settings
from acop_basement.presentation.api.app import create_app
from acop_basement.presentation.security import _development_key


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _auth(scope: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_development_key(scope, get_settings().secret_key)}"}


def test_requires_authentication(client):
    assert client.post("/admin/reload").status_code == 401


def test_introspect_scope_cannot_trigger_a_reload(client):
    """★조회 권한으로 살아 있는 트래픽의 조립을 갈아 끼울 수 있으면 안 된다."""
    assert client.post("/admin/reload", headers=_auth("ops:introspect")).status_code == 403


def test_composer_write_scope_cannot_trigger_a_reload(client):
    """★저장하는 사람과 반영 시점을 정하는 사람은 다를 수 있다."""
    assert client.post("/admin/reload", headers=_auth("composer:write")).status_code == 403


def test_reload_reports_the_revision_it_actually_activated(client):
    response = client.post("/admin/reload", headers=_auth("ops:reload"))
    assert response.status_code == 200
    body = response.json()

    assert body["reload_state"] == "active"
    assert body["active_revision"] == body["desired_revision"]
    assert body["active_revision"]

    snap = client.get("/introspection", headers=_auth("ops:introspect")).json()
    assert snap["active_revision"] == body["active_revision"]
    assert snap["reload_state"] == "active"


def test_a_failed_rebuild_keeps_the_running_composition(client, monkeypatch):
    """★반쯤 바뀐 상태를 만들지 않는다 — 새 조립이 전부 성공한 뒤에만 갈아 낀다."""
    from app import composition

    before = client.get("/introspection", headers=_auth("ops:introspect")).json()
    assert before["active_revision"]

    def explode(**_kwargs):
        raise RuntimeError("team 'broken' 을 만들지 못했다")

    monkeypatch.setattr(composition, "build_controller", explode)
    response = client.post("/admin/reload", headers=_auth("ops:reload"))

    assert response.status_code == 409
    detail = response.json()["error"]
    assert detail["code"] == "reload_failed"
    # 옛 조립이 그대로 살아 있어야 한다
    assert detail["active_revision"] == before["active_revision"]

    monkeypatch.undo()
    after = client.get("/introspection", headers=_auth("ops:introspect")).json()
    assert after["active_revision"] == before["active_revision"]
    assert after["reload_state"] == "reload_failed"
    assert "broken" in (after["reload_error"] or "")


def test_requests_keep_working_after_a_reload(client):
    """★프록시가 새 Controller 로 넘어가되, 표면은 그대로 살아 있어야 한다."""
    assert client.post("/admin/reload", headers=_auth("ops:reload")).status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/introspection", headers=_auth("ops:introspect")).status_code == 200
