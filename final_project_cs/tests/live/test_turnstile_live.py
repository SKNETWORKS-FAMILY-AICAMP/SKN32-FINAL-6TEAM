# -*- coding: utf-8 -*-
"""사람 확인(Cloudflare Turnstile) — **실제 Cloudflare** 에 공개 시험 키로 묻는다. `[2026-09-28]`

★우리 사이트가 Cloudflare 를 거치지 않아도 서버 확인이 되는지 보는 시험이다(돈·한도 없음 — 공개 시험 키).
  시험 키 `[확인 2026-09-28]` developers.cloudflare.com/turnstile/troubleshooting/testing:
  1x…AA 항상 통과 · 2x…AA 항상 실패 · 3x…AA 「이미 쓴 토큰」. 시험 사이트키가 내는 토큰은 `XXXX.DUMMY.TOKEN.XXXX`.
"""
from __future__ import annotations

import pytest

from app.core.settings import get_guardrails
from app.infrastructure.turnstile import siteverify

pytestmark = pytest.mark.live

DUMMY_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"


def _ask(secret: str) -> dict:
    guard = get_guardrails()
    return siteverify(url=str(guard.get("web_guard.turnstile.verify_url")), secret=secret, token=DUMMY_TOKEN,
                      remote_ip=None, timeout=float(guard.get("web_guard.turnstile.timeout_seconds")))


def test_the_always_pass_test_secret_passes():
    assert _ask("1x0000000000000000000000000000000AA")["success"] is True


def test_the_always_fail_test_secret_fails_with_a_reason():
    answer = _ask("2x0000000000000000000000000000000AA")
    assert answer["success"] is False and answer["error-codes"]


def test_the_spent_token_test_secret_says_so():
    answer = _ask("3x0000000000000000000000000000000AA")
    assert answer["success"] is False and "timeout-or-duplicate" in answer["error-codes"]
