# -*- coding: utf-8 -*-
"""Cloudflare Turnstile 서버 확인(`siteverify`). `[2026-09-28]` 사용자 지시 · 계획 `records/plans/2026-09-28_2130_웹_남용방어_실행계획.md`

★화면 위젯만으로는 방어가 아니다 — 서버가 토큰을 Cloudflare 에 물어 확인해야 효과가 있다.
★우리 사이트가 Cloudflare 를 거치지 않아도 된다 — 「Turnstile can be embedded into any website without sending traffic
  through Cloudflare」 `[확인 2026-09-28]` developers.cloudflare.com/turnstile.
★이 층은 **묻고 답을 그대로 돌려줄 뿐**이다. 통과 여부 정책(비밀키가 없을 때 · 닿지 못할 때)은 `web_guard.human_check` 가 정한다.

`[확인 2026-09-28]` 문서(server-side-validation): POST `secret` · `response` · `remoteip`(선택) — form 또는 JSON,
응답 JSON `success` · `error-codes` · `hostname` · `action` · `challenge_ts` · `cdata`. 토큰 5분 유효 · 한 번만 · 최대 2,048자.
"""
from __future__ import annotations

from typing import Any

import httpx


class TurnstileUnavailable(Exception):
    """Cloudflare 에 닿지 못했거나 알아볼 수 없는 답 — **통과로 보지 않는다**(부르는 쪽이 503)."""


def siteverify(*, url: str, secret: str, token: str, remote_ip: str | None, timeout: float) -> dict[str, Any]:
    """Cloudflare 의 답(JSON)을 그대로 돌려준다. 닿지 못하면 `TurnstileUnavailable`."""
    form = {"secret": secret, "response": token}
    if remote_ip:
        form["remoteip"] = remote_ip
    try:
        response = httpx.post(url, data=form, timeout=timeout)
    except httpx.HTTPError as exc:
        raise TurnstileUnavailable(f"{type(exc).__name__}: {exc}") from exc
    if response.status_code != 200:
        raise TurnstileUnavailable(f"HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise TurnstileUnavailable("JSON 이 아닌 답") from exc
    if not isinstance(body, dict) or not isinstance(body.get("success"), bool):
        raise TurnstileUnavailable("`success` 가 없는 답")
    return body


__all__ = ["TurnstileUnavailable", "siteverify"]
