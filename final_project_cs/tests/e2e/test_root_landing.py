"""루트(`/`)가 쓸모 있는 화면으로 보내는지 검사한다.

★개발 서버를 띄우면 브라우저가 `/` 로 열린다. 거기가 404 면
  "서버가 안 떴나" 로 읽힌다 — 실제로 그렇게 읽혔다.

★단, UI 모듈이 전부 꺼져 있으면 리다이렉트를 만들지 않는다.
  없는 화면으로 보내면 404 를 한 번 더 거쳐서 만나게 될 뿐이다.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.ui import mount_ui


def _client(path: Path) -> TestClient:
    app = FastAPI()
    app.state.project_config_path = path
    mount_ui(app)
    return TestClient(app)


def _write(tmp: Path, **modules) -> Path:
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    for name, enabled in modules.items():
        data["modules"][name]["enabled"] = enabled
    path = tmp / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def workdir():
    path = Path(".root-landing-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def test_root_redirects_to_cases_when_ops_ui_is_on(workdir):
    client = _client(_write(workdir, ops_ui=True))
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/cases"


def test_root_stays_404_when_every_ui_module_is_off(workdir):
    """★없는 화면으로 보내지 않는다."""
    client = _client(_write(workdir, ops_ui=False))
    assert client.get("/", follow_redirects=False).status_code == 404


def test_root_actually_lands_on_a_real_page(workdir):
    client = _client(_write(workdir, ops_ui=True))
    landed = client.get("/")  # follow_redirects 기본 True
    assert landed.status_code == 200
    assert "Case 목록" in landed.text
