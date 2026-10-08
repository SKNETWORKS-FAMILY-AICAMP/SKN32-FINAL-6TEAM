"""PostgreSQL connections for the S-DB stream."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from psycopg import Connection

from app.core.settings import get_settings


def database_dsn() -> str:
    """Return the configured DSN in psycopg's URL form."""
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Yield a connection; connection errors intentionally propagate."""
    with psycopg.connect(database_dsn()) as conn:
        yield conn


def ops_read_dsn() -> str:
    """운영 화면이 **읽기만** 하는 접속 주소. `[2026-09-29]` 운영자 콘솔 분리(ui 세션 전달 · 사용자 지시)

    ★설정 `ACOP_OPS_READ_DATABASE_URL` 이 있으면 그것(읽기 전용 DB 계정 — 만드는 법
    `scripts/sql/ops_readonly_role.sql`), 없으면 본 접속 주소다(개발). 운영 화면의 목록·상세·통계 조회가 이것을 쓴다.
    """
    url = (getattr(get_settings(), "ops_read_database_url", "") or "").strip()
    return url.replace("postgresql+psycopg://", "postgresql://", 1) if url else database_dsn()


@contextmanager
def get_ops_read_connection() -> Iterator[Connection]:
    """운영 화면의 읽기 전용 연결. 읽기 전용 계정이면 쓰기는 DB 가 거부한다."""
    with psycopg.connect(ops_read_dsn()) as conn:
        yield conn

