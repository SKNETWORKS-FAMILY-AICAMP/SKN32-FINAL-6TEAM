# -*- coding: utf-8 -*-
"""운영 API — 웹 제한값 보기 · 바꾸기 · 바꾼 기록. `[2026-09-28]` 사용자 지시(관리 콘솔의 설정 탭에서 바꾼다)

계약 `wiki/external/rest-endpoints.md` 「남용 방어」 · 저장 `runtime_limits` · `runtime_limit_state` · `runtime_limit_events`(031).

★scope 를 둘로 나눈다 — `limits:read`(보기) · `limits:write`(바꾸기). `ops:reload` 를 나눈 것과 같은 기준(영향 범위).
★scope 키를 브라우저에 두지 않는다. 운영자 로그인을 확인한 **콘솔 서버**가 부르고 `actor`(운영자 id)를 싣는다.
  이 API 는 그 값을 믿는다(한계) — 그래서 감사 줄에 부른 scope 키 id 도 함께 남긴다.
★바꾸기는 `expected_revision` 이 지금 판과 같을 때만 — 두 운영자가 같은 화면을 보고 바꾸면 뒤엣것이 409.
★라우터는 도메인 폴더에 둔다(presentation 은 도메인을 import 하지 못한다 — INV-CS-ARCH-001, 위임 API 와 같은 이유).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.types.json import Json
from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import get_guardrails
from app.infrastructure.db.session import get_connection
from app.presentation.security import Principal, require_scope

from app.domains.travel_ops.modules.web_account import web_guard


class LimitsPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    actor: str = Field(default="", max_length=200)
    reason: str = Field(default="", max_length=500)
    changes: dict[str, Any] = Field(min_length=1)


# ★`status` 를 **위치 전용**(`/`)으로 받는다 — `**extra` 에 상세로 `status` 가 들어오면(예: 아직 등록할 수 없는 접수의 현재 상태
#   `IntakeConflict(..., status=...)`) 같은 이름이 둘이라 `TypeError: got multiple values for argument 'status'` 로 409 가 서버 오류(500)가 됐다.
def _error(status: int, code: str, message: str, /, **detail: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **detail}})


def _revision(cur, tenant_id: str, *, lock: bool = False) -> int:
    cur.execute("INSERT INTO runtime_limit_state (tenant_id) VALUES (%s) ON CONFLICT DO NOTHING", (tenant_id,))
    cur.execute("SELECT revision FROM runtime_limit_state WHERE tenant_id=%s" + (" FOR UPDATE" if lock else ""),
                (tenant_id,))
    return int(cur.fetchone()[0])


def _view(tenant_id: str) -> dict[str, Any]:
    table = web_guard.specs()
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            revision = _revision(cur, tenant_id)
        stored = web_guard.overrides(conn, tenant_id)
        usage = web_guard.usage_today(conn, tenant_id)
    limits = []
    for name, spec in table.items():
        row = stored.get(name)
        in_range = row is not None and spec.check(row["value"]) is None
        limits.append({**spec.as_dict(), "value": row["value"] if in_range else spec.default,
                       "source": "override" if in_range else "default",
                       "updated_at": row["updated_at"].isoformat() if row else None,
                       "updated_by": row["updated_by"] if row else None})
    return {"revision": revision, "applies_within_seconds": int(get_guardrails().get("web_guard.cache_seconds")),
            "limits": limits, "usage_today": usage}


def build_limits_router() -> APIRouter:
    router = APIRouter(tags=["ops-limits"])

    @router.get("/admin/limits")
    def read_limits(principal: Principal = Depends(require_scope("limits:read"))):
        return _view(principal.tenant_id)

    @router.patch("/admin/limits")
    def change_limits(request: LimitsPatchIn, principal: Principal = Depends(require_scope("limits:write"))):
        if not request.actor.strip():
            raise _error(422, "actor_required", "누가 바꾸는지(운영자 id)가 없다 — 콘솔 서버가 로그인한 운영자를 싣는다")
        if not request.reason.strip():
            raise _error(422, "reason_required", "바꾸는 이유를 적는다 — 감사 기록에 남는다")
        table = web_guard.specs()
        for name, value in request.changes.items():
            spec = table.get(name)
            if spec is None:
                raise _error(422, "unknown_limit", "바꿀 수 있는 이름이 아니다", name=name, known=sorted(table))
            problem = None if value is None else spec.check(value)
            if problem:
                raise _error(422, problem, "값이 맞지 않는다", name=name, type=spec.type, min=spec.min, max=spec.max,
                             choices=list(spec.choices) if spec.choices else None)
        tenant = principal.tenant_id
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            current = _revision(cur, tenant, lock=True)
            if current != request.expected_revision:
                raise _error(409, "stale_revision", "그 사이 다른 운영자가 바꿨다 — 다시 읽고 바꾼다",
                             current_revision=current)
            revision = current + 1
            stored = web_guard.overrides(conn, tenant)
            for name, value in request.changes.items():
                old = stored.get(name, {}).get("value")
                if value is None:
                    cur.execute("DELETE FROM runtime_limits WHERE tenant_id=%s AND name=%s", (tenant, name))
                else:
                    cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,%s,%s,%s) "
                                "ON CONFLICT (tenant_id, name) DO UPDATE SET value=EXCLUDED.value, "
                                "updated_at=now(), updated_by=EXCLUDED.updated_by",
                                (tenant, name, Json(value), request.actor.strip()))
                cur.execute("INSERT INTO runtime_limit_events (tenant_id, revision, name, old_value, new_value, actor, "
                            "key_id, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (tenant, revision, name, None if old is None else Json(old),
                             None if value is None else Json(value), request.actor.strip(), principal.key_id,
                             request.reason.strip()))
            cur.execute("UPDATE runtime_limit_state SET revision=%s WHERE tenant_id=%s", (revision, tenant))
        web_guard.clear_cache()       # 이 프로세스는 바로. 다른 프로세스는 `cache_seconds` 안에
        return _view(tenant)

    @router.get("/admin/limits/events")
    def limit_events(limit: int = Query(50, ge=1, le=500),
                     principal: Principal = Depends(require_scope("limits:read"))):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT at, revision, actor, key_id, name, old_value, new_value, reason FROM runtime_limit_events "
                        "WHERE tenant_id=%s ORDER BY seq DESC LIMIT %s", (principal.tenant_id, limit))
            rows = cur.fetchall()
        return {"events": [{"at": r[0].isoformat(), "revision": r[1], "actor": r[2], "key_id": r[3], "name": r[4],
                            "old": r[5], "new": r[6], "reason": r[7]} for r in rows]}

    return router


__all__ = ["LimitsPatchIn", "build_limits_router"]
