# -*- coding: utf-8 -*-
"""시험용 운영 앱 — **운영 앱**과 **고객 API 앱**을 HTTP 경계로 잇는다. `[2026-09-29]` 운영자 콘솔 분리

★운영 화면은 이제 고객 API 앱(8042)에 없다 — 별도 운영 앱(`app/ops_entrypoint.py`)이다. 운영 화면의 승인 · 위임 ·
  바깥함은 고객 API 를 **HTTP 로** 부른다. 시험은 그 HTTP 자리(`routes.API_TRANSPORT`)에 고객 API 앱을 끼운다 —
  두 앱은 여전히 다른 객체이고, 운영 앱은 고객 앱을 import 하지 않는다.
★운영 앱의 scope 키는 **운영 앱 설정**(`ops_api_keys`)으로만 넣는다 — 운영 앱이 스스로 만들지 않는다.
  시험 키는 고객 앱이 받는 시험용 scope 키(`security._development_key`)다.
"""
from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.presentation import security

#: 운영 화면이 고객 API 를 부를 때 쓰는 scope
OPS_SCOPES = ("action:approve", "delegation:read", "delegation:write")


def ops_client(monkeypatch, *, customer_app=None, routers=None, **client_kwargs) -> TestClient:
    """운영 앱 시험 클라이언트. `customer_app` 을 주면 운영 앱의 고객 API 호출이 그 앱으로 간다(HTTP 경계)."""
    from app.ops_entrypoint import create_ops_app
    from app.presentation.ui import routes

    if customer_app is not None:
        current = settings_module.get_settings()
        keys = {scope: security._development_key(scope, current.secret_key) for scope in OPS_SCOPES}
        patched = current.model_copy(update={"ops_api_keys": json.dumps(keys),
                                             "ops_api_base_url": "http://customer-api"})
        monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
        monkeypatch.setattr(security, "get_settings", lambda: patched)
        monkeypatch.setattr(routes, "API_TRANSPORT", httpx.ASGITransport(app=customer_app))
    return TestClient(create_ops_app(routers=routers), **client_kwargs)


__all__ = ["OPS_SCOPES", "ops_client"]
