from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from acop_basement.application.runtime import ControllerProxy, RuntimeComposition
from acop_basement.introspection import snapshot
from acop_basement.presentation.api.cases import build_router
from acop_basement.presentation.api.outbox import build_router as build_outbox_router
from acop_basement.presentation.security import require_scope
from acop_basement.presentation.ui import mount_ui

# ★acop_basement 는 Core/Team 만 갖는, cs 가 항상 설치하는 pip 패키지다.
#   Composer(옛 composer_service.py/composer.py/composer_auth.py)는 별도
#   패키지 `acop_composer` 로 옮겼다 — "관리용 빌드"에만 선택적으로 얹는다
#   (`program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md`,
#   2026-08-19 구조 확정). `app.composition`(조립 루트)도 이 패키지를
#   설치하는 product 쪽이 갖는 것이라 지연 import 한다.


def create_app(controller=None, classifier=None, composer_write_router=None, composer_auth_router=None) -> FastAPI:
    injected_controller = controller is not None
    # ★"지연 import"는 함수 안에 두는 것만으로는 안 된다 — controller·classifier를
    #   둘 다 주입받은 호출(예: cs 가 자기 도메인 조립을 직접 넘기는 경우)까지
    #   무조건 `app.composition`을 요구하면 acop_basement 단독 설치 계약이
    #   깨진다(2026-08-19 버그헌팅 라운드9에서 재현 확인). 실제로 필요할 때만
    #   import 한다.
    if classifier is None:
        from app import composition
        classifier = composition.build_classifier()
    built_revision = None
    if controller is None:
        from app import composition
        # ★조립에 쓴 선언을 **먼저 손에 쥐고** 그것으로 조립한다. 조립 후에 다시
        #   읽어서 revision 을 적으면, 그 사이 바뀐 선언의 revision 을 실행 중인
        #   것으로 잘못 적게 된다(중앙 저장소 모드에서 실제로 가능하다).
        active_config = composition.load_active_config()
        built_revision = getattr(active_config, "revision", None)
        controller = composition.build_controller(config=active_config)
    app = FastAPI(title="A-COP S-API")
    runtime = RuntimeComposition(controller, built_revision)
    app.state.runtime = runtime
    # router 는 프록시를 붙잡는다 — reload 로 갈아 끼워도 옛 Controller 를
    # 계속 쓰지 않게 한다.
    controller = ControllerProxy(runtime)
    # A classifier-only override is the legacy test seam.  Explicit controller
    # injection and the configured production path both execute the runtime.
    runtime_controller = controller if injected_controller or getattr(classifier, "__module__", "").startswith("app.composition") else None
    app.include_router(build_router(classifier, runtime_controller))
    app.include_router(build_outbox_router())
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

    # ★basement 를 외부에서 "그대로 붙여 쓸 수 있게" 하는 표면이다.
    #   final_project_ui 같은 별도 콘솔 프로그램은 이 프로세스 안에서 파이썬을
    #   실행할 수 없다 — composition.build_registry() 를 직접 부르지 못한다.
    #   그래서 조립 상태를 **JSON 으로** 낸다. HTML 렌더링이 아니라 데이터다.
    #   /v1 아래에 두지 않는다 — case 리소스가 아니라 운영 메타데이터다(/health 와 같은 급).
    @app.get("/introspection")
    def introspection(_principal=Depends(require_scope("ops:introspect"))):
        return snapshot(runtime=runtime)

    # ★설정 변경을 **재기동 없이** 반영한다. 2026-08-19 설계검토는 후보 3
    #   (재기동 요구)을 골랐지만, 재검토 트리거로 "대상과 Composer 가 같은
    #   durable config store 를 쓰기로 정해진 때" 를 적어 뒀다. 중앙 설정
    #   저장소(2026-08-30)가 들어오면서 그 조건이 충족됐다.
    #
    #   계약: **새 조립이 전부 성공한 뒤에만** 갈아 끼운다. 실패하면 옛 조립을
    #   그대로 쓰고 `reload_failed` 를 드러낸다 — 실패를 성공 뒤에 숨기지 않는다.
    @app.post("/admin/reload")
    def reload_composition(_principal=Depends(require_scope("ops:reload"))):
        from app import composition
        try:
            desired = composition.load_active_config()
        except Exception as exc:
            runtime.mark_failed(None, str(exc))
            raise HTTPException(status_code=409, detail={"error": {
                "code": "reload_failed", "message": "선언을 읽지 못했다",
                "reload_state": "reload_failed",
                "active_revision": runtime.active_revision}})
        revision = getattr(desired, "revision", None)
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

    # ★Composer 는 이제 acop_basement 소속이 아니다 — "관리용 빌드"만
    #   acop_composer 를 설치하고 이 라우터들을 주입한다. 아무것도 안 주면
    #   Composer 없이 뜬다(cs 의 기본 배포가 바로 이 경로다).
    if composer_write_router is not None:
        app.include_router(composer_write_router)
    if composer_auth_router is not None:
        app.include_router(composer_auth_router)

    return app

app = create_app()
