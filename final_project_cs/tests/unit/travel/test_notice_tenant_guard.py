# -*- coding: utf-8 -*-
"""바깥으로 나가는 알림은 **운영 테넌트 것만** — 2026-09-22 사고의 회귀 시험.

☆사고: 점검을 한 회차 돌리는 사이에 시연 테넌트(`scenario-live-…`)의 통지 8건이 실제 디스코드로
  나갔다. 받는 사람은 그 여행의 고객 언어(대만 중국어)로 된 시연 문구를 받았다. 되돌릴 수 없다.
"""
from __future__ import annotations

import pytest

from app.infrastructure.notify.discord import DiscordWebhook, NoticeSuppressed


class _Post:
    def __init__(self):
        self.calls = []

    def __call__(self, url, json):
        self.calls.append(json)

        class _Response:
            status_code = 204
            text = ""
        return _Response()


def _message(tenant: str) -> dict:
    return {"message_id": "m1", "topic": "trip.notice", "tenant_id": tenant,
            "payload": {"text": "일정이 바뀌었습니다", "locale": "ko"}}


def test_a_demo_tenant_notice_never_leaves():
    post = _Post()
    send = DiscordWebhook("https://webhook.invalid/none", transport=post, allowed_tenants={"demo"})
    with pytest.raises(NoticeSuppressed, match="보낼 대상이 아닌 테넌트"):
        send(_message("scenario-live-1f0ea8d2"))
    assert post.calls == [], "시연 테넌트 통지가 바깥으로 나갔다"


def test_the_operating_tenant_still_goes_out():
    post = _Post()
    send = DiscordWebhook("https://webhook.invalid/none", transport=post, allowed_tenants={"demo"})
    send(_message("demo"))
    assert len(post.calls) == 1 and "일정이 바뀌었습니다" in post.calls[0]["content"]


def test_without_a_tenant_name_it_does_not_leave():
    """★테넌트를 못 실어 온 메시지도 내보내지 않는다 — 모르면 보내지 않는다."""
    post = _Post()
    send = DiscordWebhook("https://webhook.invalid/none", transport=post, allowed_tenants={"demo"})
    with pytest.raises(NoticeSuppressed):
        send({"message_id": "m2", "topic": "trip.notice", "payload": {"text": "x"}})
    assert post.calls == []


def test_the_old_behaviour_is_still_available_when_asked():
    """`allowed_tenants=None` 이면 전부 보낸다 — 옛 동작을 남겨 둔다(명시적으로 골라야 한다)."""
    post = _Post()
    send = DiscordWebhook("https://webhook.invalid/none", transport=post, allowed_tenants=None)
    send(_message("scenario-live-x"))
    assert len(post.calls) == 1
