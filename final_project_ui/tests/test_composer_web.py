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
from console.web import _CSRF_TOKEN, create_app


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
        "csrf_token": _CSRF_TOKEN, "path": str(project), "action": "validate", "base_revision": "rev-1", "reason": "구조 설계 테스트",
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
        "csrf_token": _CSRF_TOKEN, "path": str(project), "add_team": "1",
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
        "csrf_token": _CSRF_TOKEN, "path": str(project), "remove_team": "0",
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
        "csrf_token": _CSRF_TOKEN, "path": str(project), "action": "apply", "base_revision": "r", "reason": "   ",
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
        "csrf_token": _CSRF_TOKEN, "path": str(project), "action": "apply", "base_revision": "rev-1", "reason": "구조 설계 테스트",
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
        "csrf_token": _CSRF_TOKEN, "path": str(project), "action": "apply", "base_revision": "stale-rev", "reason": "구조 설계 테스트",
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
            "csrf_token": _CSRF_TOKEN, "path": str(project), "remove_team": bad,
            "team_id_0": "billing", "implementation_ref_0": "app.x:Billing", "active_0": "on",
        })
        assert response.status_code == 200, f"remove_team={bad!r} 에서 죽었다"
        # ★숫자가 아니면 아무 행도 지우지 않는다
        assert "value='billing'" in response.text


def test_unconnected_composer_screen_says_how_to_connect(tmp_path, monkeypatch):
    """★"composer_url 이 프로필에 없음" 만 띄우면 무엇을 해야 하는지 모른다.

    실제로 "Composer 를 콘솔로 이식한 것 아니었나?" 하는 오해를 불렀다(2026-08-19).
    이식한 것은 **화면**이고, 값은 대상에게 물어봐야 한다 — 그 사실과 다음에 할
    일을 화면이 직접 말해야 한다.
    """
    for key in ("CONSOLE_COMPOSER_URL", "CONSOLE_COMPOSER_ISSUER_SECRET"):
        monkeypatch.delenv(key, raising=False)
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "붙이려면" in body
    assert "CONSOLE_COMPOSER_URL" in body
    assert "CONSOLE_COMPOSER_ISSUER_SECRET" in body
    # ★대상 서버를 띄우라는 안내와, 왜 필요한지가 함께 있어야 한다
    assert "대상 서버를" in body
    assert "import" in body


# ── CSRF (2026-08-19 교차검증 후 도입) ────────────────────────────────────────
def test_a_post_without_a_csrf_token_is_refused_before_touching_the_target(tmp_path, monkeypatch):
    """★핵심 — 콘솔이 켜진 채로 악성 페이지를 열면 그 페이지가 여기로 form POST 를
    보낼 수 있다. 폼 POST 는 CORS preflight 대상이 아니라 브라우저가 안 막는다.
    응답은 못 읽어도 **부작용(대상 config 변경)은 일어난다.**

    그래서 토큰이 없으면 **대상에 아무것도 보내기 전에** 막아야 한다.
    """
    calls = []
    monkeypatch.setattr("console.composer.read_current", lambda *a, **k: calls.append("read"))
    monkeypatch.setattr("console.composer.apply_candidate", lambda *a, **k: calls.append("apply"))
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "s")
    project = make_project(tmp_path)

    response = TestClient(create_app(), raise_server_exceptions=False).post("/composer", data={
        "path": str(project), "action": "apply", "base_revision": "r", "reason": "공격",
    })
    assert "거부했습니다" in response.text
    # ★대상에 요청이 나가지 않았다 — 이게 이 방어의 전부다
    assert calls == []


def test_a_post_with_a_wrong_csrf_token_is_refused(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("console.composer.read_current", lambda *a, **k: calls.append("read"))
    project = make_project(tmp_path)

    response = TestClient(create_app(), raise_server_exceptions=False).post("/composer", data={
        "csrf_token": "guessed-wrong", "path": str(project), "action": "validate",
    })
    assert "거부했습니다" in response.text
    assert calls == []


def test_a_cross_origin_post_is_refused_even_with_a_leaked_token(tmp_path, monkeypatch):
    """★보조 방어 — 토큰이 어떤 경로로 새더라도 다른 출처면 막는다.

    브라우저는 cross-origin POST 에 `Origin` 을 **반드시** 붙인다.
    """
    calls = []
    monkeypatch.setattr("console.composer.read_current", lambda *a, **k: calls.append("read"))
    project = make_project(tmp_path)

    response = TestClient(create_app(), raise_server_exceptions=False).post(
        "/composer",
        data={"csrf_token": _CSRF_TOKEN, "path": str(project), "action": "validate"},
        headers={"Origin": "http://evil.example"})
    assert "거부했습니다" in response.text
    assert "evil.example" in response.text
    assert calls == []


def test_the_form_carries_the_csrf_token_so_the_real_screen_works(tmp_path, monkeypatch):
    """★방어가 정상 사용을 막으면 안 된다 — 화면이 준 폼에는 토큰이 들어 있어야 한다."""
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult(
                            "읽음", value={"revision": "r1", "config": SAMPLE_CONFIG}))
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "s")
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert f"name='csrf_token' value='{_CSRF_TOKEN}'" in body
