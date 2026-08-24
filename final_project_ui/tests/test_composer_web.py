"""`/composer` 화면 — 대상의 Composer 쓰기 채널을 부르는 유일한 화면.

★모듈 체크박스·Port 입력·Team 표(추가/제거)로 구조화된 편집을 한다 — 대상의
  원래 `/ui/composer` 화면과 같은 기능이다(`docs/backup/composer_ui_원본_2026-08-18/`
  참고). raw JSON textarea가 아니다 — §0.2 때문에 대상의 `PortConfig` 선택지를
  가져올 수 없어서, port는 text input이고 validate가 틀린 값을 잡는다.

★`console.composer`의 실제 HTTP 동작은 `tests/test_composer.py`가 이미 검증한다.
  여기서는 **화면 라우팅**만 본다 — monkeypatch로 `console.composer`의 함수를
  갈아끼운다(`console.web`이 `composer_client`로 같은 모듈을 참조하므로 그대로 반영된다).
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from console.composer import ComposerResult
from console.web import create_app


def make_project(root: Path) -> Path:
    project = root / "sample-project"
    (project / "config").mkdir(parents=True)
    (project / "config" / "project.yaml").write_text("modules: {}\nports: {}\nteams: []\n", encoding="utf-8")
    return project


SAMPLE_CONFIG = {
    "modules": {"vector_rag": {"enabled": True}, "a2a_executor": {"enabled": False}},
    "ports": {"team_executor": "local"},
    "teams": [{"team_id": "billing", "active": True, "implementation_ref": "app.x:Billing"}],
}


def test_composer_screen_without_url_says_so_not_a_500(tmp_path, monkeypatch):
    for key in ("CONSOLE_COMPOSER_URL", "CONSOLE_COMPOSER_ISSUER_SECRET"):
        monkeypatch.delenv(key, raising=False)
    project = make_project(tmp_path)
    response = TestClient(create_app()).get("/composer", params={"path": str(project)})
    assert response.status_code == 200
    assert "composer_url" in response.text and "프로필에 없음" in response.text


def test_composer_screen_shows_modules_ports_teams_and_revision(tmp_path, monkeypatch):
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult("읽음", value={"revision": "rev-1",
                                                                              "config": SAMPLE_CONFIG}))
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "issuer-secret")
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "rev-1" in body
    # ★켜진 모듈은 checked, 꺼진 모듈은 checked가 없다
    assert "name='module_vector_rag' checked" in body
    assert "name='module_a2a_executor' " in body and "name='module_a2a_executor' checked" not in body
    assert "name='port_team_executor' value='local'" in body
    assert "value='billing'" in body and "value='app.x:Billing'" in body


def test_validate_builds_the_config_from_checked_modules_not_from_raw_json(tmp_path, monkeypatch):
    """★체크박스 상태에서 config를 재구성한다 — 원래 화면과 같은 편집 방식."""
    calls = []

    def fake_validate(url, issuer_secret, config):
        calls.append(config)
        return ComposerResult("검증됨", value={"valid": True, "revision": "rev-1"})

    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult("읽음", value={"revision": "rev-1",
                                                                              "config": SAMPLE_CONFIG}))
    monkeypatch.setattr("console.composer.validate_candidate", fake_validate)
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "issuer-secret")
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer", data={
        "path": str(project), "action": "validate", "base_revision": "rev-1", "reason": "구조 설계 테스트",
        "module_vector_rag": "on",  # 체크됨 유지
        # module_a2a_executor 는 안 보냄 = 체크 해제
        "port_team_executor": "a2a",  # 값을 바꿔서 제출
        "team_id_0": "billing", "implementation_ref_0": "app.x:Billing", "active_0": "on",
    })
    assert response.status_code == 200
    assert calls == [{
        "modules": {"vector_rag": {"enabled": True}, "a2a_executor": {"enabled": False}},
        "ports": {"team_executor": "a2a"},
        "teams": [{"team_id": "billing", "active": True, "implementation_ref": "app.x:Billing"}],
    }]
    assert "검증 통과" in response.text


def test_add_team_appends_a_blank_row_without_calling_the_target(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("console.composer.validate_candidate", lambda *a, **k: calls.append(1))
    monkeypatch.setattr("console.composer.apply_candidate", lambda *a, **k: calls.append(1))
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult("읽음", value={"revision": "rev-1",
                                                                              "config": SAMPLE_CONFIG}))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer", data={
        "path": str(project), "add_team": "1",
        "team_id_0": "billing", "implementation_ref_0": "app.x:Billing", "active_0": "on",
    })
    assert response.status_code == 200
    assert calls == []  # ★대상에 요청조차 안 나갔다 — 화면만 다시 그린다
    assert "name='team_id_1'" in response.text  # 새 빈 행이 생겼다


def test_remove_team_drops_the_row_without_calling_the_target(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("console.composer.validate_candidate", lambda *a, **k: calls.append(1))
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult("읽음", value={"revision": "rev-1",
                                                                              "config": SAMPLE_CONFIG}))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer", data={
        "path": str(project), "remove_team": "0",
        "team_id_0": "billing", "implementation_ref_0": "app.x:Billing", "active_0": "on",
    })
    assert response.status_code == 200
    assert calls == []
    assert "value='billing'" not in response.text


def test_apply_without_a_reason_is_refused_before_calling_the_target(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("console.composer.apply_candidate", lambda *a, **k: calls.append(1))
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult("읽음", value={"revision": "r", "config": {}}))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer", data={
        "path": str(project), "action": "apply", "base_revision": "r", "reason": "   ",
    })
    assert response.status_code == 200
    assert "사유" in response.text
    assert calls == []


def test_apply_reports_the_new_revision(tmp_path, monkeypatch):
    def fake_apply(url, issuer_secret, config, *, base_revision):
        assert base_revision == "rev-1"
        return ComposerResult("적용됨", value={"revision": "rev-2", "applied": True})

    reads = [ComposerResult("읽음", value={"revision": "rev-1", "config": {}}),
             ComposerResult("읽음", value={"revision": "rev-2", "config": {}})]
    monkeypatch.setattr("console.composer.apply_candidate", fake_apply)
    monkeypatch.setattr("console.composer.read_current", lambda url, issuer_secret=None: reads.pop(0))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer", data={
        "path": str(project), "action": "apply", "base_revision": "rev-1", "reason": "구조 설계 테스트",
    })
    assert response.status_code == 200
    assert "적용됨" in response.text
    assert "rev-2" in response.text


def test_apply_revision_conflict_shows_current_revision_not_a_crash(tmp_path, monkeypatch):
    def fake_apply(url, issuer_secret, config, *, base_revision):
        return ComposerResult("충돌", value={"current_revision": "someone-else"}, detail="다른 변경이 먼저 적용됐다.")

    monkeypatch.setattr("console.composer.apply_candidate", fake_apply)
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult("읽음", value={"revision": "someone-else",
                                                                              "config": {}}))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer", data={
        "path": str(project), "action": "apply", "base_revision": "stale-rev", "reason": "구조 설계 테스트",
    })
    assert response.status_code == 200
    assert "다른 변경이 먼저 적용됐다" in response.text


def test_project_screen_links_to_the_composer_screen(tmp_path):
    """★한때 `... in body or "/composer?path=" in body` 였다 — **검사하는 척하는 검사**다.

    P13 상단 내비게이션이 모든 화면에 `/composer?path=` 를 넣으므로 `or` 뒤쪽이
    **항상 참**이었다. 본문의 Composer 링크가 통째로 사라져도 통과했다.
    지금은 **정확한 경로**만 본다(`CLAUDE.md` §2 — 항상 참인 단언 금지).
    """
    from urllib.parse import quote

    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/project", params={"path": str(project)}).text
    # ★링크의 경로는 **URL 인코딩**된다(`console.web.qs`) — 원문 그대로 찾으면 안 된다.
    assert f"/composer?path={quote(str(project), safe='')}" in body


# ── 인수인계 점검(2026-08-19)에서 실측한 결함 3건 회귀 방지 ──────────────────
def test_a_malformed_target_config_does_not_crash_the_screen(tmp_path, monkeypatch):
    """★대상이 이상한 것을 줘도 **콘솔은 떠야 한다**(`CLAUDE.md` §1).

    실측: 대상이 `config: null`·배열·문자열을 주면 `.get()`/`.items()` 가 터져
    화면 전체가 500 이었다 — 어느 대상이 뭘 잘못 줬는지도 안 보였다.
    """
    project = make_project(tmp_path)
    for broken in (None, [], "oops", 42):
        monkeypatch.setattr("console.composer.read_current",
                            lambda url, issuer_secret=None, _c=broken:
                            ComposerResult("읽음", value={"revision": "r", "config": _c}))
        monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
        monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "s")
        response = TestClient(create_app(), raise_server_exceptions=False).get(
            "/composer", params={"path": str(project)})
        assert response.status_code == 200, f"config={broken!r} 에서 죽었다"
        assert "읽지 못했습니다" in response.text or "형태가 예상과 다릅니다" in response.text


def test_a_non_numeric_remove_team_does_not_crash(tmp_path, monkeypatch):
    """★실측: 조작된 POST(`remove_team=abc`)가 `int()` 에서 터져 500 이었다."""
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult(
                            "읽음", value={"revision": "r1", "config": SAMPLE_CONFIG}))
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "s")
    project = make_project(tmp_path)
    client = TestClient(create_app(), raise_server_exceptions=False)

    for bad in ("abc", "", "1.5", "９９"):
        response = client.post("/composer", data={
            "path": str(project), "remove_team": bad,
            "team_id_0": "billing", "implementation_ref_0": "app.x:Billing", "active_0": "on",
        })
        assert response.status_code == 200, f"remove_team={bad!r} 에서 죽었다"
        # ★숫자가 아니면 아무 행도 지우지 않는다
        assert "value='billing'" in response.text
