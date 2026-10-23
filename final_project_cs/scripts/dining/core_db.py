"""요식 도구가 어느 DB 를 보나 — 기본은 **코어 DB**다. (2026-09-28 cs)

요식 표가 코어 DB(`acop_cs`)에 들어와 앱과 같은 DB 를 쓴다. 전에는 도구마다 요식 전용 DB
(`dining_dev` · `dining_rebuild`)를 기본으로 봐서, 앱이 쓰는 데이터와 도구가 고치는 데이터가 갈렸다.

정하는 순서
    1  DINING_DSN   접속 주소를 통째로 준 경우
    2  DINING_DB    DB 이름만 준 경우(포트·사용자는 DINING_PG_PORT · DINING_DB_USER)
    3  코어 설정    앱과 같은 `ACOP_DATABASE_URL`(`.env`)

★코어 DB 를 지우는 일은 이 모듈이 막지 않는다 — `rebuild.py` 가 `holds_live_core` 로 막는다.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # final_project_cs


def dsn() -> str:
    """psycopg 접속 주소."""
    given = os.environ.get("DINING_DSN")
    if given:
        return given
    name = os.environ.get("DINING_DB")
    if name:
        port = os.environ.get("DINING_PG_PORT", "5433")
        user = os.environ.get("DINING_DB_USER", "postgres")
        return f"postgresql://{user}@localhost:{port}/{name}"
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app.infrastructure.db.session import database_dsn   # 코어 설정을 못 읽으면 여기서 멈춘다(추측으로 채우지 않는다)

    return database_dsn()


def operating_tenant() -> str:
    """운영 테넌트 — 요식 식당을 코어 장소로 올리는 곳. `ACOP_TENANT_ID` → 코어 설정 순서."""
    given = os.environ.get("ACOP_TENANT_ID")
    if given:
        return given
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app.core.settings import get_settings

    return get_settings().tenant_id


def db_name() -> str:
    """DB 이름만."""
    return urlparse(dsn()).path.lstrip("/")
