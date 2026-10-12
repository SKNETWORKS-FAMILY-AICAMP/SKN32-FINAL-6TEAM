"""담당 실행 뒤 발견한 다른 필수 담당의 불가를 같은 답변으로 재시도한다."""
from fastapi.testclient import TestClient

from app.core.registry import TeamRegistry
from app.core.remote_team.executor import LocalTeamExecutor
from app.core.service_bindings import BindingTable, read_binding
from app.infrastructure.db.session import get_connection
from .test_conversation_resume import travel, saved  # noqa: F401
from .test_plugin_unavailable import api, changing_trip, snapshot, assert_trip_changed_once  # noqa: F401


def test_generic_http_dependency_unavailable_retries_saved_reply_and_applies_once(travel, changing_trip):
    controller, owner, tenant, _, case_id, first = travel
    dependency = owner.manifest.model_copy(update={
        "team_id": "travel_required_dependency", "active": False,
        "capabilities": ["travel.test_requirement"], "accepted_case_types": ["other"],
    })
    registry = TeamRegistry([owner])
    registry.declare_unavailable(dependency.team_id, "disabled", manifest=dependency)
    controller.registry = registry
    controller.team_executor = LocalTeamExecutor(registry)
    controller.service_bindings = BindingTable({}, registry, "dependency-disabled")
    original = owner.execute
    observed = []

    async def execute(task):
        observed.append(task.context.current_state["customer_input"])
        required = read_binding("travel_test", "required", required_team=dependency.team_id)
        assert required() == "ready"
        return await original(task)

    owner.execute = execute
    body = {"request_id": "same-generic-reply", "message": "30분이요",
            "token": first["resume_token"], "expected_version": first["version"]}
    with TestClient(api(controller, tenant)) as client:
        rejected = client.post(f"/v1/cases/{case_id}/messages", json=body)
        assert rejected.status_code == 503, rejected.text
        assert rejected.json()["error"]["reason"] == "disabled"
        case, events, runs = snapshot(tenant, case_id)
        assert case["status"] == "running"
        assert case["state_json"]["resume_token_used"] is True
        assert case["state_json"]["customer_input"] == "30분이요"
        assert case["state_json"]["customer_input_history"] == ["30분이요"]
        assert runs[-1] == ("failed",)
        store, trip_id, _, handler = changing_trip
        with get_connection() as conn:
            assert store.latest(conn, trip_id)[0]["version"] == 1
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND case_id=%s",
                            (tenant, case_id))
                assert cur.fetchone()[0] == 0
        assert handler.calls == 0

        class Required:
            manifest = dependency.model_copy(update={"active": True})

            async def execute(self, task):
                raise AssertionError("Dependency calculator should use its bound hook")

        active = TeamRegistry([owner, Required()])
        controller.registry = active
        controller.team_executor = LocalTeamExecutor(active)
        controller.service_bindings = BindingTable(
            {("travel_test", "required"): lambda: "ready"}, active, "dependency-enabled")
        retried = client.post(f"/v1/cases/{case_id}/messages", json=body)
        assert retried.status_code == 200, retried.text
        assert retried.json()["status"] == "resolved"
        repeated = client.post(f"/v1/cases/{case_id}/messages", json=body)
        assert repeated.status_code == 200 and repeated.json()["status"] == "resolved"

    assert observed == ["30분이요", "30분이요"]
    case, events, runs = snapshot(tenant, case_id)
    assert case["state_json"]["customer_input_history"] == ["30분이요"]
    assert [event["event_type"] for event in events].count("valid_input") == 1
    assert len(runs) == 3 and runs[1] == ("failed",)
    assert_trip_changed_once(tenant, case_id, changing_trip)
