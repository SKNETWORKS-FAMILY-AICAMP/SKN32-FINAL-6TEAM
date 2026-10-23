# -*- coding: utf-8 -*-
"""병렬 시험(pytest-xdist, `-n 4`)에서 일꾼마다 **자기 DB** 를 쓰게 한다. `[2026-10-12]`

시험은 DB 하나를 같이 쓰면 서로의 행을 보고 깨질 수 있다(한 시험이 지운 표를 다른 시험이 읽는 등).
그래서 일꾼(gw0, gw1 …)마다 `<DB 이름>_<일꾼>` 을 **본 DB 를 틀로 복사해** 만든다 —
본 DB 에는 CI 가 시험 전에 스키마 · 프롬프트 · 데모 데이터를 이미 넣어 두었으므로(ci-main.yml) 복사본도 같은 상태로 시작한다.
pytest-django 가 `test_<이름>_gw0` 을 만드는 것과 같은 방식이다.

★병렬이 아닐 때(`-n` 없이 돌릴 때 · 일꾼이 아닌 주 프로세스)는 아무것도 하지 않는다 — 지금까지와 똑같다.
★이 파일은 **앱을 import 하기 전에** 실행되어야 한다(설정은 처음 읽을 때 고정된다 — `get_settings` 캐시).
  그래서 tests/conftest.py 가 아니라 최상위(rootdir)에 둔다 — eval/tests 도 이 파일 아래에 있다.
★복사하려면 본 DB 에 다른 접속이 없어야 한다(PostgreSQL 규칙). 일꾼들은 주소를 바꾼 뒤에만 접속하므로 본 DB 는 비어 있다.
  일꾼 여럿이 동시에 복사하지 않게 권고 잠금(advisory lock)으로 한 줄로 세운다.
"""
import os
from urllib.parse import urlsplit, urlunsplit

_WORKER = os.environ.get("PYTEST_XDIST_WORKER")


def _base_database_url() -> str:
    url = os.environ.get("ACOP_DATABASE_URL")
    if url:
        return url
    # 셸에 없으면 설정과 같은 순서로 .env 파일을 읽는다(app/core/settings.py 의 env_file).
    from pathlib import Path

    from dotenv import dotenv_values

    here = Path(__file__).resolve().parent
    for name in (".env.apikeys", ".env"):
        value = dotenv_values(here / name).get("ACOP_DATABASE_URL")
        if value:
            return value
    raise RuntimeError("병렬 시험에는 ACOP_DATABASE_URL 이 필요하다(환경변수 또는 .env)")


def _use_worker_database(worker: str) -> None:
    import psycopg
    from psycopg import sql

    url = _base_database_url()
    parts = urlsplit(url)
    base_db = parts.path.lstrip("/")
    worker_db = f"{base_db}_{worker}"
    admin = urlunsplit((parts.scheme.replace("postgresql+psycopg", "postgresql"), parts.netloc, "/postgres", "", ""))
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(hashtext('acop_pytest_worker_db'))")
        try:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(worker_db)))
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(worker_db), sql.Identifier(base_db)))
        finally:
            conn.execute("SELECT pg_advisory_unlock(hashtext('acop_pytest_worker_db'))")
    os.environ["ACOP_DATABASE_URL"] = urlunsplit(
        (parts.scheme, parts.netloc, "/" + worker_db, parts.query, parts.fragment))
    # 같은 명시적 시험 연결도 일꾼 DB를 가리킨다. 별도로 지정한 시험 DB는 바꾸지 않는다.
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        test_parts = urlsplit(test_url)
        identity_fields = ("hostname", "port", "path", "username", "password")
        if all(getattr(test_parts, key) == getattr(parts, key) for key in identity_fields):
            os.environ["TEST_DATABASE_URL"] = urlunsplit(
                (test_parts.scheme, test_parts.netloc, "/" + worker_db, test_parts.query, test_parts.fragment))


if _WORKER:
    _use_worker_database(_WORKER)
