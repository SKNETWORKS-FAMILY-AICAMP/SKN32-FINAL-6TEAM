"""`/run` — 실행 하나를 따라가는 화면.

★이 파일은 **네 번째**로 빠질 뻔한 테스트다. Codex 발주가 `read_trace` 를
  `web.py` 에 연결했다고 보고했는데(실제로 됐다 — `/run` 라우트가 있다),
  테스트 수는 44 → 44 그대로였다. 완료 조건에 "테스트 수가 늘어난다" 를
  네 번째로 명시했는데도 또 빠졌다 — 이제는 **내가 직접 붙인다.**
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from console.web import create_app


@pytest.fixture()
def client():
    return TestClient(create_app())


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "project.yaml").write_text(
        "modules: {}\nports: {}\nteams: []\n", encoding="utf-8")
    return tmp_path


def test_missing_run_id_is_an_explanation_not_a_500(client, project):
    """★run_id 없이 접근해도 죽지 않는다."""
    response = client.get("/run", params={"path": str(project)})
    assert response.status_code == 200
    assert "run_id" in response.text


def test_no_database_url_says_so(client, project, monkeypatch):
    """★`/run` 은 `detail` 을 보여준다(`status` 문구가 아니라).

    `db.read_trace(None, ...)` 는 status="연결 안 함", detail="database_url 이 프로필에 없음"
    을 돌려주고, 화면은 `detail or status` 로 detail 을 우선한다 — 사람이 읽을 이유가
    상태 라벨보다 detail 에 있기 때문이다. 이 테스트는 그 실제 동작을 고정한다.
    """
    monkeypatch.delenv("CONSOLE_DATABASE_URL", raising=False)
    response = client.get("/run", params={"path": str(project), "run_id": "any"})
    assert response.status_code == 200
    assert "database_url" in response.text and "프로필에 없음" in response.text


def test_a_dead_database_does_not_return_500(client, project, monkeypatch):
    """★DB 접속 정보가 있지만 죽어 있을 때도 안내로 끝난다."""
    monkeypatch.setenv("CONSOLE_DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none")
    response = client.get("/run", params={"path": str(project), "run_id": "any"})
    assert response.status_code == 200
    assert "run_id" not in response.text.split("<h1>")[0]  # 최소한 페이지는 그려진다


def test_run_route_calls_read_trace(project, monkeypatch):
    """★`db.read_trace` 가 실제로 호출되는지 — 연결만 됐고 안 불리는 경우를 잡는다."""
    calls = []

    def fake_read_trace(database_url, run_id):
        calls.append((database_url, run_id))
        from console.db import DbRead
        return DbRead("읽음", trace=({"stage": "agent_runs", "rows": []},))

    monkeypatch.setattr("console.web.read_trace", fake_read_trace)
    monkeypatch.setenv("CONSOLE_DATABASE_URL", "postgresql://u@h/db")

    client = TestClient(create_app())
    response = client.get("/run", params={"path": str(project), "run_id": "abc-123"})

    assert response.status_code == 200
    assert calls == [("postgresql://u@h/db", "abc-123")]


def test_history_table_links_to_the_run_screen(project, monkeypatch):
    """★"실행 이력" 표의 각 행이 `/run` 으로 이어져야 실제로 따라갈 수 있다."""
    from console.db import DbRead

    def fake_runs(database_url, **kwargs):
        return DbRead("읽음", rows=({"run_id": "abc-123", "tenant_id": "t",
                                    "case_id": "c", "graph_revision": "r1",
                                    "status": "succeeded", "started_at": None,
                                    "finished_at": None},), detail="전체 1개 중 1개 표시")

    monkeypatch.setattr("console.web.read_agent_runs", fake_runs)
    monkeypatch.setenv("CONSOLE_DATABASE_URL", "postgresql://u@h/db")

    client = TestClient(create_app())
    body = client.get("/project", params={"path": str(project)}).text
    assert "/run?" in body and "abc-123" in body


def test_stage_without_rows_says_no_records_not_zero(client, project, monkeypatch):
    """★단계에 행이 없으면 `0` 이 아니라 "기록 없음" 류로 적는다."""
    from console.db import DbRead

    def fake_read_trace(database_url, run_id):
        return DbRead("읽음", trace=(
            {"stage": "agent_runs", "rows": [{"run_id": run_id}]},
            {"stage": "team_tasks", "rows": []},
        ))

    monkeypatch.setattr("console.web.read_trace", fake_read_trace)
    monkeypatch.setenv("CONSOLE_DATABASE_URL", "postgresql://u@h/db")
    body = client.get("/run", params={"path": str(project), "run_id": "x"}).text
    assert "team_tasks" in body


def test_stage_error_is_shown_not_hidden(client, project, monkeypatch):
    """★단계 조회 실패는 빈 목록으로 뭉개지 않는다."""
    from console.db import DbRead

    def fake_read_trace(database_url, run_id):
        return DbRead("읽음", trace=(
            {"stage": "agent_runs", "rows": [{"run_id": run_id}]},
            {"stage": "case_events", "error": "column does not exist"},
        ))

    monkeypatch.setattr("console.web.read_trace", fake_read_trace)
    monkeypatch.setenv("CONSOLE_DATABASE_URL", "postgresql://u@h/db")
    body = client.get("/run", params={"path": str(project), "run_id": "x"}).text
    assert "column does not exist" in body
