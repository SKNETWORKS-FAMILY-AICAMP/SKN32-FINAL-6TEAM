"""이 저장소(sample)의 "관리용 빌드" 진입점.

★구조(2026-08-19 확정):
    acop_basement   → cs 가 항상 설치한다. Core/Team 만 있고 Composer 없음.
    acop_composer   → 별도 선택 패키지. "관리용 빌드"에만 설치한다
                      (토글 endpoint glue, `program/plan/A-COP_Composer_v3_
                      설계_토글전용_UI이관.md`).
    final_project_ui → 패키지가 아니라 독립 서비스. HTTP 로만 대상에 접속한다.

sample 은 두 패키지를 전부 갖는 참조 구현이라, 로컬 개발 서버는 이 진입점
(관리용 빌드)을 쓴다. `cs` 처럼 Composer 없이 배포하려면
`acop_basement.presentation.api.app:app` 을 그대로 쓰면 된다(이 파일은
그 위에 `acop_composer` 라우터만 얹는다).

uvicorn 실행 대상: `app.entrypoint:app`.
"""
from __future__ import annotations

from app.composer_host import composer_host
from acop_basement.presentation.api.app import create_app
from acop_composer.api import create_composer_router
from acop_composer.auth import create_auth_router

#: ★이 저장소가 자기 스키마·등록표·저장소·인증을 넘긴다. 패키지는 이 객체가 준
#:  것만 쓴다 — `final_project_cs` 도 자기 것을 담아 같은 두 줄을 쓰면 된다.
_host = composer_host()

app = create_app(composer_write_router=create_composer_router(_host),
                 composer_auth_router=create_auth_router(_host))
