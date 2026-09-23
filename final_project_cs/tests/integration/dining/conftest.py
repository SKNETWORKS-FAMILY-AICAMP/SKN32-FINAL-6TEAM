"""dining 통합 시험이 함께 쓰는 DB 와 합성 장소.

판정 시험(test_dining_judgment)에 있던 것을 옮겼다. 분류 시험도 같은 DB 를 써야 한다.
세션 픽스처를 두 모듈에서 따로 정의하면 같은 이름의 시험 DB 를 두 번 만들고 지운다.
"""
from __future__ import annotations

import glob
import os
import uuid

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
MIGRATIONS = os.path.join(ROOT, "app", "infrastructure", "db", "migrations")

#: 022 는 코어 places 표가 있어야 올라간다. 판정과 무관하므로 뺀다.
SKIP = {"022_dining_matcher.sql"}

def _admin_dsn() -> str:
    port = os.environ.get("DINING_PG_PORT", "5433")
    user = os.environ.get("DINING_DB_USER", "postgres")
    return f"postgresql://{user}@localhost:{port}/postgres"


@pytest.fixture(scope="session")
def conn():
    psycopg = pytest.importorskip("psycopg", reason="psycopg 가 없다")
    dsn = os.environ.get("DINING_TEST_DSN")
    made = None
    if dsn is None:
        name = f"dining_test_{os.getpid()}"
        try:
            admin = psycopg.connect(_admin_dsn(), connect_timeout=5, autocommit=True)
        except Exception as exc:                        # noqa: BLE001
            pytest.skip(f"DB 에 붙지 못했다: {str(exc).splitlines()[0]}")
        with admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            admin.execute(f'CREATE DATABASE "{name}"')
        made = name
        dsn = _admin_dsn().rsplit("/", 1)[0] + "/" + name

    conn = psycopg.connect(dsn, autocommit=True)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS, "[0-9]*_dining_*.sql"))):
        if os.path.basename(path) in SKIP:
            continue
        conn.execute(open(path, encoding="utf-8").read())
    yield conn
    conn.close()
    if made:
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{made}"')


@pytest.fixture
def place(conn):
    """합성 장소를 하나 만들고 시험이 끝나면 지운다."""
    made: list[str] = []

    def make(name: str = "시험식당", lat=37.5, lng=127.0) -> str:
        uid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO dining.dn_place (place_uid, name_ko, area, record_status, "
            "is_synthetic, lat, lng) VALUES (%s, %s, '시험', 'active', true, %s, %s)",
            (uid, f"{name}-{uid[:8]}", lat, lng))
        made.append(uid)
        return uid

    yield make
    for uid in made:
        conn.execute("DELETE FROM dining.dn_hours_interval i USING dining.dn_hours_rule r "
                     "WHERE i.rule_id = r.rule_id AND r.place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_hours_rule WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_closure_rule WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_attribute WHERE place_uid = %s", (uid,))
        # 관측과 휴무 범위도 장소를 붙들고 있다. 빼먹으면 지우다 외래키에 걸린다.
        conn.execute("DELETE FROM dining.dn_live_check WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_notice WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_closure_coverage WHERE place_uid = %s", (uid,))
        # 분류 시험이 원문을 붙인다. 원문도 장소를 붙들고 있다.
        conn.execute("DELETE FROM dining.dn_source_record WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_place WHERE place_uid = %s", (uid,))
