from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import composition
from app.presentation.api.cases import build_router
from app.presentation.api.outbox import build_router as build_outbox_router
from app.presentation.api.introspection import router as introspection_router
from app.presentation.ui import mount_ui


def create_app(controller=None, classifier=None, *,
               composer_write_router=None, composer_auth_router=None) -> FastAPI:
    """릴리즈 빌드는 Composer 없이 뜬다.

    ★v9 §8-D — **cs 소스 안에 Composer 구현을 두지 않는다.** 2026-09-06 이전에는
      `app/presentation/api/composer.py` 가 여기 무조건 붙어 있었다. 즉 고객
      릴리즈에 쓰기 채널이 그대로 실려 있었고, scope 하나만이 유일한 방어였다.

      이제 관리용 빌드(`app/entrypoint.py`)만 `acop_composer` 를 설치해 라우터를
      주입한다. 아무것도 안 주면 `/composer/*` 자체가 **존재하지 않는다** —
      "권한이 없다" 보다 "그런 표면이 없다" 가 훨씬 강한 보장이다.
    """
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
    if composer_auth_router is not None:
        app.include_router(composer_auth_router)
    if composer_write_router is not None:
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
