"""**운영 앱** 진입점 — 운영자 콘솔(로그인 · Case · 승인 · 위임 · 바깥함 · VOC · 관리) · 웹 제한값 운영 API · 시나리오 모드.

`[2026-09-29 사용자 지시]` 「외부에서 절대 접근 못 하게, 가능한 물리적으로 분리」(ui 세션 · Codex 합의 1단계).
★고객 API 앱(`app.presentation.api.app:app`, 8042)과 **다른 프로세스 · 다른 포트**다. 이 파일은 고객 API 앱 객체를
  import 하지 않는다(`tests/architecture/test_ops_app_is_separate.py`). 운영 화면의 승인 · 위임 · 바깥함은 고객 API 를
  **실제 HTTP** 로 부른다(`ACOP_OPS_API_BASE_URL` · 키 `ACOP_OPS_API_KEYS`).
★이 기계 안에서만 닿는다 — 두 겹:
  ① 띄울 때 `python -m app.ops_entrypoint` 는 127.0.0.1 · ::1 · localhost 가 아닌 주소를 **거부**한다.
  ② 요청마다 루프백이 아닌 곳에서 온 요청은 403 이다(누가 uvicorn 으로 0.0.0.0 에 띄워도 바깥 요청은 못 들어온다).
     원격 운영은 SSH 터널로 — 터널로 들어온 요청은 루프백이다.
★이것은 **1단계(같은 기계의 다른 프로세스)** 다. 다른 기계 · 사설망 + VPN · SSH 터널만 여는 **2단계 전에는
  「물리 분리 완료」라고 쓰지 않는다**(Codex 합의).

실행: `python -m app.ops_entrypoint` (기본 127.0.0.1:8070 — 설정 `ACOP_OPS_PORT`).
"""
from __future__ import annotations

import argparse
import sys

from fastapi import FastAPI
from starlette.responses import JSONResponse

from app import composition
from app.core.settings import get_settings
from app.presentation.errors import install_error_handlers
from app.presentation.ui import mount_ui

#: 운영 앱이 묶일 수 있는 주소 · 받아 주는 요청 출처. `testclient` 는 시험 도구의 이름이다(네트워크에서 올 수 없다)
LOOPBACK_BINDS = frozenset({"127.0.0.1", "::1", "localhost"})
LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


class LoopbackOnly:
    """루프백이 아닌 곳에서 온 HTTP 요청은 403 — 앱 앞에서 끊는다(라우팅 · 로그인 전에)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            host = (scope.get("client") or ("", 0))[0]
            if host not in LOOPBACK_CLIENTS:
                response = JSONResponse({"error": {"code": "ops_local_only",
                                                   "message": "운영 앱은 이 기계 안에서만 연다"}}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_ops_app(*, routers: list | None = None) -> FastAPI:
    """운영 앱을 조립한다. `routers` — 시험이 도메인 경로를 갈아 끼우는 자리(없으면 `composition.build_ops_routers()`)."""
    app = FastAPI(title="triPilot 운영 콘솔")
    app.add_middleware(LoopbackOnly)
    mount_ui(app)
    # 관리자 웹앱의 JSON 표면도 이 운영 프로세스에만 등록한다.
    from app.presentation.admin_api import build_router as build_admin_router

    app.include_router(build_admin_router(snapshot_provider=composition.build_admin_snapshot))
    for router in (composition.build_ops_routers() if routers is None else routers):
        app.include_router(router)
    install_error_handlers(app)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "ops"}

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="triPilot 운영 앱 — 이 기계 안에서만")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    if args.host not in LOOPBACK_BINDS:
        print(f"운영 앱은 127.0.0.1 · ::1 · localhost 에만 묶는다 — 받은 값 {args.host!r}. 원격 운영은 SSH 터널로 연다.",
              file=sys.stderr)
        return 2
    import uvicorn

    uvicorn.run("app.ops_entrypoint:app", host=args.host, port=args.port or get_settings().ops_port)
    return 0


app = create_ops_app()

if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["LOOPBACK_BINDS", "LOOPBACK_CLIENTS", "LoopbackOnly", "app", "create_ops_app", "main"]
