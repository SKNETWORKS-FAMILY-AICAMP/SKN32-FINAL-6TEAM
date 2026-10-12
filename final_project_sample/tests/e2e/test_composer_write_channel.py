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
from app.composer_host import composer_host
from acop_composer.api import create_composer_router
from acop_composer.auth import create_auth_router
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
    _host = composer_host()
    app = create_app(composer_write_router=create_composer_router(_host),
                     composer_auth_router=create_auth_router(_host))
    # ★HTML 라우터(`app/presentation/ui/composer.py`)와 같은 관례 —
    #   실제 config/project.yaml 을 건드리지 않고 임시 선언으로 검사한다.
    app.state.project_config_path = path
    # ★같은 이유로 audit 경로도 주입한다 — 아니면 이 테스트가 돌 때마다
    #   실제 var/audit/composer_events.jsonl 에 가짜 apply 이벤트가 쌓인다.
    app.state.composer_audit_path = path.with_name("composer_events.jsonl")
    # ★이력도 같은 이유로 주입한다 — 아니면 var/audit/composer_revisions.jsonl 이 오염된다.
    app.state.composer_revisions_path = path.with_name("composer_revisions.jsonl")
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
    applied = client.post("/composer/apply", headers=_auth("composer:admin"), json={
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

    response = client.post("/composer/apply", headers=_auth("composer:admin"), json={
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
        results[index] = client.post("/composer/apply", headers=_auth("composer:admin"), json={
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


# ── D-011 (2026-09-06): 통째 교체는 관리자 도구, 되돌리기는 이력에서 ────────
def test_apply_needs_admin_scope_write_is_not_enough(config_dir):
    """★운영자 scope(`composer:write`)로는 선언 전체를 갈아끼울 수 없다.

    항목 하나 단위(`/toggle`·`/changes`)만 운영자 것이고, 전체 교체는 설치·복원·
    이관용 관리자 도구다. 두 운영자가 전체본을 동시에 보내면 한쪽이 남의 변경을
    덮거나 항상 409 로 튕긴다."""
    path = _declaration(config_dir)
    before = path.read_bytes()
    client = _client(path)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()

    response = client.post("/composer/apply", headers=_auth("composer:write"), json={
        "config": current["config"], "base_revision": current["revision"], "reason": "should be denied",
    })

    assert response.status_code == 403
    assert path.read_bytes() == before


def test_every_write_leaves_history_and_restore_returns_the_previous_content(config_dir):
    """★첫 변경 직후에도 되돌릴 수 있어야 한다 — 직전 상태가 `baseline` 으로 먼저 남는다.

    복원은 이력을 되감는 것이 아니라 **앞으로 한 칸 더 가는 새 적용**이다. 그래서
    복원 뒤 이력은 한 줄 더 늘고, 내용 해시인 revision 은 원래 값으로 돌아온다."""
    path = _declaration(config_dir, ops_ui_enabled=False)
    client = _client(path)
    start = client.get("/composer/current", headers=_auth("composer:read")).json()

    # 1) /changes 로 항목 하나 바꾼다 — 운영자 경로도 이력을 남겨야 한다
    changed = client.post("/composer/changes", headers=_auth("composer:write"), json={
        "operation": "enable", "resource_type": "module", "instance_id": "ops_ui",
        "base_revision": start["revision"], "reason": "turn ops UI on",
    })
    assert changed.status_code == 200, changed.text
    after_change = changed.json()["desired_revision"]
    assert after_change != start["revision"]

    history = client.get("/composer/revisions", headers=_auth("composer:read")).json()
    assert history["current_revision"] == after_change
    events = [(e["event"], e["revision"]) for e in history["revisions"]]
    assert events == [("change", after_change), ("baseline", start["revision"])]
    assert all("declaration" not in e for e in history["revisions"]), "전문은 내보내지 않는다"

    # 2) baseline 으로 되돌린다 — 파일 내용이 원래대로, revision 도 원래 값
    restored = client.post("/composer/restore", headers=_auth("composer:admin"), json={
        "revision": start["revision"], "base_revision": after_change, "reason": "undo",
    })
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["applied"] is True
    assert body["revision"] == start["revision"]
    assert body["restored_from"] == start["revision"]
    assert body["previous_revision"] == after_change
    declaration = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert declaration["modules"]["ops_ui"]["enabled"] is False

    history = client.get("/composer/revisions", headers=_auth("composer:read")).json()
    assert [e["event"] for e in history["revisions"]] == ["restore", "change", "baseline"]
    assert history["revisions"][0]["previous_revision"] == after_change

    # 3) 감사에도 남는다 — 무엇으로부터 되돌렸는지까지
    audit_lines = path.with_name("composer_events.jsonl").read_text(encoding="utf-8").splitlines()
    last = __import__("json").loads(audit_lines[-1])
    assert last["event"] == "composer.restore"
    assert last["restored_from"] == start["revision"]


def test_restore_needs_admin_scope(config_dir):
    path = _declaration(config_dir)
    client = _client(path)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    response = client.post("/composer/restore", headers=_auth("composer:write"), json={
        "revision": "whatever", "base_revision": current["revision"], "reason": "denied",
    })
    assert response.status_code == 403


def test_restore_unknown_revision_is_404_and_stale_base_is_409(config_dir):
    """★이력에 없는 내용은 이 경로로 들어올 수 없다(404). 그리고 되돌리기도
    다른 변경과 경쟁한다 — base_revision 이 낡았으면 409 다."""
    path = _declaration(config_dir)
    client = _client(path)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()

    missing = client.post("/composer/restore", headers=_auth("composer:admin"), json={
        "revision": "no-such-revision", "base_revision": current["revision"], "reason": "x",
    })
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "revision_not_found"

    # 이력을 하나 만든다
    toggled = client.post("/composer/toggle", headers=_auth("composer:write"), json={
        "target_type": "module", "target_id": "vector_rag", "active": False,
        "base_revision": current["revision"], "reason": "make history",
    })
    assert toggled.status_code == 200, toggled.text

    stale = client.post("/composer/restore", headers=_auth("composer:admin"), json={
        "revision": current["revision"], "base_revision": "stale", "reason": "undo",
    })
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "revision_conflict"

    same = client.post("/composer/restore", headers=_auth("composer:admin"), json={
        "revision": toggled.json()["config_revision"],
        "base_revision": toggled.json()["config_revision"], "reason": "noop",
    })
    assert same.status_code == 422
    assert same.json()["error"]["code"] == "already_at_revision"
