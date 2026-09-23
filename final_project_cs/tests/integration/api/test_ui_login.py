# -*- coding: utf-8 -*-
"""운영 화면 로그인 — **막혀야 할 것이 실제로 막히는가**. `[2026-09-23]` D-CS-007

★★왜. `/ui/*` 에는 로그인이 없었다. 그런데 승인·바깥함 해소·위임 버튼은 서버가 scope 키를
  **스스로 만들어** API 를 불렀다 — `/ui` 에 닿기만 하면 인증 없이 승인 권한을 쓰는 구조였고,
  승인자는 전부 `ui-operator` 로 남아 누가 눌렀는지 알 수 없었다.

★★200 만 보고 통과시키지 않는다. 「막혔다」는 **DB 에 아무것도 안 생겼다**로 확인한다.

재현:

    python -m pytest tests/integration/api/test_ui_login.py -v
"""
from __future__ import annotations

import json
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Json

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app
from app.presentation.ui import auth
from tests.ui_login import PASSWORD, as_operator, login


@pytest.fixture()
def world(monkeypatch):
    """승인 대기 중인 제안 하나가 있는 테넌트."""
    original = settings_module.get_settings()
    tenant = "uilogin_" + uuid4().hex[:10]
    patched = original.model_copy(update={"tenant_id": tenant, "ui_operators": ""})
    monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
    monkeypatch.setattr(security, "get_settings", lambda: patched)
    auth.reset_failures()
    customer, case_id, action_id = uuid4(), uuid4(), uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "ui login"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,'c')",
                    (customer, tenant))
        cur.execute("""INSERT INTO customer_cases (case_id,tenant_id,customer_id,status,subject,state_json,version)
                       VALUES (%s,%s,%s,'waiting_approval','login test','{}',1)""", (case_id, tenant, customer))
        cur.execute("""INSERT INTO action_requests (action_id,tenant_id,case_id,action_type,arguments_json,
                       idempotency_key,status) VALUES (%s,%s,%s,'refund.request',%s,%s,'pending_approval')""",
                    (action_id, tenant, case_id,
                     Json({"amount": 100, "evidence": [{"source_type": "policy", "source_id": "d#1",
                                                        "claim": "c"}]}), "idem-" + str(action_id)))
    client = TestClient(create_app(), raise_server_exceptions=False)
    yield {"client": client, "tenant": tenant, "case_id": case_id, "action_id": action_id}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM action_approvals WHERE action_id=%s", (action_id,))
        for table in ("case_events", "action_requests", "customer_cases", "customers", "tenants"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))


def _approvals(action_id) -> list[tuple]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT approver_id, decision FROM action_approvals WHERE action_id=%s", (action_id,))
        return cur.fetchall()


def _approve_url(world) -> str:
    return f"/ui/approvals/{world['case_id']}/{world['action_id']}"


# ── 막히는가 ────────────────────────────────────────────────────
@pytest.mark.parametrize("path", ["/ui/cases", "/ui/approvals", "/ui/delegations", "/ui/admin",
                                  "/ui/scenario", "/ops/outbox", "/ui/ops/outbox"])
def test_every_screen_sends_a_stranger_to_the_login_page(world, path):
    response = world["client"].get(path, follow_redirects=False)
    assert response.status_code == 303, (path, response.status_code)
    assert response.headers["location"].startswith("/ui/login?next=")


def test_a_stranger_cannot_approve_and_nothing_is_recorded(world):
    """★★이것이 막으려던 구멍이다 — 전에는 이 요청 하나로 승인이 났다."""
    response = world["client"].post(_approve_url(world), data={"decision": "approved"},
                                     follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/ui/login")
    assert _approvals(world["action_id"]) == [], "로그인 안 한 요청으로 승인이 기록됐다"


def test_with_no_operator_configured_the_screen_is_closed(world):
    """★기본이 닫힘이다 — 계정이 하나도 없으면 아무도 못 들어온다."""
    page = world["client"].get("/ui/login")
    assert "운영자 계정이 하나도 설정되지 않았습니다" in page.text
    response = world["client"].post("/ui/login", data={"operator_id": "anyone", "password": "x"},
                                    follow_redirects=False)
    assert response.status_code == 401 and auth.COOKIE not in response.cookies


# ── 들어가는가 ──────────────────────────────────────────────────
def test_a_logged_in_approval_names_the_real_operator(world, monkeypatch):
    """★승인자가 `ui-operator` 가 아니라 **누른 사람**으로 남는다."""
    login(world["client"], monkeypatch, operator_id="op-kim")
    response = world["client"].post(_approve_url(world), data={"decision": "rejected"},
                                     follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    assert _approvals(world["action_id"]) == [("op-kim", "rejected")]


def test_without_the_scope_the_button_does_nothing_and_says_why(world, monkeypatch):
    login(world["client"], monkeypatch, operator_id="viewer", scopes=("case:read",))
    assert world["client"].get("/ui/approvals").status_code == 200        # 보는 것은 된다
    response = world["client"].post(_approve_url(world), data={"decision": "approved"},
                                     follow_redirects=False)
    assert response.status_code == 403
    assert "action:approve" in response.text and "아무것도 바뀌지 않았습니다" in response.text
    assert _approvals(world["action_id"]) == []


def test_the_page_shows_who_is_logged_in_and_logout_works(world, monkeypatch):
    login(world["client"], monkeypatch, operator_id="op-kim")
    page = world["client"].get("/ui/cases")
    assert page.status_code == 200 and "op-kim" in page.text and "/ui/logout" in page.text
    world["client"].post("/ui/logout", follow_redirects=False)
    assert world["client"].get("/ui/cases", follow_redirects=False).status_code == 303


# ── 비밀번호 · 잠금 ─────────────────────────────────────────────
def test_a_wrong_password_and_an_unknown_id_look_the_same(world, monkeypatch):
    """★어느 id 가 있는지 알려 주지 않는다."""
    as_operator(monkeypatch, operator_id="op-kim")
    wrong = world["client"].post("/ui/login", data={"operator_id": "op-kim", "password": "nope"})
    ghost = world["client"].post("/ui/login", data={"operator_id": "op-ghost", "password": "nope"})
    assert wrong.status_code == ghost.status_code == 401
    assert "id 또는 비밀번호가 맞지 않습니다" in wrong.text and "id 또는 비밀번호가 맞지 않습니다" in ghost.text


def test_repeated_failures_lock_the_id_even_for_the_right_password(world, monkeypatch):
    as_operator(monkeypatch, operator_id="op-kim")
    limit = int(settings_module.get_guardrails().get("security.ui_login_max_failures"))
    for _ in range(limit):
        world["client"].post("/ui/login", data={"operator_id": "op-kim", "password": "nope"})
    right = world["client"].post("/ui/login", data={"operator_id": "op-kim", "password": PASSWORD},
                                 follow_redirects=False)
    assert right.status_code == 429 and auth.COOKIE not in right.cookies
    assert "잠시 막혔습니다" in right.text


def test_the_stored_value_is_a_hash_not_the_password():
    stored = auth.hash_password("correct horse battery", iterations=1000)
    assert "correct horse battery" not in stored and stored.startswith("pbkdf2_sha256$1000$")
    assert auth.verify_password("correct horse battery", stored)
    assert not auth.verify_password("correct horse batterY", stored)


# ── 쿠키 ────────────────────────────────────────────────────────
def test_a_tampered_cookie_is_refused(world, monkeypatch):
    """★scope 를 손으로 늘린 쿠키를 받아 주면 로그인이 장식이 된다."""
    as_operator(monkeypatch, operator_id="viewer", scopes=("case:read",))
    token = auth.issue(auth.Operator("viewer", frozenset({"case:read"})))
    payload, sig = token.rsplit(".", 1)
    forged = auth._b64(json.dumps({"sub": "viewer", "scopes": ["action:approve"],
                                   "exp": int(time.time()) + 3600}).encode())
    assert auth.read(forged + "." + sig) is None
    assert auth.read(token) is not None


def test_an_expired_cookie_is_refused(monkeypatch):
    as_operator(monkeypatch, operator_id="op-kim")
    old = auth.issue(auth.Operator("op-kim", frozenset({"case:read"})), now=time.time() - 10 * 3600)
    assert auth.read(old) is None


def test_removing_an_operator_or_a_scope_takes_effect_on_the_next_request(monkeypatch):
    """★쿠키만 믿으면 권한을 거둬도 만료(8시간)까지 버틴다."""
    as_operator(monkeypatch, operator_id="op-kim", scopes=("case:read", "action:approve"))
    token = auth.issue(auth.Operator("op-kim", frozenset({"case:read", "action:approve"})))
    as_operator(monkeypatch, operator_id="op-kim", scopes=("case:read",))
    assert auth.read(token).scopes == frozenset({"case:read"})
    as_operator(monkeypatch, operator_id="someone-else")
    assert auth.read(token) is None


def test_the_cookie_is_not_readable_by_scripts_or_sent_cross_site(world, monkeypatch):
    as_operator(monkeypatch, operator_id="op-kim")
    response = world["client"].post("/ui/login", data={"operator_id": "op-kim", "password": PASSWORD},
                                    follow_redirects=False)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


@pytest.mark.parametrize("target", ["https://evil.example/ui", "//evil.example/ui", "/tripilot", ""])
def test_after_login_it_never_goes_outside_the_console(world, monkeypatch, target):
    """★`?next=` 에 바깥 주소를 받으면 우리 로그인 화면이 피싱 발판이 된다."""
    as_operator(monkeypatch, operator_id="op-kim")
    response = world["client"].post("/ui/login", data={"operator_id": "op-kim", "password": PASSWORD,
                                                       "next": target}, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/ui/cases"


def test_a_broken_operator_setting_is_said_out_loud(world, monkeypatch):
    """★설정이 깨졌는데 「계정 없음」처럼 보이면 왜 못 들어가는지 모른다."""
    broken = settings_module.get_settings().model_copy(update={"ui_operators": "{not json"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: broken)
    assert "운영자 설정이 잘못됐습니다" in world["client"].get("/ui/login").text
