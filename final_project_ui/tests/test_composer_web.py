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
    def fake_apply(url, issuer_secret, config, *, base_revision, reason):
        assert base_revision == "rev-1"
        # ★사유는 대상이 필수로 요구한다. 한때 화면이 사유를 입력받고도 클라이언트에
        #   넘기지 않아 적용이 늘 422로 거부됐다 — 그때 이 stub은 `reason` 을 아예
        #   받지 않아서 결함을 못 잡았다(2026-08-28 결함 점검).
        assert reason == "구조 설계 테스트"
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
    def fake_apply(url, issuer_secret, config, *, base_revision, reason):
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


def test_structure_diagram_explains_component_module_instance_and_teams_are_instances(tmp_path, monkeypatch):
    """★실측(2026-08-24): 대상의 원래 `/ui/composer` 화면에는 "고정"·"모듈"·"인스턴스"
    세 노드 종류를 설명하는 범례가 있었다
    (`docs/backup/composer_ui_원본_2026-08-18/composer_ui_final_project_cs.py:127-131`).
    이 콘솔로 옮길 때 그 범례가 빠졌고, Team 노드도 "인스턴스"(개수가 바뀐다) 대신
    "모듈"(고정 목록에서 켜고 끈다)로 잘못 표시되고 있었다 — 사용자가 실제 화면에서
    발견했다.
    """
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: ComposerResult(
                            "읽음", value={"revision": "r1", "config": SAMPLE_CONFIG}))
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "s")
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "고정</b> = 컴포넌트" in body and "모듈</b> = 선택" in body and "인스턴스</b> = 개수가 바뀐다" in body
    # ★SAMPLE_CONFIG 의 team_id "billing" — 인스턴스 노드로 그려져야 한다
    assert "node--instance" in body
    assert "class='node node--module" in body  # vector_rag 같은 모듈도 여전히 그려진다
    assert "class='node node--component" in body  # REST API 같은 고정 컴포넌트도 그려진다


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


# ── v3 토글 카드 (2026-08-24 추가, 안 C — v2 와 병행) ──────────────────────────
# ★계약은 아직 잠정이다(program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md §2).
#   여기서는 그 제안 형태를 기준으로 화면 쪽 판단·렌더링만 검증한다.

def _live(status: str, value: dict | None = None):
    from console.live import LiveRead
    return LiveRead(status, value=value)


def test_toggle_card_is_absent_when_introspection_is_not_connected(tmp_path, monkeypatch):
    """★introspection 이 안 붙어 있으면(기본 상태) 조용히 사라진다 — v2 화면은 그대로다."""
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text
    assert "빠른 토글" not in body


def test_toggle_card_is_absent_for_an_unknown_contract_version(tmp_path, monkeypatch):
    """★`CLAUDE.md` §1 — 모르는 계약 버전으로는 그리지 않는다.

    `registered_ids` 가 모양상 있어도, `contract_version` 이
    `CONSOLE_CONTRACT_VERSIONS` 목록에 없으면(`live.status != "읽음"`) 추측해서
    그리지 않는다.
    """
    monkeypatch.setattr("console.web.read_introspection", lambda *a, **k: _live(
        "계약 버전 모름", value={"registered_ids": {"modules": ["vector_rag"]}, "modules": {"vector_rag": {"enabled": True}}}))
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text
    assert "빠른 토글" not in body


def test_toggle_card_shows_registered_items_with_current_state(tmp_path, monkeypatch):
    monkeypatch.setattr("console.web.read_introspection", lambda *a, **k: _live("읽음", value={
        "config_revision": "rev-i1",
        "registered_ids": {"modules": ["vector_rag"], "teams": ["order_shipping"], "ports": ["team_executor"]},
        "modules": {"vector_rag": {"enabled": True}},
        "teams": {"order_shipping": {"active": False}},
        "ports": {"team_executor": {"active": True}},
    }))
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "빠른 토글" in body and "rev-i1" in body
    assert "vector_rag" in body and "order_shipping" in body and "team_executor" in body
    # ★켜진 것(vector_rag)에는 "끄기" 버튼(새 값 false), 꺼진 것(order_shipping)에는 "켜기"(새 값 true)
    assert "끄기" in body and "켜기" in body
    assert "name='target_type' value='module'" in body
    assert "name='target_id' value='vector_rag'" in body


def test_toggle_card_reads_the_shape_the_target_actually_emits(tmp_path, monkeypatch):
    """★대상(contract_version 1.0)은 `modules`를 boolean map, `teams`를 객체 list로 낸다.

    위 테스트는 v3 설계 §2.2의 제안 형태(객체 map)만 썼다. 그 형태를 내는 대상은
    하나도 없어서, 실제로는 상태가 늘 `모름`이 되고 카드에 버튼이 하나도 안 그려졌다
    — 그런데 위 테스트는 통과했다(2026-08-28 결함 점검, 브라우저로 실측).
    이 테스트는 대상이 진짜 내는 형태를 넣는다.
    """
    monkeypatch.setattr("console.web.read_introspection", lambda *a, **k: _live("읽음", value={
        "config_revision": "rev-i1",
        "registered_ids": {"modules": ["vector_rag", "a2a_executor"], "teams": ["voc_store_manager"]},
        "modules": {"vector_rag": True, "a2a_executor": False},
        "teams": [{"team_id": "voc_store_manager", "active": True}],
    }))
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "빠른 토글" in body
    # 켜진 둘에는 끄기, 꺼진 하나에는 켜기 — 상태를 못 읽으면 이 버튼들이 아예 없다
    assert body.count("끄기") == 2 and body.count("켜기") == 1
    assert "name='target_id' value='vector_rag'" in body
    assert "name='target_id' value='voc_store_manager'" in body
    assert "name='target_type' value='team'" in body
    assert "모름" not in body


def test_toggle_card_shows_unknown_state_without_a_button(tmp_path, monkeypatch):
    """★등록은 됐는데 현재 상태를 대상이 안 줬으면 "모름"이라 적는다 — 지어내지 않는다(§0.4).

    버튼(반대값)을 만들려면 지금 값을 알아야 한다 — 모르면 액션도 안 준다.
    """
    monkeypatch.setattr("console.web.read_introspection", lambda *a, **k: _live("읽음", value={
        "config_revision": "rev-i1",
        "registered_ids": {"modules": ["ghost_module"]},
        "modules": {},
    }))
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "ghost_module" in body and "모름" in body
    assert "name='target_id' value='ghost_module'" not in body


def test_composer_toggle_post_calls_the_adapter_and_shows_new_state(tmp_path, monkeypatch):
    calls = []

    def fake_toggle(url, issuer_secret, *, target_type, target_id, active, base_revision, reason):
        calls.append((target_type, target_id, active, base_revision, reason))
        return ComposerResult("토글됨", value={"target_type": target_type, "target_id": target_id,
                                              "active": active, "config_revision": "rev-i2"})

    monkeypatch.setattr("console.composer.toggle_target", fake_toggle)
    monkeypatch.setattr("console.web.read_introspection", lambda *a, **k: _live("읽음", value={}))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer/toggle", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "target_type": "module",
        "target_id": "vector_rag", "active": "false", "base_revision": "rev-i1", "reason": "점검",
    })
    assert response.status_code == 200
    assert calls == [("module", "vector_rag", False, "rev-i1", "점검")]
    assert "토글됨" in response.text and "rev-i2" in response.text


def test_composer_toggle_without_a_reason_is_refused_before_calling_the_target(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("console.composer.toggle_target", lambda *a, **k: calls.append(1))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer/toggle", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "target_type": "module",
        "target_id": "vector_rag", "active": "false", "base_revision": "rev-i1", "reason": "   ",
    })
    assert response.status_code == 200
    assert "사유" in response.text
    assert calls == []


def test_composer_toggle_without_a_csrf_token_is_refused_before_calling_the_target(tmp_path, monkeypatch):
    """★v2 와 같은 방어 — 토글도 부작용을 내는 폼 POST 다."""
    calls = []
    monkeypatch.setattr("console.composer.toggle_target", lambda *a, **k: calls.append(1))
    project = make_project(tmp_path)

    response = TestClient(create_app(), raise_server_exceptions=False).post("/composer/toggle", data={
        "path": str(project), "target_type": "module", "target_id": "vector_rag",
        "active": "false", "base_revision": "rev-i1", "reason": "공격",
    })
    assert "거부했습니다" in response.text
    assert calls == []


def test_composer_toggle_reports_revision_conflict_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr("console.composer.toggle_target",
                        lambda *a, **k: ComposerResult("충돌", detail="다른 변경이 먼저 적용됐다."))
    project = make_project(tmp_path)

    response = TestClient(create_app()).post("/composer/toggle", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "target_type": "module",
        "target_id": "vector_rag", "active": "false", "base_revision": "stale", "reason": "점검",
    })
    assert response.status_code == 200
    assert "다른 변경이 먼저 적용됐다" in response.text


# ── 카탈로그 기반 인스턴스 CRUD 화면 (2026-08-29) ────────────────────
CATALOG_VALUE = {
    "config_revision": "rev-1",
    "implementations": [
        {"implementation_id": "team.declarative.v1", "kind": "team",
         "display_name": "선언형 Team", "description": "코드 없이 만든다",
         "parameters_schema": {"properties": {"display_name": {}, "capabilities": {},
                                              "prompt_key": {}}},
         "requires_restart": True},
        {"implementation_id": "team.placeholder", "kind": "team",
         "display_name": "자리표시 Team", "description": "", "parameters_schema": None,
         "requires_restart": True},
        {"implementation_id": "module.vector_rag", "kind": "module",
         "display_name": "vector_rag", "description": "", "parameters_schema": None,
         "requires_restart": True},
    ],
}


def _wire(monkeypatch, *, catalog=None, current=None):
    monkeypatch.setattr("console.composer.read_current",
                        lambda url, issuer_secret=None: current or ComposerResult(
                            "읽음", value={"revision": "rev-1", "config": SAMPLE_CONFIG}))
    monkeypatch.setattr("console.composer.read_catalog",
                        lambda url, issuer_secret=None: catalog if catalog is not None
                        else ComposerResult("조회됨", value=CATALOG_VALUE))
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://x/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "issuer-secret")


def test_catalog_card_lists_implementations_and_offers_a_create_form(tmp_path, monkeypatch):
    _wire(monkeypatch)
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "인스턴스 만들기" in body
    assert "team.declarative.v1" in body and "team.placeholder" in body
    assert "action='/composer/instance'" in body
    # 대상이 준 스키마 항목을 그대로 안내한다 — UI 가 스키마를 복제하지 않는다
    assert "prompt_key" in body
    # 모듈 종류는 이 카드에 섞이지 않는다(Team 인스턴스 생성 화면이다)
    assert "module.vector_rag" not in body


def test_catalog_card_is_absent_when_the_target_has_no_catalog(tmp_path, monkeypatch):
    """순수 추가 기능 — 대상에 없으면 카드만 빠지고 나머지 화면은 그대로다."""
    _wire(monkeypatch, catalog=ComposerResult("대상이 응답하지 않음", detail="HTTP 404"))
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "인스턴스 만들기" not in body
    assert "rev-1" in body  # v2 편집 폼은 그대로 뜬다


def test_create_sends_the_declared_parameters_to_the_target(tmp_path, monkeypatch):
    sent = {}

    def fake_change(url, issuer_secret, **kwargs):
        sent.update(kwargs)
        return ComposerResult("변경됨", value={"desired_revision": "rev-2",
                                            "activation_state": "pending_restart",
                                            "dry_run": False})

    _wire(monkeypatch)
    monkeypatch.setattr("console.composer.submit_change", fake_change)
    project = make_project(tmp_path)
    response = TestClient(create_app()).post("/composer/instance", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "operation": "create",
        "resource_type": "team", "instance_id": "vip_review",
        "implementation_id": "team.declarative.v1",
        "parameters": '{"display_name": "VIP", "capabilities": ["demo.vip"]}',
        "base_revision": "rev-1", "reason": "새 팀"})

    assert response.status_code == 200
    assert sent["operation"] == "create"
    assert sent["instance_id"] == "vip_review"
    assert sent["parameters"] == {"display_name": "VIP", "capabilities": ["demo.vip"]}
    assert sent["dry_run"] is False


def test_pending_restart_is_shown_not_hidden(tmp_path, monkeypatch):
    """★저장과 반영은 다르다 — 화면이 '적용됨' 만 보여주면 안 된다."""
    _wire(monkeypatch)
    monkeypatch.setattr("console.composer.submit_change",
                        lambda url, issuer_secret, **k: ComposerResult(
                            "변경됨", value={"desired_revision": "rev-2",
                                          "activation_state": "pending_restart",
                                          "dry_run": False}))
    project = make_project(tmp_path)
    body = TestClient(create_app()).post("/composer/instance", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "operation": "create",
        "resource_type": "team", "instance_id": "x",
        "implementation_id": "team.placeholder", "base_revision": "rev-1",
        "reason": "확인"}).text

    assert "재시작" in body


def test_dry_run_says_it_did_not_save(tmp_path, monkeypatch):
    _wire(monkeypatch)
    monkeypatch.setattr("console.composer.submit_change",
                        lambda url, issuer_secret, **k: ComposerResult(
                            "변경됨", value={"desired_revision": "rev-1", "dry_run": True,
                                          "activation_state": "pending_restart"}))
    project = make_project(tmp_path)
    body = TestClient(create_app()).post("/composer/instance", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "operation": "create",
        "resource_type": "team", "instance_id": "x",
        "implementation_id": "team.placeholder", "base_revision": "rev-1",
        "reason": "검증만", "dry_run": "true"}).text

    assert "저장하지 않았습니다" in body


def test_broken_parameters_json_is_reported_without_calling_the_target(tmp_path, monkeypatch):
    """JSON 문법은 이 폼의 입력 형식이라 여기서 본다 — 대상 스키마 판정은 아니다."""
    calls = []
    _wire(monkeypatch)
    monkeypatch.setattr("console.composer.submit_change",
                        lambda *a, **k: calls.append(1))
    project = make_project(tmp_path)
    body = TestClient(create_app()).post("/composer/instance", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "operation": "create",
        "resource_type": "team", "instance_id": "x",
        "implementation_id": "team.declarative.v1", "parameters": "{not json",
        "base_revision": "rev-1", "reason": "확인"}).text

    assert "설정 JSON 을 읽지 못했습니다" in body
    assert calls == []


def test_change_without_a_reason_is_refused(tmp_path, monkeypatch):
    calls = []
    _wire(monkeypatch)
    monkeypatch.setattr("console.composer.submit_change", lambda *a, **k: calls.append(1))
    project = make_project(tmp_path)
    body = TestClient(create_app()).post("/composer/instance", data={
        "csrf_token": _CSRF_TOKEN, "path": str(project), "operation": "delete",
        "resource_type": "team", "instance_id": "billing", "base_revision": "rev-1",
        "reason": "  "}).text

    assert "사유" in body
    assert calls == []


def test_instance_route_requires_the_csrf_token(tmp_path, monkeypatch):
    calls = []
    _wire(monkeypatch)
    monkeypatch.setattr("console.composer.submit_change", lambda *a, **k: calls.append(1))
    project = make_project(tmp_path)
    response = TestClient(create_app()).post("/composer/instance", data={
        "path": str(project), "operation": "delete", "resource_type": "team",
        "instance_id": "billing", "base_revision": "rev-1", "reason": "확인"})

    # ★거부는 4xx 가 아니라 **안내 페이지**다(`_csrf_denied`) — 이 저장소의
    #   기존 관례를 그대로 따른다. 중요한 것은 대상을 부르지 않았다는 사실이다.
    assert calls == []
    assert response.status_code == 200
    assert "요청을 거부했습니다" in response.text
