"""인증 헤더 형식과 scope 가드 — 2026-08-31 추가.

두 변경이 전체 424개를 전부 통과했다(`../program/research/테스트_사각지대_실측.md`).

1. `authenticate` 에서 `Bearer ` 형식 검사 제거
2. `require_scope` 에서 scope 목록이 빈 주체를 통과시키기

권한 경로에 구멍이 나도 테스트가 울지 않는 상태였다. 여기서 센다.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.settings import get_settings
from app.presentation import security
from app.presentation.security import Principal, authenticate, require_scope

VALID_SCOPE = "case:read"


def valid_token() -> str:
    return security._development_key(VALID_SCOPE, get_settings().secret_key)


def test_valid_bearer_token_authenticates() -> None:
    principal = authenticate(f"Bearer {valid_token()}")
    assert VALID_SCOPE in principal.scopes


def test_any_seven_character_prefix_must_not_authenticate() -> None:
    """형식 검사를 빼면 앞 7글자가 무엇이든 통과한다.

    `authorization[7:]` 로 자르기 때문에 `Bearer ` 인지 보지 않으면
    `1234567<진짜키>` 도 인증된다. 오류 메시지 차이가 아니라 인증 우회다.
    """
    token = valid_token()
    for prefix in ("1234567", "Basic  ", "Bearer\t"):
        with pytest.raises(HTTPException) as caught:
            authenticate(prefix + token)
        assert caught.value.status_code == 401


def test_missing_and_malformed_headers_are_unauthenticated() -> None:
    for header in (None, "", "Bearer", "Token abc"):
        with pytest.raises(HTTPException) as caught:
            authenticate(header)
        assert caught.value.status_code == 401


def test_scope_guard_denies_a_principal_with_no_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """권한 목록이 빈 주체가 오히려 모든 문을 지나면 안 된다.

    빈 값을 '검사할 게 없다'로 읽으면 가장 권한 없는 쪽이 가장 자유로워진다.
    """
    monkeypatch.setattr(
        security, "authenticate",
        lambda _: Principal(tenant_id="t1", scopes=frozenset(), key_id="k"),
    )
    with pytest.raises(HTTPException) as caught:
        require_scope(VALID_SCOPE)(authorization="Bearer whatever")
    assert caught.value.status_code == 403


def test_scope_guard_denies_a_principal_holding_another_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security, "authenticate",
        lambda _: Principal(tenant_id="t1", scopes=frozenset({"order:read"}), key_id="k"),
    )
    with pytest.raises(HTTPException) as caught:
        require_scope(VALID_SCOPE)(authorization="Bearer whatever")
    assert caught.value.status_code == 403


def test_scope_guard_lets_the_matching_scope_through() -> None:
    principal = require_scope(VALID_SCOPE)(authorization=f"Bearer {valid_token()}")
    assert VALID_SCOPE in principal.scopes
