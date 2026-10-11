"""설정 서비스 진입점 — 중앙 1곳에서 수천 대상의 구성을 관리한다.

★앱 자체는 패키지(`acop_composer.service_app`)에 있고, 이 파일은 **어느 제품의
  선언을 다루는지**만 지정한다. 패키지가 제품을 import 하면 그 제품에서만 뜨는
  앱이 된다 — `final_project_cs` 도 자기 호스트로 같은 두 줄을 쓴다.

uvicorn 실행 대상: `app.config_service:app`.
"""
from __future__ import annotations

from app.composer_host import composer_host
from acop_composer.service_app import create_config_service_app

app = create_config_service_app(composer_host())

__all__ = ["app"]
