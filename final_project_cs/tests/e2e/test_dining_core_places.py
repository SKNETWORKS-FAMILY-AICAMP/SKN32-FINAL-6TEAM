"""요식 식당을 코어 장소로 — 올리기 · 동기화 · 여행 등록 재사용 (2026-09-28, 마이그레이션 221·222).

계획: wiki/records/plans/2026-09-28_2108_요식데이터_코어통합_실행계획.md 「고친 단계」 4·5·7.
임시 테넌트로 한 트랜잭션 안에서 돌리고 끝에 되돌린다 — 운영 테넌트의 행은 건드리지 않는다.
요식 표가 없는 DB 면 건너뛴다(요식 적재 전).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.instances.dining.ledger import ledger_ready


@pytest.fixture()
def tx():
    with get_connection() as conn:
        if not ledger_ready(conn):
            pytest.skip("요식 표가 없는 DB")
        # ★표만 있고 자료가 비어 있는 DB(마이그레이션만 돌린 새 DB · CI)도 건너뛴다 — 요식 자료는 git 밖이라 CI 에 없다
        if conn.execute("SELECT count(*) FROM dining.dn_place WHERE NOT is_synthetic AND lat IS NOT NULL").fetchone()[0] == 0:
            pytest.skip("요식 원장 자료가 적재되지 않은 DB")
        # 연결은 autocommit 이 아니다 — 끝에 rollback 하면 이 시험의 행이 모두 사라진다
        tenant = "dining_core_" + uuid4().hex[:10]
        conn.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)", (tenant, "dining core"))
        try:
            yield conn, tenant
        finally:
            conn.rollback()


def _promote(conn, tenant):
    return dict(conn.execute("SELECT result, n FROM dining.promote_to_core(%s, 'test') "
                             "UNION ALL SELECT result, n FROM dining.sync_core_places(%s)",
                             (tenant, tenant)).fetchall())


def test_같은_이름_지점도_모두_올라가고_두_번_돌려도_같다(tx):
    conn, tenant = tx
    first = _promote(conn, tenant)
    expected = conn.execute("SELECT count(*) FROM dining.dn_place WHERE record_status <> 'closed' "
                            "AND NOT is_synthetic AND lat IS NOT NULL").fetchone()[0]
    assert first["made"] == expected                       # 이름이 같아 빠지는 곳이 없다(222 전에는 10곳)
    again = _promote(conn, tenant)
    assert again["made"] == 0 and again["synced"] == first["synced"]
    dupes = conn.execute("SELECT count(*) FROM (SELECT name FROM places WHERE tenant_id=%s "
                         "AND source_name='dining_ledger' GROUP BY name HAVING count(*) > 1) x",
                         (tenant,)).fetchone()[0]
    assert dupes > 0


def test_동기화가_요일별_영업시간과_식사_조건을_채운다(tx):
    conn, tenant = tx
    _promote(conn, tenant)
    hours, dietary = conn.execute(
        "SELECT count(*) FILTER (WHERE attributes ? 'hours_week'), count(*) FILTER (WHERE cardinality(dietary) > 0) "
        "FROM places WHERE tenant_id=%s AND source_name='dining_ledger'", (tenant,)).fetchone()
    assert hours > 0 and dietary > 0


# `test_여행_등록은_같은_식당이면_요식_행을_쓴다` 는 지웠다 `[2026-10-05]` — 등록할 때 공용 요식 행으로 잇던 `ledger_place_for` 를 걷고, 그 여행 전용 행에
#  판정할 때 원장 가게를 잇는 팀 방식(`resolve_place`)을 쓴다(그 시험은 `tests/integration/dining/test_dining_runtime_link.py`)


def test_요식_식당과_이름이_같은_장소도_등록_문장이_실패하지_않는다(tx):
    """222 가 이름 유일 조건을 쪼갰다 — trip_api._insert 의 충돌 대상이 맞지 않으면 등록이 500 이 된다."""
    conn, tenant = tx
    _promote(conn, tenant)
    name = conn.execute("SELECT name FROM places WHERE tenant_id=%s AND source_name='dining_ledger' LIMIT 1",
                        (tenant,)).fetchone()[0]
    sql = ("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s) "
           "ON CONFLICT (tenant_id, name, kind) WHERE trip_scope IS NULL "
           "AND source_name IS DISTINCT FROM 'dining_ledger' DO UPDATE "
           "SET attributes = EXCLUDED.attributes || places.attributes RETURNING place_id")
    first = conn.execute(sql, (tenant, name, "dining", 37.5, 127.0, False, "{}")).fetchone()[0]
    again = conn.execute(sql, (tenant, name, "dining", 37.5, 127.0, False, "{}")).fetchone()[0]
    assert first == again                                   # 요식 밖의 같은 이름은 여전히 하나다


def test_폐업한_식당은_동기화_뒤_모든_요일이_쉬는_날이다(tx):
    """요식에서 폐업으로 바뀐 곳이 일정·대체 후보에 남지 않게 한다(222 sync_core_places)."""
    conn, tenant = tx
    _promote(conn, tenant)
    place_id, uid = conn.execute("SELECT place_id, source_content_id FROM places WHERE tenant_id=%s "
                                 "AND source_name='dining_ledger' LIMIT 1", (tenant,)).fetchone()
    conn.execute("UPDATE dining.dn_place SET record_status='closed' WHERE place_uid=%s", (uid,))
    got = dict(conn.execute("SELECT result, n FROM dining.sync_core_places(%s)", (tenant,)).fetchall())
    assert got["closed"] == 1
    attributes = conn.execute("SELECT attributes FROM places WHERE place_id=%s", (place_id,)).fetchone()[0]
    assert attributes["permanently_closed"] is True
    assert set(attributes["hours_week"].values()) == {"closed"}


def test_운영_테넌트_밖에는_올리지_않는다(tx):
    """적재 도구는 운영 테넌트에만 올린다 — 다른 테넌트에는 요식 행이 생기지 않는다."""
    conn, tenant = tx
    _promote(conn, tenant)
    other = conn.execute("SELECT count(*) FROM places WHERE source_name='dining_ledger' "
                         "AND tenant_id <> %s AND tenant_id LIKE 'dining_core_%%'", (tenant,)).fetchone()[0]
    assert other == 0
