# -*- coding: utf-8 -*-
"""디스코드 웹훅 발행자 — 「보내지 않은 알림이 보낸 것으로 기록되지 않는가」가 핵심이다."""
from __future__ import annotations

import httpx
import pytest

from app.infrastructure.notify.discord import (DiscordWebhook, MAX_CONTENT, NoticeNotConfigured,
                                               render)

NOTICE = {"topic": "trip.notice", "payload": {
    "text": "오늘 오전 잠실 스카이타워 야외 전망 데크는 시야 확보가 어려울 것으로 예상되어, "
            "같은 건물 지하 1층 아쿠아리움으로 변경됩니다.",
    "other_options": ["롯데월드 어드벤처"], "replay": True, "version": 2}}


def _hook(status=204, *, url="https://discord.example/webhook", raise_exc=None, seen=None):
    def post(target, json):
        if seen is not None:
            seen.append((target, json))
        if raise_exc is not None:
            raise raise_exc
        return httpx.Response(status, request=httpx.Request("POST", target))
    return DiscordWebhook(url, transport=post)


def test_a_replay_notice_is_labelled_and_carries_other_options():
    content = render(NOTICE["payload"])
    assert content.startswith("[재생] 오늘 오전 잠실 스카이타워")
    assert "다른 안: 롯데월드 어드벤처" in content and "(일정 버전 2)" in content


def test_success_posts_once():
    seen = []
    assert _hook(seen=seen)(NOTICE) is None
    [(target, body)] = seen
    assert target.endswith("/webhook") and body["content"].startswith("[재생]")


def test_without_a_url_it_fails_instead_of_pretending_to_deliver():
    """★조용히 반환하면 일꾼이 `delivered` 로 찍는다 — 보낸 적 없는 알림이 보낸 것이 된다."""
    with pytest.raises(NoticeNotConfigured):
        _hook(url="")(NOTICE)


def test_a_timeout_becomes_unknown_not_success():
    """★일꾼은 TimeoutError 를 `unknown` 으로 둔다 — 자동 재전송으로 두 번 보내지 않는다."""
    with pytest.raises(TimeoutError):
        _hook(raise_exc=httpx.ReadTimeout("slow"))(NOTICE)


def test_a_connection_error_becomes_unknown():
    with pytest.raises(ConnectionError):
        _hook(raise_exc=httpx.ConnectError("down"))(NOTICE)


@pytest.mark.parametrize("status", [400, 429, 500])
def test_a_non_2xx_is_a_retryable_failure(status):
    with pytest.raises(RuntimeError):
        _hook(status=status)(NOTICE)


def test_other_topics_go_to_the_fallback_untouched():
    handled = []
    hook = DiscordWebhook("https://x", transport=lambda *a, **k: pytest.fail("posted"),
                          fallback=handled.append)
    hook({"topic": "provider.refund", "payload": {}})
    assert handled == [{"topic": "provider.refund", "payload": {}}]


def test_an_empty_notice_is_not_sent():
    with pytest.raises(ValueError):
        render({"text": "  "})


def test_long_content_is_cut_with_a_visible_mark():
    content = render({"text": "가" * 3000})
    assert len(content) <= MAX_CONTENT and content.endswith("…(잘림)")
