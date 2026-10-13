"""기존 동의 HTTP 회귀 시험을 새 임시 DB로 돌린다. 접속 값은 출력하지 않는다."""
import os
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest

from app.core.settings import get_settings
from app.infrastructure.db.migrate import apply_all

parts = urlsplit(get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1))
name = "acop_consent_regression_" + uuid4().hex[:10]
test_dsn = urlunsplit(parts._replace(path="/" + name))
admin = psycopg.connect(urlunsplit(parts._replace(path="/postgres")), autocommit=True, connect_timeout=5)
admin.execute(f'CREATE DATABASE "{name}"')
try:
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        apply_all(conn)
    os.environ["ACOP_DATABASE_URL"] = test_dsn
    get_settings.cache_clear()
    result = pytest.main(["tests/e2e/test_consents.py", "-q"])
finally:
    admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    admin.close()
raise SystemExit(result)
