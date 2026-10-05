# -*- coding: utf-8 -*-
"""고객별 알림 발송 — 일정 변경 알림(`trip.notice`)이 **고객이 연결한 곳 한 곳**으로 나가는가. `[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」]`

구현 `app/modules/travel_ops/notice_routing.py`(일꾼의 발행자 자리에 끼우는 래퍼) · 연결 `scripts/run_outbox_worker.py` · 일꾼 `app/infrastructure/messaging/worker.py`.
★텔레그램과 디스코드는 **mock 서버**(`httpx.MockTransport`)다 — 실제 봇 · 실제 디스코드 채널로 보낸 것이 아니다(「실서버 확인: 안 했음」). DB 는 실제 개발 DB 다.

지키려는 것
 ①스위치(`travel.notice_per_customer_enabled`)가 **꺼져 있으면(기본)** 옛 동작 그대로 — 운영자 채널 발행자가 불리고 고객 채널로는 아무것도 안 나간다
 ②켜져 있으면 여행 → 고객 → `notice_channel` 로 **한 곳에만** 보낸다(텔레그램 평문 · 디스코드 `allowed_mentions` 막음) — 문구 · 번역 · `[재생]` 은 운영자 채널과 같은 규칙
 ③보낼 수 없는 것은 `NoticeSuppressed`(= 일꾼이 `skipped`): 연결 없음 · 여행 없음 · 허용 안 된 테넌트 · 키 모양 이상 · 동의 없음 · 저장값 못 풂 · 규칙에 안 맞는 웹훅 · 막힌 텔레그램 · 거부된 웹훅
 ④막힘 · 거부를 알게 되면 프로필 상태를 `blocked` / `invalid` 로 남기고, 성공하면 `ok`
 ⑤429 → `RetryAfter`(공급자 초) · 5xx → `RuntimeError` · 시간 초과 · 연결 끊김 → `TimeoutError` / `ConnectionError`(일꾼이 `unknown`) · 봇 토큰 없음 → `NoticeNotConfigured`
 ⑥토큰 · 웹훅 · 대화 번호 · 본문이 로그와 예외 문구에 없다 · 길이 한도(텔레그램 4,096 · 디스코드 2,000)
 ⑦실제 `OutboxWorker.process_once` 한 바퀴: delivered / skipped / pending(429) / unknown(시간 초과)

재현:

    python -m pytest tests/e2e/test_notice_routing.py -v
"""
from __future__ import annotations

import json
import logging
import traceback
from uuid import UUID, uuid4

import httpx
import pytest
from psycopg.types.json import Jsonb

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.infrastructure.messaging.worker import OutboxWorker
from app.infrastructure.notify import telegram as telegram_client
from app.infrastructure.notify.discord import DiscordWebhook, NoticeNotConfigured, RetryAfter
from app.infrastructure.notify.phrase import PhraseCache
from app.infrastructure.notify.suppressed import NoticeSuppressed
from app.modules.travel_ops import consents, customer_profile, notice_routing, telegram_connect
from app.modules.travel_ops.notice_routing import CustomerNoticeRouter, trip_id_of

from .test_trip_api import _create, api  # noqa: F401 — 픽스처를 그대로 쓴다

TOKEN = "123456789:AAExampleBotTokenForTestsOnly_abcdefghijk"
USERNAME = "tripilot_test_bot"
SECRET = "webhook-secret-for-tests_ABC-123"
CHAT = 555000111
URL = "https://discord.com/api/" + "webhooks/" + "111111111111111111/" + "A" * 68        # 글자 그대로 적지 않는다(보안 검사가 웹훅 모양 문자열을 막는다)
PAYLOAD = {"text": "오늘 오전 잠실 야외 전망 데크는 시야 확보가 어려워 같은 건물 아쿠아리움으로 바뀝니다.", "replay": True, "version": 2,
           "plan_url": "https://plan.example.test/p/abc"}
EXPECTED = "[재생] " + PAYLOAD["text"] + "\n(일정 버전 2)\nhttps://plan.example.test/p/abc"


# ── 마련 ────────────────────────────────────────────────────────
@pytest.fixture()
def rt(api, monkeypatch):  # noqa: F811
    """봇이 설정된 서버 · 여행 하나 · 텔레그램/디스코드 mock 서버. `box` 에 보낸 것이 쌓이고, 응답은 시험이 정한다."""
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(settings, "telegram_bot_username", USERNAME)
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)
    box: dict = {"telegram": [], "discord": [],
                 "tg": {"status": 200, "body": {"ok": True}, "headers": {}, "raise": None},
                 "dc": {"status": 204, "body": {}, "headers": {}, "raise": None}}

    def telegram(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/bot{TOKEN}/sendMessage", "토큰은 주소에만"
        box["telegram"].append(json.loads(request.content))
        if box["tg"]["raise"]:
            raise box["tg"]["raise"]
        return httpx.Response(box["tg"]["status"], json=box["tg"]["body"], headers=box["tg"]["headers"])

    def discord(request: httpx.Request) -> httpx.Response:
        box["discord"].append((str(request.url), json.loads(request.content)))
        if box["dc"]["raise"]:
            raise box["dc"]["raise"]
        return httpx.Response(box["dc"]["status"], json=box["dc"]["body"], headers=box["dc"]["headers"])

    monkeypatch.setattr(telegram_client, "TRANSPORT", httpx.MockTransport(telegram))
    monkeypatch.setattr(notice_routing, "TRANSPORT", httpx.MockTransport(discord))
    trip = _create(api)                                                       # 여행 만들기가 첫 알림 한 줄을 바깥함에 넣는다 — 이 시험은 자기 줄만 쓰려고 비운다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (api["tenant"],))
    yield {**api, "box": box, "trip_id": UUID(trip["trip_id"])}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL app.consent_purge = 'on'")
        cur.execute("DELETE FROM consent_events WHERE tenant_id=%s", (api["tenant"],))
        cur.execute("DELETE FROM customer_profiles WHERE tenant_id=%s", (api["tenant"],))
        cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (api["tenant"],))


def _profile(rt, *, channel, telegram=False, discord=False, tg_status="untested", dc_status="untested") -> None:
    """고객 프로필 한 줄을 직접 넣는다(연결 절차는 `test_telegram_connect.py` · `test_web_profile.py` 가 따로 시험한다)."""
    tenant, customer = rt["tenant"], rt["customer"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM customer_profiles WHERE tenant_id=%s AND customer_id=%s", (tenant, customer))
        cur.execute(
            "INSERT INTO customer_profiles (tenant_id, customer_id, discord_webhook_enc, discord_status, telegram_chat_enc, telegram_chat_hash, "
            "telegram_status, notice_channel) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (tenant, customer, customer_profile.encrypt(URL) if discord else None, dc_status,
             telegram_connect.encrypt_chat(CHAT) if telegram else None, telegram_connect.chat_hash(tenant, CHAT) if telegram else None,
             tg_status if telegram else None, channel))


def _statuses(rt) -> tuple:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT telegram_status, discord_status, notice_channel FROM customer_profiles WHERE tenant_id=%s AND customer_id=%s",
                    (rt["tenant"], rt["customer"]))
        return cur.fetchone()


def _renderer(translator=None) -> DiscordWebhook:
    return DiscordWebhook("https://renderer.invalid/unused", translator=translator, phrases=PhraseCache())


def _router(rt, *, enabled=True, allowed="mine", operator=None, translator=None, token=None) -> CustomerNoticeRouter:
    kwargs = {} if token is None else {"telegram_token": lambda: token}
    return CustomerNoticeRouter(operator=operator or (lambda message: None), connection_factory=get_connection, enabled=lambda: enabled,
                                renderer=_renderer(translator), allowed_tenants={rt["tenant"]} if allowed == "mine" else allowed, **kwargs)


def _message(rt, *, version=1, payload=None, tenant=None, key="auto", topic="trip.notice") -> dict:
    return {"message_id": str(uuid4()), "topic": topic, "payload": dict(PAYLOAD if payload is None else payload),
            "tenant_id": tenant or rt["tenant"], "dedupe_key": f"{rt['trip_id']}:v{version}" if key == "auto" else key}


def _no_requests(rt) -> None:
    assert rt["box"]["telegram"] == [] and rt["box"]["discord"] == []


def _the_whole_of(exc: BaseException) -> str:
    return "\n".join([str(exc), repr(exc), "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))])


# ── ① 스위치 ────────────────────────────────────────────────────
def test_the_per_customer_switch_is_off_by_default():
    assert settings_module.get_guardrails().get("travel.notice_per_customer_enabled") is False


def test_with_the_switch_off_the_operator_channel_is_used_exactly_as_before(rt):
    _profile(rt, channel="telegram", telegram=True)
    seen = []
    message = _message(rt)
    assert _router(rt, enabled=False, operator=seen.append)(message) is None
    assert seen == [message]                                                  # 옛 동작 — 운영자 채널 발행자가 같은 메시지를 받는다
    _no_requests(rt)                                                          # 고객 채널로는 아무것도 안 나간다
    assert _statuses(rt) == ("untested", "untested", "telegram")              # 프로필도 안 건드린다


def test_with_the_switch_on_other_topics_still_go_to_the_operator(rt):
    _profile(rt, channel="telegram", telegram=True)
    seen = []
    other = _message(rt, topic="case.escalated")
    _router(rt, enabled=True, operator=seen.append)(other)
    assert seen == [other]
    _no_requests(rt)


# ── ② 한 곳으로 ─────────────────────────────────────────────────
def test_telegram_gets_the_same_text_as_plain_text_and_discord_gets_nothing(rt):
    _profile(rt, channel="telegram", telegram=True, discord=True)           # 둘 다 연결돼 있어도 notice_channel 이 정한 한 곳으로만
    operator = []
    _router(rt, operator=operator.append)(_message(rt))
    assert rt["box"]["telegram"] == [{"chat_id": CHAT, "text": EXPECTED}]      # 평문(parse_mode 없음) · `[재생]` · 링크 줄 · 버전
    assert rt["box"]["discord"] == [] and operator == []
    assert _statuses(rt) == ("ok", "untested", "telegram")                    # 성공하면 ok


def test_discord_gets_the_same_text_with_mentions_disabled_and_telegram_gets_nothing(rt):
    _profile(rt, channel="discord", telegram=True, discord=True)
    _router(rt)(_message(rt))
    assert rt["box"]["telegram"] == []
    [(url, body)] = rt["box"]["discord"]
    assert url == URL and body == {"content": EXPECTED, "allowed_mentions": {"parse": []}}
    assert _statuses(rt) == ("untested", "ok", "discord")


def test_the_text_is_translated_to_the_customer_language_like_the_operator_channel(rt):
    _profile(rt, channel="telegram", telegram=True)
    translator = lambda text, locale: f"[{locale}] {text}"                    # noqa: E731 — 모델 흉내
    _router(rt, translator=translator)(_message(rt, payload={**PAYLOAD, "locale": "zh-TW", "plan_url": None}))
    [sent] = rt["box"]["telegram"]
    assert sent["text"] == "[zh-TW] [재생] " + PAYLOAD["text"] + "\n(일정 버전 2)"
    rt["box"]["telegram"].clear()
    _router(rt, translator=translator)(_message(rt, version=3, payload={**PAYLOAD, "locale": "ko", "plan_url": None}))
    assert rt["box"]["telegram"][0]["text"] == "[재생] " + PAYLOAD["text"] + "\n(일정 버전 2)"        # 한국어는 옮기지 않는다


# ── ③ 보낼 수 없는 것 = skipped ─────────────────────────────────
def test_a_customer_without_a_connected_channel_is_suppressed(rt):
    with pytest.raises(NoticeSuppressed, match="연결하지 않았다"):
        _router(rt)(_message(rt))                                              # 프로필 줄이 아예 없다
    _profile(rt, channel=None, discord=True)                                   # 웹훅은 있어도 알림 받는 곳이 정해지지 않았다
    with pytest.raises(NoticeSuppressed, match="연결하지 않았다"):
        _router(rt)(_message(rt))
    _no_requests(rt)


def test_a_deleted_trip_is_suppressed(rt):
    _profile(rt, channel="telegram", telegram=True)
    with pytest.raises(NoticeSuppressed, match="지워졌다"):
        _router(rt)(_message(rt, key=f"{uuid4()}:v1"))
    _no_requests(rt)


def test_a_tenant_that_is_not_allowed_is_suppressed_before_anything_is_looked_up_or_sent(rt):
    """시험 알림이 실제 고객에게 나간 사고(2026-09-22)를 막는 규칙 — 고객별 길에도 똑같이 적용한다."""
    _profile(rt, channel="telegram", telegram=True)
    with pytest.raises(NoticeSuppressed, match="보낼 대상이 아닌 테넌트"):
        _router(rt, allowed={"some-other-tenant"})(_message(rt))
    with pytest.raises(NoticeSuppressed, match="보낼 대상이 아닌 테넌트"):
        _router(rt, allowed=set())(_message(rt))
    _no_requests(rt)
    assert _statuses(rt) == ("untested", "untested", "telegram")


@pytest.mark.parametrize("key", [None, "", "no-colon-here", "not-a-uuid:v1", ":v1", 12345])
def test_a_malformed_dedupe_key_is_suppressed(rt, key):
    _profile(rt, channel="telegram", telegram=True)
    with pytest.raises(NoticeSuppressed, match="어느 여행의 알림인지"):
        _router(rt)(_message(rt, key=key))
    _no_requests(rt)


def test_trip_id_of_reads_only_the_uuid_in_front_of_the_first_colon():
    trip = uuid4()
    assert trip_id_of(f"{trip}:v1") == trip and trip_id_of(f"{trip}:day:2026-10-05") == trip
    assert trip_id_of(None) is None and trip_id_of("x:v1") is None and trip_id_of(str(trip)) is None


def test_with_the_consent_gate_on_no_alert_channel_consent_means_nothing_is_sent(rt, monkeypatch):
    _profile(rt, channel="telegram", telegram=True)
    monkeypatch.setattr(consents, "gate_enabled", lambda: True)
    with pytest.raises(NoticeSuppressed, match="동의가 없다"):
        _router(rt)(_message(rt))
    _no_requests(rt)
    with get_connection() as conn:                                             # 동의한 뒤에는 나간다 — 키 사용자의 동의 기록
        consents.record(conn, tenant_id=rt["tenant"], user_id=rt["customer"], session_kind="key", version=consents.current_version(), ip=None, user_agent=None,
                        items=[{"code": c, "agreed": True, "text_sha256": "a" * 64} for c in ("service_terms", "privacy", "alert_channel")])
    _router(rt)(_message(rt))
    assert len(rt["box"]["telegram"]) == 1


def test_an_unreadable_stored_value_is_suppressed_not_sent_and_not_a_crash(rt, monkeypatch):
    _profile(rt, channel="telegram", telegram=True)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE customer_profiles SET telegram_chat_enc='v1:garbage' WHERE tenant_id=%s", (rt["tenant"],))
    with pytest.raises(NoticeSuppressed, match="읽을 수 없다"):
        _router(rt)(_message(rt))
    _profile(rt, channel="discord", discord=True)
    monkeypatch.setattr(settings_module.get_settings(), "secret_key", "a-different-server-secret-" + uuid4().hex)       # 서버 비밀이 바뀌어 저장값을 못 푼다
    with pytest.raises(NoticeSuppressed, match="읽을 수 없다"):
        _router(rt)(_message(rt))
    _no_requests(rt)


def test_a_stored_discord_value_that_is_not_a_discord_webhook_is_never_called(rt):
    """저장 뒤 값이 오염돼도(다른 호스트 · 사내 주소) 그 주소로 요청을 보내지 않는다."""
    _profile(rt, channel="discord", discord=True)
    for evil in ("https://evil.example/api/" + "webhooks/" + "111111111111111111/" + "A" * 68, "http://169.254.169.254/latest", "https://discord.com.evil.example/x"):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE customer_profiles SET discord_webhook_enc=%s WHERE tenant_id=%s", (customer_profile.encrypt(evil), rt["tenant"]))
        with pytest.raises(NoticeSuppressed, match="규칙에 맞지 않는다"):
            _router(rt)(_message(rt))
    _no_requests(rt)


# ── ④ 막힘 · 거부 → 상태 표시 ───────────────────────────────────
@pytest.mark.parametrize("status,body", [(403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}),
                                         (400, {"ok": False, "description": "Bad Request: chat not found"})])
def test_a_blocked_telegram_chat_is_marked_blocked_and_never_called_again(rt, status, body):
    _profile(rt, channel="telegram", telegram=True, tg_status="ok")
    rt["box"]["tg"].update(status=status, body=body)
    with pytest.raises(NoticeSuppressed, match="막힘으로 표시"):
        _router(rt)(_message(rt))
    assert _statuses(rt)[0] == "blocked" and len(rt["box"]["telegram"]) == 1
    with pytest.raises(NoticeSuppressed, match="막혀 있다"):                     # 이미 막힘 — 호출하지 않는다
        _router(rt)(_message(rt, version=2))
    assert len(rt["box"]["telegram"]) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 410])
def test_a_removed_or_rejected_discord_webhook_is_marked_invalid(rt, status):
    _profile(rt, channel="discord", discord=True, dc_status="ok")
    rt["box"]["dc"].update(status=status, body={"message": "Unknown Webhook", "code": 10015})
    with pytest.raises(NoticeSuppressed, match=f"HTTP {status}"):
        _router(rt)(_message(rt))
    assert _statuses(rt)[1] == "invalid"


# ── ⑤ 일꾼이 읽는 실패의 모양 ───────────────────────────────────
def test_telegram_429_becomes_retry_after_with_the_wait_telegram_gave_and_changes_no_status(rt):
    _profile(rt, channel="telegram", telegram=True, tg_status="ok")
    rt["box"]["tg"].update(status=429, body={"ok": False, "error_code": 429, "parameters": {"retry_after": 7}})
    with pytest.raises(RetryAfter) as caught:
        _router(rt)(_message(rt))
    assert caught.value.seconds == 7.0 and _statuses(rt)[0] == "ok"


def test_discord_429_becomes_retry_after_with_the_wait_discord_gave(rt):
    _profile(rt, channel="discord", discord=True, dc_status="ok")
    rt["box"]["dc"].update(status=429, body={"message": "rate limited", "retry_after": 2.5}, headers={})
    with pytest.raises(RetryAfter) as caught:
        _router(rt)(_message(rt))
    assert caught.value.seconds == 2.5 and _statuses(rt)[1] == "ok"


@pytest.mark.parametrize("channel", ["telegram", "discord"])
def test_a_server_error_is_a_plain_runtime_error_so_the_worker_retries(rt, channel):
    _profile(rt, channel=channel, telegram=channel == "telegram", discord=channel == "discord", tg_status="ok", dc_status="ok")
    rt["box"]["tg" if channel == "telegram" else "dc"].update(status=500, body={"ok": False})
    with pytest.raises(RuntimeError) as caught:
        _router(rt)(_message(rt))
    assert not isinstance(caught.value, (RetryAfter, NoticeSuppressed, NoticeNotConfigured)) and "500" in str(caught.value)
    assert _statuses(rt)[0 if channel == "telegram" else 1] == "ok"             # 일시 장애로 상태를 바꾸지 않는다


@pytest.mark.parametrize("channel", ["telegram", "discord"])
def test_timeouts_and_dropped_connections_are_not_treated_as_success_or_failure(rt, channel):
    """★일꾼은 TimeoutError · ConnectionError 를 `unknown` 으로 둔다 — 갔는지 모르니 자동으로 다시 보내지 않는다."""
    _profile(rt, channel=channel, telegram=channel == "telegram", discord=channel == "discord")
    slot = rt["box"]["tg" if channel == "telegram" else "dc"]
    slot["raise"] = httpx.ReadTimeout("slow")
    with pytest.raises(TimeoutError):
        _router(rt)(_message(rt))
    slot["raise"] = httpx.ConnectError("refused")
    with pytest.raises(ConnectionError):
        _router(rt)(_message(rt, version=2))
    assert _statuses(rt) == ("untested" if channel == "telegram" else None, "untested", channel)           # 일시 오류는 상태를 건드리지 않는다


def test_a_missing_bot_token_fails_instead_of_pretending_to_send(rt, monkeypatch):
    _profile(rt, channel="telegram", telegram=True)
    monkeypatch.setattr(settings_module.get_settings(), "telegram_bot_token", "")           # 기본 토큰 공급자는 설정에서 읽는다 — 셋 중 하나라도 비면 꺼진 것
    with pytest.raises(NoticeNotConfigured):
        _router(rt)(_message(rt))
    with pytest.raises(NoticeNotConfigured):
        _router(rt, token="")(_message(rt))
    _no_requests(rt)


def test_a_failure_to_record_the_status_does_not_change_the_delivery_result(rt, caplog):
    """상태 표시는 부가 기록이다 — 못 남겨도 이미 보낸 알림을 실패로 바꾸지 않는다(그러면 같은 알림이 두 번 간다)."""
    _profile(rt, channel="telegram", telegram=True)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] >= 2:                                                    # 첫 번째(받을 곳 찾기)는 되고 두 번째(상태 표시)부터 깨진다
            raise ConnectionError("db went away PRIVATE-DB-DETAIL")
        return get_connection()

    caplog.set_level(logging.DEBUG)
    router = CustomerNoticeRouter(operator=lambda m: None, connection_factory=flaky, enabled=lambda: True, renderer=_renderer(), allowed_tenants={rt["tenant"]})
    router(_message(rt))                                                       # 예외 없이 끝난다
    assert len(rt["box"]["telegram"]) == 1
    assert "PRIVATE-DB-DETAIL" not in "\n".join(record.getMessage() for record in caplog.records)      # 로그에는 예외 종류만


# ── ⑥ 한도 · 비밀 ───────────────────────────────────────────────
def test_the_text_is_cut_to_each_channels_limit_with_a_marker(rt):
    long_payload = {"text": "가" * 5000}
    _profile(rt, channel="telegram", telegram=True)
    _router(rt)(_message(rt, payload=long_payload))
    sent = rt["box"]["telegram"][0]["text"]
    assert len(sent) <= 4096 and sent.endswith("(잘림)")
    _profile(rt, channel="discord", discord=True)
    _router(rt)(_message(rt, version=2, payload=long_payload))
    content = rt["box"]["discord"][0][1]["content"]
    assert len(content) <= 2000 and content.endswith("(잘림)")


@pytest.mark.parametrize("scenario", ["telegram_ok", "telegram_blocked", "telegram_500", "telegram_timeout", "discord_ok", "discord_gone", "discord_500", "discord_timeout"])
def test_no_token_webhook_chat_number_or_body_reaches_the_logs_or_exception_text(rt, caplog, scenario):
    channel, case = scenario.split("_", 1)
    _profile(rt, channel=channel, telegram=channel == "telegram", discord=channel == "discord")
    slot = rt["box"]["tg" if channel == "telegram" else "dc"]
    if case == "blocked":
        slot.update(status=403, body={"ok": False, "description": "Forbidden: bot was blocked by the user"})
    elif case == "gone":
        slot.update(status=404, body={"message": "Unknown Webhook"})
    elif case == "500":
        slot.update(status=500, body={"ok": False})
    elif case == "timeout":
        slot["raise"] = httpx.ReadTimeout(f"timeout talking to {URL} and /bot{TOKEN}/sendMessage")
    caplog.set_level(logging.DEBUG)
    payload = {**PAYLOAD, "text": "PRIVATE-BODY " + PAYLOAD["text"]}
    texts = []
    try:
        _router(rt)(_message(rt, payload=payload))
    except Exception as exc:                                                   # noqa: BLE001 — 어느 실패든 문구를 훑는다
        texts.append(_the_whole_of(exc))
    logged = "\n".join(record.getMessage() for record in caplog.records) + "\n".join(texts)
    for secret in (TOKEN, URL, URL.rsplit("/", 1)[1], str(CHAT), "PRIVATE-BODY"):
        assert secret not in logged, f"{scenario}: 로그나 예외에 비밀값이 있다"


# ── ⑦ 실제 일꾼으로 한 바퀴 ─────────────────────────────────────
def _enqueue(rt, version: int, payload=None) -> UUID:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json) VALUES (%s,'trip.notice',%s,%s) RETURNING message_id",
                    (rt["tenant"], f"{rt['trip_id']}:v{version}", Jsonb(dict(PAYLOAD if payload is None else payload))))
        return cur.fetchone()[0]


def _row(message_id: UUID) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, attempts, last_error, available_at > now() + interval '4 seconds' AND available_at < now() + interval '10 seconds' "
                    "FROM outbox WHERE message_id=%s", (message_id,))
        status, attempts, error, soon = cur.fetchone()
    return {"status": status, "attempts": attempts, "error": error, "in_about_seven_seconds": soon}


def _worker(rt, router) -> OutboxWorker:
    return OutboxWorker(get_connection, router, tenant_id=rt["tenant"])


def test_the_worker_marks_a_delivered_notice_delivered_and_hands_the_dedupe_key_to_the_router(rt):
    _profile(rt, channel="telegram", telegram=True)
    message_id = _enqueue(rt, 2)
    assert _worker(rt, _router(rt)).process_once() is True
    assert _row(message_id)["status"] == "delivered" and _row(message_id)["error"] is None
    assert rt["box"]["telegram"] == [{"chat_id": CHAT, "text": EXPECTED}]


def test_the_worker_marks_an_unroutable_notice_skipped_with_the_reason_and_does_not_retry_it(rt):
    message_id = _enqueue(rt, 2)                                               # 연결한 곳이 없다
    worker = _worker(rt, _router(rt))
    assert worker.process_once() is True
    row = _row(message_id)
    assert row["status"] == "skipped" and "연결하지 않았다" in row["error"]
    assert worker.process_once() is False                                      # 다시 집지 않는다
    _no_requests(rt)


def test_the_worker_puts_a_rate_limited_notice_back_at_the_time_telegram_named_without_using_up_an_attempt(rt):
    _profile(rt, channel="telegram", telegram=True)
    rt["box"]["tg"].update(status=429, body={"ok": False, "parameters": {"retry_after": 7}})
    message_id = _enqueue(rt, 2)
    _worker(rt, _router(rt)).process_once()
    row = _row(message_id)
    assert row["status"] == "pending" and row["attempts"] == 0 and row["in_about_seven_seconds"] is True and "429" in row["error"]


def test_the_worker_leaves_a_timed_out_notice_unknown_instead_of_resending(rt):
    _profile(rt, channel="telegram", telegram=True)
    rt["box"]["tg"]["raise"] = httpx.ReadTimeout("slow")
    message_id = _enqueue(rt, 2)
    worker = _worker(rt, _router(rt))
    worker.process_once()
    assert _row(message_id)["status"] == "unknown"
    assert worker.process_once() is False and len(rt["box"]["telegram"]) == 1  # 자동 재전송 없음


def test_the_worker_retries_a_server_error_and_gives_up_into_dead_letter_after_the_limit(rt):
    _profile(rt, channel="telegram", telegram=True)
    rt["box"]["tg"].update(status=500, body={"ok": False})
    message_id = _enqueue(rt, 2)
    worker = OutboxWorker(get_connection, _router(rt), max_attempts=2, tenant_id=rt["tenant"])
    worker.process_once()
    assert _row(message_id)["status"] == "pending" and _row(message_id)["attempts"] == 1
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE outbox SET available_at=now() WHERE message_id=%s", (message_id,))
    worker.process_once()
    assert _row(message_id)["status"] == "dead_letter" and _row(message_id)["attempts"] == 2


def test_with_the_switch_off_the_worker_still_delivers_through_the_operator_channel(rt):
    _profile(rt, channel="telegram", telegram=True)
    seen = []
    message_id = _enqueue(rt, 2)
    _worker(rt, _router(rt, enabled=False, operator=seen.append)).process_once()
    assert _row(message_id)["status"] == "delivered" and len(seen) == 1 and seen[0]["dedupe_key"] == f"{rt['trip_id']}:v2"
    _no_requests(rt)
