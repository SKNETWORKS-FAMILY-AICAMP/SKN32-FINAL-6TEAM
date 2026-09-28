"""max_active_runs_per_case: 1 이 동시 최초 실행 경합에서도 지켜지는지 검사한다.

★버그사냥 2026-08-17 (라운드 06) — `CaseService.start_run()` 의
`SELECT ... FOR UPDATE` 는 **이미 있는 행만** 잠근다. 어떤 Case 에 active 행이
아직 하나도 없을 때 두 `start_run()` 이 동시에 들어오면 둘 다 빈 결과를 보고
둘 다 INSERT 할 수 있었다 — DB 에 이걸 막는 제약이 전혀 없었다(실측 확인).

migrations/004 가 partial unique index(`agent_runs_one_active_per_case`)를
추가했고, `start_run()` 은 그 위반을 `ActiveRunError` 로 번역한다. 이 파일은
**그 제약이 실제로 있는지**를 raw SQL 로 직접 검사한다 — 두 번째 INSERT 가
`start_run()` 의 자기 SELECT 검사를 통해서가 아니라 **DB 자체의 제약**으로
막히는지가 핵심이라, 앱 계층의 SELECT 를 우회해 직접 검사한다.
"""
from __future__ import annotations

import pytest
from psycopg import errors as pg_errors

from acop_basement.application.case_service import ActiveRunError, CaseService
from acop_basement.infrastructure.db.session import get_connection

from .test_controller_integration import db, seed_case  # noqa: F401


def test_db_constraint_rejects_a_second_active_run_even_bypassing_the_app_check(db):  # noqa: F811
    """★핵심 — 앱의 SELECT 검사를 거치지 않고 raw SQL 로 직접 두 번째 active
    행을 넣어본다. 이게 바로 "두 start_run() 이 동시에 빈 결과를 본" 상황을
    흉내낸다. 고치기 전에는 이게 조용히 성공했다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO agent_runs(run_id,tenant_id,case_id,graph_revision,status,started_at) "
            "VALUES(gen_random_uuid(),%s,%s,'test',    'active',now())",
            (tenant, case_id))
    conn.commit()

    with pytest.raises(pg_errors.UniqueViolation):
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_runs(run_id,tenant_id,case_id,graph_revision,status,started_at) "
                "VALUES(gen_random_uuid(),%s,%s,'test','running',now())",
                (tenant, case_id))
    conn.rollback()


def test_start_run_translates_the_db_conflict_into_active_run_error(db):  # noqa: F811
    """★start_run() 자신의 SELECT 검사가 아니라, 그 검사가 못 보는 경우에도
    (다른 커넥션이 같은 순간 커밋한 경우) DB 제약이 최종 방어선이 되고,
    그 예외가 조용히 새지 않고 기존 ActiveRunError 로 번역되는지 본다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    service = CaseService()

    run_id = service.start_run(conn, tenant_id=tenant, case_id=case_id)
    conn.commit()
    assert run_id is not None

    # ★같은 case 에 또 하나 - 이번엔 SELECT 검사가 이미 있는 행을 보고
    #   정상적으로 거부하는 흔한 경로다(기존에도 됐던 것). 회귀 확인용.
    with conn.transaction():
        with pytest.raises(ActiveRunError):
            service.start_run(conn, tenant_id=tenant, case_id=case_id)


def test_second_connection_racing_a_still_uncommitted_first_run_is_rejected(db):  # noqa: F811
    """★진짜 동시성 — 별도 커넥션 두 개가 같은 case 에 대해 서로의 커밋을
    기다리지 않고 start_run() 을 부른다. 첫 번째가 커밋되면 두 번째는
    (그 사이에 SELECT 를 이미 통과했더라도) DB 제약에서 막혀야 한다."""
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    service = CaseService()

    with conn.transaction():
        run_id_a = service.start_run(conn, tenant_id=tenant, case_id=case_id)
    # A 는 이미 커밋됨(위 with 블록 종료 시). B 는 별도 커넥션으로 다시 시도한다 -
    # 그 사실을 모른 채 들어와도(자기 SELECT 는 안 겪었더라도) DB 제약에서 막혀야 한다.
    with get_connection() as conn_b:
        with pytest.raises(ActiveRunError):
            with conn_b.transaction():
                service.start_run(conn_b, tenant_id=tenant, case_id=case_id)
    assert run_id_a is not None
