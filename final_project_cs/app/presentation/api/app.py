from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Route

from app import composition
from app.application.runtime import ControllerProxy, RuntimeComposition
from app.core.project_config import config_revision
from app.core.settings import get_settings
from app.presentation.api.cases import build_router
from app.presentation.api.outbox import build_router as build_outbox_router
from app.presentation.api.introspection import router as introspection_router
from app.presentation.errors import install_error_handlers
from app.presentation.security import require_scope


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """앱 생명주기 — MCP 표면이 붙어 있으면 그 세션 관리자를 앱과 함께 연다(없으면 아무것도 안 한다). ★서버(uvicorn)가 돌릴 때만 의미가 있다."""
    surface = getattr(app.state, "mcp_surface", None)
    if surface is None:
        yield
        return
    async with surface.lifespan():
        yield


def create_app(controller=None, classifier=None, *,
               composer_write_router=None, composer_auth_router=None,
               domain_routers=None, subject_resolver=None, subject_interpreter=None,
               management: bool = False) -> FastAPI:
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
    app = FastAPI(title="triPilot S-API", lifespan=_lifespan)
    # ★`[2026-09-24]` 웹(`frontend/apps/web`)이 다른 출처(포트 3100)에서 부른다(D-020). 허용하는 헤더는
    #   사용자 식별 키(`X-User-Key`)와 Content-Type 뿐 — 서버용 `Authorization` 은 브라우저에서 받지 않는다.
    origins = [o.strip() for o in get_settings().web_allowed_origins.split(",") if o.strip()]
    # ★`[2026-09-28]` 사람 확인 토큰 헤더(`X-Turnstile-Token`, 키 발급)를 받고, 한도 응답의 `Retry-After` 를 화면이 읽게 연다
    # ★`[2026-10-01]` `PUT` 도 연다 — 고객 연락처 저장(`PUT /v1/web/profile`)이 화면(다른 출처)에서 온다
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"],
                           allow_headers=["X-User-Key", "Content-Type", "X-Turnstile-Token"],
                           expose_headers=["Retry-After"], allow_credentials=False)
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
    # ★`[2026-10-02 사용자 지시]` 개인 AI(MCP) 입구 — `/mcp/`(Streamable HTTP, 사용자 키). 도메인은 조립이 만든다(INV-CS-ARCH-001).
    #   `mcp` 모듈 토글 · 쓰기 도구 스위치(`travel.mcp.write_enabled`)는 `composition.build_mcp_surface` 가 본다. 모듈이 꺼져 있으면 요청이 404 다.
    app.state.mcp_surface = composition.build_mcp_surface(lambda: app)
    app.mount("/mcp", app.state.mcp_surface.asgi)
    app.router.routes.append(Route("/mcp", endpoint=app.state.mcp_surface.root, methods=["GET", "POST", "DELETE"]))   # 슬래시 없이 불러도 열린다

    # ★재기동 없이 반영시키는 유일한 길 (2026-09-06, sample 에서 이식).
    #   `ops:reload` 는 `composer:write` 와 **분리**한다 — 저장은 되돌릴 수 있지만
    #   반영은 그 순간 트래픽이 받는 것을 바꾼다.
    #   계약: **새 조립이 전부 성공한 뒤에만** 갈아 끼운다. 실패하면 옛 조립을
    #   그대로 쓰고 `reload_failed` 를 드러낸다 — 실패를 성공 뒤에 숨기지 않는다.
    # ★`[2026-09-29 사용자 지시]` 운영 화면(로그인 · Case · 승인 · 위임 · 바깥함 · VOC · 관리 · 시나리오)은 **여기 없다** —
    #   별도 운영 앱(`app/ops_entrypoint.py`, 다른 포트 · 127.0.0.1)이다. 「외부에서 절대 접근 못 하게」. 전에는 고객 API
    #   앱(8042)에 같이 붙어 있어 고객이 닿는 포트로 운영 화면이 열려 있었다(로그인으로만 막았다).
    # ★`[2026-09-29 사용자 지시]` 재기동 없는 반영은 **관리용 빌드**(`app/entrypoint.py`, `management=True`)에만 연다 —
    #   고객 릴리즈 빌드에는 이 경로가 없다(404). 반영은 **그 프로세스 안**에서만 뜻이 있어 운영 앱으로 옮길 수 없다.
    if management:
        _mount_reload(app, runtime)
    install_error_handlers(app, origins=origins)
    @app.get("/health")
    def health(): return {"status": "ok"}
    return app


def _mount_reload(app: FastAPI, runtime: RuntimeComposition) -> None:
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


app = create_app()
