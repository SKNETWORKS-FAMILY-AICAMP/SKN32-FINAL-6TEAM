"""Server-rendered operations UI.

The API application owns registration.  Call ``mount_ui(app)`` from the
composition root; keeping this router separate preserves the S-API boundary.
"""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfig, load_project_config
from app.presentation.ui.routes import configure_nav, ops_router, router, voc_router

#: 로컬 이름 → 첫 화면. `http://<이름>.localhost:8042` 로 열면 그 화면으로 간다(개발 미리보기용).
HOST_LANDINGS = {"tripilot": "/tripilot", "scenario": "/ui/scenario"}


def mount_ui(app: FastAPI, config: ProjectConfig | None = None) -> FastAPI:
    """Mount each declared UI module independently.

    The composition root validates that enabled modules have implementations;
    this boundary performs the corresponding conditional route registration.

    ★Composer(module/Team/Port 편집)는 여기 없다. `/ui/composer`는 인증이 전혀
      없는 채로 이 앱(고객 접근 가능 포트)에 물려 있었다 — 실측(2026-08-18)으로
      확인. 같은 기능은 이제 `final_project_ui`(별도 프로그램)가 대상의 인증된
      `/composer/*` API(scope 필요)로만 제공한다. 자세한 경위는
      `wiki/records/handoff/09_Composer_GUI_계약.md` 상단 주석 참고.
    """
    if config is None:
        selected = getattr(app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
        config = load_project_config(selected)
    landing: str | None = None
    if config.module_enabled("ops_ui"):
        app.include_router(router)
        app.include_router(ops_router)
        landing = "/ui/cases"
        # ★VOC 화면은 `voc` 모듈에 딸려 있다. 모듈을 끄면 등록하지 않아 /ui/voc 가
        #   404 가 된다. 2026-08-30 이전에는 토글과 무관하게 늘 떠 있었다
        #   (`docs/handoff/08` §2 가 끄면 사라진다고 지정한 표면이다).
        if config.module_enabled("voc"):
            app.include_router(voc_router)
    # ★메뉴를 라우터와 같은 선언으로 같은 시점에 정한다. 둘이 어긋나면
    #   메뉴엔 있는데 누르면 404 인 링크가 생긴다.
    configure_nav(config)

    # ★루트가 404 였다. 개발 서버를 띄우면 브라우저가 `/` 로 열리는데
    #   빈 404 페이지가 떠서 "서버가 안 떴나" 로 읽힌다.
    #   ★UI 모듈이 전부 꺼져 있으면 만들지 않는다 — 없는 화면으로 보내면 안 된다.
    if landing is not None:
        @app.get("/", include_in_schema=False)
        def _root(request: Request) -> RedirectResponse:
            # ★앱 미리보기 목록에는 localhost 주소에 **경로를 못 붙인다**(포트까지만). 그래서
            #   같은 서버를 이름으로 나눠 붙인다 — `tripilot.localhost` 는 사용자 화면으로,
            #   `scenario.localhost` 는 시나리오 스위치로 보낸다. 같은 프로세스라 시나리오 한
            #   판(메모리)을 운영콘솔과 사용자 화면이 같이 본다(2026-09-14).
            host = (request.headers.get("host") or "").split(":")[0].lower()
            target = HOST_LANDINGS.get(host.split(".")[0], landing) if host.endswith(".localhost") \
                else landing
            return RedirectResponse(target, status_code=307)

    return app
