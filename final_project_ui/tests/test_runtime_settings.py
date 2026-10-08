"""실행 중 설정 어댑터 — 지도 종류(osm ↔ google)를 화면 없이 바꾸는 기능. `[2026-09-29 사용자 지시]`

★검사하는 것은 「바뀐다」만이 아니라 **바뀌지 않을 때 무엇이라고 말하는가**다:
  연결 안 함 · 인증 실패 · 그 설정이 없음 · 다른 운영자가 먼저 바꿈 · 오타 — 서로 다르게 말해야 한다.
★가짜 대상은 진짜 HTTP 서버다(대상 계약 `GET·PATCH /admin/limits` 모양 그대로). 함수를 가로채지 않는다.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from console import runtime_settings as rs

READ, WRITE = "read-key", "write-key"


class FakeTarget:
    def __init__(self, names=("web.map_provider", "web.dev_mode")):
        self.revision = 0
        self.values = {name: {"value": "off" if name == "web.dev_mode" else "osm", "source": "default"} for name in names}
        self.patches: list[dict] = []


@pytest.fixture()
def target():
    state = FakeTarget()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 시험 출력 조용히
            pass

        def _send(self, status, body):
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _view(self):
            return {"revision": state.revision, "applies_within_seconds": 30,
                    "limits": [{"name": n, **v, "updated_by": v.get("by"), "updated_at": None} for n, v in state.values.items()]}

        def do_GET(self):
            if self.path != "/admin/limits":
                return self._send(404, {"detail": "Not Found"})
            if self.headers.get("Authorization") not in (f"Bearer {READ}",):
                return self._send(403, {"detail": {"error": {"code": "forbidden"}}})
            self._send(200, self._view())

        def do_PATCH(self):
            # ★본문을 먼저 다 읽는다 — 읽기 전에 거절하면 보내던 쪽 연결이 끊겨 가끔 「응답하지 않음」으로 보였다(1/4 재현)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.headers.get("Authorization") != f"Bearer {WRITE}":
                return self._send(403, {"detail": {"error": {"code": "forbidden"}}})
            state.patches.append(body)
            if body["expected_revision"] != state.revision:
                return self._send(409, {"detail": {"error": {"code": "stale_revision", "message": "그 사이 다른 운영자가 바꿨다",
                                                             "current_revision": state.revision}}})
            for name, value in body["changes"].items():
                if name not in state.values:
                    return self._send(422, {"detail": {"error": {"code": "unknown_limit", "message": "바꿀 수 있는 이름이 아니다"}}})
                state.values[name] = {"value": ("off" if name == "web.dev_mode" else "osm") if value is None else value,
                                      "source": "default" if value is None else "override", "by": body["actor"]}
            state.revision += 1
            self._send(200, self._view())

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}/admin/limits"
    yield state
    server.shutdown()


def test_reads_the_map_provider_and_its_revision(target):
    result = rs.read_map_provider(url=target.url, token=READ)
    assert (result.status, result.value, result.revision) == ("읽음", "osm", 0)


def test_changes_the_map_provider_with_actor_reason_and_the_current_revision(target):
    result = rs.set_map_provider("google", actor="dev", reason="구글 지도 시험", url=target.url, read_token=READ, write_token=WRITE)
    assert (result.status, result.value, result.revision) == ("바꿈", "google", 1)
    assert target.patches == [{"expected_revision": 0, "actor": "dev", "reason": "구글 지도 시험", "changes": {"web.map_provider": "google"}}]
    back = rs.set_map_provider(None, actor="dev", reason="기본값으로", url=target.url, read_token=READ, write_token=WRITE)
    assert (back.status, back.value) == ("바꿈", "osm")
    assert target.patches[-1]["changes"] == {"web.map_provider": None}


def test_a_typo_is_stopped_here_and_nothing_is_sent(target):
    result = rs.set_map_provider("gogle", actor="dev", reason="x", url=target.url, read_token=READ, write_token=WRITE)
    assert result.status == "바꾸지 못함" and "gogle" in result.detail
    assert target.patches == []


def test_someone_else_changed_it_first_is_reported_not_overwritten(target):
    target.revision = 5          # 다른 운영자가 그 사이 바꿨다
    result = rs.set_map_provider("google", actor="dev", reason="x", expected_revision=4, url=target.url, write_token=WRITE)
    assert result.status == "다른 운영자가 먼저 바꿈" and result.revision == 5
    assert target.values["web.map_provider"]["value"] == "osm"


def test_the_read_key_cannot_change_anything(target):
    result = rs.set_map_provider("google", actor="dev", reason="x", url=target.url, read_token=READ, write_token=READ)
    assert result.status == "인증 실패"
    assert target.values["web.map_provider"]["value"] == "osm"


def test_actor_and_reason_are_required_before_anything_is_sent(target):
    assert rs.set_map_provider("google", actor=" ", reason="x", url=target.url, write_token=WRITE).status == "바꾸지 못함"
    assert rs.set_map_provider("google", actor="dev", reason="", url=target.url, write_token=WRITE).status == "바꾸지 못함"
    assert target.patches == []


def test_a_target_without_the_setting_says_so_instead_of_a_default(target):
    target.values = {"web.session_issue_per_ip_per_hour": {"value": 5, "source": "default"}}
    result = rs.read_map_provider(url=target.url, token=READ)
    assert result.status == "그 설정이 없음" and result.value is None
    assert "web.session_issue_per_ip_per_hour" in result.detail


def test_no_address_or_no_key_is_not_connected_rather_than_osm(monkeypatch):
    monkeypatch.delenv("CONSOLE_LIMITS_URL", raising=False)
    monkeypatch.delenv("CONSOLE_LIMITS_READ_TOKEN", raising=False)
    assert rs.read_map_provider().status == "연결 안 함"
    monkeypatch.setenv("CONSOLE_LIMITS_URL", "http://127.0.0.1:9/admin/limits")
    result = rs.read_map_provider()
    assert result.status == "연결 안 함" and "limits:read" in result.detail


def test_an_unreachable_target_is_not_a_value(monkeypatch):
    result = rs.read_map_provider(url="http://127.0.0.1:9/admin/limits", token=READ)
    assert result.status == "대상이 응답하지 않음" and result.value is None


def test_command_line_reads_and_changes(target, monkeypatch, capsys):
    monkeypatch.setenv("CONSOLE_LIMITS_URL", target.url)
    monkeypatch.setenv("CONSOLE_LIMITS_READ_TOKEN", READ)
    monkeypatch.setenv("CONSOLE_LIMITS_WRITE_TOKEN", WRITE)
    assert rs.main(["map-provider"]) == 0
    assert json.loads(capsys.readouterr().out)["value"] == "osm"
    assert rs.main(["map-provider", "google", "--actor", "dev", "--reason", "시험"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "바꿈", "value": "google", "revision": 1,
                                                   "detail": "다른 대상 프로세스에는 30초 안에 반영"}
    assert rs.main(["map-provider", "google", "--actor", "dev"]) == 1          # 이유 없음


def test_dev_mode_turns_on_and_off_and_rejects_anything_else(target, monkeypatch, capsys):
    """개발 모드 — 켜면 고객 채팅 답에 근거가 실린다(대상이 판단). 여기서는 켜고 끄는 요청만 보낸다."""
    assert rs.read_dev_mode(url=target.url, token=READ).value == "off"
    on = rs.set_dev_mode("on", actor="dev", reason="근거 확인", url=target.url, read_token=READ, write_token=WRITE)
    assert (on.status, on.value) == ("바꿈", "on")
    assert target.patches[-1]["changes"] == {"web.dev_mode": "on"}
    assert rs.set_dev_mode("yes", actor="dev", reason="x", url=target.url, write_token=WRITE).status == "바꾸지 못함"
    monkeypatch.setenv("CONSOLE_LIMITS_URL", target.url)
    monkeypatch.setenv("CONSOLE_LIMITS_READ_TOKEN", READ)
    monkeypatch.setenv("CONSOLE_LIMITS_WRITE_TOKEN", WRITE)
    assert rs.main(["dev-mode", "default", "--actor", "dev", "--reason", "끄기"]) == 0
    assert json.loads(capsys.readouterr().out)["value"] == "off"
