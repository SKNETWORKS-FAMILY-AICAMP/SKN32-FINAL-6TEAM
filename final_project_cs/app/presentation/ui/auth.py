# -*- coding: utf-8 -*-
"""운영 화면(`/ui/*`) 로그인. `[2026-09-23]`

★★왜. 이 화면에는 로그인이 없었다. 그런데 승인·바깥함 해소·위임 버튼은 **서버가 scope 키를
  스스로 만들어** API 를 불렀다(`_development_key("action:approve", …)`). 즉 `/ui` 에 닿기만
  하면 누구나 **인증 없이 승인 권한을 쓰는** 구조였고, 승인자는 전부 `ui-operator` 로 남아
  **누가 눌렀는지 알 수 없었다.** 같은 이유로 2026-08-18 에 Composer 화면을 지웠다(D-CS-001).

★정한 것 — `wiki/decisions/D-CS-007-ui-operator-login.md`
  - 운영자 계정은 설정(`ACOP_UI_OPERATORS`, `.env` — 커밋 안 됨)에 둔다. 비밀번호 원문은 어디에도
    두지 않는다 — PBKDF2-SHA256 해시만(`python -m scripts.ui_operator` 가 만든다).
  - 로그인하면 **서명 쿠키**(HMAC-SHA256 · 만료 · HttpOnly · SameSite=Strict)를 준다.
  - **계정이 하나도 없으면 아무도 못 들어온다** — 기본이 닫힘이다.
  - 쓰기는 그 운영자의 scope 가 있어야 한다. 승인자·처리자는 **그 운영자 id** 로 남는다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from dataclasses import dataclass

import app.core.settings as settings_module

COOKIE = "acop_ui"
_ALGO = "pbkdf2_sha256"
#: 해시를 새로 만들 때의 반복 횟수. ★해시 문자열에 같이 적히므로 나중에 올려도 옛 해시가 안 깨진다.
DEFAULT_ITERATIONS = 600_000


@dataclass(frozen=True)
class Operator:
    id: str
    scopes: frozenset[str]

    def can(self, scope: str) -> bool:
        return scope in self.scopes


# ── 비밀번호 ─────────────────────────────────────────────────────
def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS,
                  salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != _ALGO:
            return False
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _unb64(salt), int(iterations))
        return hmac.compare_digest(got, _unb64(digest))
    except (ValueError, TypeError):
        return False


# ── 계정 ─────────────────────────────────────────────────────────
class OperatorConfigError(ValueError):
    """`ACOP_UI_OPERATORS` 가 잘못됐다. ★조용히 빈 목록으로 읽지 않는다 — 그러면 「왜 못 들어가지」가 된다."""


def operators() -> dict[str, tuple[str, frozenset[str]]]:
    raw = (getattr(settings_module.get_settings(), "ui_operators", "") or "").strip()
    if not raw:
        return {}
    try:
        rows = json.loads(raw)
    except ValueError as exc:
        raise OperatorConfigError(f"ACOP_UI_OPERATORS 가 JSON 이 아니다: {exc}") from exc
    if not isinstance(rows, list):
        raise OperatorConfigError("ACOP_UI_OPERATORS 는 목록이어야 한다")
    allowed = set(settings_module.get_guardrails().get("security.scopes"))
    found: dict[str, tuple[str, frozenset[str]]] = {}
    for row in rows:
        op_id = str(row.get("id", "")).strip()
        pw_hash = str(row.get("password_hash", ""))
        scopes = frozenset(str(s) for s in row.get("scopes") or [])
        if not op_id or not pw_hash.startswith(_ALGO + "$"):
            raise OperatorConfigError(f"운영자 항목에 id·password_hash 가 없다: {row.get('id')!r}")
        unknown = scopes - allowed
        if unknown:
            raise OperatorConfigError(f"운영자 {op_id!r} 의 모르는 scope: {sorted(unknown)}")
        found[op_id] = (pw_hash, scopes)
    return found


# ── 로그인 실패 잠금 (프로세스 안) ────────────────────────────────
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def _limits() -> tuple[int, float]:
    guard = settings_module.get_guardrails()
    return (int(guard.get("security.ui_login_max_failures")),
            float(guard.get("security.ui_login_lock_minutes")) * 60)


def locked(op_id: str, now: float | None = None) -> float:
    """잠겨 있으면 남은 초, 아니면 0."""
    now = time.time() if now is None else now
    max_failures, window = _limits()
    with _lock:
        recent = [t for t in _failures.get(op_id, []) if now - t < window]
        _failures[op_id] = recent
        if len(recent) >= max_failures:
            return max(0.0, window - (now - recent[0]))
    return 0.0


def authenticate(op_id: str, password: str, now: float | None = None) -> Operator | None:
    """맞으면 운영자, 아니면 `None`.

    ★없는 id 와 틀린 비밀번호를 **같게** 다룬다 — 어느 id 가 있는지 알려 주지 않는다. 없는 id 도
      가짜 해시를 한 번 돌려 걸리는 시간을 맞춘다.
    """
    now = time.time() if now is None else now
    if locked(op_id, now):
        return None
    stored = operators().get(op_id)
    ok = verify_password(password, stored[0] if stored else _dummy_hash())
    if not (stored and ok):
        with _lock:
            _failures.setdefault(op_id, []).append(now)
        return None
    with _lock:
        _failures.pop(op_id, None)
    return Operator(op_id, stored[1])


_DUMMY: list[str] = []


def _dummy_hash() -> str:
    if not _DUMMY:
        _DUMMY.append(hash_password("never-matches", salt=b"\0" * 16))
    return _DUMMY[0]


# ── 서명 쿠키 ───────────────────────────────────────────────────
def issue(op: Operator, now: float | None = None) -> str:
    now = time.time() if now is None else now
    hours = float(settings_module.get_guardrails().get("security.ui_session_hours"))
    body = json.dumps({"sub": op.id, "scopes": sorted(op.scopes), "exp": int(now + hours * 3600)},
                      separators=(",", ":")).encode()
    payload = _b64(body)
    return payload + "." + _sign(payload)


def read(value: str | None, now: float | None = None) -> Operator | None:
    """쿠키를 읽는다. 서명이 틀리거나 만료됐거나 **그 계정이 설정에서 빠졌으면** `None`.

    ★계정을 지우거나 scope 를 줄이면 **다음 요청부터** 반영된다 — 쿠키에 적힌 scope 와 지금 설정의
      scope 의 **교집합**만 쓴다. 쿠키만 믿으면 권한을 거둬도 만료까지 버틴다.
    """
    if not value or "." not in value:
        return None
    payload, sig = value.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
    except ValueError:
        return None
    now = time.time() if now is None else now
    if int(data.get("exp", 0)) <= now:
        return None
    current = operators().get(str(data.get("sub")))
    if current is None:
        return None
    return Operator(str(data["sub"]), frozenset(data.get("scopes") or []) & current[1])


def _sign(payload: str) -> str:
    key = ("acop-ui-session:" + settings_module.get_settings().secret_key).encode()
    return _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def reset_failures() -> None:
    """시험용 — 잠금 상태를 비운다."""
    with _lock:
        _failures.clear()


__all__ = ["COOKIE", "Operator", "OperatorConfigError", "authenticate", "hash_password", "issue",
           "locked", "operators", "read", "reset_failures", "verify_password"]
