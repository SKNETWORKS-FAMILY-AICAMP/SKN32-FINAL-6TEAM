"""대상의 인증된 Composer 쓰기 채널 어댑터.

대상 프로세스가 제공하는 `/auth/token`에서 동작별 단명 JWT를 발급받은 뒤
`/composer/current`·`/composer/validate`·`/composer/apply`를 호출한다.
실제 대상 모델은 import하지 않고 raw dict만 주고받는다.

★계약 v2 전환 완료(2026-08-18): issuer secret은 토큰 발급에만 사용하고,
실제 Composer 요청에는 동작별 scope가 담긴 access token을 사용한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


TOKEN_SUBJECT = "final_project_ui.console"


@dataclass(frozen=True)
class ComposerResult:
    """Composer 호출 결과를 화면에서 구분하기 위한 값."""

    status: str
    value: dict[str, Any] | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("읽음", "검증됨", "적용됨", "토글됨")


def _payload_from_http_error(exc: HTTPError) -> dict[str, Any]:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_detail(payload: dict[str, Any], fallback: str) -> str:
    error = payload.get("error", {})
    return error.get("message", fallback) if isinstance(error, dict) else fallback


def _issue_access_token(url: str, issuer_secret: str | None, scope: str) -> str | ComposerResult:
    if not issuer_secret:
        return ComposerResult("토큰 발급 실패", detail="composer_issuer_secret 이 프로필에 없음")
    parsed = urlsplit(url)
    auth_url = urlunsplit((parsed.scheme, parsed.netloc, "/auth/token", "", ""))
    request = Request(
        auth_url,
        method="POST",
        headers={
            "Authorization": f"Bearer {issuer_secret}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"sub": TOKEN_SUBJECT, "scope": [scope]}).encode("utf-8"),
    )
    try:
        with urlopen(request, timeout=5) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = _payload_from_http_error(exc)
        return ComposerResult("토큰 발급 실패", detail=f"HTTP {exc.code}: {_error_detail(payload, 'token issuance failed')}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return ComposerResult("토큰 발급 실패", detail=str(exc))
    if not isinstance(raw, dict) or not isinstance(raw.get("access_token"), str) or not raw["access_token"]:
        return ComposerResult("토큰 발급 실패", detail="access_token 이 응답에 없음")
    return raw["access_token"]


def _request(url: str, *, method: str, access_token: str, body: dict[str, Any] | None,
             success_status: str) -> ComposerResult:
    headers = {"Authorization": f"Bearer {access_token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    try:
        request = Request(url, method=method, headers=headers, data=data)
        with urlopen(request, timeout=5) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = _payload_from_http_error(exc)
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if exc.code in (401, 403):
            return ComposerResult("인증 실패", detail=f"HTTP {exc.code}: {_error_detail(payload, 'authentication failed')}")
        if exc.code == 409:
            return ComposerResult("충돌", value=error, detail=_error_detail(payload, "revision_conflict"))
        if exc.code == 422:
            return ComposerResult("검증 실패", value=error, detail=_error_detail(payload, "invalid_declaration"))
        return ComposerResult("대상이 응답하지 않음", detail=f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return ComposerResult("대상이 응답하지 않음", detail=str(exc))
    if not isinstance(raw, dict):
        return ComposerResult("대상이 응답하지 않음", detail="응답이 객체가 아님")
    return ComposerResult(success_status, value=raw)


def _call(url: str | None, issuer_secret: str | None, *, path: str, method: str,
          scope: str, body: dict[str, Any] | None, success_status: str) -> ComposerResult:
    if not url:
        return ComposerResult("연결 안 함", detail="composer_url 이 프로필에 없음")
    token = _issue_access_token(url, issuer_secret, scope)
    if isinstance(token, ComposerResult):
        return token
    return _request(f"{url.rstrip('/')}{path}", method=method, access_token=token, body=body,
                    success_status=success_status)


def read_current(url: str | None, issuer_secret: str | None = None) -> ComposerResult:
    """현재 revision과 config를 읽는다."""
    return _call(url, issuer_secret, path="/current", method="GET", scope="composer:read",
                 body=None, success_status="읽음")


def validate_candidate(url: str | None, issuer_secret: str | None,
                       config: dict[str, Any]) -> ComposerResult:
    """후보 config를 검증한다."""
    result = _call(url, issuer_secret, path="/validate", method="POST", scope="composer:validate",
                   body={"config": config}, success_status="검증됨")
    if result.status == "검증됨" and result.value is not None and result.value.get("valid") is False:
        return ComposerResult("검증 실패", value=result.value,
                              errors=tuple(result.value.get("errors", ())))
    return result


def apply_candidate(url: str | None, issuer_secret: str | None, config: dict[str, Any],
                    *, base_revision: str) -> ComposerResult:
    """검증된 후보를 base revision이 일치할 때 적용한다."""
    return _call(url, issuer_secret, path="/apply", method="POST", scope="composer:write",
                 body={"config": config, "base_revision": base_revision}, success_status="적용됨")


def toggle_target(url: str | None, issuer_secret: str | None, *, target_type: str, target_id: str,
                  active: bool, base_revision: str, reason: str) -> ComposerResult:
    """등록된 모듈·Team·Port 하나의 활성 상태만 바꾼다 (v3 제안, `POST /composer/toggle`).

    ★2026-08-24 시점 잠정: 계약 형태는
    `program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md` §2.2 제안을 따른다.
    이 설계는 아직 대상(final_project_cs)에서 확정·구현 중이라(다른 세션 작업),
    필드명·경로가 최종 계약과 다를 수 있다 — 화면에는 아직 연결하지 않는다.
    v2(`read_current`·`validate_candidate`·`apply_candidate`)는 이 함수와 무관하게
    그대로 동작한다(사용자 결정: 안 C — 병행, v2 유지 + toggle 추가).
    """
    body = {
        "target_type": target_type,
        "target_id": target_id,
        "active": active,
        "base_revision": base_revision,
        "reason": reason,
    }
    return _call(url, issuer_secret, path="/toggle", method="POST", scope="composer:write",
                 body=body, success_status="토글됨")
