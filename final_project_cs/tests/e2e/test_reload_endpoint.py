"""`POST /admin/reload` — 재기동 없이 바뀐 선언을 반영한다 (2026-09-06 이식).

★왜 이제 왔나. `final_project_sample` 은 2026-08-31 에 이걸 넣고도 **릴리스
  대상인 여기에는 안 넣었다.** 그 결과 콘솔이 cs 대상에 대고 "저장됐지만 아직
  반영 전" 이라고만 말할 뿐 반영시킬 길이 없었고, 화면은 **없는 엔드포인트**를
  부르라고 안내하기까지 했다
  (`docs/reports/2026-09-06_Composer를_패키지로_들어냈다.md` §10).
  "한 쪽을 고치면 다른 쪽에 같은 결함이 남는다" 가 또 나온 자리다.

★검사하는 것: 인증·scope 분리, 성공 시 active 가 실제로 옮겨가는가,
  **실패 시 옛 조립이 살아남는가**, 그리고 그 실패가 200 뒤에 숨지 않는가.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.presentation.api.app import create_app
from app.presentation.security import _development_key

#: ★분류기를 주입해 LLM 없이 뜨게 한다. 이 파일이 재는 것은 분류가 아니라 반영이다.
_CLASSIFIER = lambda _text: {"intent": "billing", "issue_code": "x", "sentiment": "neutral"}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(classifier=_CLASSIFIER))


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


def test_composer_admin_scope_cannot_trigger_a_reload(client):
    """★선언 전체를 갈아끼우는 권한도 **반영** 권한은 아니다.

    `composer:admin` 은 저장소에 쓰는 권한이고, 반영은 그 순간 트래픽이 받는
    것을 바꾼다. 둘을 묶으면 "복원했더니 즉시 라이브가 바뀌었다" 가 된다.
    """
    assert client.post("/admin/reload", headers=_auth("composer:admin")).status_code == 403


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


def test_a_declaration_that_cannot_be_read_does_not_swap_anything(client, monkeypatch):
    """★선언을 못 읽는 것과 조립에 실패하는 것은 다르지만, **둘 다** 옛 조립을
    남긴다. 못 읽었는데 빈 조립으로 갈아 끼우면 그 순간 서비스가 죽는다."""
    from app import composition

    before = client.get("/introspection", headers=_auth("ops:introspect")).json()

    def unreadable(*_args, **_kwargs):
        raise RuntimeError("선언 파일이 YAML 이 아니다")

    monkeypatch.setattr(composition, "load_project_config", unreadable)
    response = client.post("/admin/reload", headers=_auth("ops:reload"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reload_failed"
    assert response.json()["error"]["active_revision"] == before["active_revision"]


def test_requests_keep_working_after_a_reload(client):
    """★프록시가 새 Controller 로 넘어가되, 표면은 그대로 살아 있어야 한다."""
    assert client.post("/admin/reload", headers=_auth("ops:reload")).status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/introspection", headers=_auth("ops:introspect")).status_code == 200
