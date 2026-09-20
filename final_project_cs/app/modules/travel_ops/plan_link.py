# -*- coding: utf-8 -*-
"""여행계획서 링크 — 여행별 토큰과 주소.

★`[2026-09-20]` `trip_api.py` 에 있던 둘을 여기로 옮겼다. 통지·안내를 만드는 쪽(`itinerary.py`
  ·`trip_reminders.py`)이 링크를 붙이려면 API 라우터 모듈을 import 해야 했는데, 그쪽은 FastAPI 를
  끌고 온다. `trip_api.py` 는 이 둘을 다시 내보낸다 — 부르는 쪽은 안 바뀐다.

★**상태의 정본은 링크다**(v11 §6-A). 통지를 못 봐도 링크를 열면 최신 일정을 본다. 그래서 알림에는
  늘 링크를 붙인다.
★토큰은 **저장하지 않는다** — 비밀 키로 매번 다시 계산해 맞춰 본다.
"""
from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

from app.core import settings as settings_module


def plan_token(tenant_id: str, trip_id: UUID | str) -> str:
    secret = settings_module.get_settings().secret_key.encode()
    return hmac.new(secret, f"plan:{tenant_id}:{trip_id}".encode(), hashlib.sha256).hexdigest()[:32]


def plan_url(tenant_id: str, trip_id: UUID | str) -> str:
    base = settings_module.get_settings().public_base_url.rstrip("/")
    return f"{base}/plan/{trip_id}?t={plan_token(tenant_id, trip_id)}"


__all__ = ["plan_token", "plan_url"]
