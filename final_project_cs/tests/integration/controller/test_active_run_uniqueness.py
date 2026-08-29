"""Concurrency coverage for the one-active-run-per-case invariant."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.application.case_service import ActiveRunError, CaseService
from app.infrastructure.db.session import get_connection

from .test_controller_integration import db, seed_case  # noqa: F401


def _start_run(tenant: str, case_id):
    service = CaseService()
    try:
        with get_connection() as conn:
            with conn.transaction():
                run_id = service.start_run(conn, tenant_id=tenant, case_id=case_id)
            return "succeeded", run_id
    except ActiveRunError as exc:
        return "rejected", str(exc)


def test_two_simultaneous_first_start_runs_leave_exactly_one_active_run(db):  # noqa: F811
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)

    # Each worker uses its own transaction/connection. With no active row at
    # the start, both application SELECT ... FOR UPDATE checks can observe an
    # empty set; the database index must arbitrate the INSERT race.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _start_run(tenant, case_id), range(2)))

    assert [result[0] for result in results].count("succeeded") == 1
    assert [result[0] for result in results].count("rejected") == 1
    assert all("active run already exists" in result[1] for result in results if result[0] == "rejected")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM agent_runs "
            "WHERE tenant_id=%s AND case_id=%s AND status IN ('active','running','resuming')",
            (tenant, case_id),
        )
        assert cur.fetchone()[0] == 1
