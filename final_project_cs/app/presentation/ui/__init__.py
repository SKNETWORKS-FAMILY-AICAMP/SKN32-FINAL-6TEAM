"""Server-rendered operations UI.

The API application owns registration.  Call ``mount_ui(app)`` from the
composition root; keeping this router separate preserves the S-API boundary.
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfig, load_project_config
from app.presentation.ui.routes import ops_router, router


def mount_ui(app: FastAPI, config: ProjectConfig | None = None) -> FastAPI:
    """Mount each declared UI module independently.

    The composition root validates that enabled modules have implementations;
    this boundary performs the corresponding conditional route registration.

    ★Composer(module/Team/Port 편집)는 여기 없다. `/ui/composer`는 인증이 전혀
      없는 채로 이 앱(고객 접근 가능 포트)에 물려 있었다 — 실측(2026-08-18)으로
      확인. 같은 기능은 이제 `final_project_ui`(별도 프로그램)가 대상의 인증된
      `/composer/*` API(scope 필요)로만 제공한다. 자세한 경위는
      `docs/handoff/09_Composer_GUI_계약.md` 상단 주석 참고.
    """
    if config is None:
        selected = getattr(app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
        config = load_project_config(selected)
    landing: str | None = None
    if config.module_enabled("ops_ui"):
        app.include_router(router)
        app.include_router(ops_router)
        landing = "/ui/cases"

    # ★루트가 404 였다. 개발 서버를 띄우면 브라우저가 `/` 로 열리는데
    #   빈 404 페이지가 떠서 "서버가 안 떴나" 로 읽힌다.
    #   ★UI 모듈이 전부 꺼져 있으면 만들지 않는다 — 없는 화면으로 보내면 안 된다.
    if landing is not None:
        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(landing, status_code=307)

    return app
