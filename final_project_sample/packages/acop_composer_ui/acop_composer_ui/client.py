"""Composer HTTP 클라이언트 — `final_project_ui` 가 pip 로 설치해 쓴다.

★이 패키지의 경계 (`program/research/_컴포저_UI배포구조_점검_2026-08-29.md` §7-1)

    넣는 것    토큰 발급 요청, HTTP 전송, 오류 정규화, 엔드포인트 래퍼
    안 넣는 것 ProjectConfig·TeamManifest 등 Core 모델, 선언 유효성 판정,
               capability 충돌 검사, 권한 판정

  유효성은 **대상 서버가** 판정한다. 여기서 미리 검사하면 그 순간 대상의
  검증 모델을 복제하는 것이고, `final_project_ui/CLAUDE.md` §0.2 가 금지하는
  포크가 시작된다. 이 패키지는 raw dict 를 그대로 주고받는 운반책이다.

★의존성이 없다. 표준 라이브러리만 쓴다 — UI 는 서버 프레임워크가 필요 없고,
  `acop_basement`·`app` 을 끌어오면 경계가 무너진다. `tests/architecture/
  test_composer_ui_package_boundary.py` 가 이것을 강제한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

#: `(method, url, headers, body) -> (status, body_bytes)`
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]

#: 토큰의 `sub` — 누가 부르는지 감사 로그에 남는 값이다.
DEFAULT_SUBJECT = "final_project_ui"
DEFAULT_TIMEOUT = 10.0


@dataclass
class ComposerResponse:
    """호출 결과. ★실패를 조용히 삼키지 않는다 — 무슨 일이 있었는지 남긴다."""

    ok: bool
    status: int
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    #: 어느 단계에서 끝났는가 — `config`(설정 부족) · `token`(발급 실패) ·
    #: `request`(대상 호출). ★호출자가 "인증이 틀렸다" 와 "토큰을 못 받았다" 를
    #: 구분해 안내하려면 이 정보가 필요하다. 상태코드만으로는 둘 다 401 이다.
    phase: str = "request"

    @property
    def revision_conflict(self) -> bool:
        """다른 사람이 먼저 바꿨다. 최신 상태를 다시 읽고 재시도해야 한다."""
        return self.status == 409


def _urllib_transport(method: str, url: str, headers: dict[str, str],
                      body: bytes | None) -> tuple[int, bytes]:
    request = Request(url, method=method, data=body, headers=headers)
    try:
        with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def _decode(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _error_of(payload: dict[str, Any], fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("code")
        if message:
            return str(message)
    detail = payload.get("detail")
    if isinstance(detail, str) and detail:
        return detail
    return fallback


class ComposerClient:
    """대상 제품의 Composer API 를 부르는 운반책.

    `base_url` 은 대상의 루트(예: `http://127.0.0.1:8001`)다. 경로는 이
    클래스가 붙인다 — UI 가 엔드포인트 문자열을 손으로 조립하지 않게 한다.
    """

    def __init__(self, base_url: str | None, issuer_secret: str | None = None, *,
                 subject: str = DEFAULT_SUBJECT,
                 transport: Transport | None = None) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.issuer_secret = issuer_secret
        self.subject = subject
        self._transport = transport or _urllib_transport

    # ── 내부 ────────────────────────────────────────────────────────
    def _url(self, path: str) -> str:
        parts = urlsplit(self.base_url + path)
        return urlunsplit(parts)

    def _issue_token(self, scope: str) -> str | ComposerResponse:
        if not self.issuer_secret:
            return ComposerResponse(False, 0, error="발급자 비밀키가 설정되지 않았다",
                                    phase="token")
        # ★서버의 `TokenRequest` 는 `extra="forbid"` 다 — `sub`·`scope` 외에
        #   아무것도 보내면 안 된다. `aud` 는 서버가 자기 상수로 박는다.
        body = json.dumps({"sub": self.subject, "scope": [scope]}).encode("utf-8")
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.issuer_secret}"}
        try:
            status, raw = self._transport("POST", self._url("/auth/token"), headers, body)
        except URLError as exc:
            return ComposerResponse(False, 0, error=f"대상에 연결하지 못했다: {exc}",
                                    phase="token")
        payload = _decode(raw)
        if status != 200:
            return ComposerResponse(False, status, payload,
                                    _error_of(payload, "토큰 발급에 실패했다"), phase="token")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            return ComposerResponse(False, status, payload,
                                    "토큰 응답에 access_token 이 없다", phase="token")
        return token

    def _call(self, path: str, *, method: str, scope: str,
              body: dict[str, Any] | None = None) -> ComposerResponse:
        if not self.base_url:
            return ComposerResponse(False, 0, error="대상 주소가 설정되지 않았다",
                                    phase="config")
        token = self._issue_token(scope)
        if isinstance(token, ComposerResponse):
            return token
        headers = {"Authorization": f"Bearer {token}"}
        encoded = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            status, raw = self._transport(method, self._url(path), headers, encoded)
        except URLError as exc:
            return ComposerResponse(False, 0, error=f"대상에 연결하지 못했다: {exc}")
        payload = _decode(raw)
        if status // 100 != 2:
            return ComposerResponse(False, status, payload,
                                    _error_of(payload, f"요청이 {status} 로 실패했다"))
        return ComposerResponse(True, status, payload)

    # ── 카탈로그 기반 CRUD (정본 관리 계약) ──────────────────────────
    def catalog(self) -> ComposerResponse:
        """고를 수 있는 구현 종류와 입력 스키마."""
        return self._call("/composer/catalog", method="GET", scope="composer:read")

    def change(self, *, operation: str, resource_type: str, instance_id: str,
               base_revision: str, reason: str,
               implementation_id: str | None = None,
               parameters: dict[str, Any] | None = None,
               active: bool | None = None, dry_run: bool = False,
               idempotency_key: str | None = None) -> ComposerResponse:
        """인스턴스 하나를 만들거나 고치거나 지운다.

        ★성공해도 응답의 `activation_state` 는 보통 `pending_restart` 다 —
          저장된 것이지 이미 떠 있는 런타임에 반영된 것이 아니다. 화면은 이
          상태를 감추지 말고 그대로 보여줘야 한다.
        """
        body: dict[str, Any] = {
            "operation": operation, "resource_type": resource_type,
            "instance_id": instance_id, "base_revision": base_revision,
            "reason": reason, "dry_run": dry_run,
        }
        if implementation_id is not None:
            body["implementation_id"] = implementation_id
        if parameters is not None:
            body["parameters"] = parameters
        if active is not None:
            body["active"] = active
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        return self._call("/composer/changes", method="POST", scope="composer:write", body=body)

    def toggle(self, *, target_type: str, target_id: str, active: bool,
               base_revision: str, reason: str) -> ComposerResponse:
        """등록된 module/team 의 활성 상태만 바꾼다."""
        return self._call("/composer/toggle", method="POST", scope="composer:write",
                          body={"target_type": target_type, "target_id": target_id,
                                "active": active, "base_revision": base_revision,
                                "reason": reason})

    # ── v2 (호환·bulk migration 경로) ───────────────────────────────
    def read_current(self) -> ComposerResponse:
        return self._call("/composer/current", method="GET", scope="composer:read")

    def validate(self, config: dict[str, Any]) -> ComposerResponse:
        return self._call("/composer/validate", method="POST", scope="composer:validate",
                          body={"config": config})

    def apply(self, config: dict[str, Any], *, base_revision: str,
              reason: str) -> ComposerResponse:
        return self._call("/composer/apply", method="POST", scope="composer:write",
                          body={"config": config, "base_revision": base_revision,
                                "reason": reason})


__all__ = ["ComposerClient", "ComposerResponse", "Transport", "DEFAULT_SUBJECT"]
