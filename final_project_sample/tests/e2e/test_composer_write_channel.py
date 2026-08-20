"""`/composer/validate`, `/composer/apply` — 릴리스 이후에도 남는 쓰기 채널.

★왜 필요한가 — `/ui/composer` HTML 폼은 인증이 전혀 없어 삭제됐다(2026-08-18,
  `docs/handoff/09_Composer_GUI_계약.md`). 이 두 엔드포인트는 그 HTML 페이지의
  존재·토글과 무관하게 항상 등록된다 — `final_project_ui` 같은 외부 콘솔이
  이 API 로 계속 모듈을 켜고 끈다.
  이게 지켜지는지가 이 파일의 핵심 검사 대상이다
  (`docs/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md`).

★검사하는 것: 인증·scope 분리, JWT 만료/위조 거부, HTML 이 꺼져도 API 는 산다,
  validate 는 파일을 안 건드린다, 구현 안 된 참조는 거부한다, 동시 apply 는
  1건만 이긴다(409). `docs/handoff/13` "테스트 계약" 절이 이 목록을 규정한다.
"""
from __future__ import annotations

import threading
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from fastapi.testclient import TestClient

from acop_basement.core.settings import get_settings
from acop_basement.presentation.api.app import create_app
from acop_composer.api import router as composer_write_router
from acop_composer.auth import router as composer_auth_router
import jwt
from datetime import datetime, timedelta, timezone


def _token(scope: str | list[str]) -> str:
    scopes = [scope] if isinstance(scope, str) else scope
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": "test-actor", "aud": "final_project_sample", "scope": scopes,
                       "iat": now, "exp": now + timedelta(minutes=30), "jti": str(uuid4())},
                      get_settings().composer_jwt_secret, algorithm="HS256")


def _auth(scope: str = "composer:write") -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(scope)}"}


def _declaration(tmp_path: Path, *, ops_ui_enabled: bool = True) -> Path:
    source = Path("config/project.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["modules"]["ops_ui"]["enabled"] = ops_ui_enabled
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def config_dir():
    path = Path(".composer-write-e2e-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def _client(path: Path) -> TestClient:
    # ★acop_composer 는 acop_basement 와 별도 패키지다(2026-08-19 구조
    #   확정) — "관리용 빌드"만 이렇게 명시적으로 라우터를 주입한다.
    app = create_app(composer_write_router=composer_write_router, composer_auth_router=composer_auth_router)
    # ★HTML 라우터(`app/presentation/ui/composer.py`)와 같은 관례 —
    #   실제 config/project.yaml 을 건드리지 않고 임시 선언으로 검사한다.
    app.state.project_config_path = path
    # ★같은 이유로 audit 경로도 주입한다 — 아니면 이 테스트가 돌 때마다
    #   실제 var/audit/composer_events.jsonl 에 가짜 apply 이벤트가 쌓인다.
    app.state.composer_audit_path = path.with_name("composer_events.jsonl")
    return TestClient(app)


def test_requires_authentication(config_dir):
    client = _client(_declaration(config_dir))
    assert client.get("/composer/current").status_code == 401


def test_wrong_scope_is_rejected(config_dir):
    """★조회 scope(`ops:introspect`)로는 쓰기 채널을 못 연다 — 읽기·쓰기는 분리된다."""
    client = _client(_declaration(config_dir))
    response = client.get("/composer/current", headers=_auth("ops:introspect"))
    assert response.status_code == 403


def test_expired_token_is_rejected(config_dir):
    """★`docs/handoff/13` "테스트 계약" 이 요구하는 JWT 만료 검사.

    TTL 이 지난 토큰은 서명이 유효해도 401 이다 — `exp` 를 과거로 발급한다.
    """
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": "test-actor", "aud": "final_project_sample", "scope": ["composer:read"],
         "iat": now - timedelta(hours=2), "exp": now - timedelta(minutes=1), "jti": str(uuid4())},
        get_settings().composer_jwt_secret, algorithm="HS256",
    )
    client = _client(_declaration(config_dir))
    response = client.get("/composer/current", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_forged_signature_is_rejected(config_dir):
    """★`docs/handoff/13` "테스트 계약" 이 요구하는 JWT 위조 검사.

    실제 signing secret 이 아닌 다른 값으로 서명한 토큰은 claim 이 유효해 보여도
    거부된다 — signature 검증이 실제로 도는지 확인한다.
    """
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": "attacker", "aud": "final_project_sample", "scope": ["composer:write"],
         "iat": now, "exp": now + timedelta(minutes=30), "jti": str(uuid4())},
        "not-the-real-composer-jwt-secret", algorithm="HS256",
    )
    client = _client(_declaration(config_dir))
    response = client.get("/composer/current", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_write_channel_survives_every_html_ui_being_disabled(config_dir):
    """★핵심 — HTML 화면이 전부 꺼져도(`/ui/composer`는 아예 없고, 주입한 선언은
    `ops_ui`도 off) 이 API 는 살아 있어야 한다. `final_project_ui`는 이 JSON API 로만
    모듈을 켜고 끈다 — HTML 화면의 존재 여부와 무관해야 이 채널을 만든 이유가 선다.

    ★`/ops/cases` 는 여기서 확인하지 않는다 — `create_app()` 은 호출 시점의 기본
    선언으로 라우트를 미리 구성하고, `project_config_path` 주입은 그 이후라 반영되지
    않는다(이 파일의 `_client` 패턴 자체의 특성). `/ui/composer`는 애초에 라우터
    자체가 없으므로 이 제약과 무관하게 항상 404 다.
    """
    path = _declaration(config_dir, ops_ui_enabled=False)
    client = _client(path)

    # HTML 폼(/ui/composer)은 아예 없다 (사실 확인 — 이 테스트의 전제)
    assert client.get("/ui/composer").status_code == 404

    # 그런데도 JSON API 는 살아 있다
    current = client.get("/composer/current", headers=_auth("composer:read"))
    assert current.status_code == 200
    body = current.json()
    assert body["config"]["modules"]["ops_ui"]["enabled"] is False

    body["config"]["modules"]["ops_ui"]["enabled"] = True
    applied = client.post("/composer/apply", headers=_auth(), json={
        "config": body["config"], "base_revision": body["revision"], "reason": "re-enable ops UI",
    })
    assert applied.status_code == 200
    assert applied.json()["applied"] is True

    declaration = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert declaration["modules"]["ops_ui"]["enabled"] is True


def test_validate_does_not_write_the_file(config_dir):
    path = _declaration(config_dir)
    before = path.read_bytes()
    client = _client(path)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["implementation_ref"] = "app.nonexistent:Missing"

    response = client.post("/composer/validate", headers=_auth("composer:validate"), json={"config": current["config"]})

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert path.read_bytes() == before
    assert not path.with_suffix(".yaml.bak").exists()


def test_apply_rejects_unimplementable_reference(config_dir):
    path = _declaration(config_dir)
    before = path.read_bytes()
    client = _client(path)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["implementation_ref"] = "app.nonexistent:Missing"

    response = client.post("/composer/apply", headers=_auth(), json={
        "config": current["config"], "base_revision": current["revision"], "reason": "test registry rejection",
    })

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_declaration"
    assert path.read_bytes() == before


def test_concurrent_apply_one_wins_one_gets_409(config_dir):
    """★Codex 교차검증이 명시적으로 요구한 검사 —
    동일 base_revision 으로 보낸 apply 2건 중 1건은 성공(200), 1건은 409 다.
    """
    path = _declaration(config_dir)
    client = _client(path)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()

    # ★둘 다 원본과, 그리고 서로와 달라야 한다. revision 은 내용 해시라서
    #   "수정 없는" payload 를 보내면 파일이 안 바뀌어 revision 도 안 바뀐다 —
    #   그러면 스레드 스케줄링 순서에 따라 둘 다 통과해 버릴 수 있다(flaky).
    #   실측 재현: docs/reports/debugs/2026-08-17_동시_apply_테스트가_flaky했다.md
    payload_a = dict(current["config"])
    payload_a["teams"] = [dict(t) for t in current["config"]["teams"]]
    payload_a["teams"].append({
        "team_id": "demo_team",
        "active": True,
        "implementation_ref": "app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
    })
    payload_a["teams"][0]["active"] = not payload_a["teams"][0]["active"]

    payload_b = dict(current["config"])
    payload_b["teams"] = [dict(t) for t in current["config"]["teams"]]
    payload_b["teams"].append({
        "team_id": "demo_team",
        "active": True,
        "implementation_ref": "app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
    })
    payload_b["teams"][1]["active"] = not payload_b["teams"][1]["active"]

    results: list = [None, None]

    def _apply(index: int, payload: dict) -> None:
        results[index] = client.post("/composer/apply", headers=_auth(), json={
            "config": payload, "base_revision": current["revision"], "reason": "concurrent test",
        })

    t1 = threading.Thread(target=_apply, args=(0, payload_a))
    t2 = threading.Thread(target=_apply, args=(1, payload_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 409]
    conflict = next(r for r in results if r.status_code == 409)
    assert conflict.json()["error"]["code"] == "revision_conflict"
