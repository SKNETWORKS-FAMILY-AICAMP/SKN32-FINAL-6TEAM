# -*- coding: utf-8 -*-
"""약관의 보관 기간 HTTP — 공개 읽기(웹이 약관에 끼운다) · 운영 보기/바꾸기(관리 화면). `[2026-10-07 사용자 결정 — uiux 전달]`

값 · 문장 · 이력 `components/customer/retention.py` · 정리 작업 `member_cleanup.py` · 저장 056(`legal_retention` · `legal_retention_history` · `retention_runs`).

공개(고객 API 앱, 키 없음 · 개인 정보 없음):
    GET   /v1/web/legal/retention   → {revision, terms_version, cells:[{key, label_ko, label_en, value, unit, default, editable, text_ko, text_en, min?, max?}]}
운영(운영 앱, 루프백 전용 · scope `limits:read` / `limits:write` — 라우터는 인증 의존을 이미 쓰는 `web_limits_api.build_retention_ops_router`):
    GET   /admin/retention          → 위 내용 + {history:[…], purge:{mode, runs:[…]}}
    PATCH /admin/retention          {expected_revision, actor, reason, changes:{칸: 숫자|null}} → 바뀐 뒤의 같은 모양 + changed

★값이 **실제로 바뀌면** `revision` 이 오르고 약관 버전이 `…+ret{revision}` 이 된다 — 웹은 `terms_version` 을 이 응답(또는 `GET /v1/web/consents` 의 `current_version`)에서 읽어 동의를 보낸다.
  웹이 상수로 들고 있는 버전과 다르면 서버가 409 `terms_version_changed` 로 거절한다(값이 바뀐 직후의 정상 동작 — 웹이 새 버전으로 다시 동의를 받는다).
★정리 모드(`retention.purge_mode`)는 여기서 안 바꾼다 — `/admin/limits` 의 한 칸이다(같은 감사 기록).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection

from app.domains.travel_ops.components.customer import retention
from app.domains.travel_ops.modules.web_account import member_cleanup


class RetentionPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    actor: str = Field(default="", max_length=200)
    reason: str = Field(default="", max_length=500)
    changes: dict[str, StrictInt | None] = Field(min_length=1)       # 문자열 "365" 를 숫자로 받아 주지 않는다


def build_public_retention_router() -> APIRouter:
    router = APIRouter(tags=["web-legal"])

    @router.get("/v1/web/legal/retention")
    def public_retention():
        tenant = settings_module.get_settings().tenant_id
        with get_connection() as conn:
            return retention.public_view(conn, tenant)

    return router


def ops_view(conn, tenant_id: str) -> dict[str, Any]:
    """운영 화면의 보기 모양 — 공개 내용 + 이력 + 정리 모드와 최근 정리 기록(건수). 운영 라우터(`web_limits_api.build_retention_ops_router`)가 쓴다."""
    from app.domains.travel_ops.modules.web_account import web_guard

    web_guard.clear_cache()
    return {**retention.public_view(conn, tenant_id), "history": retention.history(conn, tenant_id),
            "purge": {"mode": web_guard.values(tenant_id)["retention.purge_mode"], "runs": member_cleanup.last_runs(conn, tenant_id)}}


def error(status: int, code: str, message: str, /, **detail: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **detail}})


__all__ = ["RetentionPatchIn", "build_public_retention_router", "error", "ops_view"]
