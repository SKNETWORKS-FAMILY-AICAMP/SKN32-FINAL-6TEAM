# -*- coding: utf-8 -*-
"""고객 연락처 — `GET·PUT /v1/web/profile` · `POST /v1/web/profile/discord/test`. `[2026-10-01 사용자 지시 — ui 세션 전달]`

웹훅은 서버가 나중에 그 주소로 POST 하는 **비밀값이자 바깥 호출 통로**다. 시험(요청): ①저장 뒤 조회가 마스킹만 주나 ②디스코드가 아닌 호스트 · http · IP ·
리다이렉트 시도가 막히나 ③원문 URL 이 로그 · 오류 · Case · 대화 기록에 없나(문자열 검사) ④남의 키 격리 ⑤null 로 지우기 ⑥시험 발송 횟수 제한.
★바깥 호출은 가로챈다(`customer_profile.TRANSPORT`) — 실제 디스코드로 나가지 않는다.

재현:

    python -m pytest tests/e2e/test_web_profile.py -v
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.modules.web_account import customer_profile as profile

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _fresh_limit_cache, _h, _session  # noqa: F401

TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-zYxWvUtSrQpOnMlKjIhGfEdCbA9876"
ID = "123456789012345678"
GOOD = f"https://discord.com/api/webhooks/{ID}/{TOKEN}"


@pytest.fixture()
def sent(monkeypatch):
    """바깥 호출을 가로챈다 — 보낸 요청을 모으고, `answer["code"]` 로 디스코드의 응답을 정한다."""
    box = {"requests": [], "code": 204}

    def handler(request: httpx.Request) -> httpx.Response:
        box["requests"].append(request)
        return httpx.Response(box["code"], headers={"location": "https://evil.example/x"} if box["code"] in (301, 302) else {})

    monkeypatch.setattr(profile, "TRANSPORT", httpx.MockTransport(handler))
    return box


def _get(api, me):
    return api["client"].get("/v1/web/profile", headers=_h(me["user_key"]))


def _put(api, me, body):
    return api["client"].put("/v1/web/profile", headers=_h(me["user_key"]), json=body)


def _test(api, me):
    return api["client"].post("/v1/web/profile/discord/test", headers=_h(me["user_key"]))


def test_a_new_user_has_an_empty_profile(api):
    me = _session(api)
    body = _get(api, me).json()
    assert body == {"recovery_email": None, "discord_webhook": {"set": False, "masked": None, "status": None,
                                                                "checked_at": None}, "updated_at": None,
                    "discord_connect": {"available": False},        # `[2026-10-05]` 디스코드 앱이 설정되지 않은 서버 — 단추를 보이지 않는다
                    "telegram_connect": {"available": False}, "telegram": {"connected": False, "status": None, "connected_at": None},
                    "notice_channel": None}                         # 텔레그램 봇이 설정되지 않은 서버 — 텔레그램 줄을 통째로 숨긴다


def test_saving_returns_and_reads_back_only_the_masked_webhook(api):
    """①: 저장 뒤 조회가 마스킹만 준다 — 원문(특히 토큰)은 어느 응답에도 없다. 저장은 암호화돼 있다."""
    me = _session(api)
    saved = _put(api, me, {"recovery_email": " me@example.com ", "discord_webhook_url": GOOD})
    assert saved.status_code == 200, saved.text
    for body in (saved.json(), _get(api, me).json()):
        assert body["recovery_email"] == "me@example.com"
        assert body["discord_webhook"] == {"set": True, "masked": f"https://discord.com/api/webhooks/{ID[:4]}…/••••",
                                           "status": "untested", "checked_at": None}
    assert TOKEN not in saved.text and TOKEN not in _get(api, me).text and ID not in _get(api, me).text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT discord_webhook_enc, discord_hint FROM customer_profiles WHERE tenant_id=%s",
                    (api["tenant"],))
        [(stored, hint)] = cur.fetchall()
    assert TOKEN not in stored and ID not in stored and stored.startswith("v1:")        # 원문은 DB 어디에도 없다
    assert profile.decrypt(stored) == GOOD and TOKEN not in hint and ID not in hint


@pytest.mark.parametrize("url", [
    f"http://discord.com/api/webhooks/{ID}/{TOKEN}",                       # http
    f"https://evil.example/api/webhooks/{ID}/{TOKEN}",                     # 다른 호스트
    f"https://discord.com.evil.example/api/webhooks/{ID}/{TOKEN}",         # 앞이 같은 다른 호스트
    f"https://evil.example/discord.com/api/webhooks/{ID}/{TOKEN}",
    f"https://notdiscord.com/api/webhooks/{ID}/{TOKEN}",
    f"https://127.0.0.1/api/webhooks/{ID}/{TOKEN}",                        # IP 주소
    f"https://169.254.169.254/api/webhooks/{ID}/{TOKEN}",                  # 클라우드 메타데이터 주소
    f"https://[::1]/api/webhooks/{ID}/{TOKEN}",
    f"https://discord.com@evil.example/api/webhooks/{ID}/{TOKEN}",         # 사용자정보로 속이기
    f"https://evil.example@discord.com/api/webhooks/{ID}/{TOKEN}",
    f"https://discord.com:8443/api/webhooks/{ID}/{TOKEN}",                 # 포트
    f"https://discord.com:443/api/webhooks/{ID}/{TOKEN}",
    f"https://discord.com./api/webhooks/{ID}/{TOKEN}",                     # 점이 붙은 호스트
    f"https://discord.com/api/webhooks/{ID}/{TOKEN}?wait=true",            # 쿼리
    f"https://discord.com/api/webhooks/{ID}/{TOKEN}?url=https://evil.example",
    f"https://discord.com/api/webhooks/{ID}/{TOKEN}#x",                    # 조각
    f"https://discord.com/api/webhooks/{ID}/{TOKEN}/extra",                # 경로 뒤에 더
    f"https://discord.com/api/webhooks/{ID}/{TOKEN}%2Fx",                  # 퍼센트 인코딩
    f"https://discord.com/api/webhooks/{ID}/{TOKEN};x=1",
    f"https://discord.com/api/webhooks/{ID}",                              # 토큰 없음
    f"https://discord.com/api/webhooks/abc/{TOKEN}",                       # id 가 숫자 아님
    f"https://discord.com/api/webhooks/{ID}/short",                        # 토큰이 너무 짧음
    f"https://discord.com/api/webhooks/{ID}/{TOKEN[:30]}!?",               # 토큰에 못 쓰는 글자
    f"https://discord.com//api/webhooks/{ID}/{TOKEN}",
    f"https://discord.com/api/webhooks/../../x/{ID}/{TOKEN}",
    f"ftp://discord.com/api/webhooks/{ID}/{TOKEN}",
    f"javascript:alert(1)//discord.com/api/webhooks/{ID}/{TOKEN}",
    f"https://discord.com/api/webhooks/{ID}/{TOKEN}\\x",                   # 역슬래시
    f"https://ｄiscord.com/api/webhooks/{ID}/{TOKEN}",                     # 전각 글자로 속이기
    "https://discord.com/api/webhooks/" + ID + "/" + TOKEN + "\n",         # 줄바꿈이 뒤에 붙은 것은 strip 되지만 중간은 안 됨 → 아래서 따로
])
def test_anything_that_is_not_a_discord_webhook_is_refused_without_echoing_it(api, url):
    """②: 다른 호스트 · http · IP · 사용자정보 · 포트 · 쿼리 · 리다이렉트를 노린 모양은 모두 422 — 오류 문구가 받은 값을 되돌려 싣지 않는다."""
    me = _session(api)
    refused = _put(api, me, {"discord_webhook_url": url})
    if url.endswith("\n"):                                                 # 끝 줄바꿈은 공백이라 잘려 나가 정상 주소가 된다
        assert refused.status_code == 200
        return
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "invalid_webhook", refused.text
    assert TOKEN not in refused.text and ID not in refused.text and "evil" not in refused.text
    assert _get(api, me).json()["discord_webhook"]["set"] is False        # 저장되지 않았다


def test_whitespace_inside_the_address_is_refused(api):
    me = _session(api)
    for bad in (f"https://discord.com/api/webhooks/{ID}/ {TOKEN}", f"https://disc ord.com/api/webhooks/{ID}/{TOKEN}",
                f"https://discord.com/api/webhooks/{ID}/{TOKEN}\nhttps://evil.example"):
        assert _put(api, me, {"discord_webhook_url": bad}).status_code == 422


def test_the_official_subdomains_are_accepted(api):
    me = _session(api)
    for host in ("canary.discord.com", "ptb.discord.com", "discordapp.com", "canary.discordapp.com"):
        assert _put(api, me, {"discord_webhook_url": f"https://{host}/api/webhooks/{ID}/{TOKEN}"}).status_code == 200, host


def test_a_bad_email_or_unknown_field_or_wrong_type_is_a_422_that_names_no_values(api):
    me = _session(api)
    assert _put(api, me, {"recovery_email": "not-an-email"}).json()["error"]["code"] == "invalid_email"
    assert _put(api, me, {"recovery_email": "a@b"}).status_code == 422
    assert _put(api, me, {"recovery_email": 123}).status_code == 422
    unknown = _put(api, me, {"nickname": "secret-nick-xyz", "discord_webhook_url": GOOD})
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "unknown_field"
    assert "nickname" in unknown.text and "secret-nick-xyz" not in unknown.text and TOKEN not in unknown.text
    assert _get(api, me).json()["discord_webhook"]["set"] is False        # 일부만 저장되지 않는다(칸 하나라도 틀리면 전부 거절)
    assert _put(api, me, {"discord_webhook_url": 12345}).status_code == 422


def test_null_or_blank_clears_and_a_missing_field_is_left_alone(api):
    """⑤"""
    me = _session(api)
    _put(api, me, {"recovery_email": "me@example.com", "discord_webhook_url": GOOD})
    kept = _put(api, me, {"recovery_email": "new@example.com"}).json()                  # 웹훅 칸이 없다 → 그대로
    assert kept["recovery_email"] == "new@example.com" and kept["discord_webhook"]["set"] is True
    cleared_email = _put(api, me, {"recovery_email": "   "}).json()                      # 공백만 → 지움
    assert cleared_email["recovery_email"] is None and cleared_email["discord_webhook"]["set"] is True
    cleared_hook = _put(api, me, {"discord_webhook_url": None}).json()                   # null → 지움
    assert cleared_hook["discord_webhook"] == {"set": False, "masked": None, "status": None, "checked_at": None}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT discord_webhook_enc, discord_hint FROM customer_profiles WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchall() == [(None, None)]                                          # 암호화한 값도 지워졌다


def test_one_users_profile_is_invisible_to_another_key(api):
    """④"""
    mine, other = _session(api), _session(api)
    _put(api, mine, {"recovery_email": "mine@example.com", "discord_webhook_url": GOOD})
    seen = _get(api, other).json()
    assert seen["recovery_email"] is None and seen["discord_webhook"]["set"] is False
    assert "mine@example.com" not in _get(api, other).text
    assert _test(api, other).status_code == 409                                         # 남의 웹훅으로 보낼 수 없다(내 것이 없다)
    assert api["client"].get("/v1/web/profile").status_code == 401
    assert api["client"].put("/v1/web/profile", json={}).status_code == 401
    assert api["client"].post("/v1/web/profile/discord/test").status_code == 401


def test_the_test_send_posts_one_line_to_the_saved_address_and_records_the_result(api, sent):
    me = _session(api)
    _put(api, me, {"discord_webhook_url": GOOD})
    answer = _test(api, me)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["result"] == "ok" and body["profile"]["discord_webhook"]["status"] == "ok"
    assert body["profile"]["discord_webhook"]["checked_at"] and TOKEN not in answer.text
    [request] = sent["requests"]
    assert str(request.url) == GOOD and request.method == "POST"                        # 저장한 주소 그대로 · 쿼리 없음
    payload = json.loads(request.content)
    assert "triPilot" in payload["content"] and payload["allowed_mentions"] == {"parse": []}   # 누구도 호출(@)하지 않는다


@pytest.mark.parametrize("code, result, stored", [(404, "invalid", "invalid"), (401, "invalid", "invalid"),
                                                   (429, "rate_limited", "untested"), (500, "failed", "untested")])
def test_the_result_follows_what_discord_answered(api, sent, code, result, stored):
    me = _session(api)
    _put(api, me, {"discord_webhook_url": GOOD})
    sent["code"] = code
    body = _test(api, me).json()
    assert body["result"] == result and body["profile"]["discord_webhook"]["status"] == stored, body


def test_a_redirect_is_never_followed(api, sent):
    """②: 디스코드가 아닌 곳으로 보내는 리다이렉트를 따라가지 않는다 — 요청은 한 번뿐이고 결과는 실패."""
    me = _session(api)
    _put(api, me, {"discord_webhook_url": GOOD})
    sent["code"] = 302
    body = _test(api, me).json()
    assert body["result"] == "failed" and len(sent["requests"]) == 1
    assert all("evil" not in str(r.url) for r in sent["requests"])


def test_a_network_failure_is_reported_as_failed_without_the_address(api, monkeypatch, caplog):
    me = _session(api)
    _put(api, me, {"discord_webhook_url": GOOD})

    def boom(request):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(profile, "TRANSPORT", httpx.MockTransport(boom))
    caplog.set_level(logging.DEBUG)
    answer = _test(api, me)
    assert answer.json()["result"] == "failed" and TOKEN not in answer.text
    assert TOKEN not in "\n".join(r.getMessage() for r in caplog.records)


def test_the_test_send_is_limited_to_one_per_interval(api, sent):
    """⑥: 마지막 시도 뒤 `test_interval_seconds` 안이면 429 `too_soon` + Retry-After — 간격이 지나면 다시 된다."""
    me = _session(api)
    _put(api, me, {"discord_webhook_url": GOOD})
    assert _test(api, me).status_code == 200
    again = _test(api, me)
    assert again.status_code == 429 and again.json()["error"]["code"] == "too_soon"
    assert int(again.headers["retry-after"]) >= 1 and len(sent["requests"]) == 1          # 두 번째는 나가지 않았다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:             # 간격이 지난 것처럼 시각을 되돌린다
        cur.execute("UPDATE customer_profiles SET discord_tested_at = now() - interval '60 seconds' WHERE tenant_id=%s",
                    (api["tenant"],))
    assert _test(api, me).status_code == 200 and len(sent["requests"]) == 2


def test_the_test_send_without_a_saved_webhook_is_a_409(api, sent):
    me = _session(api)
    assert _test(api, me).status_code == 409 and sent["requests"] == []


def test_a_new_webhook_resets_the_status_and_a_lost_key_asks_to_enter_it_again(api, sent, monkeypatch):
    me = _session(api)
    _put(api, me, {"discord_webhook_url": GOOD})
    _test(api, me)
    assert _get(api, me).json()["discord_webhook"]["status"] == "ok"
    again = _put(api, me, {"discord_webhook_url": GOOD.replace(ID, "987654321098765432")}).json()
    assert again["discord_webhook"]["status"] == "untested" and again["discord_webhook"]["checked_at"] is None
    # 서버 비밀키가 바뀌어 저장값을 못 풀면 — 보내지 않고 다시 넣으라고 알린다
    from app.core import settings as settings_module

    changed = settings_module.get_settings().model_copy(update={"secret_key": "another-secret-key-value-xyz"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: changed)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE customer_profiles SET discord_tested_at = NULL WHERE tenant_id=%s", (api["tenant"],))
    broken = _test(api, me)
    assert broken.status_code == 409 and broken.json()["error"]["code"] == "unreadable"
    assert len(sent["requests"]) == 1                                                  # 새 주소로는 나가지 않았다(앞의 한 번뿐)


def test_the_raw_webhook_is_in_no_log_error_case_chat_or_outbox(api, sent, caplog):
    """③: 원문(토큰 · id)이 로그 · 오류 · Case · 대화 기록 · 바깥함 어디에도 없다 — 저장 · 거절 · 시험 발송 · 실패를 모두 거친 뒤 문자열 검사."""
    caplog.set_level(logging.DEBUG)
    me = _session(api)
    bodies = [_put(api, me, {"discord_webhook_url": GOOD, "recovery_email": "me@example.com"}).text,
              _put(api, me, {"discord_webhook_url": f"http://discord.com/api/webhooks/{ID}/{TOKEN}"}).text,
              _put(api, me, {"discord_webhook_url": f"https://evil.example/api/webhooks/{ID}/{TOKEN}"}).text,
              _get(api, me).text, _test(api, me).text]
    sent["code"] = 404
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE customer_profiles SET discord_tested_at = NULL WHERE tenant_id=%s", (api["tenant"],))
    bodies.append(_test(api, me).text)
    with get_connection() as conn, conn.cursor() as cur:
        dumps = []
        for sql in ("SELECT payload_json::text FROM case_events", "SELECT state_json::text FROM customer_cases",
                    "SELECT subject FROM customer_cases", "SELECT text FROM trip_chat_turns",
                    "SELECT payload_json::text FROM outbox", "SELECT attributes::text FROM places",
                    "SELECT * FROM web_usage::text".replace("::text", ""),
                    "SELECT recovery_email || coalesce(discord_hint, '') FROM customer_profiles"):
            cur.execute(sql)
            dumps += [str(row) for row in cur.fetchall()]
    haystack = "\n".join(bodies + dumps + [r.getMessage() for r in caplog.records])
    assert TOKEN not in haystack and ID not in haystack
    assert "discord.com/api/webhooks" not in "\n".join(r.getMessage() for r in caplog.records)   # httpx 가 주소를 INFO 로 찍는 것도 걸렀다


def test_the_httpx_request_log_line_with_a_webhook_path_is_dropped():
    """httpx 는 요청 주소를 INFO 로 찍는다 — 웹훅 경로가 든 기록은 필터가 버린다(필터가 켜져 있는지 직접 본다)."""
    logger = logging.getLogger("httpx")
    record = logging.LogRecord("httpx", logging.INFO, __file__, 1, 'HTTP Request: POST %s "HTTP/1.1 204"',
                               (GOOD,), None)
    assert not all(f.filter(record) for f in logger.filters)
    plain = logging.LogRecord("httpx", logging.INFO, __file__, 1, "HTTP Request: GET %s", ("https://example.com/",), None)
    assert all(f.filter(plain) for f in logger.filters)


def test_parse_helpers_directly():
    assert profile.parse_webhook(f"  https://DISCORD.com/api/webhooks/{ID}/{TOKEN}  ") == ("discord.com", ID, TOKEN)
    assert profile.mask(("discord.com", ID, TOKEN)) == f"https://discord.com/api/webhooks/{ID[:4]}…/••••"
    assert profile.parse_email("  A.B+tag@Example.COM ") == "A.B+tag@Example.COM"
    assert profile.parse_email("   ") is None
    for bad in ("a@@b.com", "a b@c.com", "@c.com", "a@c", "a@b..com", "x" * 250 + "@c.com"):
        with pytest.raises(profile.ProfileError):
            profile.parse_email(bad)


def test_the_browser_may_send_put_with_the_user_key_from_the_web_origin(monkeypatch):
    """화면(다른 출처 — 포트 3100)이 `PUT /v1/web/profile` 을 `X-User-Key` 와 함께 보내려면 사전 확인(OPTIONS)이 통과해야 한다."""
    from fastapi.testclient import TestClient

    from app.core import settings as settings_module
    from app.presentation.api.app import create_app

    allowed = settings_module.get_settings().model_copy(update={"web_allowed_origins": "http://localhost:3100"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: allowed)
    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[]))
    preflight = client.options("/v1/web/profile", headers={
        "Origin": "http://localhost:3100", "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "x-user-key,content-type"})
    assert preflight.status_code == 200, preflight.text
    assert "PUT" in preflight.headers["access-control-allow-methods"]
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3100"
    refused = client.options("/v1/web/profile", headers={"Origin": "https://evil.example",
                                                         "Access-Control-Request-Method": "PUT"})
    assert "access-control-allow-origin" not in refused.headers                           # 허용 목록 밖은 열지 않는다
