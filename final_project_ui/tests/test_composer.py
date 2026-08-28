"""Composer v2 어댑터 — 모킹하지 않고 최소 HTTP 서버로 계약을 실측한다."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from console.composer import apply_candidate, read_current, toggle_target, validate_candidate


@pytest.fixture()
def composer_server():
    servers = []
    # ★대상이 실제로 받은 요청 본문을 기록한다. 이게 없어서 "적용에 사유가 안 실려
    #   간다"는 결함을 테스트가 못 잡았다 — 가짜 서버가 본문을 안 보고 200만 냈다
    #   (2026-08-28 결함 점검). `composer_server.received` 로 꺼내 쓴다.
    received: list[tuple[str, dict | None]] = []

    def start(script: dict, *, token_status: int = 200, issuer_secret: str = "issuer-secret",
              token_payload: dict | None = None, token_raw: str | None = None) -> str:
        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: dict | str):
                data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _body(self):
                length = int(self.headers.get("Content-Length", 0))
                return json.loads(self.rfile.read(length).decode()) if length else None

            def do_POST(self):
                body = self._body()
                if self.path == "/auth/token":
                    if self.headers.get("Authorization") != f"Bearer {issuer_secret}":
                        return self._json(token_status if token_status != 200 else 401,
                                          {"error": {"message": "issuer rejected"}})
                    if token_status != 200:
                        return self._json(token_status, {"error": {"message": "scope rejected"}})
                    if token_raw is not None:
                        return self._json(200, token_raw)
                    if token_payload is not None:
                        return self._json(200, token_payload)
                    scope = body["scope"][0]
                    return self._json(200, {"access_token": f"access-{scope}", "token_type": "bearer", "expires_in": 900})
                self._handle_composer(body)

            def do_GET(self):
                self._handle_composer(None)

            def _handle_composer(self, body):
                received.append((self.path, body))
                entry = script.get(self.path)
                if entry is None:
                    return self._json(404, {})
                status, payload, expected_token = entry
                if expected_token and self.headers.get("Authorization") != f"Bearer {expected_token}":
                    return self._json(401, {"error": {"message": "bad access token"}})
                return self._json(status, payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_port}/composer"

    start.received = received
    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_no_url_is_not_a_failure():
    result = read_current(None, "issuer-secret")
    assert result.status == "연결 안 함"


def test_current_issues_minimal_read_scope(composer_server):
    url = composer_server({"/composer/current": (200, {"revision": "abc"}, "access-composer:read")})
    result = read_current(url, "issuer-secret")
    assert result.status == "읽음" and result.value["revision"] == "abc"


def test_validate_issues_validate_scope_and_promotes_invalid_result(composer_server):
    url = composer_server({"/composer/validate": (200, {"valid": False, "errors": ["bad"]}, "access-composer:validate")})
    result = validate_candidate(url, "issuer-secret", {"modules": {}})
    assert result.status == "검증 실패" and result.errors == ("bad",)


def test_apply_issues_write_scope(composer_server):
    url = composer_server({"/composer/apply": (200, {"revision": "new", "applied": True}, "access-composer:write")})
    result = apply_candidate(url, "issuer-secret", {}, base_revision="old", reason="구조 설계 테스트")
    assert result.status == "적용됨" and result.value["revision"] == "new"


def test_apply_puts_the_reason_in_the_request_body(composer_server):
    """★대상의 `ApplyPayload`는 `reason`을 `min_length=1`로 요구한다.

    한때 어댑터가 `config`와 `base_revision`만 보내서 화면의 [적용]이 늘 422로
    거부됐다. 가짜 서버가 본문을 안 보고 200만 내주는 바람에 기존 테스트는 이걸
    통과시켰다(2026-08-28 결함 점검). 이제 본문을 실제로 확인한다.
    """
    url = composer_server({"/composer/apply": (200, {"revision": "new", "applied": True},
                                                "access-composer:write")})
    apply_candidate(url, "issuer-secret", {"modules": {}}, base_revision="old",
                    reason="모듈 구조 설계 테스트")

    sent = dict(composer_server.received)["/composer/apply"]
    assert sent["reason"] == "모듈 구조 설계 테스트"
    assert sent["base_revision"] == "old"
    assert sent["config"] == {"modules": {}}


def test_apply_requires_a_reason_argument():
    """사유를 빠뜨린 호출은 조용히 나가지 않고 그 자리에서 깨져야 한다."""
    with pytest.raises(TypeError):
        apply_candidate("http://127.0.0.1:1/composer", "issuer", {}, base_revision="r")


def test_token_issuance_401_is_distinct(composer_server):
    result = read_current(composer_server({}, token_status=401), "wrong-secret")
    assert result.status == "토큰 발급 실패" and "HTTP 401" in result.detail


def test_token_issuance_403_is_distinct(composer_server):
    result = validate_candidate(composer_server({}, token_status=403), "issuer-secret", {})
    assert result.status == "토큰 발급 실패" and "HTTP 403" in result.detail


def test_token_issuance_422_is_distinct(composer_server):
    result = apply_candidate(composer_server({}, token_status=422), "issuer-secret", {},
                              base_revision="r", reason="구조 설계 테스트")
    assert result.status == "토큰 발급 실패" and "HTTP 422" in result.detail


def test_missing_issuer_secret_does_not_call_composer(composer_server):
    result = read_current(composer_server({}), None)
    assert result.status == "토큰 발급 실패"


def test_composer_401_and_403_remain_auth_failures(composer_server):
    for status in (401, 403):
        url = composer_server({"/composer/current": (status, {"error": {"message": "denied"}}, "access-composer:read")})
        assert read_current(url, "issuer-secret").status == "인증 실패"


def test_apply_conflict_and_validation_errors(composer_server):
    conflict = composer_server({"/composer/apply": (409, {"error": {"message": "stale", "current_revision": "new"}}, "access-composer:write")})
    assert apply_candidate(conflict, "issuer-secret", {}, base_revision="old",
                           reason="구조 설계 테스트").status == "충돌"
    invalid = composer_server({"/composer/apply": (422, {"error": {"message": "invalid"}}, "access-composer:write")})
    assert apply_candidate(invalid, "issuer-secret", {}, base_revision="old",
                           reason="구조 설계 테스트").status == "검증 실패"


def test_refused_connection_during_token_issuance_is_distinct():
    result = apply_candidate("http://127.0.0.1:1/composer", "issuer", {}, base_revision="r",
                              reason="구조 설계 테스트")
    assert result.status == "토큰 발급 실패"


def test_composer_module_does_not_import_target_models():
    lines = Path("console/composer.py").read_text(encoding="utf-8").splitlines()
    imports = [x for x in lines if x.strip().startswith(("import ", "from "))]
    assert not any("project_config" in x.lower() or "app.core" in x or "app.application" in x for x in imports)


def test_token_issuance_other_http_error_is_token_failure(composer_server):
    result = read_current(composer_server({}, token_status=500), "issuer-secret")
    assert result.status == "\ud1a0\ud070 \ubc1c\uae09 \uc2e4\ud328"
    assert "HTTP 500" in result.detail


def test_token_issuance_without_access_token_is_reported(composer_server):
    result = read_current(composer_server({}, token_payload={"token_type": "bearer"}), "issuer-secret")
    assert result.status == "\ud1a0\ud070 \ubc1c\uae09 \uc2e4\ud328"
    assert result.detail


def test_token_issuance_malformed_json_is_reported(composer_server):
    result = read_current(composer_server({}, token_raw="not-json"), "issuer-secret")
    assert result.status == "\ud1a0\ud070 \ubc1c\uae09 \uc2e4\ud328"
    assert result.detail


def test_toggle_issues_write_scope(composer_server):
    url = composer_server({"/composer/toggle": (200, {"target_type": "module", "target_id": "vector_rag",
                                                       "active": False, "config_revision": "new"},
                                                 "access-composer:write")})
    result = toggle_target(url, "issuer-secret", target_type="module", target_id="vector_rag",
                           active=False, base_revision="old", reason="운영 점검")
    assert result.status == "토글됨" and result.value["config_revision"] == "new"


def test_toggle_reports_revision_conflict(composer_server):
    url = composer_server({"/composer/toggle": (409, {"error": {"message": "stale", "current_revision": "new"}},
                                                 "access-composer:write")})
    result = toggle_target(url, "issuer-secret", target_type="team", target_id="order_shipping",
                           active=True, base_revision="old", reason="재활성화")
    assert result.status == "충돌"


def test_toggle_reports_unregistered_id_as_validation_failure(composer_server):
    url = composer_server({"/composer/toggle": (422, {"error": {"message": "unknown target_id"}},
                                                 "access-composer:write")})
    result = toggle_target(url, "issuer-secret", target_type="module", target_id="no_such_module",
                           active=False, base_revision="old", reason="오타")
    assert result.status == "검증 실패"


def test_other_composer_http_errors_are_unresponsive(composer_server):
    for status in (500, 503):
        url = composer_server({"/composer/current": (status, {"error": {"message": "server"}}, "access-composer:read")})
        result = read_current(url, "issuer-secret")
        assert result.status == "\ub300\uc0c1\uc774 \uc751\ub2f5\ud558\uc9c0 \uc54a\uc74c"
        assert f"HTTP {status}" in result.detail
