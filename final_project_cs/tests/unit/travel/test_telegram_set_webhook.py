# -*- coding: utf-8 -*-
"""텔레그램 웹훅 등록 스크립트(`scripts/telegram_set_webhook.py`) — 등록 · 확인 · 해제가 맞는 요청을 보내고, **출력에 토큰 · 주소 · 비밀값이 안 찍히는가**.
`[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」]`

★텔레그램은 **mock 서버**(`httpx.MockTransport`)다 — 실제 봇에 등록해 본 것이 아니다(그건 사용자가 봇을 만든 뒤 배포 환경에서 한다).
 ①등록: `setWebhook` 에 주소(`{공개 주소}/v1/telegram/webhook`) · `secret_token` · `allowed_updates` ②https 가 아니거나 허용 밖 포트 · 비밀값 모양 이상 · 설정 누락은 **호출 전에** 멈춘다
 ③출력(성공 · 실패 · 텔레그램 설명 문구 · 예외)에 토큰 · 주소 · 비밀값이 없다 ④`--info` 는 처리 못 한 업데이트 수와 마지막 오류만 · `--delete` 는 `deleteWebhook`

재현:

    python -m pytest tests/unit/travel/test_telegram_set_webhook.py -v
"""
from __future__ import annotations

import io
import json
from types import SimpleNamespace

import httpx
import pytest

from scripts.telegram_set_webhook import SetupError, main, webhook_url

TOKEN = "123456789:AAExampleBotTokenForTestsOnly_abcdefghijk"
SECRET = "webhook-secret-for-tests_ABC-123"
BASE = "https://tripilot.example.test"
HOOK = BASE + "/v1/telegram/webhook"


def _settings(**override):
    values = {"telegram_bot_token": TOKEN, "telegram_webhook_secret": SECRET, "public_base_url": BASE}
    values.update(override)
    return SimpleNamespace(**values)


def _transport(*, status=200, body=None, raise_exc=None, seen=None, content=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append((request.url.path, json.loads(request.content) if request.content else None))
        if raise_exc is not None:
            raise raise_exc
        if content is not None:
            return httpx.Response(status, content=content)
        return httpx.Response(status, json=body if body is not None else {"ok": True, "result": True, "description": "Webhook was set"})
    return httpx.MockTransport(handler)


def _run(argv, settings=None, **kwargs):
    out = io.StringIO()
    code = main(argv, settings=settings or _settings(), out=out, **kwargs)
    return code, out.getvalue()


def _secret_free(text: str) -> None:
    for secret in (TOKEN, SECRET, HOOK, BASE, "tripilot.example.test", "api.telegram.org/bot"):
        assert secret not in text, f"출력에 {secret[:12]}… 가 있다: {text!r}"


# ── 주소 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("base,expected", [
    (BASE, HOOK), (BASE + "/", HOOK), ("  " + BASE + "  ", HOOK), (BASE + ":8443", BASE + ":8443/v1/telegram/webhook"),
    (BASE + ":443", BASE + ":443/v1/telegram/webhook"), (BASE + "/prefix", BASE + "/prefix/v1/telegram/webhook")])
def test_the_webhook_url_is_the_public_address_plus_the_fixed_path(base, expected):
    assert webhook_url(base) == expected


@pytest.mark.parametrize("base", ["", "   ", "http://tripilot.example.test", "http://127.0.0.1:8042", "ftp://tripilot.example.test", "tripilot.example.test",
                                  "https://", BASE + ":9000", BASE + ":80000", "https://user:pw@tripilot.example.test", BASE + "?x=1", BASE + "#frag"])
def test_a_non_https_or_odd_address_is_refused_without_echoing_it(base):
    with pytest.raises(SetupError) as caught:
        webhook_url(base)
    assert "tripilot.example.test" not in str(caught.value) and "pw" not in str(caught.value).replace("포트", "")


# ── 등록 ────────────────────────────────────────────────────────
def test_register_posts_the_url_the_secret_and_only_the_update_kinds_we_handle():
    seen = []
    code, out = _run([], transport=_transport(seen=seen))
    assert code == 0 and out.strip() == "ok=true Webhook was set"
    assert seen == [(f"/bot{TOKEN}/setWebhook", {"url": HOOK, "secret_token": SECRET, "allowed_updates": ["message", "my_chat_member"]})]
    _secret_free(out)


def test_a_refusal_from_telegram_is_exit_1_and_still_prints_nothing_secret():
    leaky = {"ok": False, "error_code": 400, "description": f"Bad Webhook: could not reach {HOOK} with {SECRET} using {TOKEN}"}
    code, out = _run([], transport=_transport(status=400, body=leaky))
    assert code == 1 and out.startswith("ok=false") and "Bad Webhook" in out
    _secret_free(out)                                                         # 텔레그램의 설명에 섞여 와도 가려서 찍는다


def test_a_wrong_token_is_exit_1_with_telegrams_short_reason():
    code, out = _run([], transport=_transport(status=401, body={"ok": False, "error_code": 401, "description": "Unauthorized"}))
    assert code == 1 and out.strip() == "ok=false Unauthorized"


# ── 호출 전에 멈추는 것 ─────────────────────────────────────────
@pytest.mark.parametrize("override,hint", [
    ({"telegram_bot_token": ""}, "ACOP_TELEGRAM_BOT_TOKEN"),
    ({"telegram_webhook_secret": ""}, "ACOP_TELEGRAM_WEBHOOK_SECRET"),
    ({"telegram_bot_token": "  "}, "ACOP_TELEGRAM_BOT_TOKEN"),
    ({"public_base_url": "http://127.0.0.1:8042"}, "https"),
    ({"public_base_url": BASE + ":9000"}, "포트"),
    ({"telegram_webhook_secret": "bad secret!"}, "영문"),
    ({"telegram_webhook_secret": "x" * 257}, "영문"),
    ({"telegram_webhook_secret": "한글비밀값"}, "영문"),
])
def test_missing_or_invalid_settings_stop_before_any_call(override, hint):
    seen = []
    code, out = _run([], settings=_settings(**override), transport=_transport(seen=seen))
    assert code == 2 and out.startswith("중단:") and hint in out and seen == []
    _secret_free(out)
    assert "bad secret" not in out and "한글비밀값" not in out


def test_delete_and_info_need_only_the_token():
    seen = []
    assert _run(["--delete"], settings=_settings(telegram_webhook_secret="", public_base_url=""), transport=_transport(seen=seen))[0] == 0
    assert _run(["--info"], settings=_settings(telegram_webhook_secret="", public_base_url=""),
                transport=_transport(seen=seen, body={"ok": True, "result": {"url": "", "pending_update_count": 0}}))[0] == 0
    assert [path for path, _body in seen] == [f"/bot{TOKEN}/deleteWebhook", f"/bot{TOKEN}/getWebhookInfo"]
    code, out = _run(["--delete"], settings=_settings(telegram_bot_token=""), transport=_transport(seen=seen))
    assert code == 2 and len(seen) == 2


# ── 확인 · 해제 ─────────────────────────────────────────────────
def test_info_prints_only_the_pending_count_and_the_last_error_and_never_the_address():
    body = {"ok": True, "result": {"url": HOOK, "has_custom_certificate": False, "pending_update_count": 3, "max_connections": 40,
                                   "last_error_date": 1760000000, "last_error_message": f"Connection refused to {HOOK}", "allowed_updates": ["message"]}}
    code, out = _run(["--info"], transport=_transport(body=body))
    assert code == 0 and "처리 못 한 업데이트=3" in out and "등록됨=예" in out and "마지막 오류=" in out and "Connection refused" in out
    _secret_free(out)
    assert "max_connections" not in out and "has_custom_certificate" not in out


def test_info_with_nothing_registered_says_so():
    code, out = _run(["--info"], transport=_transport(body={"ok": True, "result": {"url": "", "pending_update_count": 0}}))
    assert code == 0 and "등록됨=아니오" in out and "처리 못 한 업데이트=0" in out and "마지막 오류=없음" in out


def test_delete_calls_delete_webhook_and_keeps_pending_updates():
    seen = []
    code, out = _run(["--delete"], transport=_transport(seen=seen, body={"ok": True, "result": True, "description": "Webhook was deleted"}))
    assert code == 0 and out.strip() == "ok=true Webhook was deleted" and seen == [(f"/bot{TOKEN}/deleteWebhook", {})]


def test_info_and_delete_cannot_be_combined():
    with pytest.raises(SystemExit):
        _run(["--info", "--delete"], transport=_transport())


# ── 연결 실패 ───────────────────────────────────────────────────
@pytest.mark.parametrize("exc,expected", [
    (httpx.ReadTimeout(f"slow {TOKEN}"), "시간 안에"),
    (httpx.ConnectError(f"refused https://api.telegram.org/bot{TOKEN}/setWebhook"), "ConnectError"),
])
def test_a_network_failure_is_exit_2_with_only_the_kind(exc, expected):
    code, out = _run([], transport=_transport(raise_exc=exc))
    assert code == 2 and expected in out
    _secret_free(out)


def test_a_non_json_answer_is_exit_2():
    code, out = _run([], transport=_transport(status=502, content=b"<html>bad gateway</html>"))
    assert code == 2 and "HTTP 502" in out
    _secret_free(out)

