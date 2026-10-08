# -*- coding: utf-8 -*-
"""운영 앱이 **다른 프로세스**의 고객 API 를 실제 HTTP 로 불러 일한다. `[2026-09-29 사용자 지시]` 운영자 콘솔 분리

★완료 기준 「운영 기능(승인 · 위임 · 바깥함 · 조회)이 별도 프로세스에서 동작」을 그대로 잰다 — 고객 API 앱을
  uvicorn 으로 **따로 띄우고**(다른 프로세스 · 빈 포트), 운영 앱은 그 주소를 설정으로만 안다. 두 앱을 잇는
  시험용 자리(`routes.API_TRANSPORT`)를 쓰지 않는다.
★운영 앱의 scope 키는 운영 앱 설정(`ops_api_keys`)으로만 준다. 고객 앱이 받는 키와 같은 값이다(같은 비밀키).
★폼 위조 방지 — 확인값 없이 누른 승인은 403 이고 **DB 에 아무것도 안 생긴다.**
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from psycopg.types.json import Json

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.ui import auth
from tests.ui_login import csrf, login

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture()
def world(monkeypatch):
    original = settings_module.get_settings()
    tenant = "opsproc_" + uuid4().hex[:10]
    customer, case_id, action_id = uuid4(), uuid4(), uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "ops two processes"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,'c')", (customer, tenant))
        cur.execute("""INSERT INTO customer_cases (case_id,tenant_id,customer_id,status,subject,state_json,version)
                       VALUES (%s,%s,%s,'waiting_approval','two processes','{}',1)""", (case_id, tenant, customer))
        cur.execute("""INSERT INTO action_requests (action_id,tenant_id,case_id,action_type,arguments_json,
                       idempotency_key,status) VALUES (%s,%s,%s,'refund.request',%s,%s,'pending_approval')""",
                    (action_id, tenant, case_id,
                     Json({"amount": 100, "evidence": [{"source_type": "policy", "source_id": "d#1", "claim": "c"}]}),
                     "idem-" + str(action_id)))
    # ── 고객 API 앱 — 다른 프로세스 ──
    port = _free_port()
    env = {**os.environ, "ACOP_TENANT_ID": tenant, "PYTHONIOENCODING": "utf-8"}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.presentation.api.app:app", "--host", "127.0.0.1",
                               "--port", str(port)], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if httpx.get(base + "/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            pytest.fail("고객 API 앱이 90초 안에 뜨지 않았다")
        # ── 운영 앱 — 이 프로세스. 고객 API 는 주소와 키로만 안다 ──
        keys = {s: security._development_key(s, original.secret_key)
                for s in ("action:approve", "delegation:read", "delegation:write")}
        patched = original.model_copy(update={"tenant_id": tenant, "ops_api_base_url": base,
                                              "ops_api_keys": json.dumps(keys), "ui_operators": ""})
        monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
        monkeypatch.setattr(security, "get_settings", lambda: patched)
        auth.reset_failures()
        from fastapi.testclient import TestClient

        from app.ops_entrypoint import create_ops_app

        client = TestClient(create_ops_app(routers=[]), raise_server_exceptions=False)
        login(client, monkeypatch)
        yield {"client": client, "tenant": tenant, "case_id": case_id, "action_id": action_id, "base": base}
    finally:
        server.terminate()
        server.wait(timeout=30)
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM action_approvals WHERE action_id=%s", (action_id,))
            for table in ("case_events", "action_requests", "customer_cases", "customers", "tenants"):
                cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))


def _approvals(action_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT approver_id, decision FROM action_approvals WHERE action_id=%s", (action_id,))
        return cur.fetchall()


def test_an_approval_from_the_ops_app_reaches_the_customer_api_in_another_process(world):
    url = f"/ui/approvals/{world['case_id']}/{world['action_id']}"
    # 폼 확인값 없이 — 막히고 아무것도 안 생긴다
    forged = world["client"].post(url, data={"decision": "rejected"}, follow_redirects=False)
    assert forged.status_code == 403 and forged.json()["error"]["code"] == "csrf_failed"
    assert _approvals(world["action_id"]) == []
    # 화면에서 누른 것처럼 — 다른 프로세스의 고객 API 가 기록한다(승인자 = 로그인한 운영자)
    done = world["client"].post(url, data={"decision": "rejected", "csrf": csrf(world["client"])},
                                follow_redirects=False)
    assert done.status_code == 303, done.text[:400]
    assert _approvals(world["action_id"]) == [("op-test", "rejected")]
    # 같은 승인을 다시 보내도 두 번 기록되지 않는다 — 고객 API 가 같은 승인자 · 같은 결정을 **멱등 키**로 묶어
    #   앞 결과를 돌려준다(`cases.py` approve). 시간 초과 뒤 운영자가 다시 눌러도 두 번 실행되지 않는다
    again = world["client"].post(url, data={"decision": "rejected", "csrf": csrf(world["client"])},
                                 follow_redirects=False)
    assert again.status_code == 303
    assert _approvals(world["action_id"]) == [("op-test", "rejected")]


def test_the_ops_screens_read_and_the_customer_api_is_only_reached_over_http(world):
    client = world["client"]
    assert str(world["case_id"])[:8] in client.get("/ui/cases").text           # 조회 — 운영 앱의 읽기 연결
    delegations = client.get("/ui/delegations")                                # 위임 — 다른 프로세스 고객 API
    assert delegations.status_code == 200 and "현황을 읽지 못했습니다" not in delegations.text
    # 고객 API 앱에는 운영 화면이 없다(다른 프로세스에 직접 물어도)
    assert httpx.get(world["base"] + "/ui/cases", timeout=5).status_code == 404


def test_a_missing_ops_key_sends_nothing_and_says_so(world, monkeypatch):
    current = settings_module.get_settings()
    no_keys = current.model_copy(update={"ops_api_keys": ""})
    monkeypatch.setattr(settings_module, "get_settings", lambda: no_keys)
    response = world["client"].post(f"/ui/approvals/{world['case_id']}/{world['action_id']}",
                                    data={"decision": "rejected", "csrf": csrf(world["client"])})
    assert response.status_code == 200 and "ops_api_key_missing" in response.text
    assert _approvals(world["action_id"]) == []
