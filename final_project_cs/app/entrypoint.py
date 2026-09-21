"""**관리용 빌드** 진입점 — 릴리즈 빌드와 다르다.

★v9 §8-D. 고객 릴리즈는 `app.presentation.api.app:app` 을 그대로 쓴다 —
  거기엔 `/composer/*` 가 **아예 없다.** 구성을 바꿔야 할 때만 이 진입점으로
  띄운다. 그때만 `acop_composer` 가 설치돼 있으면 된다.

★이 파일이 이 제품에서 Composer 를 아는 유일한 곳 중 하나다(다른 하나는
  `app/composer_host.py`). 그게 게이트로 강제된다
  (`tests/architecture/test_composer_package_boundary.py`).

uvicorn 실행 대상: `app.entrypoint:app`.
"""
from __future__ import annotations

from acop_composer.api import create_composer_router
from acop_composer.auth import create_auth_router

from app.composer_host import composer_host
from app.presentation.api.app import create_app

_host = composer_host()

app = create_app(composer_write_router=create_composer_router(_host),
                 composer_auth_router=create_auth_router(_host))

__all__ = ["app"]
