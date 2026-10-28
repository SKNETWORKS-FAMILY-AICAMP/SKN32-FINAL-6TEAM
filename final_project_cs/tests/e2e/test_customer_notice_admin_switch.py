"""관리자 설정 저장이 재시작 없이 고객 발송 판정에 반영된다."""
import pytest

from app.domains.travel_ops.modules.web_account import customer_notice_delivery as delivery
from .test_trip_api import api  # noqa: F401
from .test_web_guard import _audit_cleanup, _client  # noqa: F401 — 감사 줄(덧붙이기 전용) 시험 정리


@pytest.mark.usefixtures("_audit_cleanup")
def test_console_switch_changes_delivery_and_preserves_revision_audit(api):
    client = _client()
    read, write = api["auth"]("limits:read"), api["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == delivery.KEY)
    assert (row["type"], row["value"]) == ("bool", False)
    assert "고객" in row["label"] and "관리자 채널" in row["text_ko"]
    assert delivery.enabled(api["tenant"]) is False
    body = {"expected_revision":view["revision"],"actor":"notice-test", "reason":"고객 알림 검증",
            "changes":{delivery.KEY: True}}
    denied = client.patch("/admin/limits", headers=read, json=body)
    assert denied.status_code == 403
    wrong = client.patch("/admin/limits", headers=write, json={**body,"changes":{delivery.KEY:"true"}})
    assert wrong.status_code == 422
    enabled = client.patch("/admin/limits", headers=write, json=body)
    assert enabled.status_code == 200, enabled.text
    assert delivery.enabled(api["tenant"]) is True
    assert client.patch("/admin/limits", headers=write, json=body).status_code == 409
    disabled = client.patch("/admin/limits", headers=write, json={**body,
        "expected_revision":enabled.json()["revision"],"changes":{delivery.KEY:False}})
    assert disabled.status_code == 200
    assert delivery.enabled(api["tenant"]) is False
    events = client.get("/admin/limits/events",headers=read).json()["events"]
    assert [e["new"] for e in events if e["name"] == delivery.KEY] == [False,True]
    assert all(e["actor"] == "notice-test" for e in events if e["name"] == delivery.KEY)
