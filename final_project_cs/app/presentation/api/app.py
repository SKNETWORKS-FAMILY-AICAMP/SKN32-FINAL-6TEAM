from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import composition
from app.presentation.api.cases import build_router
from app.presentation.api.outbox import build_router as build_outbox_router
from app.presentation.api.composer import router as composer_write_router
from app.presentation.api.introspection import router as introspection_router
from app.presentation.composer_auth import router as composer_auth_router
from app.presentation.ui import mount_ui


def create_app(controller=None, classifier=None) -> FastAPI:
    injected_controller = controller is not None
    if classifier is None:
        classifier = composition.build_classifier()
    if controller is None:
        controller = composition.build_controller()
    app = FastAPI(title="A-COP S-API")
    # A classifier-only override is the legacy test seam.  Explicit controller
    # injection and the configured production path both execute the runtime.
    runtime_controller = controller if injected_controller or getattr(classifier, "__module__", "").startswith("app.composition") else None
    app.include_router(build_router(classifier, runtime_controller))
    app.include_router(build_outbox_router())
    app.include_router(composer_auth_router)
    app.include_router(composer_write_router)
    app.include_router(introspection_router)
    # 운영 화면(Case/Trace/Approval/VOC). S-UI 가 소유 범위를 지켜 mount 함수만 제공하고
    # 이 한 줄 등록을 리포트로 요청했다 — docs/reports/2026-08-12_S-UI_리포트.md §6
    mount_ui(app)
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "error": {"code": "http_error", "message": str(exc.detail)}
        }
        return JSONResponse(status_code=exc.status_code, content=detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "request validation failed"}})

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "internal server error"}})
    @app.get("/health")
    def health(): return {"status": "ok"}
    return app

app = create_app()
