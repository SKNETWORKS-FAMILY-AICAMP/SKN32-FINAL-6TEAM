# -*- coding: utf-8 -*-
"""운영 화면 시험용 로그인 도우미. `[2026-09-23]` D-CS-007

★`/ui/*` 는 이제 로그인한 운영자만 본다. 화면을 보는 시험은 여기서 **운영자 한 명을 지금 설정 위에
  얹고** 실제 로그인 경로(`POST /ui/login`)로 들어간다 — 쿠키를 손으로 만들지 않는다. 손으로 만들면
  로그인 경로가 깨져도 시험이 초록이다.
★해시 반복 횟수를 낮춘다(1,000). 운영 기본값(600,000)이면 시험마다 수백 ms 가 든다.
"""
from __future__ import annotations

import json

import app.core.settings as settings_module
from app.presentation import security
from app.presentation.ui import auth

PASSWORD = "test-operator-password"
DEFAULT_SCOPES = ("case:read", "action:approve", "delegation:read", "delegation:write")


def as_operator(monkeypatch, *, operator_id: str = "op-test",
                scopes: tuple[str, ...] = DEFAULT_SCOPES) -> str:
    """지금 설정에 운영자 한 명을 얹는다. 로그인은 하지 않는다."""
    current = settings_module.get_settings()
    patched = current.model_copy(update={"ui_operators": json.dumps([{
        "id": operator_id, "password_hash": auth.hash_password(PASSWORD, iterations=1000),
        "scopes": list(scopes)}])})
    monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
    monkeypatch.setattr(security, "get_settings", lambda: patched)
    auth.reset_failures()
    return operator_id


def login(client, monkeypatch, *, operator_id: str = "op-test",
          scopes: tuple[str, ...] = DEFAULT_SCOPES) -> str:
    """운영자를 얹고 **실제 로그인 경로로** 들어간다. 쿠키는 `client` 에 남는다."""
    as_operator(monkeypatch, operator_id=operator_id, scopes=scopes)
    response = client.post("/ui/login", data={"operator_id": operator_id, "password": PASSWORD,
                                              "next": "/ui/cases", "csrf": login_csrf(client)},
                           follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    assert auth.COOKIE in response.cookies or auth.COOKIE in client.cookies
    return operator_id


def login_csrf(client) -> str:
    """로그인 화면을 열어 로그인 폼의 위조 방지 값을 받는다(쿠키는 `client` 에 남는다). `[2026-09-29]`"""
    import re

    page = client.get("/ui/login")
    found = re.search(r"name='csrf' value='([^']+)'", page.text)
    assert found, page.text[:300]
    return found.group(1)


def csrf(client) -> str:
    """로그인한 뒤의 폼 위조 방지 값 — 화면이 숨은 칸에 넣는 것과 같다(로그인 쿠키에서 서명). `[2026-09-29]`"""
    return auth.csrf_for(client.cookies.get(auth.COOKIE) or "")

