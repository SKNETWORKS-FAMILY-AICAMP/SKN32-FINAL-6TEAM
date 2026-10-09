"""약관 확인 SSE: 실제 DB 조회 단계, JSON 호환, 인증·상한·오류·생존 신호."""
import json
import time

from app.domains.travel_ops.components.customer import consents
from app.domains.travel_ops.modules.live_progress import op_stream
from .test_consents import gate, cookies, _guest, _agree_required  # noqa: F401
from .test_trip_api import api  # noqa: F401


def events(response):
    blocks = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        blocks.append((name, data))
    return blocks


def test_consent_stream_reports_real_read_stages_and_matches_json(gate):
    _guest(gate)
    _agree_required(gate["client"])
    client = gate["client"]
    expected = client.get("/v1/web/consents").json()
    response = client.get("/v1/web/consents", headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    seen = events(response)
    assert seen[0][0] == "accepted"
    assert [data["stage"] for name, data in seen if name == "stage"] == ["consent_records", "consent_version", "consent_required"]
    assert seen[-1] == ("result", expected)
    assert not op_stream._OPEN


def test_consent_stream_rejects_no_identity_before_opening(gate):
    response = gate["client"].get("/v1/web/consents", headers={"Accept": "text/event-stream"})
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert "event:" not in response.text


def test_consent_stream_cap_is_a_json_refusal(gate, monkeypatch):
    _guest(gate)
    monkeypatch.setattr(op_stream, "acquire", lambda *args, **kwargs: False)
    response = gate["client"].get("/v1/web/consents", headers={"Accept": "text/event-stream"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_streams"


def test_consent_stream_keeps_beating_while_the_read_waits_and_hides_internal_errors(gate, monkeypatch):
    _guest(gate)
    def failed(conn, tenant_id, customer_id, *, progress=None):
        progress("consent_records")
        time.sleep(.06)
        raise RuntimeError("private internal connection detail")
    monkeypatch.setattr(consents, "state", failed)
    monkeypatch.setattr(op_stream, "limits", lambda op: {"beat_seconds": .01, "slow_seconds": .015, "max_per_user": 3, "max_seconds": 1})
    response = gate["client"].get("/v1/web/consents", headers={"Accept": "text/event-stream"})
    seen = events(response)
    assert any(name == "beat" and data["stage"] == "consent_records" and data["slow"] for name, data in seen)
    assert seen[-1][0] == "error"
    assert "private internal" not in response.text
    assert not op_stream._OPEN
