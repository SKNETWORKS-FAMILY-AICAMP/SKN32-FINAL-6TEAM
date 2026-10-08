"""대상의 **실행 중 설정**(운영 설정값)을 읽고 바꾸는 어댑터 — 화면 없이 함수·명령줄만. `[2026-09-29 사용자 지시]`

사용자 지시: 「개발자 앱에서 지도를 구글 ↔ 무료 지도(OSM)로 바꿀 수 있게 옵션으로 만들어 둔다. 화면은 없고 기능만.」

★§0.3 예외와 같은 성격이다(`live.trigger_reload` 처럼). 대상이 인증해서(scope `limits:read` / `limits:write`)
  **자기 프로세스 안에서** 검증·저장·감사 기록을 하는 API(`GET·PATCH /admin/limits`)를 **부를 뿐**이다.
  여기서 대상의 파일·DB·파이썬을 건드리지 않는다. 값이 맞는지 판정하는 것도 대상이다 — 여기서는
  오타만 먼저 막는다(모르는 지도 이름을 그대로 보내 대상의 422 를 기다리지 않는다).

★두 토큰을 나눈다 — 보기(`CONSOLE_LIMITS_READ_TOKEN`)와 바꾸기(`CONSOLE_LIMITS_WRITE_TOKEN`).
  대상이 scope 를 나눠 둔 이유(보는 사람이 문을 열지 못하게)를 여기서 하나로 합치지 않는다.
★바꾸기는 `expected_revision` 을 싣는다 — 그 사이 다른 운영자가 바꿨으면 대상이 409 로 거절하고,
  그 사실을 그대로 전한다(뒤엣것이 조용히 덮지 않는다).

명령줄:
    python -m console.runtime_settings map-provider                 # 지금 값 보기
    python -m console.runtime_settings map-provider osm --reason "개발 중 무료 지도"
    python -m console.runtime_settings dev-mode on --reason "근거 확인"          # 고객 채팅 답에 근거 표시
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

#: 대상이 지도 종류를 담는 설정 이름. ★대상과 맞춘 이름이다 — 대상이 바꾸면 여기서 먼저 깨진다(`unknown_limit`).
MAP_PROVIDER = "web.map_provider"
MAP_PROVIDERS = ("osm", "google")
#: `[2026-09-29 사용자 지시]` 개발 모드 — 켜면 고객 채팅 답에 근거(규정 절 id)가 함께 실린다. 끄면(기본) 고객은 못 본다.
DEV_MODE = "web.dev_mode"
DEV_MODES = ("off", "on")


@dataclass(frozen=True)
class SettingRead:
    #: 읽음 · 연결 안 함 · 대상이 응답하지 않음 · 인증 실패 · 그 경로가 없음 · 그 설정이 없음 · 바꿈 · 바꾸지 못함 · 다른 운영자가 먼저 바꿈
    status: str
    value: Any = None
    revision: int | None = None
    detail: str = ""


def limits_url() -> str | None:
    """`CONSOLE_LIMITS_URL` — 대상의 `/admin/limits` 주소(끝까지 적는다)."""
    return (os.environ.get("CONSOLE_LIMITS_URL") or "").strip() or None


def _call(url: str, token: str, method: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, method=method, data=data, headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            payload = {}
        return exc.code, payload if isinstance(payload, dict) else {}


def _error_of(payload: dict[str, Any]) -> dict[str, Any]:
    error = payload.get("detail", payload).get("error") if isinstance(payload.get("detail", payload), dict) else None
    return error if isinstance(error, dict) else {}


def read_setting(name: str, *, url: str | None = None, token: str | None = None) -> SettingRead:
    """설정 하나의 지금 값과 판(revision). ★못 읽으면 못 읽었다고 — 기본값으로 채우지 않는다."""
    url = url if url is not None else limits_url()
    token = token if token is not None else os.environ.get("CONSOLE_LIMITS_READ_TOKEN")
    if not url:
        return SettingRead("연결 안 함", detail="CONSOLE_LIMITS_URL 이 없음")
    if not token:
        return SettingRead("연결 안 함", detail="CONSOLE_LIMITS_READ_TOKEN 이 없음 (대상 scope `limits:read`)")
    try:
        status, payload = _call(url, token, "GET")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return SettingRead("대상이 응답하지 않음", detail=str(exc))
    if status in (401, 403):
        return SettingRead("인증 실패", detail="CONSOLE_LIMITS_READ_TOKEN 의 scope 가 `limits:read` 가 아님")
    if status == 404:
        return SettingRead("그 경로가 없음", detail=url)
    if status != 200:
        return SettingRead("대상이 응답하지 않음", detail=f"HTTP {status}")
    revision = payload.get("revision")
    row = next((item for item in payload.get("limits") or [] if item.get("name") == name), None)
    if row is None:
        known = sorted(str(item.get("name")) for item in payload.get("limits") or [])
        return SettingRead("그 설정이 없음", revision=revision, detail=f"{name} 이 대상 설정 목록에 없음 — 대상이 아는 이름: {known}")
    return SettingRead("읽음", value=row.get("value"), revision=revision,
                       detail=f"source={row.get('source')} updated_by={row.get('updated_by')} updated_at={row.get('updated_at')}")


def change_setting(name: str, value: Any, *, actor: str, reason: str, expected_revision: int | None = None,
                   url: str | None = None, read_token: str | None = None, write_token: str | None = None) -> SettingRead:
    """설정 하나를 바꾼다(`PATCH /admin/limits`). `expected_revision` 을 안 주면 먼저 읽어 지금 판을 싣는다.

    `value=None` 은 운영자 값을 지우고 대상의 기본값으로 돌린다(대상 계약).
    """
    url = url if url is not None else limits_url()
    write_token = write_token if write_token is not None else os.environ.get("CONSOLE_LIMITS_WRITE_TOKEN")
    if not url:
        return SettingRead("연결 안 함", detail="CONSOLE_LIMITS_URL 이 없음")
    if not write_token:
        return SettingRead("연결 안 함", detail="CONSOLE_LIMITS_WRITE_TOKEN 이 없음 (대상 scope `limits:write`)")
    if not actor.strip():
        return SettingRead("바꾸지 못함", detail="누가 바꾸는지(actor)가 없음 — 대상 감사 기록에 남는다")
    if not reason.strip():
        return SettingRead("바꾸지 못함", detail="바꾸는 이유(reason)가 없음 — 대상 감사 기록에 남는다")
    if expected_revision is None:
        current = read_setting(name, url=url, token=read_token)
        if current.revision is None:
            return SettingRead(current.status, detail=f"지금 판을 읽지 못해 바꾸지 않았음 — {current.detail}")
        expected_revision = int(current.revision)
    body = {"expected_revision": expected_revision, "actor": actor.strip(), "reason": reason.strip(), "changes": {name: value}}
    try:
        status, payload = _call(url, write_token, "PATCH", body)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return SettingRead("대상이 응답하지 않음", detail=str(exc))
    if status in (401, 403):
        return SettingRead("인증 실패", detail="CONSOLE_LIMITS_WRITE_TOKEN 의 scope 가 `limits:write` 가 아님")
    if status == 404:
        return SettingRead("그 경로가 없음", detail=url)
    error = _error_of(payload)
    if status == 409:
        return SettingRead("다른 운영자가 먼저 바꿈", revision=error.get("current_revision"),
                           detail=error.get("message") or "stale_revision — 다시 읽고 바꾼다")
    if status != 200:
        return SettingRead("바꾸지 못함", detail=f"HTTP {status} {error.get('code') or ''} {error.get('message') or ''}".strip())
    row = next((item for item in payload.get("limits") or [] if item.get("name") == name), None)
    return SettingRead("바꿈", value=None if row is None else row.get("value"), revision=payload.get("revision"),
                       detail=f"다른 대상 프로세스에는 {payload.get('applies_within_seconds')}초 안에 반영")


def read_map_provider(**kwargs: Any) -> SettingRead:
    return read_setting(MAP_PROVIDER, **kwargs)


def set_map_provider(provider: str | None, *, actor: str, reason: str, **kwargs: Any) -> SettingRead:
    """지도 종류를 바꾼다: `osm`(무료 지도) · `google` · `None`(대상 기본값으로).

    ★모르는 이름은 보내지 않는다 — 오타(`gogle`)를 대상에 보내 거절을 기다리는 것보다 여기서 먼저 막는다.
      그래도 판정은 대상이 한다(대상이 선택지를 바꾸면 대상의 422 를 그대로 전한다).
    """
    if provider is not None and provider not in MAP_PROVIDERS:
        return SettingRead("바꾸지 못함", detail=f"지도 종류는 {MAP_PROVIDERS} 중 하나(또는 None=기본값) — 받은 값 {provider!r}")
    return change_setting(MAP_PROVIDER, provider, actor=actor, reason=reason, **kwargs)


def read_dev_mode(**kwargs: Any) -> SettingRead:
    return read_setting(DEV_MODE, **kwargs)


def set_dev_mode(mode: str | None, *, actor: str, reason: str, **kwargs: Any) -> SettingRead:
    """개발 모드를 켜고 끈다: `on` · `off` · `None`(대상 기본값 = off). 모르는 값은 보내지 않는다."""
    if mode is not None and mode not in DEV_MODES:
        return SettingRead("바꾸지 못함", detail=f"개발 모드는 {DEV_MODES} 중 하나(또는 None=기본값) — 받은 값 {mode!r}")
    return change_setting(DEV_MODE, mode, actor=actor, reason=reason, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m console.runtime_settings", description="대상의 실행 중 설정 보기·바꾸기")
    sub = parser.add_subparsers(dest="command", required=True)
    maps = sub.add_parser("map-provider", help="웹 지도 종류(osm · google) 보기·바꾸기")
    maps.add_argument("value", nargs="?", choices=[*MAP_PROVIDERS, "default"], help="없으면 보기만. default = 대상 기본값으로")
    maps.add_argument("--reason", default="", help="바꾸는 이유(감사 기록)")
    maps.add_argument("--actor", default=os.environ.get("CONSOLE_ACTOR") or os.environ.get("USERNAME") or "", help="누가 바꾸나")
    dev = sub.add_parser("dev-mode", help="개발 모드(고객 채팅 답에 근거 표시) 보기·켜기·끄기")
    dev.add_argument("value", nargs="?", choices=[*DEV_MODES, "default"], help="없으면 보기만. default = 대상 기본값(off)으로")
    dev.add_argument("--reason", default="", help="바꾸는 이유(감사 기록)")
    dev.add_argument("--actor", default=os.environ.get("CONSOLE_ACTOR") or os.environ.get("USERNAME") or "", help="누가 바꾸나")
    args = parser.parse_args(argv)
    read, change = (read_map_provider, set_map_provider) if args.command == "map-provider" else (read_dev_mode, set_dev_mode)
    if args.value is None:
        result = read()
    else:
        result = change(None if args.value == "default" else args.value, actor=args.actor, reason=args.reason)
    print(json.dumps({"status": result.status, "value": result.value, "revision": result.revision, "detail": result.detail},
                     ensure_ascii=False))
    return 0 if result.status in ("읽음", "바꿈") else 1


if __name__ == "__main__":
    sys.exit(main())
