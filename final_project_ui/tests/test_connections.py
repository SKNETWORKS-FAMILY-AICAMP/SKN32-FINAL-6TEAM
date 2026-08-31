"""연결 어댑터 — profiles · live · db.

★이 테스트는 **세 번 빠졌다.** 발주를 세 번 했는데 코드만 늘고 테스트는 24 그대로였다.
  완료 조건을 "24건 이상" 으로 쓴 것이 "그대로도 통과" 로 읽혔다.

★검사하는 것은 "연결된다" 가 아니라 **"연결 안 될 때 무엇이라고 말하는가"** 다.
  이 콘솔은 대상이 없어도 떠야 하고, 없을 때 `0` 이 아니라 **모른다**고 말해야 한다.

★네 가지 사건을 **서로 다르게** 보고해야 한다:
    연결 안 함 · 연결하지 못했다 · 그 경로가 없음 · 계약 버전 모름
  하나로 뭉치면 사용자가 무엇을 고쳐야 할지 모른다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from console.db import _state_counts, read_runs, read_trace
from console.live import read_introspection
from console.profiles import profile_for


# ── profiles ─────────────────────────────────────────────────────────────────
def test_profile_without_environment_has_no_connection(monkeypatch, tmp_path):
    """★프로필이 없어도 화면은 떠야 한다. 없는 것은 `None` 이다."""
    for key in ("CONSOLE_DATABASE_URL", "CONSOLE_INTROSPECTION_URL"):
        monkeypatch.delenv(key, raising=False)
    profile = profile_for(tmp_path)
    assert profile.database_url is None
    assert profile.introspection_url is None
    assert profile.name == tmp_path.name


def test_profile_reads_connections_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CONSOLE_DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("CONSOLE_INTROSPECTION_URL", "http://127.0.0.1:9/introspection")
    monkeypatch.setenv("CONSOLE_INTROSPECTION_TOKEN", "sekret")
    monkeypatch.setenv("CONSOLE_COMPOSER_URL", "http://127.0.0.1:9/composer")
    monkeypatch.setenv("CONSOLE_COMPOSER_ISSUER_SECRET", "issuer-secret")
    profile = profile_for(tmp_path)
    assert profile.database_url == "postgresql://u@h/db"
    assert profile.introspection_url.endswith("/introspection")
    assert profile.introspection_token == "sekret"
    assert profile.composer_url.endswith("/composer")
    assert profile.composer_issuer_secret == "issuer-secret"


def test_default_contract_version_matches_what_targets_actually_emit(monkeypatch, tmp_path):
    """★기본값만으로 대상의 introspection을 읽을 수 있어야 한다.

    대상이 내는 `contract_version`은 `1.0`이다(2026-08-17 P8 실연결 검증).
    한때 기본값이 `v1`이라 아무 대상과도 맞지 않았고, 환경변수를 손으로 맞추지
    않으면 조립 실측과 빠른 토글 카드가 조용히 안 떴다(2026-08-28 결함 점검).
    """
    monkeypatch.delenv("CONSOLE_CONTRACT_VERSIONS", raising=False)
    assert "1.0" in profile_for(tmp_path).contract_versions


def test_contract_versions_can_be_widened_by_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CONSOLE_CONTRACT_VERSIONS", "1.0, 1.1 ,")
    assert profile_for(tmp_path).contract_versions == ("1.0", "1.1")


def test_profile_without_a_token_has_none_not_empty_string(monkeypatch, tmp_path):
    monkeypatch.delenv("CONSOLE_INTROSPECTION_TOKEN", raising=False)
    assert profile_for(tmp_path).introspection_token is None


def test_credentials_live_in_the_environment_not_in_a_file(tmp_path):
    """★프로필 **파일**을 만들지 않는다. 파일에 비밀번호가 들어가면 그 파일이 유출 지점이다."""
    profile_for(tmp_path)
    assert not list(tmp_path.rglob("*profile*")), "프로필 파일을 디스크에 만들었다"


# ── live (introspection HTTP) ────────────────────────────────────────────────
def test_no_url_is_not_a_failure(tmp_path):
    """★"설정 안 함" 과 "실패" 는 다른 사건이다."""
    result = read_introspection(None)
    assert result.status == "연결 안 함"
    assert "프로필에 없" in result.detail


def test_refused_connection_says_the_target_did_not_answer():
    """★실제로 연결을 거부당하게 만든다. 모킹한 반환값을 단언하는 것은 증거가 아니다."""
    result = read_introspection("http://127.0.0.1:1/introspection", ("1.0",))
    assert result.status == "대상이 응답하지 않음"
    assert result.detail  # 무엇 때문인지 남는다
    assert result.value is None


def test_a_404_is_distinguished_from_a_refused_connection(http_server):
    """★404 와 연결거부를 같은 값으로 뭉치면 무엇을 고쳐야 할지 모른다."""
    url = http_server(status=404, body="")
    assert read_introspection(url, ("1.0",)).status == "그 경로가 없음"


def test_an_unknown_contract_version_is_not_drawn(http_server):
    """★모르는 버전이면 값이 있어도 **모른다고 말한다.** 추측해서 그리면 화면이 거짓말을 한다."""
    url = http_server(status=200, body=json.dumps({"contract_version": "9.9", "modules": {}}))
    result = read_introspection(url, ("1.0",))
    assert result.status == "계약 버전 모름"
    assert result.value is not None          # 값은 갖고 있되
    assert "9.9" in result.detail            # 어느 버전인지 말한다


def test_a_known_contract_version_is_read(http_server):
    url = http_server(status=200, body=json.dumps({"contract_version": "1.0", "modules": {"a": True}}))
    result = read_introspection(url, ("1.0",))
    assert result.status == "읽음"
    assert result.value["modules"] == {"a": True}


def test_a_non_json_response_is_reported(http_server):
    url = http_server(status=200, body="not json")
    assert read_introspection(url, ("1.0",)).status == "대상이 응답하지 않음"


def test_a_401_is_reported_as_auth_failure_not_unresponsive(http_server):
    """★실측(2026-08-17) — 대상 `/introspection` 은 scope 인증이 걸려 있다.

    토큰 없이 실서버에 붙였더니 401 이 났고, 고치기 전 코드는 이걸
    "대상이 응답하지 않음" 으로 뭉쳤다 — 대상은 응답했다, 인증이 안 됐을 뿐이다.
    """
    url = http_server(status=401, body="")
    result = read_introspection(url, ("1.0",))
    assert result.status == "인증 실패"
    assert result.status != "대상이 응답하지 않음"


def test_a_bearer_token_is_sent_when_the_profile_has_one(auth_http_server):
    url, received = auth_http_server(expected_token="right-token",
                                      body=json.dumps({"contract_version": "1.0", "modules": {}}))
    result = read_introspection(url, ("1.0",), token="right-token")
    assert result.status == "읽음"
    assert received["Authorization"] == "Bearer right-token"


def test_a_wrong_token_still_fails_as_auth_not_unresponsive(auth_http_server):
    url, _ = auth_http_server(expected_token="right-token", body="")
    result = read_introspection(url, ("1.0",), token="wrong-token")
    assert result.status == "인증 실패"


# ── db ───────────────────────────────────────────────────────────────────────
def test_missing_database_url_is_not_an_error():
    result = read_runs(None)
    assert result.status == "연결 안 함"
    assert result.rows == ()
    # ★상태 분포를 0 으로 채우지 않는다
    assert result.state_counts == {}


def test_unsupported_url_scheme_is_named():
    result = read_runs("sqlite:///x.db")
    assert result.status == "연결 안 함"
    assert "지원하지 않는" in result.detail


def test_a_dead_database_does_not_raise():
    """★예외로 죽지 않는다. 콘솔은 DB 가 없어도 떠야 한다."""
    result = read_runs("postgresql://nobody@127.0.0.1:1/none")
    assert result.status == "연결하지 못했다"
    assert result.detail


def test_trace_without_a_url_is_reported():
    assert read_trace(None, "any").status == "연결 안 함"


def test_trace_joins_case_events_by_case_id_not_run_id():
    """★`case_events` 에는 `run_id` 컬럼이 없다.

    한때 이 파일이 `WHERE run_id = ?` 로 짜여 있었다 — sqlite 플레이스홀더에,
    없는 컬럼에, tenant 조건도 없었다. 실행되면 죽는다.
    """
    source = Path("console/db.py").read_text(encoding="utf-8")
    assert "FROM case_events WHERE tenant_id=%s AND case_id=%s" in source
    assert "case_events WHERE run_id" not in source
    # ★플레이스홀더가 psycopg 형식이어야 한다
    assert "= ?" not in source


def test_db_module_does_not_import_sqlite():
    """대상은 PostgreSQL 이다.

    ★**import 줄만** 본다. 처음엔 파일 전체에서 `sqlite` 를 찾았는데,
      "한때 sqlite3 로 짜여 있었다" 는 **주석**에 걸려 실패했다 —
      과거 결함을 기록한 주석을 지우게 만드는 검사는 잘못된 검사다.
    """
    lines = Path("console/db.py").read_text(encoding="utf-8").splitlines()
    imports = [x for x in lines if x.strip().startswith(("import ", "from "))]
    assert not any("sqlite" in x.lower() for x in imports), imports


def test_trace_with_valid_unknown_run_id_reports_connection_failure_when_database_is_dead():
    result = read_trace("postgresql://nobody@127.0.0.1:1/none", "00000000-0000-0000-0000-000000000001")
    assert result.status == "\uc5f0\uacb0\ud558\uc9c0 \ubabb\ud588\ub2e4"
    assert result.detail


def test_runs_query_contains_tenant_filter_and_passes_limit():
    source = Path("console/db.py").read_text(encoding="utf-8")
    assert "WHERE tenant_id=%s" in source
    assert "ORDER BY started_at DESC NULLS LAST LIMIT %s" in source
    assert "(*params, limit)" in source


def test_state_count_query_failure_is_retained_as_error():
    class Connection:
        def rollback(self):
            self.rolled_back = True

    class Cursor:
        def __init__(self):
            self.connection = Connection()
            self.description = [type("Column", (), {"name": "status"})(),
                                type("Column", (), {"name": "n"})()]
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((sql, params))
            if "customer_cases" in sql:
                raise RuntimeError("missing table")

        def fetchall(self):
            return [("ready", 2)]

    cursor = Cursor()
    counts = _state_counts(cursor, "WHERE tenant_id=%s", ("tenant-a",))
    assert "__error__" in counts["customer_cases"]
    assert counts["outbox"] == {"ready": 2}
    assert cursor.connection.rolled_back


# ── 서버 fixture ─────────────────────────────────────────────────────────────
@pytest.fixture()
def http_server():
    """★진짜 HTTP 서버를 띄운다. 모킹하면 urlopen 의 실제 동작을 검사하지 못한다."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    servers = []

    def start(*, status: int, body: str) -> str:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_port}/introspection"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def auth_http_server():
    """★`Authorization` 헤더를 실제로 검사하는 서버. 토큰이 코드에서 나가는지 확인한다."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    servers = []

    def start(*, expected_token: str, body: str) -> tuple[str, dict]:
        received: dict = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received["Authorization"] = self.headers.get("Authorization")
                if self.headers.get("Authorization") != f"Bearer {expected_token}":
                    self.send_response(401)
                    self.end_headers()
                    return
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_port}/introspection", received

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_reload_url_is_derived_from_the_introspection_url(tmp_path):
    """★주소를 따로 받게 하면 서로 다른 대상을 가리켜 놓고 **남의 프로세스를
    반영시키는** 사고가 난다. 두 표면은 같은 프로세스의 것이다."""
    from console.live import reload_url_for

    assert reload_url_for("http://t:8071/introspection") == "http://t:8071/admin/reload"
    assert reload_url_for("http://t:8071/introspection/") == "http://t:8071/admin/reload"
    assert reload_url_for("http://t:8071") == "http://t:8071/admin/reload"
    assert reload_url_for(None) is None


def test_reload_without_a_token_refuses_before_calling_the_target(monkeypatch):
    """★토큰 없이 보내면 401 이 난다. 왜 안 되는지 먼저 말한다."""
    from console import live

    called = []
    monkeypatch.setattr(live, "urlopen", lambda *a, **k: called.append(1))
    outcome = live.trigger_reload("http://t/introspection", None)

    assert called == []
    assert outcome.status == "연결 안 함"
    assert "CONSOLE_RELOAD_TOKEN" in outcome.detail


def test_a_409_from_the_target_is_reported_as_a_failed_reload(monkeypatch):
    """★대상이 조립에 실패한 것과 대상이 죽은 것은 운영자가 할 일이 다르다."""
    import io
    import json
    from urllib.error import HTTPError

    from console import live

    body = json.dumps({"error": {"code": "reload_failed",
                                 "message": "새 선언으로 조립하지 못했다"}}).encode()

    def raise_409(*_a, **_k):
        raise HTTPError("http://t/admin/reload", 409, "Conflict", {}, io.BytesIO(body))

    monkeypatch.setattr(live, "urlopen", raise_409)
    outcome = live.trigger_reload("http://t/introspection", "tok")

    assert outcome.status == "반영 실패"
    assert "조립하지 못했다" in outcome.detail


def test_a_404_says_the_target_does_not_support_reload_yet(monkeypatch):
    import io
    from urllib.error import HTTPError

    from console import live

    def raise_404(*_a, **_k):
        raise HTTPError("http://t/admin/reload", 404, "Not Found", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(live, "urlopen", raise_404)
    outcome = live.trigger_reload("http://t/introspection", "tok")

    assert outcome.status == "그 경로가 없음"
    assert "계약 1.0" in outcome.detail
