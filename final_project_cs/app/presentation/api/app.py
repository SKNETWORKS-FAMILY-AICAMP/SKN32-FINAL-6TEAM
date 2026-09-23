from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import composition
from app.application.runtime import ControllerProxy, RuntimeComposition
from app.core.project_config import config_revision
from app.presentation.api.cases import build_router
from app.presentation.api.outbox import build_router as build_outbox_router
from app.presentation.api.introspection import router as introspection_router
from app.presentation.security import require_scope
from app.presentation.ui import mount_ui


def create_app(controller=None, classifier=None, *,
               composer_write_router=None, composer_auth_router=None,
               domain_routers=None, subject_resolver=None, subject_interpreter=None) -> FastAPI:
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
    built_revision = None
    if controller is None:
        # ★조립에 쓴 선언을 **먼저 손에 쥐고** 그것으로 조립한다. 조립한 뒤에 다시
        #   읽어 revision 을 적으면, 그 사이 바뀐 선언의 revision 을 실행 중인
        #   것으로 잘못 적게 된다.
        active_config = composition.load_project_config()
        built_revision = config_revision(active_config)
        controller = composition.build_controller(config=active_config)
    app = FastAPI(title="A-COP S-API")
    runtime = RuntimeComposition(controller, built_revision)
    app.state.runtime = runtime
    # ★router 는 프록시를 붙잡는다 — reload 로 갈아 끼워도 옛 Controller 를
    #   계속 쓰지 않게 한다.
    controller = ControllerProxy(runtime)
    # A classifier-only override is the legacy test seam.  Explicit controller
    # injection and the configured production path both execute the runtime.
    runtime_controller = controller if injected_controller or getattr(classifier, "__module__", "").startswith("app.composition") else None
    # ★대상 확인기도 조립이 만든다 — 이 층은 대상이 무엇인지 모른다(INV-CS-ARCH-001).
    if subject_resolver is None:
        subject_resolver = composition.build_subject_resolver()
    if subject_interpreter is None:
        subject_interpreter = composition.build_subject_interpreter()
    app.include_router(build_router(classifier, runtime_controller, subject_resolver, subject_interpreter))
    app.include_router(build_outbox_router())
    # ★도메인 라우터는 조립이 만든다 — 이 층은 도메인을 import 하지 못한다
    #   (INV-CS-ARCH-001). 테스트는 `domain_routers=[...]` 로 갈아 끼운다.
    for router in (composition.build_domain_routers() if domain_routers is None
                   else domain_routers):
        app.include_router(router)
    if composer_auth_router is not None:
        app.include_router(composer_auth_router)
    if composer_write_router is not None:
        app.include_router(composer_write_router)
    app.include_router(introspection_router)

    # ★재기동 없이 반영시키는 유일한 길 (2026-09-06, sample 에서 이식).
    #   `ops:reload` 는 `composer:write` 와 **분리**한다 — 저장은 되돌릴 수 있지만
    #   반영은 그 순간 트래픽이 받는 것을 바꾼다.
    #   계약: **새 조립이 전부 성공한 뒤에만** 갈아 끼운다. 실패하면 옛 조립을
    #   그대로 쓰고 `reload_failed` 를 드러낸다 — 실패를 성공 뒤에 숨기지 않는다.
    @app.post("/admin/reload")
    def reload_composition(_principal=Depends(require_scope("ops:reload"))):
        try:
            desired = composition.load_project_config()
        except Exception as exc:
            runtime.mark_failed(None, str(exc))
            raise HTTPException(status_code=409, detail={"error": {
                "code": "reload_failed", "message": "선언을 읽지 못했다",
                "reload_state": "reload_failed",
                "active_revision": runtime.active_revision}})
        revision = config_revision(desired)
        try:
            rebuilt = composition.build_controller(config=desired)
        except Exception as exc:
            # 옛 조립은 건드리지 않는다. 반쯤 바뀐 상태를 만들지 않는다.
            runtime.mark_failed(revision, str(exc))
            raise HTTPException(status_code=409, detail={"error": {
                "code": "reload_failed", "message": "새 선언으로 조립하지 못했다",
                "reload_state": "reload_failed",
                "active_revision": runtime.active_revision,
                "desired_revision": revision}})
        runtime.swap(rebuilt, revision)
        return {"reload_state": runtime.state(revision),
                "active_revision": runtime.active_revision,
                "desired_revision": revision}
    # 운영 화면(Case/Trace/Approval/VOC). S-UI 가 소유 범위를 지켜 mount 함수만 제공하고
    # 이 한 줄 등록을 리포트로 요청했다 — wiki/records/reports/2026-08-12_S-UI_리포트.md §6
    mount_ui(app)
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
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "request validation failed"}})

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "internal server error"}})
    @app.get("/health")
    def health(): return {"status": "ok"}
    return app

app = create_app()
