"""Server-rendered operations UI.

The API application owns registration.  Call ``mount_ui(app)`` from the
composition root; keeping this router separate preserves the S-API boundary.

★UI 모듈은 하나다 — `ops_ui`(고객사 대시보드, **납품되는 제품**).

★"개발 콘솔"(조립 조회·DoD·평가 대시보드)은 이 저장소에 없다.
  `final_project_ui` 가 별도 프로그램으로 그 역할을 한다 — 이 프로세스 밖에서,
  read-only 로, `/introspection` 엔드포인트와 파일·DB 를 읽어서 붙는다.

★Composer(module/Team/Port 편집)도 여기 없다. `/ui/composer`는 인증이 전혀
  없는 채로 이 앱(고객 접근 가능 포트)에 물려 있었다 — 실측(2026-08-18)으로
  확인. "read-only 외부 프로그램으로 옮길 수 없다"던 예전 판단은
  `docs/handoff/13_Composer_쓰기채널_계약.md`의 인증된 `/composer/*` 쓰기
  채널(JWT + scope 분리)이 생기면서 더 이상 맞지 않는다 — `final_project_ui`가
  이제 그 API로만 같은 기능을 제공한다.
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from acop_basement.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfig, load_project_config
from acop_basement.presentation.ui.routes import tenant_router


def mount_ui(app: FastAPI, config: ProjectConfig | None = None) -> FastAPI:
    """Mount each declared UI module independently."""
    if config is None:
        selected = getattr(app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
        config = load_project_config(selected)

    landing: str | None = None
    if config.module_enabled("ops_ui"):
        app.include_router(tenant_router)
        landing = "/ops/cases"

    # ★루트가 404 였다. 개발 서버를 띄우면 브라우저가 `/` 로 열리는데
    #   빈 404 페이지가 떠서 "서버가 안 떴나" 로 읽힌다.
    #   ★UI 모듈이 전부 꺼져 있으면 만들지 않는다 — 없는 화면으로 보내면 안 된다.
    if landing is not None:
        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(landing, status_code=307)

    return app
