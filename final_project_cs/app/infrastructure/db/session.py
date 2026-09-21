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

