# -*- coding: utf-8 -*-
"""★디스코드가 「이때 다시 와라」고 하면 그 값을 따른다.

`[2026-10-03]` 전에는 429 를 다른 실패와 똑같이 다뤄 **고정 1분 뒤**에 다시 걸었다.
디스코드 문서는 `Retry-After` 헤더(또는 본문 `retry_after`)를 따르라고 요구하고,
어기면 **IP 단위로 막는다** — 유효하지 않은 요청이 10분에 10,000건을 넘으면 차단이다.
우리가 간격을 지어내면 더 자주 두드리거나(차단) 쓸데없이 늦어진다. 둘 다 손해다.

★시도 횟수를 올리지 않는 것도 함께 본다. 429 는 우리 잘못이 아니라 「지금은 말고」라서,
  이것으로 `dead_letter` 가 되면 보낼 수 있는 알림을 버리는 것이 된다.
"""
from __future__ import annotations

import httpx
import pytest

from app.infrastructure.notify.discord import (MAX_RETRY_AFTER_SECONDS, DiscordWebhook,
                                               RetryAfter)

WEBHOOK = "https://example.invalid/hook"
MESSAGE = {"topic": "trip.notice", "tenant_id": "t1",
           "payload": {"text": "알림", "locale": "ko"}}


def _hook(response: httpx.Response) -> DiscordWebhook:
    # ★테넌트 제한은 이 시험의 관심사가 아니다 — 열어 두고 429 처리만 본다.
    hook = DiscordWebhook(WEBHOOK, allowed_tenants=None)
    hook._post = lambda url, json: response       # noqa: SLF001 — 보내는 자리만 바꾼다
    return hook


def _429(headers=None, body=None) -> httpx.Response:
    return httpx.Response(429, headers=headers or {}, json=body if body is not None else {},
                          request=httpx.Request("POST", WEBHOOK))


def test_429_헤더가_말한_초를_그대로_물고_올라온다():
    with pytest.raises(RetryAfter) as caught:
        _hook(_429(headers={"Retry-After": "3.75"}))(MESSAGE)
    assert caught.value.seconds == pytest.approx(3.75)


def test_헤더가_없으면_본문의_값을_읽는다():
    """★디스코드는 헤더와 본문 양쪽에 같은 값을 싣는다. 한쪽만 와도 받아야 한다."""
    with pytest.raises(RetryAfter) as caught:
        _hook(_429(body={"retry_after": 2.5}))(MESSAGE)
    assert caught.value.seconds == pytest.approx(2.5)


@pytest.mark.parametrize("headers, body", [
    ({"Retry-After": "not-a-number"}, {}),
    ({"Retry-After": "-5"}, {}),
    ({"Retry-After": str(MAX_RETRY_AFTER_SECONDS + 1)}, {}),
    ({}, {}),
])
def test_믿을_수_없는_값이면_None_이라_우리_기본값으로_간다(headers, body):
    """★공급자가 이상한 값을 줘도 알림이 하루 넘게 멈추면 안 된다."""
    with pytest.raises(RetryAfter) as caught:
        _hook(_429(headers=headers, body=body))(MESSAGE)
    assert caught.value.seconds is None


def test_429_가_아닌_실패는_예전처럼_일반_오류다():
    """★429 만 특별히 다룬다. 5xx 는 우리 쪽 재시도 규칙 그대로여야 한다."""
    response = httpx.Response(500, text="서버 오류",
                              request=httpx.Request("POST", WEBHOOK))
    with pytest.raises(RuntimeError) as caught:
        _hook(response)(MESSAGE)
    assert not isinstance(caught.value, RetryAfter)


def test_재시도_간격이_설정에서_온다():
    """★`[2026-10-03]` 전에는 SQL 에 박혀 있어 설정으로 못 바꿨다."""
    from app.infrastructure.messaging.worker import OutboxWorker

    assert OutboxWorker._retry_seconds() == 60.0      # noqa: SLF001
