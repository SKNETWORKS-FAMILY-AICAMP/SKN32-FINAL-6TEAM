# -*- coding: utf-8 -*-
"""웹 남용 방어 — 횟수 제한 · 키 발급 · 운영 API · 사람 확인 · 빈 키 정리. `[2026-09-28]` 사용자 지시

계획 `wiki/records/plans/2026-09-28_2130_웹_남용방어_실행계획.md` · 계약 `wiki/external/rest-endpoints.md` 「남용 방어」.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import web_guard

from .test_trip_api import _body, api  # noqa: F401 — 픽스처를 그대로 쓴다

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture(autouse=True)
def _fresh_cache():
    web_guard.clear_cache()
    yield
    web_guard.clear_cache()


def _client(verify=None, chat=None):
    from app.modules.travel_ops.trip_api import build_trip_router
    from app.modules.travel_ops.web_limits_api import build_limits_router
    from app.presentation.api.app import create_app

    return TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(human_verify=verify, chat_factory=(lambda: chat) if chat else None),
                        build_limits_router()]))


def _set(api, name, value):
    from psycopg.types.json import Json

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,%s,%s,'test') "
                    "ON CONFLICT (tenant_id, name) DO UPDATE SET value=EXCLUDED.value", (api["tenant"], name, Json(value)))
    web_guard.clear_cache()


def _key(client) -> dict:
    response = client.post("/v1/web/session")
    assert response.status_code == 201, response.text
    return {"X-User-Key": response.json()["user_key"]}


def _member(api, headers: dict) -> dict:
    """소셜 계정이 붙은 사용자(회원) — 게스트는 여행 1개뿐이라(D-CS-011) 한도보다 많이 만드는 시험은 회원으로 한다."""
    from uuid import uuid4

    from app.modules.travel_ops.web_session import resolve

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        customer = resolve(conn, tenant_id=api["tenant"], raw=headers["X-User-Key"])
        cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,'google',%s,%s)",
                    (api["tenant"], "h-" + uuid4().hex, customer))
    return headers


def _web_trip(api, request_id):
    body = _body(api["customer"], request_id=request_id)
    body.pop("customer_id")
    return body


def _usage(api):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT who_kind, who, action, used FROM web_usage WHERE tenant_id=%s ORDER BY 1, 3",
                    (api["tenant"],))
        return cur.fetchall()


# ── 횟수 제한 ────────────────────────────────────────────────────
def test_limits_are_off_by_default_but_every_expensive_call_is_counted(api):
    """★사용자 결정(개발 단계) — 기본은 꺼짐. 꺼져 있어도 세어 둔다(오늘 사용량 · 비용 산정 재료)."""
    assert web_guard.specs()["web.limits_enabled"].default is False
    client = _client()
    headers = _member(api, _key(client))
    cap = web_guard.values(api["tenant"])["web.trip_create.per_key_day"]
    for n in range(cap + 1):                                   # 한도보다 한 번 더 — 막지 않는다
        assert client.post("/v1/web/trips", json=_web_trip(api, f"off-{n}"), headers=headers).status_code == 201
    counted = {(kind, action): used for kind, _, action, used in _usage(api) if action == "trip_create"}
    assert counted == {("all", "trip_create"): cap + 1, ("ip", "trip_create"): cap + 1, ("key", "trip_create"): cap + 1}


def test_when_on_the_per_key_limit_answers_429_with_when_to_retry(api):
    _set(api, "web.limits_enabled", True)
    _set(api, "web.trip_create.per_key_day", 1)
    _set(api, "web.trip_create.per_ip_day", 100)
    _set(api, "web.trip_create.service_day", 100)
    client = _client()
    headers = _key(client)
    assert client.post("/v1/web/trips", json=_web_trip(api, "on-1"), headers=headers).status_code == 201
    refused = client.post("/v1/web/trips", json=_web_trip(api, "on-2"), headers=headers)
    assert refused.status_code == 429, refused.text
    error = refused.json()["error"]
    assert (error["code"], error["limit"], error["action"], error["used"], error["cap"]) == \
        ("usage_limit", "per_key", "trip_create", 1, 1)
    assert 0 < int(refused.headers["retry-after"]) <= 24 * 3600 + 1
    # ★막힌 요청은 아무것도 올리지 않는다(서비스·주소 칸도 그대로 1)
    assert {used for _, _, action, used in _usage(api) if action == "trip_create"} == {1}
    # 다른 사용자는 막히지 않는다
    assert client.post("/v1/web/trips", json=_web_trip(api, "on-3"), headers=_key(client)).status_code == 201


def test_the_service_cap_is_503_not_the_users_fault(api):
    _set(api, "web.limits_enabled", True)
    _set(api, "web.trip_create.service_day", 1)
    _set(api, "web.trip_create.per_key_day", 100)
    _set(api, "web.trip_create.per_ip_day", 100)
    client = _client()
    assert client.post("/v1/web/trips", json=_web_trip(api, "svc-1"), headers=_key(client)).status_code == 201
    refused = client.post("/v1/web/trips", json=_web_trip(api, "svc-2"), headers=_key(client))
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "service_daily_cap"
    assert refused.headers["retry-after"]


def test_many_processes_at_once_never_go_over_the_cap(api):
    """★세는 곳이 DB 한 곳이라 동시에 부르는 여러 연결(= 여러 프로세스)의 합이 상한을 넘지 않는다."""
    _set(api, "web.limits_enabled", True)
    _set(api, "web.message.service_day", 5)
    passed, refused = [], []

    def one(n):
        try:
            web_guard.count(api["tenant"], "message", customer_id=uuid4(), ip=f"10.0.0.{n}")
            passed.append(n)
        except web_guard.UsageRefused:
            refused.append(n)

    threads = [threading.Thread(target=one, args=(n,)) for n in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(passed) == 5 and len(refused) == 7
    assert dict(((k, a), u) for k, _, a, u in _usage(api) if k == "all")[("all", "message")] == 5


def test_the_address_is_never_stored_as_it_is(api):
    client = _client()
    client.post("/v1/web/trips", json=_web_trip(api, "ip-1"), headers=_key(client))
    ips = [who for kind, who, _, _ in _usage(api) if kind == "ip"]
    assert ips and all(len(who) == 32 and "testclient" not in who for who in ips)
    day = datetime.now(KST)
    assert web_guard.ip_token("10.1.2.3", f"day:{day:%Y-%m-%d}") != web_guard.ip_token(
        "10.1.2.3", f"day:{day + timedelta(days=1):%Y-%m-%d}")          # 다른 날과 이어지지 않는다


def test_forwarded_address_is_believed_only_from_a_trusted_proxy(monkeypatch):
    import app.core.settings as settings_module

    assert web_guard.client_ip("10.9.9.9", "10.1.1.1") == "10.9.9.9"               # 믿는 프록시 없음 — 머리를 안 믿는다
    trusted = settings_module.get_settings().model_copy(update={"trusted_proxies": "10.0.0.1"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: trusted)
    assert web_guard.client_ip("10.0.0.1", "10.1.1.1, 10.5.5.5") == "10.5.5.5"     # 오른쪽부터 믿는 프록시를 건너뛴다
    assert web_guard.client_ip("10.9.9.9", "10.1.1.1") == "10.9.9.9"               # 믿지 않는 곳이 보낸 머리


# ── 운영 API ─────────────────────────────────────────────────────
def test_the_limits_api_needs_its_own_scopes(api):
    client = _client()
    assert client.get("/admin/limits").status_code == 401
    assert client.get("/admin/limits", headers=api["auth"]("trip:read")).status_code == 403
    assert client.patch("/admin/limits", headers=api["auth"]("limits:read"), json={
        "expected_revision": 0, "actor": "op", "reason": "r", "changes": {"web.limits_enabled": True}}).status_code == 403


def test_the_map_provider_is_a_choice_setting_and_only_listed_values_pass(api):
    """`[2026-09-29 사용자 결정]` 화면 지도 종류 — 개발 콘솔이 구글 ↔ 무료 지도(OSM)를 바꾼다. 기본은 무료 지도."""
    client = _client()
    read, write = api["auth"]("limits:read"), api["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == "web.map_provider")
    assert (row["type"], row["value"], row["choices"]) == ("choice", "osm", ["osm", "google"])
    wrong = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "시험", "changes": {"web.map_provider": "bing"}})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "not_a_choice"
    assert wrong.json()["error"]["choices"] == ["osm", "google"]
    changed = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "구글 지도 시험", "changes": {"web.map_provider": "google"}})
    assert changed.status_code == 200, changed.text
    assert web_guard.values(api["tenant"])["web.map_provider"] == "google"


def test_an_operator_changes_a_limit_and_it_is_audited(api):
    client = _client()
    read, write = api["auth"]("limits:read"), api["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == "web.intake.per_key_day")
    assert row["source"] == "default" and row["value"] == row["default"] and view["applies_within_seconds"] == 30
    assert set(view["usage_today"]["all"]) == set(web_guard.ACTIONS)

    changed = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "행사 기간",
        "changes": {"web.intake.per_key_day": 9, "web.limits_enabled": True}})
    assert changed.status_code == 200, changed.text
    after = changed.json()
    assert after["revision"] == view["revision"] + 1
    row = next(r for r in after["limits"] if r["name"] == "web.intake.per_key_day")
    assert (row["value"], row["source"], row["updated_by"]) == (9, "override", "op-kim")
    assert web_guard.values(api["tenant"])["web.intake.per_key_day"] == 9          # 이 프로세스는 바로

    # 옛 판으로 바꾸면 409 — 두 운영자가 같은 화면을 보고 바꾼 경우
    stale = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-lee", "reason": "x", "changes": {"web.intake.per_key_day": 3}})
    assert stale.status_code == 409 and stale.json()["error"]["current_revision"] == after["revision"]

    # null = 기본값으로
    back = client.patch("/admin/limits", headers=write, json={
        "expected_revision": after["revision"], "actor": "op-kim", "reason": "원복", "changes": {"web.intake.per_key_day": None}})
    assert next(r for r in back.json()["limits"] if r["name"] == "web.intake.per_key_day")["source"] == "default"

    events = client.get("/admin/limits/events", headers=read).json()["events"]
    assert [(e["name"], e["old"], e["new"], e["actor"]) for e in events] == [      # 새것부터
        ("web.intake.per_key_day", 9, None, "op-kim"),
        ("web.limits_enabled", None, True, "op-kim"), ("web.intake.per_key_day", None, 9, "op-kim")]
    assert all(e["key_id"] and e["reason"] for e in events)
    # ★감사 줄은 고칠 수 없다
    with pytest.raises(Exception, match="append-only"):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE runtime_limit_events SET actor='x' WHERE tenant_id=%s", (api["tenant"],))


@pytest.mark.parametrize("changes, code", [
    ({"web.nope": 1}, "unknown_limit"),
    ({"web.intake.per_key_day": 0}, "out_of_range"),
    ({"web.intake.per_key_day": True}, "wrong_type"),
    ({"web.limits_enabled": 1}, "wrong_type"),
])
def test_a_bad_change_is_refused_and_nothing_is_written(api, changes, code):
    client = _client()
    response = client.patch("/admin/limits", headers=api["auth"]("limits:write"), json={
        "expected_revision": 0, "actor": "op", "reason": "r", "changes": changes})
    assert response.status_code == 422 and response.json()["error"]["code"] == code
    assert client.get("/admin/limits", headers=api["auth"]("limits:read")).json()["revision"] == 0


def test_who_and_why_are_required(api):
    client = _client()
    for body, code in (({"actor": "", "reason": "r"}, "actor_required"), ({"actor": "op", "reason": " "}, "reason_required")):
        response = client.patch("/admin/limits", headers=api["auth"]("limits:write"),
                                json={"expected_revision": 0, "changes": {"web.limits_enabled": True}, **body})
        assert response.json()["error"]["code"] == code


@pytest.fixture()
def _audit_cleanup(api):
    yield
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL session_replication_role = replica")     # 시험 정리만 — 감사 트리거를 건너뛴다
        cur.execute("DELETE FROM runtime_limit_events WHERE tenant_id=%s", (api["tenant"],))


# 감사 줄 정리는 위 두 시험이 남긴 것을 지운다
test_an_operator_changes_a_limit_and_it_is_audited = pytest.mark.usefixtures("_audit_cleanup")(
    test_an_operator_changes_a_limit_and_it_is_audited)


# ── 사람 확인 ────────────────────────────────────────────────────
def _with_secret(monkeypatch, **extra):
    import app.core.settings as settings_module

    changed = settings_module.get_settings().model_copy(update={"turnstile_secret": "test-secret", **extra})
    monkeypatch.setattr(settings_module, "get_settings", lambda: changed)


def test_without_a_secret_the_check_is_skipped_and_says_so(api):
    response = _client().post("/v1/web/session")
    assert response.status_code == 201 and response.json()["human_check"] == "skipped"


def test_with_a_secret_the_token_is_checked_with_cloudflare(api, monkeypatch):
    _with_secret(monkeypatch)
    asked = []

    def verify(**kwargs):
        asked.append(kwargs)
        return {"success": kwargs["token"] == "good", "error-codes": [] if kwargs["token"] == "good" else ["invalid-input-response"]}

    client = _client(verify)
    ok = client.post("/v1/web/session", headers={"X-Turnstile-Token": "good"})
    assert ok.status_code == 201 and ok.json()["human_check"] == "passed"
    assert asked[0]["secret"] == "test-secret" and asked[0]["remote_ip"] == "testclient"
    assert client.post("/v1/web/session", json={"turnstile_token": "good"}).status_code == 201   # 몸통으로도
    bad = client.post("/v1/web/session", headers={"X-Turnstile-Token": "bad"})
    assert bad.status_code == 403 and bad.json()["error"]["reasons"] == ["invalid-input-response"]
    missing = client.post("/v1/web/session")
    assert missing.status_code == 403 and missing.json()["error"]["reasons"] == ["missing-input-response"]
    # 계획 읽기 — 폼 칸 turnstile_token
    headers = {"X-User-Key": ok.json()["user_key"]}
    refused = client.post("/v1/web/trip-intakes", headers=headers, data={"text": "09:00 경복궁", "turnstile_token": "bad"})
    assert refused.status_code == 403
    assert not [row for row in _usage(api) if row[2] == "intake"]                 # 사람 확인에서 막히면 세지도 않는다


def test_cloudflare_out_of_reach_is_503_never_a_pass(api, monkeypatch):
    from app.infrastructure.turnstile import TurnstileUnavailable

    _with_secret(monkeypatch)

    def down(**_kwargs):
        raise TurnstileUnavailable("ConnectTimeout")

    response = _client(down).post("/v1/web/session", headers={"X-Turnstile-Token": "x"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "human_check_unavailable"
    assert response.headers["retry-after"]


def test_a_hostname_list_rejects_tokens_from_elsewhere(api, monkeypatch):
    _with_secret(monkeypatch, turnstile_hostnames="tripilot.example")
    client = _client(lambda **_k: {"success": True, "hostname": "evil.example"})
    response = client.post("/v1/web/session", headers={"X-Turnstile-Token": "x"})
    assert response.status_code == 403 and response.json()["error"]["reasons"] == ["hostname-mismatch"]


@pytest.mark.parametrize("update", [{"turnstile_required": True}, {"env": "prod"}])
def test_production_without_a_secret_does_not_start(monkeypatch, update):
    import app.core.settings as settings_module

    changed = settings_module.get_settings().model_copy(update={"turnstile_secret": "", **update})
    monkeypatch.setattr(settings_module, "get_settings", lambda: changed)
    with pytest.raises(RuntimeError, match="TURNSTILE_SECRET"):
        _client()


# ── 사용량 정리(옛 빈 키 정리는 게스트 정리 `tests/e2e/test_guest_cleanup.py` 가 대신한다 — D-CS-011) ───────────────
def test_address_rows_go_after_48_hours(api):
    web_guard.count(api["tenant"], "message", customer_id=uuid4(), ip="10.1.2.3")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_usage SET updated_at = now() - interval '49 hours' WHERE tenant_id=%s", (api["tenant"],))
    with get_connection() as conn:
        result = web_guard.prune_usage(conn, api["tenant"])
    assert result == {"ip_rows_deleted": 1, "usage_rows_deleted": 0}
    assert {kind for kind, *_ in _usage(api)} == {"all", "key"}


# ── 브라우저 허용 헤더 ───────────────────────────────────────────
def test_an_unhandled_error_still_carries_the_allowed_origin_so_the_browser_can_read_it(api):
    """★`[2026-09-28]` 500 에 `Access-Control-Allow-Origin` 이 없어 화면이 오류 문장을 못 읽고 「연결하지 못했어요」로
    잘못 보였다(ui 세션 실측 — 등록 확인 500). 허용한 출처에만 붙는다."""
    from fastapi import APIRouter

    from app.presentation.api.app import create_app

    broken = APIRouter()

    @broken.get("/v1/web/broken")
    def boom():
        raise RuntimeError("boom")

    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[broken]), raise_server_exceptions=False)
    ok = client.get("/v1/web/broken", headers={"Origin": "http://127.0.0.1:3100"})
    assert ok.status_code == 500 and ok.json()["error"]["code"] == "internal_error"
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:3100"
    other = client.get("/v1/web/broken", headers={"Origin": "https://evil.example"})
    assert other.status_code == 500 and other.headers.get("access-control-allow-origin") is None


def test_the_browser_may_send_the_human_check_header_and_read_retry_after(api):
    client = _client()
    preflight = client.options("/v1/web/session", headers={
        "Origin": "http://127.0.0.1:3100", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Turnstile-Token, Content-Type"})
    assert preflight.status_code == 200 and "x-turnstile-token" in preflight.headers["access-control-allow-headers"].lower()
    response = client.post("/v1/web/session", headers={"Origin": "http://127.0.0.1:3100"})
    assert "retry-after" in response.headers.get("access-control-expose-headers", "").lower()


# ── 모델 예열 ────────────────────────────────────────────────────
class _Model:
    """자동 시험 안에서만 쓰는 모델 자리 — 올라가 있는지 · 깨우기가 되는지를 정해 둔다(실서버는 모델 서버 의 gemma4 를 부른다)."""

    model = "gemma4:12b"

    def __init__(self, *, loaded=False, fails=None):
        self.is_loaded, self.fails, self.warmed = loaded, fails, 0

    def loaded(self):
        return self.is_loaded

    def warm(self):
        self.warmed += 1
        if self.fails:
            from app.infrastructure.ollama_chat import OllamaError

            raise OllamaError(self.fails)
        self.is_loaded = True


@pytest.fixture()
def _fresh_warmup():
    from app.modules.travel_ops import model_warmup

    model_warmup.reset()
    yield model_warmup
    model_warmup.reset()


def test_warmup_does_nothing_when_the_model_is_already_up(api, _fresh_warmup):
    model = _Model(loaded=True)
    client = _client(chat=model)
    body = client.post("/v1/web/warmup", headers=_key(client)).json()
    assert body["status"] == "warm" and model.warmed == 0
    assert not [row for row in _usage(api) if row[2] == "warmup"]              # 부르지 않았으니 세지 않는다


def test_warmup_wakes_a_cold_model_once_per_minute(api, _fresh_warmup):
    model = _Model(loaded=False)
    client = _client(chat=model)
    headers = _key(client)
    first = client.post("/v1/web/warmup", headers=headers).json()
    assert first["status"] == "warming" and model.warmed == 1                  # 응답 뒤에 깨웠다
    model.is_loaded = False                                                    # (다시 식었다고 쳐도)
    second = client.post("/v1/web/warmup", headers=headers).json()
    assert second["status"] == "warming" and second["deduped"] is True and model.warmed == 1   # 1분 안 — 다시 안 부른다
    assert second["last_attempt"]["ok"] is True
    assert [used for kind, _, action, used in _usage(api) if action == "warmup" and kind == "key"] == [1]


def test_a_failed_warmup_says_why_on_the_next_answer(api, _fresh_warmup):
    model = _Model(fails="Ollama HTTP 500: cudaMalloc failed: out of memory")
    client = _client(chat=model)
    headers = _key(client)
    client.post("/v1/web/warmup", headers=headers)
    again = client.post("/v1/web/warmup", headers=headers).json()
    assert again["last_attempt"]["ok"] is False and "out of memory" in again["last_attempt"]["reason"]


def test_warmup_counts_against_the_limits_when_they_are_on(api, _fresh_warmup):
    _set(api, "web.limits_enabled", True)
    _set(api, "web.warmup.per_key_day", 1)
    model = _Model(loaded=False)
    client = _client(chat=model)
    headers = _key(client)
    assert client.post("/v1/web/warmup", headers=headers).json()["status"] == "warming"
    _fresh_warmup.reset()                                                      # 1분이 지났다고 치고
    model.is_loaded = False
    refused = client.post("/v1/web/warmup", headers=headers)
    assert refused.status_code == 429 and refused.json()["error"]["action"] == "warmup"


def test_warmup_without_a_model_says_unavailable(api, _fresh_warmup):
    client = _client()
    assert client.post("/v1/web/warmup", headers=_key(client)).json()["status"] == "unavailable"

