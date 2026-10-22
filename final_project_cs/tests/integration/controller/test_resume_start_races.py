"""실제 DB와 인스턴스 바인딩에서 재개 실행 입구의 두 경합을 고정한다."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event, local

import pytest

from app.core.contracts import CaseStatus
from app.core.service_bindings import BindingTable, current_bindings, read_binding
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from .test_conversation_resume import resume, travel  # noqa: F401


def _wait(event, stage):
    assert event.wait(15), f"resume race barrier timed out: {stage}"


def _observation(travel, responses):
    _, team, tenant, _, case_id, _ = travel
    with get_connection() as conn:
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM agent_runs WHERE tenant_id=%s AND case_id=%s "
                        "ORDER BY started_at,run_id", (tenant, case_id))
            runs = [row[0] for row in cur.fetchall()]
    event_counts = Counter(event["event_type"] for event in events)
    return {"responses": responses, "team_calls": len(team.tasks), "runs": runs,
            "events": {name: event_counts[name] for name in ("valid_input", "resumed", "completed")},
            "status": case["status"],
            "input_history": case["state_json"].get("customer_input_history"),
            "accepted_requests": len(case["state_json"].get("resume_requests", []))}


@pytest.mark.parametrize("race", ["completed_before_recovery_read", "completed_after_running_read",
                                  "active_during_start"])
def test_duplicate_resume_start_races_execute_once(travel, monkeypatch, record_property, race):
    controller, team, tenant, _, case_id, _ = travel
    sentinel = object()
    bindings = BindingTable({("resume_test", "sentinel"): sentinel}, controller.registry, "resume-start-race")
    controller.service_bindings = bindings
    request_thread = local()
    duplicate_ready, winner_started, duplicate_read, winner_finished = (Event() for _ in range(4))
    duplicate_finished = Event()
    lock_probes = []
    validate = controller.case_service.validate_resume
    run_case = controller.run_case
    get_case = repository.get_case
    execute = team.execute

    def bound():
        assert current_bindings() is bindings
        assert read_binding("resume_test", "sentinel") is sentinel

    def validate_and_label(*args, **kwargs):
        bound()
        outcome = validate(*args, **kwargs)
        request_thread.role = "duplicate" if outcome == "idempotent" else "winner"
        return outcome

    async def run_at_barrier(**kwargs):
        bound()
        if request_thread.role == "winner":
            _wait(duplicate_ready, "duplicate released its input lock")
            try:
                return await run_case(**kwargs)
            finally:
                winner_finished.set()
        duplicate_ready.set()
        if race == "completed_before_recovery_read":
            _wait(winner_finished, "winner finished before recovery run read")
        else:
            _wait(winner_started, "winner started its resumed team")
        try:
            return await run_case(**kwargs)
        finally:
            duplicate_finished.set()

    def read_at_barrier(conn, **kwargs):
        case = get_case(conn, **kwargs)
        if (race in {"completed_after_running_read", "active_during_start"}
                and getattr(request_thread, "role", None) == "duplicate"
                and not getattr(request_thread, "snapshot_observed", False)
                and case is not None and case["status"] == CaseStatus.RUNNING):
            bound()
            request_thread.snapshot_observed = True
            duplicate_read.set()
            if race == "completed_after_running_read":
                _wait(winner_finished, "winner completed after duplicate read RUNNING")
        return case

    async def execute_at_barrier(task):
        bound()
        # Another real connection must be able to lock both rows during Team execution.
        # The execution-start locks must end at the short transaction boundary.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM customer_cases WHERE tenant_id=%s AND case_id=%s FOR UPDATE NOWAIT",
                            (tenant, case_id))
                assert cur.fetchone() is not None
                cur.execute("SELECT 1 FROM agent_runs WHERE run_id=%s FOR UPDATE NOWAIT", (task.run_id,))
                assert cur.fetchone() is not None
        lock_probes.append("case_and_run_released")
        if race in {"completed_after_running_read", "active_during_start"} and request_thread.role == "winner":
            winner_started.set()
            _wait(duplicate_read, "duplicate observed old RUNNING snapshot")
            if race == "active_during_start":
                _wait(duplicate_finished, "active duplicate released its start locks")
        return await execute(task)

    monkeypatch.setattr(controller.case_service, "validate_resume", validate_and_label)
    monkeypatch.setattr(controller, "run_case", run_at_barrier)
    monkeypatch.setattr(repository, "get_case", read_at_barrier)
    monkeypatch.setattr(team, "execute", execute_at_barrier)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = [pool.submit(resume, travel) for _ in range(2)]
        responses = [future.result(timeout=35) for future in replies]

    # Remove the request-local observation hooks before reading the final DB state.
    monkeypatch.setattr(repository, "get_case", get_case)
    observed = _observation(travel, responses)
    observed["race"] = race
    observed["instance_bindings"] = bindings.revision
    observed["locks_during_team"] = lock_probes
    record_property("resume_race_observation", json.dumps(observed, ensure_ascii=False, default=str))
    print("RESUME_RACE_OBSERVATION=" + json.dumps(observed, ensure_ascii=False, default=str))

    # Check effects before response metadata, so a marker failure cannot hide double execution.
    assert observed["team_calls"] == 2, observed  # Initial question + exactly one resumed execution.
    assert observed["runs"] == ["succeeded", "succeeded"], observed
    assert observed["events"] == {"valid_input": 1, "resumed": 1, "completed": 1}, observed
    assert observed["accepted_requests"] == 1, observed
    assert observed["input_history"] == ["30분이요"], observed
    assert observed["status"] == "resolved", observed
    assert lock_probes == ["case_and_run_released"], observed
    allowed = {"resolved", "running", "resuming"} if race == "active_during_start" else {"resolved"}
    assert all(reply["case_id"] == str(case_id) and reply["status"] in allowed
               for reply in responses), observed
    duplicate = next(reply for reply in responses if reply.get("idempotent") or reply.get("skipped"))
    assert duplicate.get("idempotent") is True, observed
