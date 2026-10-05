# -*- coding: utf-8 -*-
"""텔레그램으로 알림 받기 — 연결 한 바퀴 · 웹훅 업데이트 · 알림 받는 곳 · 시험 발송 · 연결 풀기. `[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」 — ui 세션 요청서]`

계약: `wiki/records/plans/2026-10-05_텔레그램_연결_백엔드_요청.md` · 구현 `telegram_connect.py` · `trip_api.py` · 저장 048.
★텔레그램은 **mock 서버**다 — `infrastructure/notify/telegram.TRANSPORT` 에 꽂은 가짜 응답이 `sendMessage` 를 받아 기록한다. 실제 봇 · 웹훅 등록 · 휴대폰의 「시작」 단추는
 사용자가 @BotFather 로 봇을 만든 뒤에야 확인할 수 있어 여기서는 안 한다(보고에 「실서버 확인: 안 했음」으로 적는다). 업데이트는 시험이 웹훅에 직접 넣는다(텔레그램이 보내는 모양).

지키려는 것
 ①봇 설정이 없으면 `available:false`(웹이 텔레그램 줄을 숨긴다) · `start` 404 · 웹훅은 늘 401
 ②한 바퀴: `start`(링크 · 만료) → 웹훅에 `/start <코드>` → `connected` · `notice_channel=telegram` · `status=untested` · 봇이 인사 · 대화 번호는 어느 응답에도 없다
 ③같은 코드 두 번 · 11분 뒤 · 모르는 코드 → 「이미 쓴 링크」 답 · 비밀 헤더가 없거나 틀림 → 401 이고 아무것도 안 바뀐다 · 텔레그램이 같은 업데이트를 다시 보내도 한 번만 처리
 ④다른 사용자에게 묶인 대화로 시도 → 묶지 않고 안내 답(합치지 않는다)
 ⑤알림만: 아무 글이나 → 고정 문장 · **모델 호출 0** · 글 내용이 DB · 로그에 없다 · 그룹 대화는 무시
 ⑥`my_chat_member`: 차단 → `blocked` · 해제 → `untested`
 ⑦`DELETE` → 대화 번호 삭제 · 알림 받는 곳이 디스코드(있으면)로 또는 없음 · `PUT notice_channel`(연결 안 된 곳은 422) · 디스코드를 연결하면 알림 받는 곳이 디스코드로
 ⑧시험 발송: ok · blocked(차단) · rate_limited · failed · 너무 자주면 429 · 연결 없으면 409
 ⑨봇 토큰 · 대화 번호 · 일회용 코드 · 웹훅 비밀값이 DB · 로그 · 응답 어디에도 평문으로 없다 · 게이트가 켜져 있으면 알림 채널 동의 없이는 연결 안 됨

재현:

    python -m pytest tests/e2e/test_telegram_connect.py -v
"""
from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.infrastructure.notify import telegram as client
from app.modules.travel_ops import consents, telegram_connect

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _h
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401

TOKEN = "123456789:AAExampleBotTokenForTestsOnly_abcdefghijk"
USERNAME = "tripilot_test_bot"
SECRET = "webhook-secret-for-tests_ABC-123"
CHAT = 555000111
OTHER_CHAT = 555000222
URL_A = "https://discord.com/api/" + "webhooks/" + "111111111111111111/" + "A" * 68


@pytest.fixture()
def tg(cookies, monkeypatch):  # noqa: F811
    """봇이 설정된 서버 + 텔레그램 mock 서버. `box["sent"]` 에 봇이 보낸 메시지(대화 번호 · 본문)가 쌓이고, `box["status"]` 로 텔레그램의 답을 정한다."""
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(settings, "telegram_bot_username", USERNAME)
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)
    box: dict = {"sent": [], "status": 200, "body": {"ok": True}, "headers": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/bot{TOKEN}/sendMessage", "토큰은 주소에만"
        payload = json.loads(request.content)
        box["sent"].append((payload["chat_id"], payload["text"]))
        return httpx.Response(box["status"], json=box["body"], headers=box["headers"])

    monkeypatch.setattr(client, "TRANSPORT", httpx.MockTransport(handler))
    yield {**cookies, "box": box}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL app.consent_purge = 'on'")                          # 동의 기록은 DB 가 지우기를 막는다 — 정리 작업과 같은 문을 연다
        cur.execute("DELETE FROM consent_events WHERE tenant_id=%s", (cookies["tenant"],))
        cur.execute("DELETE FROM telegram_link_codes WHERE tenant_id=%s", (cookies["tenant"],))
        cur.execute("DELETE FROM customer_profiles WHERE tenant_id=%s", (cookies["tenant"],))
        cur.execute("DELETE FROM telegram_seen_updates WHERE update_id >= %s AND update_id < %s", (_BASE, _BASE + 1_000_000))


def _key(env) -> dict:
    response = env["client"].post("/v1/web/session")
    assert response.status_code == 201, response.text
    return _h(response.json()["user_key"])


def _start(env, headers):
    return env["client"].post("/v1/web/profile/telegram/connect/start", headers=headers)


def _code(started) -> str:
    assert started.status_code == 200, started.text
    return parse_qs(urlparse(started.json()["link"]).query)["start"][0]


#: 텔레그램 업데이트 번호 — 처리한 번호를 DB 가 이틀 동안 기억하므로(재전송 방지) 실행마다 다른 범위에서 시작한다(앞 실행이 남긴 번호와 겹쳐 「이미 처리한 것」으로 건너뛰지 않게)
_BASE = 1_000_000 + (uuid4().int % 900_000_000)
_update_ids = iter(range(_BASE, _BASE + 1_000_000))


def _message(chat_id: int, text: str, *, chat_type: str = "private", update_id: int | None = None) -> dict:
    return {"update_id": update_id or next(_update_ids), "message": {"message_id": 1, "chat": {"id": chat_id, "type": chat_type},
                                                                     "from": {"id": chat_id, "first_name": "Kim", "username": "kimcs"}, "text": text}}


def _member(chat_id: int, status: str, update_id: int | None = None) -> dict:
    return {"update_id": update_id or next(_update_ids),
            "my_chat_member": {"chat": {"id": chat_id, "type": "private"}, "new_chat_member": {"status": status, "user": {"id": 1}}}}


def _hook(env, update: dict, secret: str | None = SECRET):
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {}
    return env["client"].post("/v1/telegram/webhook", json=update, headers=headers)


def _profile(env, headers) -> dict:
    return env["client"].get("/v1/web/profile", headers=headers).json()


def _connect(env, headers, chat_id: int = CHAT) -> dict:
    assert _hook(env, _message(chat_id, f"/start {_code(_start(env, headers))}")).status_code == 200
    return _profile(env, headers)


# ── ① 설정 ──────────────────────────────────────────────────────
def test_without_a_bot_the_row_is_hidden_and_start_is_404_and_the_webhook_is_always_401(cookies):  # noqa: F811
    headers = _key(cookies)
    body = _profile(cookies, headers)
    assert body["telegram_connect"] == {"available": False} and body["telegram"]["connected"] is False and body["notice_channel"] is None
    assert _start(cookies, headers).status_code == 404
    assert _hook(cookies, _message(CHAT, "/start x" * 5), secret=SECRET).status_code == 401           # 설정이 없으면 비밀값이 맞아도 열지 않는다


def test_half_configured_bot_is_not_available(cookies, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings_module.get_settings(), "telegram_bot_token", TOKEN)
    assert _profile(cookies, _key(cookies))["telegram_connect"] == {"available": False}


def test_every_profile_response_carries_the_telegram_fields(tg, monkeypatch):
    headers = _key(tg)
    assert _profile(tg, headers)["telegram_connect"] == {"available": True}
    saved = tg["client"].put("/v1/web/profile", headers=headers, json={"recovery_email": "me@example.com"}).json()
    assert saved["telegram_connect"] == {"available": True} and saved["telegram"]["connected"] is False and saved["notice_channel"] is None


# ── ② 한 바퀴 ───────────────────────────────────────────────────
def test_start_gives_a_telegram_link_with_a_valid_one_time_code(tg):
    started = _start(tg, _key(tg))
    assert started.status_code == 200 and started.headers["cache-control"] == "no-store"
    link = urlparse(started.json()["link"])
    assert f"{link.scheme}://{link.netloc}{link.path}" == f"https://t.me/{USERNAME}"
    code = parse_qs(link.query)["start"][0]
    assert 20 <= len(code) <= 64 and all(c.isalnum() or c in "_-" for c in code)           # 텔레그램 규칙: 64자 이하 · A-Z a-z 0-9 _ -
    assert started.json()["expires_at"]


def test_a_full_round_trip_connects_greets_and_never_returns_the_chat_number(tg, caplog):
    caplog.set_level(logging.DEBUG)
    headers = _key(tg)
    code = _code(_start(tg, headers))
    response = _hook(tg, _message(CHAT, f"/start {code}"))
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.SAY_CONNECTED)]                   # 봇이 인사한다
    body = _profile(tg, headers)
    assert body["telegram"]["connected"] is True and body["telegram"]["status"] == "untested" and body["telegram"]["connected_at"]
    assert body["notice_channel"] == "telegram"
    assert str(CHAT) not in json.dumps(body)                                                # 대화 번호는 어느 응답에도 없다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT telegram_chat_enc, telegram_chat_hash FROM customer_profiles WHERE tenant_id=%s", (tg["tenant"],))
        [(stored, hashed)] = cur.fetchall()
    assert stored.startswith("v1:") and str(CHAT) not in stored and str(CHAT) not in hashed and telegram_connect.decrypt_chat(stored) == CHAT
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in logged and code not in logged and str(CHAT) not in logged and "kimcs" not in logged


# ── ③ 코드 · 비밀 헤더 · 재전송 ─────────────────────────────────
def test_the_same_code_twice_and_unknown_or_old_codes_get_the_expired_reply(tg):
    headers = _key(tg)
    code = _code(_start(tg, headers))
    _hook(tg, _message(CHAT, f"/start {code}"))
    tg["box"]["sent"].clear()
    _hook(tg, _message(OTHER_CHAT, f"/start {code}"))                                         # 같은 코드를 다른 대화가 또
    _hook(tg, _message(CHAT, "/start " + "z" * 43))                                            # 모르는 코드
    _hook(tg, _message(CHAT, "/start bad code!"))                                              # 모양이 틀린 코드
    assert [text for _chat, text in tg["box"]["sent"]] == [telegram_connect.SAY_EXPIRED] * 3


def test_a_code_older_than_ten_minutes_is_expired(tg):
    headers = _key(tg)
    code = _code(_start(tg, headers))
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE telegram_link_codes SET created_at = now() - interval '11 minutes' WHERE tenant_id=%s", (tg["tenant"],))
    _hook(tg, _message(CHAT, f"/start {code}"))
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.SAY_EXPIRED)] and _profile(tg, headers)["telegram"]["connected"] is False


@pytest.mark.parametrize("secret", [None, "", "wrong-secret", SECRET + "x", SECRET[:-1]])
def test_a_missing_or_wrong_secret_header_is_401_and_nothing_changes(tg, secret):
    headers = _key(tg)
    code = _code(_start(tg, headers))
    refused = _hook(tg, _message(CHAT, f"/start {code}"), secret=secret)
    assert refused.status_code == 401 and tg["box"]["sent"] == []
    assert _profile(tg, headers)["telegram"]["connected"] is False                            # 코드도 안 쓰였다
    assert _hook(tg, _message(CHAT, f"/start {code}")).status_code == 200 and _profile(tg, headers)["telegram"]["connected"] is True


def test_telegram_redelivering_the_same_update_is_processed_once(tg):
    headers = _key(tg)
    update = _message(CHAT, f"/start {_code(_start(tg, headers))}", update_id=_BASE + 900_001)
    _hook(tg, update)
    _hook(tg, update)                                                                        # 2xx 가 늦어 텔레그램이 같은 업데이트를 다시 보냈다
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.SAY_CONNECTED)]                       # 「이미 쓴 링크」라는 엉뚱한 답이 나가지 않는다


def test_a_malformed_body_is_400_after_the_secret_check(tg):
    bad = tg["client"].post("/v1/telegram/webhook", content=b"not json", headers={"X-Telegram-Bot-Api-Secret-Token": SECRET, "Content-Type": "application/json"})
    assert bad.status_code == 400
    assert tg["client"].post("/v1/telegram/webhook", content=b"not json").status_code == 401        # 비밀 헤더가 먼저다


# ── ④ 다른 사용자에게 묶인 대화 ─────────────────────────────────
def test_a_chat_already_linked_to_someone_else_is_not_linked_again(tg):
    first, second = _key(tg), _key(tg)
    _connect(tg, first)
    tg["box"]["sent"].clear()
    _hook(tg, _message(CHAT, f"/start {_code(_start(tg, second))}"))
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.SAY_ELSEWHERE)]
    assert _profile(tg, second)["telegram"]["connected"] is False and _profile(tg, first)["telegram"]["connected"] is True       # 합치지 않는다


def test_the_same_user_reconnecting_with_another_chat_replaces_the_old_one(tg):
    headers = _key(tg)
    _connect(tg, headers, CHAT)
    _connect(tg, headers, OTHER_CHAT)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT telegram_chat_enc FROM customer_profiles WHERE tenant_id=%s", (tg["tenant"],))
        [(stored,)] = cur.fetchall()
    assert telegram_connect.decrypt_chat(stored) == OTHER_CHAT


# ── ⑤ 알림만 ────────────────────────────────────────────────────
def test_any_other_message_gets_one_fixed_line_without_storing_or_logging_it(tg, caplog):
    caplog.set_level(logging.DEBUG)
    secret_words = "내 카드번호는 9999-8888-7777-6666 이에요 PRIVATE-WORDS"
    _hook(tg, _message(CHAT, secret_words))
    _hook(tg, _message(CHAT, "/start"))                                                       # 코드 없는 시작
    _hook(tg, _message(CHAT, "/help"))
    assert [text for _chat, text in tg["box"]["sent"]] == [telegram_connect.SAY_OTHER] * 3
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "PRIVATE-WORDS" not in logged and "9999" not in logged
    with get_connection() as conn, conn.cursor() as cur:
        for table in ("customer_profiles", "telegram_link_codes", "telegram_seen_updates", "trip_chat_turns", "case_events"):
            cur.execute(f"SELECT count(*) FROM {table} t WHERE t::text LIKE '%%PRIVATE-WORDS%%'")
            assert cur.fetchone()[0] == 0, f"{table} 에 글 내용이 있다"


def test_a_group_chat_is_ignored(tg):
    _hook(tg, _message(-100123, "/start abc", chat_type="supergroup"))
    assert tg["box"]["sent"] == []


# ── ⑥ 차단 · 해제 ───────────────────────────────────────────────
def test_blocking_the_bot_marks_blocked_and_unblocking_marks_untested(tg):
    headers = _key(tg)
    _connect(tg, headers)
    _hook(tg, _member(CHAT, "kicked"))
    assert _profile(tg, headers)["telegram"]["status"] == "blocked"
    _hook(tg, _member(CHAT, "member"))
    assert _profile(tg, headers)["telegram"]["status"] == "untested"
    _hook(tg, _member(999, "kicked"))                                                         # 모르는 대화는 아무것도 안 바꾼다
    assert _profile(tg, headers)["telegram"]["status"] == "untested"


# ── ⑦ 풀기 · 알림 받는 곳 ───────────────────────────────────────
def test_disconnect_deletes_the_chat_and_falls_back_to_discord_or_nothing(tg):
    headers = _key(tg)
    _connect(tg, headers)
    assert tg["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_A}).json()["notice_channel"] == "discord"      # 마지막에 연결한 곳이 활성
    assert tg["client"].put("/v1/web/profile", headers=headers, json={"notice_channel": "telegram"}).json()["notice_channel"] == "telegram"
    gone = tg["client"].delete("/v1/web/profile/telegram", headers=headers)
    assert gone.status_code == 200 and gone.json()["profile"]["notice_channel"] == "discord" and gone.json()["profile"]["telegram"]["connected"] is False
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT telegram_chat_enc, telegram_chat_hash, telegram_status FROM customer_profiles WHERE tenant_id=%s", (tg["tenant"],))
        assert cur.fetchone() == (None, None, None)
    tg["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": None})
    assert _profile(tg, headers)["notice_channel"] is None                                    # 둘 다 없으면 없음


def test_removing_the_webhook_while_telegram_is_connected_moves_the_channel_to_telegram(tg):
    headers = _key(tg)
    tg["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_A})
    _connect(tg, headers)
    assert _profile(tg, headers)["notice_channel"] == "telegram"                              # 텔레그램을 나중에 연결했으니 활성
    tg["client"].put("/v1/web/profile", headers=headers, json={"notice_channel": "discord"})
    out = tg["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": None}).json()
    assert out["notice_channel"] == "telegram"


@pytest.mark.parametrize("value,expected", [("telegram", "channel_not_connected"), ("discord", "channel_not_connected"),
                                            ("kakao", "invalid_notice_channel"), (None, "invalid_notice_channel"), (7, "invalid_notice_channel")])
def test_choosing_a_channel_that_is_not_connected_or_unknown_is_422(tg, value, expected):
    headers = _key(tg)
    refused = tg["client"].put("/v1/web/profile", headers=headers, json={"notice_channel": value})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == expected


def test_a_refused_update_changes_nothing_at_all(tg):
    """하나라도 틀리면 전부 거절 — 이메일은 맞아도 알림 받는 곳이 틀리면 이메일도 안 바뀐다."""
    headers = _key(tg)
    refused = tg["client"].put("/v1/web/profile", headers=headers, json={"recovery_email": "me@example.com", "notice_channel": "telegram"})
    assert refused.status_code == 422 and _profile(tg, headers)["recovery_email"] is None


# ── ⑧ 시험 발송 ─────────────────────────────────────────────────
def _test_send(env, headers):
    return env["client"].post("/v1/web/profile/telegram/test", headers=headers)


def test_the_test_message_reports_ok_blocked_rate_limited_and_failed(tg, monkeypatch):
    headers = _key(tg)
    _connect(tg, headers)
    interval = float(settings_module.get_guardrails().get("travel.profile.test_interval_seconds"))

    def retry():
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE customer_profiles SET telegram_tested_at = now() - make_interval(secs => %s) WHERE tenant_id=%s", (interval + 5, tg["tenant"]))

    tg["box"]["sent"].clear()
    ok = _test_send(tg, headers)
    assert ok.status_code == 200 and ok.json()["result"] == "ok" and ok.json()["profile"]["telegram"]["status"] == "ok"
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.TEST_TEXT)]
    too_soon = _test_send(tg, headers)
    assert too_soon.status_code == 429 and too_soon.json()["error"]["code"] == "too_soon" and int(too_soon.headers["retry-after"]) >= 1
    retry()
    tg["box"].update(status=403, body={"ok": False, "description": "Forbidden: bot was blocked by the user"})
    blocked = _test_send(tg, headers)
    assert blocked.json()["result"] == "blocked" and blocked.json()["profile"]["telegram"]["status"] == "blocked"
    retry()
    tg["box"].update(status=429, body={"ok": False, "parameters": {"retry_after": 7}})
    assert _test_send(tg, headers).json()["result"] == "rate_limited"
    retry()
    tg["box"].update(status=500, body={"ok": False})
    assert _test_send(tg, headers).json()["result"] == "failed"


def test_the_test_message_without_a_connection_is_409(tg):
    refused = _test_send(tg, _key(tg))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "no_telegram"


# ── ⑨ 비밀 · 한도 · 동의 ────────────────────────────────────────
def test_no_token_chat_number_code_or_secret_is_stored_in_plain_text(tg):
    headers = _key(tg)
    code = _code(_start(tg, headers))
    _hook(tg, _message(CHAT, f"/start {code}"))
    with get_connection() as conn, conn.cursor() as cur:
        for table in ("customer_profiles", "telegram_link_codes", "telegram_seen_updates"):
            cur.execute(f"SELECT t::text FROM {table} t")
            dump = "\n".join(row[0] for row in cur.fetchall())
            for secret in (TOKEN, SECRET, code, str(CHAT)):
                assert secret not in dump, f"{table} 에 평문 비밀값이 있다"


def test_start_is_limited_per_user_per_hour(tg):
    cap = int(settings_module.get_guardrails().get("security.telegram_connect_start_per_hour"))
    one, other = _key(tg), _key(tg)
    for _ in range(cap):
        assert _start(tg, one).status_code == 200
    refused = _start(tg, one)
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "too_many_requests" and int(refused.headers["retry-after"]) >= 1
    assert _start(tg, other).status_code == 200


def test_start_needs_a_logged_in_user_and_a_cookie_session_needs_the_csrf_token(tg):
    assert tg["client"].post("/v1/web/profile/telegram/connect/start").status_code == 401
    body, _raw = _guest(tg)
    assert tg["client"].post("/v1/web/profile/telegram/connect/start", headers={"Origin": WEB}).status_code == 403
    ok = tg["client"].post("/v1/web/profile/telegram/connect/start", headers={"Origin": WEB, "X-CSRF-Token": body["csrf_token"]})
    assert ok.status_code == 200 and ok.json()["link"].startswith("https://t.me/")


def test_with_the_consent_gate_on_connecting_needs_the_alert_channel_consent(tg, monkeypatch):
    monkeypatch.setattr(consents, "gate_enabled", lambda: True)
    headers = _key(tg)
    digest = "a" * 64

    def agree(*codes):
        done = tg["client"].post("/v1/web/consents", headers=headers, json={"version": consents.current_version(),
                                 "items": [{"code": c, "agreed": True, "text_sha256": digest} for c in codes]})
        assert done.status_code == 200, done.text

    # ① 필수 동의가 하나도 없으면 웹 전체 관문이 먼저 막는다(어느 항목인지가 아니라 필수 목록을 싣는다)
    first = _start(tg, headers)
    assert first.status_code == 403 and first.json()["error"]["code"] == "consent_required" and "item" not in first.json()["error"]
    # ② 필수만 동의 → 관문은 지나고, 알림 채널 동의가 없어서 이 기능이 막는다(오류 본문에 항목 이름 `item`)
    agree("service_terms", "privacy")
    blocked = _start(tg, headers)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "consent_required" and blocked.json()["error"]["item"] == "alert_channel"
    blocked_put = tg["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_A})
    assert blocked_put.status_code == 403 and blocked_put.json()["error"]["item"] == "alert_channel"
    assert tg["client"].put("/v1/web/profile", headers=headers, json={"notice_channel": "telegram"}).json()["error"]["item"] == "alert_channel"
    # ③ 알림 채널까지 동의한 뒤에는 된다 — 키 사용자의 동의 기록은 옛 키로 기록한다
    agree("alert_channel")
    assert _start(tg, headers).status_code == 200


def test_a_code_made_before_the_consent_was_withdrawn_does_not_connect(tg, monkeypatch):
    """게이트가 켜졌고 동의가 없으면 봇에서 「시작」을 눌러도 묶지 않는다 — 안내 답을 하고 코드는 그대로 둔다."""
    headers = _key(tg)
    code = _code(_start(tg, headers))                                                          # 게이트가 꺼져 있을 때 만든 코드
    monkeypatch.setattr(consents, "gate_enabled", lambda: True)
    _hook(tg, _message(CHAT, f"/start {code}"))
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.SAY_CONSENT)]
    monkeypatch.setattr(consents, "gate_enabled", lambda: False)
    tg["box"]["sent"].clear()
    _hook(tg, _message(CHAT, f"/start {code}"))
    assert tg["box"]["sent"] == [(CHAT, telegram_connect.SAY_CONNECTED)]                       # 코드는 안 쓰였으니 동의가 풀린 뒤엔 된다


def test_withdrawing_the_alert_channel_consent_deletes_the_telegram_chat_and_the_webhook_and_clears_the_channel(tg, monkeypatch):
    """★개인정보: 알림 채널 동의를 거두면 저장해 둔 알림 받는 곳(대화 번호 · 웹훅)이 **둘 다** 지워진다 — 디스코드만 지우고 텔레그램을 남기면 안 된다."""
    monkeypatch.setattr(consents, "gate_enabled", lambda: True)
    headers = _key(tg)

    def post(*pairs):
        done = tg["client"].post("/v1/web/consents", headers=headers, json={"version": consents.current_version(),
                                 "items": [{"code": c, "agreed": agreed, "text_sha256": "a" * 64} for c, agreed in pairs]})
        assert done.status_code == 200, done.text

    post(("service_terms", True), ("privacy", True), ("alert_channel", True))
    _connect(tg, headers)
    tg["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_A})
    assert _profile(tg, headers)["notice_channel"] == "discord"
    post(("alert_channel", False))
    body = _profile(tg, headers)
    assert body["telegram"] == {"connected": False, "status": None, "connected_at": None}
    assert body["discord_webhook"]["set"] is False and body["notice_channel"] is None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT telegram_chat_enc, telegram_chat_hash, discord_webhook_enc, notice_channel FROM customer_profiles WHERE tenant_id=%s", (tg["tenant"],))
        assert cur.fetchone() == (None, None, None, None)
    # 텔레그램만 연결돼 있던 사람도 같다
    post(("alert_channel", True))
    _connect(tg, headers, OTHER_CHAT)
    post(("alert_channel", False))
    assert _profile(tg, headers)["telegram"]["connected"] is False and _profile(tg, headers)["notice_channel"] is None
