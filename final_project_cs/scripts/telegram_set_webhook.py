# -*- coding: utf-8 -*-
"""텔레그램 웹훅 등록 · 확인 · 해제 — 배포 뒤에 운영자가 한 번 돌린다. `[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」]`

    python -m scripts.telegram_set_webhook            # 등록: 텔레그램이 업데이트(고객이 봇에 쓴 글 · 차단)를 우리 서버로 보내게 한다
    python -m scripts.telegram_set_webhook --info     # 지금 상태(처리 못 한 업데이트 수 · 마지막 오류)
    python -m scripts.telegram_set_webhook --delete   # 등록 해제

필요한 설정(서버 환경 파일, git 밖): `ACOP_TELEGRAM_BOT_TOKEN` · `ACOP_TELEGRAM_WEBHOOK_SECRET` · `ACOP_PUBLIC_BASE_URL`(https 로 시작하는 공개 주소).
등록 주소는 `{공개 주소}/v1/telegram/webhook` 이고, 텔레그램이 요청마다 비밀값을 헤더 `X-Telegram-Bot-Api-Secret-Token` 에 실어 보낸다(서버가 같을 때만 처리한다).

★**출력에는 토큰 · 주소 · 비밀값을 찍지 않는다.** 결과(ok 여부)와 텔레그램이 준 설명 한 줄만 보인다 — 텔레그램의 설명 문구에 그것들이 섞여 있어도 가려서 찍는다.
★https 가 아니거나 텔레그램이 허용하지 않는 포트(443 · 80 · 88 · 8443 만 가능)면 **호출하기 전에** 멈춘다.
★시험 봇과 운영 봇은 환경 파일이 따로이므로 이 스크립트도 **그 환경 파일의 봇 하나**만 건드린다.
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Any
from urllib.parse import urlsplit

import httpx

API = "https://api.telegram.org"
WEBHOOK_PATH = "/v1/telegram/webhook"
#: 우리가 받을 업데이트 종류 — 글(`message`)과 차단 · 해제(`my_chat_member`)뿐이다
ALLOWED_UPDATES = ["message", "my_chat_member"]
#: 텔레그램이 웹훅 주소에 허용하는 포트(공식 문서)
ALLOWED_PORTS = (443, 80, 88, 8443)
#: 텔레그램 `secret_token` 규칙 — 1~256자, `A-Z a-z 0-9 _ -`
_SECRET = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
REDACTED = "<가림>"


class SetupError(Exception):
    """설정이 모자라거나 틀렸다 · 텔레그램에 닿지 못했다. ★메시지에 토큰 · 주소 · 비밀값을 싣지 않는다."""


def webhook_url(public_base_url: str) -> str:
    """`{공개 주소}/v1/telegram/webhook` — https 가 아니거나 포트가 허용 밖이면 `SetupError`(받은 값을 문구에 싣지 않는다)."""
    text = (public_base_url or "").strip().rstrip("/")
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise SetupError("ACOP_PUBLIC_BASE_URL 모양이 틀렸어요") from None
    if parts.scheme != "https" or not parts.hostname:
        raise SetupError("ACOP_PUBLIC_BASE_URL 이 https 로 시작하는 공개 주소여야 해요 — 텔레그램은 https 웹훅만 받아요")
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        raise SetupError("ACOP_PUBLIC_BASE_URL 에는 계정 · 쿼리 · 조각을 넣지 말아 주세요")
    if port is not None and port not in ALLOWED_PORTS:
        raise SetupError("텔레그램 웹훅 포트는 443 · 80 · 88 · 8443 만 가능해요 — ACOP_PUBLIC_BASE_URL 의 포트를 확인해 주세요")
    return text + WEBHOOK_PATH


def _scrub(text: Any, *secrets: str) -> str:
    """텔레그램이 준 문구에 토큰 · 주소 · 비밀값이 섞여 있으면 가린다. 길이도 줄인다."""
    out = str(text or "")
    for secret in secrets:
        if secret:
            out = out.replace(secret, REDACTED)
    return re.sub(r"https?://\S+", REDACTED, out)[:300]


def _call(token: str, method: str, payload: dict[str, Any], *, transport: httpx.BaseTransport | None = None, timeout: float = 15.0) -> dict[str, Any]:
    """텔레그램 봇 API 한 번 → 본문(JSON 객체). 닿지 못하면 `SetupError`(종류만 알린다 — 오류 문구에 주소 · 토큰이 들어 있어서)."""
    try:
        with httpx.Client(transport=transport, timeout=httpx.Timeout(timeout), follow_redirects=False) as client:
            response = client.post(f"{API}/bot{token}/{method}", json=payload)
    except httpx.TimeoutException:
        raise SetupError("텔레그램이 시간 안에 답하지 않았어요") from None
    except httpx.TransportError as exc:
        raise SetupError(f"텔레그램에 연결하지 못했어요({type(exc).__name__})") from None
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise SetupError(f"텔레그램이 알 수 없는 답을 보냈어요(HTTP {response.status_code})")
    return body


def _need(settings: Any, *names: str) -> list[str]:
    values = [str(getattr(settings, name, "") or "").strip() for name in names]
    missing = [f"ACOP_{name.upper()}" for name, value in zip(names, values) if not value]
    if missing:
        raise SetupError("서버 환경 파일에 " + " · ".join(missing) + " 이(가) 비어 있어요")
    return values


def set_webhook(settings: Any, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    """`setWebhook` — 돌려주는 것은 `{"ok": bool, "description": str}` 뿐(주소 · 비밀값 없음)."""
    token, secret = _need(settings, "telegram_bot_token", "telegram_webhook_secret")
    if not _SECRET.match(secret):
        raise SetupError("ACOP_TELEGRAM_WEBHOOK_SECRET 은 영문 · 숫자 · _ · - 로 1~256자여야 해요")
    url = webhook_url(getattr(settings, "public_base_url", ""))
    body = _call(token, "setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ALLOWED_UPDATES}, transport=transport)
    return {"ok": body.get("ok") is True, "description": _scrub(body.get("description"), token, secret, url)}


def delete_webhook(settings: Any, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    (token,) = _need(settings, "telegram_bot_token")
    body = _call(token, "deleteWebhook", {}, transport=transport)
    return {"ok": body.get("ok") is True, "description": _scrub(body.get("description"), token)}


def webhook_info(settings: Any, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    """`getWebhookInfo` — **처리 못 한 업데이트 수 · 마지막 오류 문구 · 등록돼 있는지**만 돌려준다(주소는 버린다)."""
    (token,) = _need(settings, "telegram_bot_token")
    body = _call(token, "getWebhookInfo", {}, transport=transport)
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    secret = str(getattr(settings, "telegram_webhook_secret", "") or "")
    return {"ok": body.get("ok") is True, "url_set": bool(result.get("url")), "pending_update_count": result.get("pending_update_count"),
            "last_error_message": _scrub(result.get("last_error_message"), token, secret, str(result.get("url") or "")) or None,
            "description": _scrub(body.get("description"), token, secret)}


def main(argv: list[str] | None = None, *, settings: Any = None, transport: httpx.BaseTransport | None = None, out=None) -> int:
    """종료 코드: 0 = 텔레그램이 ok · 1 = 텔레그램이 거절 · 2 = 설정이 모자라거나 틀림 · 연결 실패."""
    out = out or sys.stdout
    parser = argparse.ArgumentParser(description="텔레그램 웹훅 등록(기본) · --info 상태 · --delete 해제")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--info", action="store_true", help="처리 못 한 업데이트 수와 마지막 오류만 본다")
    group.add_argument("--delete", action="store_true", help="웹훅 등록을 푼다")
    args = parser.parse_args(argv)
    if settings is None:
        from app.core.settings import get_settings

        settings = get_settings()
    try:
        if args.info:
            info = webhook_info(settings, transport=transport)
            print(f"ok={str(info['ok']).lower()} 등록됨={'예' if info['url_set'] else '아니오'} 처리 못 한 업데이트={info['pending_update_count']} "
                  f"마지막 오류={info['last_error_message'] or '없음'}", file=out)
            return 0 if info["ok"] else 1
        result = delete_webhook(settings, transport=transport) if args.delete else set_webhook(settings, transport=transport)
    except SetupError as exc:
        print(f"중단: {exc}", file=out)
        return 2
    print(f"ok={str(result['ok']).lower()} {result['description']}".rstrip(), file=out)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
