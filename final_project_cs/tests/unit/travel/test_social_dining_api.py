"""SNS API의 고객 범위·입력 경계·오류·SSE를 검증한다. 네트워크/DB 대신 서비스 경계만 주입한다."""
from contextlib import nullcontext
from importlib import import_module, util
from uuid import UUID

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

MODULE = "app.domains.travel_ops.entry.social_dining_api"
CUSTOMER = UUID("00000000-0000-0000-0000-000000000011")
INTAKE = "00000000-0000-0000-0000-000000000022"
BASE = f"/v1/web/trip-intakes/{INTAKE}/dining-links"


class Service:
    def __init__(self):
        self.calls = []
        self.failure = None

    def __getattr__(self, operation):
        def run(conn, **kwargs):
            self.calls.append((operation, kwargs))
            if self.failure:
                raise self.failure
            return {"revision": 3, "links": [{"key": "kept"}], "operation": operation}
        return run


def make_client():
    assert util.find_spec(MODULE) is not None, "authenticated SNS dining routes are not implemented"
    module = import_module(MODULE)
    service = Service()
    counted = []

    def customer(request: Request):
        if request.headers.get("authorization") != "Bearer own-key":
            raise HTTPException(401, "authentication required")
        return "travel-test", CUSTOMER

    def error(status, code, message, **detail):
        return HTTPException(status, {"error": {"code": code, "message": message, **detail}})

    def stream(tenant, customer, *, op, http, work, **kwargs):
        import json
        from types import SimpleNamespace
        body = work(SimpleNamespace(stage=lambda *args, **kw: None), lambda *args, **kw: None)
        return StreamingResponse(iter(["event: accepted\ndata: {}\n\n",
                                       "event: result\ndata: " + json.dumps(body) + "\n\n"]),
                                 media_type="text/event-stream")

    router = APIRouter()
    module.register_routes(router, web_customer=customer, count=lambda *args: counted.append(args),
                           lazy=lambda name, factory: factory() if factory else None,
                           chat_factory=None, kakao_factory=None, dining_factory=None, error=error,
                           service=service, connection_factory=lambda: nullcontext(object()),
                           sse_response=stream)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), service, counted


AUTH = {"authorization": "Bearer own-key"}


def test_authentication_and_customer_scope_are_required():
    client, service, _ = make_client()
    assert client.get(BASE).status_code == 401
    assert not service.calls
    response = client.get(BASE, headers=AUTH)
    assert response.status_code == 200
    assert service.calls[0][1] == {"tenant_id": "travel-test", "customer_id": CUSTOMER,
                                    "intake_id": UUID(INTAKE)}


@pytest.mark.parametrize("body", [{"links": []}, {"links": [{"url": "x", "priority": "automatic"}]},
                                  {"links": [{"url": ""}]}, {"links": [], "customer_id": str(CUSTOMER)}])
def test_resolve_rejects_invalid_body_before_service(body):
    client, service, _ = make_client()
    assert client.post(BASE, json=body, headers=AUTH).status_code == 422
    assert not service.calls


def test_resolve_passes_links_and_progress_with_no_schedule_write():
    client, service, counted = make_client()
    response = client.post(BASE, headers=AUTH, json={"links": [{"url": "https://youtu.be/abc123xyz01"}]})
    assert response.status_code == 200
    assert [name for name, _ in service.calls] == ["resolve"]
    assert service.calls[0][1]["entries"][0]["priority"] == "if_fits"
    assert counted and counted[0][0] == "place_search"


def test_sse_and_json_return_the_same_resolve_payload():
    client, _, _ = make_client()
    payload = {"links": [{"url": "https://youtu.be/abc123xyz01", "priority": "must"}]}
    normal = client.post(BASE, headers=AUTH, json=payload)
    streamed = client.post(BASE, headers={**AUTH, "accept": "text/event-stream"}, json=payload)
    import json
    result = streamed.text.split("event: result\ndata: ")[1].split("\n\n")[0]
    assert json.loads(result) == normal.json()


def test_other_customer_intake_is_not_found_and_stale_proposal_is_conflict():
    from app.domains.travel_ops.components.intake.pipeline import IntakeConflict
    client, service, _ = make_client()
    service.failure = LookupError("intake")
    assert client.get(BASE, headers=AUTH).status_code == 404
    service.failure = IntakeConflict("stale_revision", "reload", current_revision=4)
    response = client.post(BASE + "/apply", headers=AUTH, json={"revision": 3, "proposal_id": "p1"})
    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "stale_revision"


def test_streamed_preview_adapts_existing_progress_stage_object():
    client, _, _ = make_client()
    response = client.post(BASE + "/preview", headers={**AUTH, "accept": "text/event-stream"},
                           json={"revision": 3})
    assert response.status_code == 200
    assert '"operation": "preview"' in response.text


def test_streamed_apply_returns_the_same_result_as_json():
    # [2026-10-15 브라우저 실측] 적용은 전체 일정을 다시 검사해 1분을 넘길 수 있다 — 일반 요청이면 화면이 먼저 포기하고
    #   「서버가 응답하지 않아요」를 보이는데 서버는 저장을 마쳤다. 미리보기처럼 진행 상태(SSE)로 받는다.
    client, service, _ = make_client()
    plain = client.post(BASE + "/apply", headers=AUTH, json={"revision": 3, "proposal_id": "p1"})
    streamed = client.post(BASE + "/apply", headers={**AUTH, "accept": "text/event-stream"},
                           json={"revision": 3, "proposal_id": "p1"})
    assert plain.status_code == streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert '"operation": "apply"' in streamed.text
    assert [call[0] for call in service.calls] == ["apply", "apply"]


def test_patch_only_passes_explicit_changes_and_preview_has_revision():
    client, service, _ = make_client()
    assert client.patch(BASE + "/kept", headers=AUTH, json={"priority": "must"}).status_code == 200
    changes = service.calls[-1][1]
    assert changes["key"] == "kept" and changes["priority"] == "must"
    assert "name" not in changes and "selected_ref" not in changes
    assert client.post(BASE + "/preview", headers=AUTH, json={}).status_code == 422
    assert client.post(BASE + "/apply", headers=AUTH, json={"revision": 3, "proposal_id": "p", "edits": []}).status_code == 422


def test_the_browser_may_send_patch_for_a_saved_link_from_the_web_origin(monkeypatch):
    """[2026-10-15 브라우저 실측] 우선순위 · 식당 · 지점 선택 · 보완은 PATCH 다 — 화면(다른 출처)의 사전 확인이 400 이면 하나도 안 된다."""
    from app.core import settings as settings_module
    from app.presentation.api.app import create_app

    allowed = settings_module.get_settings().model_copy(update={"web_allowed_origins": "http://localhost:3100"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: allowed)
    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[]))
    preflight = client.options(f"{BASE}/key", headers={
        "Origin": "http://localhost:3100", "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "content-type,x-csrf-token"})
    assert preflight.status_code == 200, preflight.text
    assert "PATCH" in preflight.headers["access-control-allow-methods"]
