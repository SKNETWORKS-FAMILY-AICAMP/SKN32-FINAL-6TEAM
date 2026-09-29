"""오류 응답 모양 — 고객 API 앱과 운영 앱이 **같은 모양**을 쓴다. `[2026-09-29]` 운영자 콘솔 분리 때 떼어 냈다.

★두 앱이 따로 들고 있으면 한쪽만 고쳐져 어긋난다(예: 303 의 `Location` 헤더를 버리던 결함 — 2026-09-23).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def install_error_handlers(app: FastAPI, *, origins: list[str] | tuple[str, ...] = ()) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "error": {"code": "http_error", "message": str(exc.detail)}
        }
        # ★`[2026-09-23]` 헤더를 버리고 있었다 — 운영 화면 관문의 303 에 `Location` 이 빠져 브라우저가
        #   로그인 화면으로 못 갔다. 예외가 들고 온 헤더(`Location`·`WWW-Authenticate` 등)는 그대로 싣는다.
        return JSONResponse(status_code=exc.status_code, content=detail,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error",
                                                                "message": "request validation failed"}})

    @app.exception_handler(Exception)
    async def internal_error(request: Request, _exc: Exception):
        # ★`[2026-09-28]` 처리 안 된 예외의 응답은 허용 헤더를 붙이는 층 **바깥**에서 만들어져 `Access-Control-Allow-Origin` 이
        #   빠졌다 — 브라우저가 오류 문장을 못 읽어 화면이 「서버에 연결하지 못했어요」로 잘못 보였다(ui 세션 실측, 등록 확인 500).
        #   허용한 출처에만 같은 헤더를 직접 붙인다
        origin = request.headers.get("origin")
        headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"} if origin and origin in origins else None
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error",
                                                                "message": "internal server error"}},
                            headers=headers)


__all__ = ["install_error_handlers"]
