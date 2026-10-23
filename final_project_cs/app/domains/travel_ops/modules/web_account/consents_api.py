# -*- coding: utf-8 -*-
"""약관 동의 HTTP — 계약 `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md`. `[2026-10-05]`

    GET  /v1/web/consents    지금 동의 상태 → {current_version, required, items:[{code, agreed, version, agreed_at}], ok}
    POST /v1/web/consents    동의 · 철회 기록 {version, items:[{code, agreed, text_sha256}]} → 같은 모양(보낸 항목만 바꾼다)

★세션(쿠키 · 옛 키)이 있으면 된다 — 게스트도 같다. 쿠키로 쓰면 CSRF 까지 본다. **에이전트 키로는 못 한다**(`agent_forbidden` — 동의는 사람이 브라우저에서 한다).
★이 길은 사용 조건(게이트)에서 면제다(`consents.EXEMPT_PREFIXES`) — 동의하러 오는 길을 막으면 아무도 못 쓴다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.infrastructure.db.session import get_connection

from app.domains.travel_ops.components.customer import consents
from app.domains.travel_ops.modules.web_account import web_cookie
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.modules.live_progress import op_stream


def build_consents_router() -> APIRouter:
    router = APIRouter()

    def _kind(who: web_cookie.Identity) -> str:
        return who.session.kind if who.session is not None else "key"

    def _ip(http: Request) -> str:
        return web_guard.client_ip(http.client.host if http.client else None, http.headers.get("x-forwarded-for"))

    @router.get("/v1/web/consents")
    async def consents_state(http: Request, who: web_cookie.Identity = Depends(web_cookie.require_identity)):
        def read(progress=None):
            with get_connection() as conn:
                return consents.state(conn, who.tenant_id, who.customer_id, progress=progress)

        if "text/event-stream" not in http.headers.get("accept", "").lower():
            return JSONResponse(await run_in_threadpool(read), headers={"Cache-Control": "no-store"})
        cfg = op_stream.limits("consents")
        if not op_stream.acquire(who.tenant_id, who.customer_id, cap=int(cfg["max_per_user"])):
            refused = web_cookie.refuse(429, "too_many_streams", "실시간 확인이 너무 많이 열려 있어요. 잠시 뒤 다시 시도해 주세요.")
            refused.headers = {"Retry-After": "5"}
            raise refused

        async def flow():
            try:
                async for chunk in op_stream.run(lambda progress, _defer: read(progress.stage), op="consents",
                                                 is_disconnected=http.is_disconnected, cfg=cfg):
                    yield chunk
            finally:
                op_stream.release(who.tenant_id, who.customer_id)

        return StreamingResponse(flow(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @router.post("/v1/web/consents")
    def consents_record(http: Request, body: dict[str, Any] = Body(...), who: web_cookie.Identity = Depends(web_cookie.require_identity)):
        """보낸 항목만 바꾼다. 버전이 지금과 다르면 409 `terms_version_changed`(지금 버전을 싣는다) · 모르는 코드 422 `unknown_code` · 해시 모양 422 `invalid_text_sha256`.
        필수 항목을 `agreed:false` 로 보내면 기록하고 `ok:false`(앱 사용 중지)가 된다."""
        try:
            with get_connection() as conn:
                result = consents.record(conn, tenant_id=who.tenant_id, user_id=who.customer_id, session_kind=_kind(who),
                                         version=body.get("version"), items=body.get("items"), ip=_ip(http),
                                         user_agent=http.headers.get("user-agent"))
        except consents.ConsentError as refused:
            raise web_cookie.refuse(refused.status, refused.code, refused.message, **refused.extra) from None
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    return router


__all__ = ["build_consents_router"]
