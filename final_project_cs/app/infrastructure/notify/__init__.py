# -*- coding: utf-8 -*-
"""바깥으로 나가는 통지 전송. ★전송만 한다 — 무엇을 보낼지는 도메인이 정한다."""
from .discord import DiscordWebhook, NoticeNotConfigured

__all__ = ["DiscordWebhook", "NoticeNotConfigured"]
