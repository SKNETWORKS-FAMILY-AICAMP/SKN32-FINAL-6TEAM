"""설정 서비스 — 중앙 1곳에서 수천 대상의 구성을 관리하는 진입점.

★왜 별도 진입점인가 (`program/plan/A-COP_Composer_중앙설정저장소_결정.md`)

  대상(cs)에 쓰기 코드를 넣지 않기로 했다. 그러면 쓰기는 어딘가 **한 곳**에서
  돌아야 하는데, 그게 이 앱이다. 고객 대면 API(`/v1/cases`)도, Team 조립도,
  LLM 도 필요 없다 — 선언을 검증하고 저장하고 감사에 남기는 일만 한다.

  그래서 `create_app()`(고객 런타임)을 쓰지 않는다. 그걸 쓰면 Controller 를
  조립하느라 OpenAI 키·도메인 모듈·RAG 까지 요구하는데, 설정 서비스에는
  그중 어느 것도 필요 없고 있어서도 안 된다.

★대상은 **요청**이 지정한다(`X-Deployment-Id`). 이 앱은 자기 설정의 대상
  하나가 아니라 수천 개를 다루기 때문이다. 헤더가 없으면 거부한다 — 기본
  대상으로 떨어지면 남의 설정을 건드리는 사고가 조용히 일어난다.

★배포·운영(HA·백업·네트워크 경계)은 **아직 하지 않는다.** 실제 고객이
  생기고 토폴로지가 정해진 뒤다. 지금은 코드 경로만 갖춰 둔다 — 그래야 첫
  릴리즈 때 마이그레이션 없이 중앙으로 시작할 수 있고, 지금은 서버를 안 켜니
  운영 부담이 0이다.

실행 대상: `acop_composer.service_app:app`
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from acop_composer.api import router as composer_write_router
from acop_composer.auth import router as composer_auth_router


def create_config_service_app() -> FastAPI:
    """Composer 와 토큰 발급만 있는 앱. 고객 API 는 없다."""
    app = FastAPI(title="A-COP Config Service")
    # ★이 플래그가 "대상을 요청에서 받는다" 를 켠다(`acop_composer.api`).
    app.state.multi_deployment = True

    app.include_router(composer_write_router)
    app.include_router(composer_auth_router)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "error": {"code": "http_error", "message": str(exc.detail)}
        }
        return JSONResponse(status_code=exc.status_code, content=detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={
            "error": {"code": "validation_error", "message": "request validation failed"}})

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        return JSONResponse(status_code=500, content={
            "error": {"code": "internal_error", "message": "internal server error"}})

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "config"}

    return app


app = create_config_service_app()

__all__ = ["create_config_service_app", "app"]
