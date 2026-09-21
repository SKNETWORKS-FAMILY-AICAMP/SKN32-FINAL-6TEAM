from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from console.web import create_app


def make_project(root: Path) -> Path:
    project = root / "sample-project"
    config = project / "config"
    config.mkdir(parents=True)
    (config / "project.yaml").write_text(
        "modules:\n"
        "  console:\n"
        "    enabled: true\n"
        "teams:\n"
        "  - team_id: team-alpha\n"
        "    active: true\n"
        "    implementation_ref: impl.alpha\n"
        "ports:\n"
        "  team_executor: 8123\n",
        encoding="utf-8",
    )
    (config / "guardrails.yaml").write_text(
        "context:\n  token_budget: 12000\n",
        encoding="utf-8",
    )
    return project


def test_project_screen_contains_all_sections_and_values(tmp_path, monkeypatch):
    for key in ("CONSOLE_DATABASE_URL", "CONSOLE_INTROSPECTION_URL"):
        monkeypatch.delenv(key, raising=False)

    project = make_project(tmp_path)
    response = TestClient(create_app()).get("/project", params={"path": str(project)})

    assert response.status_code == 200
    body = response.text
    for section in ("조립", "무엇이 막혀 있나", "평가 실행", "상태 분포", "연결"):
        assert f"<h2>{section}</h2>" in body
    assert "12000" in body
    assert "team-alpha" in body


def test_project_screen_reports_missing_connections_without_zero_filling(
    tmp_path, monkeypatch
):
    for key in ("CONSOLE_DATABASE_URL", "CONSOLE_INTROSPECTION_URL"):
        monkeypatch.delenv(key, raising=False)

    project = make_project(tmp_path)
    body = TestClient(create_app()).get(
        "/project", params={"path": str(project)}
    ).text

    assert "연결 안 함" in body
    assert "database_url 이 프로필에 없음" in body
    state_section = body.split("<h2>상태 분포</h2>", 1)[1].split("<h2>연결</h2>", 1)[0]
    assert ">0<" not in state_section


def test_project_screen_reports_non_project_path(tmp_path):
    non_project = tmp_path / "not-a-project"
    non_project.mkdir()
    response = TestClient(create_app()).get(
        "/project", params={"path": str(non_project)}
    )

    assert response.status_code == 200
    assert "프로젝트가 아닙니다" in response.text
    assert "config/project.yaml" in response.text


def test_projects_screen_keeps_non_project_entries_distinct(tmp_path):
    project = make_project(tmp_path)
    non_project = tmp_path / "plain-folder"
    non_project.mkdir()
    (non_project / "config").mkdir()
    response = TestClient(create_app()).get("/", params={"root": str(tmp_path)})

    assert response.status_code == 200
    assert project.name in response.text
    assert non_project.name in response.text
    assert "아님" in response.text


def test_project_screen_passes_the_introspection_token_through(tmp_path, monkeypatch):
    """★실측(2026-08-17) 결함 회귀 방지.

    대상 `/introspection` 은 scope 인증이 걸려 있는데, `read_introspection` 호출부가
    토큰을 안 넘기고 있었다 — 그래서 실서버에 붙이면 항상 401 이었다.
    """
    calls = []

    def fake_read_introspection(url, versions, token=None):
        calls.append((url, versions, token))
        from console.live import LiveRead
        return LiveRead("읽음", value={"modules": {}})

    monkeypatch.setattr("console.web.read_introspection", fake_read_introspection)
    monkeypatch.setenv("CONSOLE_INTROSPECTION_URL", "http://127.0.0.1:9/introspection")
    monkeypatch.setenv("CONSOLE_INTROSPECTION_TOKEN", "the-token")

    project = make_project(tmp_path)
    TestClient(create_app()).get("/project", params={"path": str(project)})

    assert calls and calls[0][2] == "the-token"


def test_project_screen_is_rendered_as_html(tmp_path):
    project = make_project(tmp_path)

    response = TestClient(create_app()).get("/project", params={"path": str(project)})

    assert response.headers["content-type"].startswith("text/html")
    assert "<!doctype html>" in response.text


def test_top_navigation_marks_project_screen_and_links_to_composer(tmp_path):
    from urllib.parse import quote

    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/project", params={"path": str(project)}).text

    assert "<a href='/project?path=" in body
    assert "aria-current='page'" in body
    # ★링크의 경로는 **URL 인코딩**된다(`console.web.qs`) — 원문 그대로 찾으면 안 된다.
    assert f"/composer?path={quote(str(project), safe='')}" in body


def test_top_navigation_marks_composer_screen(tmp_path):
    project = make_project(tmp_path)
    body = TestClient(create_app()).get("/composer", params={"path": str(project)}).text

    assert "<a href='/composer?path=" in body
    composer_nav = body.split("<nav aria-label='주 메뉴'>", 1)[1].split("</nav>", 1)[0]
    assert "<a href='/composer?path=" in composer_nav
    assert "aria-current='page'" in composer_nav


def test_top_navigation_disables_project_links_without_a_path(tmp_path):
    body = TestClient(create_app()).get("/", params={"root": str(tmp_path)}).text
    nav = body.split("<nav aria-label='주 메뉴'>", 1)[1].split("</nav>", 1)[0]

    assert "<span class='nav-disabled' aria-disabled='true'>조립</span>" in nav
    assert "<span class='nav-disabled' aria-disabled='true'>Composer</span>" in nav
    assert "/project?path=" not in nav
    assert "/composer?path=" not in nav


def test_project_screen_without_a_path_explains_instead_of_returning_422(tmp_path):
    """★`/project` 만 `path` 가 필수라 FastAPI 가 raw JSON 422 를 냈다.

    주소창에 `/project` 만 치거나 쿼리 없는 북마크로 들어오면 화면이 아니라
    JSON 이 떴다 — 다른 라우트는 전부 안내 화면을 낸다. 여기만 다를 이유가 없다.
    """
    response = TestClient(create_app()).get("/project")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "프로젝트 경로가 없습니다" in response.text


def test_a_path_with_query_special_characters_still_links_correctly(tmp_path):
    """★`esc()` 만으로는 링크가 깨진다 — URL 인코딩이 따로 필요하다.

    실측(2026-08-19): 폴더 이름에 `&`·`#` 가 있으면(둘 다 합법이다) 링크가
    `path=...\a` 에서 잘리고 `#c` 는 서버에 오지도 않아, **엉뚱한 경로**를
    가리켰다. 지금은 `%26`·`%23` 로 인코딩된다.
    """
    import re

    project = tmp_path / "a&b#c"
    (project / "config").mkdir(parents=True)
    (project / "config" / "project.yaml").write_text(
        "modules: {}\nports: {}\nteams: []\n", encoding="utf-8")

    client = TestClient(create_app())
    body = client.get("/", params={"root": str(tmp_path)}).text
    links = re.findall(r"href='(/project\?path=[^']*)'", body)
    assert links, "프로젝트 링크가 아예 없다"
    assert "%26" in links[0] and "%23" in links[0], f"인코딩 안 됨: {links[0]}"

    # ★링크를 실제로 따라가면 그 프로젝트가 열려야 한다
    followed = client.get(links[0].replace("&amp;", "&"))
    assert followed.status_code == 200
    assert "프로젝트가 아닙니다" not in followed.text
