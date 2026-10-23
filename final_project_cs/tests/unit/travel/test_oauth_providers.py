# -*- coding: utf-8 -*-
"""소셜 로그인 업체와 말하는 층 — 로그인 주소 · PKCE · ID 토큰 확인. `[2026-10-03 ui 세션 요청서 「소셜 로그인」 — 1단계는 구글 하나]`

DB · 네트워크 없이 도는 단위 시험 — 같은 일을 서버 전체(시작 → 콜백 → 교환)로 보는 것은 `tests/e2e/test_web_social_login.py`.

★지키려는 것: ①설정이 **둘 다** 있어야 업체가 켜진다(클라이언트 ID · 비밀값) ②로그인 주소에 `state` · PKCE(`S256`) · `nonce` · 정확한 콜백 주소가 실린다 · 권한 범위는 `openid` 하나(이메일 · 이름을 요청하지 않는다)
③ID 토큰은 **서명 · 발급자 · 대상 · 만료 · nonce** 를 모두 본다 — 하나라도 틀리면 `OAuthError`(서명 없는 토큰 · 다른 알고리즘 · 남의 앱용 토큰을 받지 않는다) ④업체가 오류를 주면 `OAuthError`.

재현:

    python -m pytest tests/unit/travel/test_oauth_providers.py -v
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.infrastructure import oauth_providers as oauth

CLIENT_ID = "client-id-for-test"
REDIRECT = "https://api.example.test/v1/web/auth/google/callback"


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, other


def _provider() -> oauth.Provider:
    return oauth.configured(SimpleNamespace(google_client_id=CLIENT_ID, google_client_secret="secret-for-test"))["google"]


def _token(private, **claims) -> str:
    now = int(time.time())
    base = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1234567890", "iat": now, "exp": now + 300, "nonce": "N1"}
    return jwt.encode({**base, **claims}, private, algorithm="RS256")


class _Response:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body


def _exchange(keys, token=None, *, status=200, nonce="N1", body=None, signer=None):
    private, _ = keys
    calls = []

    def post(url, data, timeout):
        calls.append((url, data))
        return _Response(status, body if body is not None else {"id_token": token if token is not None else _token(private)})

    sub = oauth.exchange_code(_provider(), code="abc", verifier="V" * 50, redirect_uri=REDIRECT, nonce=nonce, post=post,
                              signing_key=signer or (lambda provider, id_token: private.public_key()))
    return sub, calls


def test_a_provider_is_on_only_when_both_the_client_id_and_the_secret_are_set():
    assert oauth.configured(SimpleNamespace(google_client_id="", google_client_secret="")) == {}
    assert oauth.configured(SimpleNamespace(google_client_id=CLIENT_ID, google_client_secret="")) == {}        # 반쯤 켜진 채 뜨지 않는다
    assert oauth.configured(SimpleNamespace(google_client_id="", google_client_secret="s")) == {}
    assert set(oauth.configured(SimpleNamespace(google_client_id=CLIENT_ID, google_client_secret="s"))) == {"google"}
    assert oauth.configured(SimpleNamespace()) == {}                                                          # 설정 칸이 아예 없어도 안 깨진다


def test_pkce_challenge_matches_the_rfc_7636_example_and_verifiers_are_long_enough():
    assert oauth.pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    verifier = oauth.new_verifier()
    assert 43 <= len(verifier) <= 128 and verifier != oauth.new_verifier()


def test_the_login_address_carries_state_pkce_nonce_the_exact_callback_and_only_the_openid_scope():
    url = oauth.authorize_url(_provider(), redirect_uri=REDIRECT, state="S1", nonce="N1", verifier="V" * 50)
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    assert query["client_id"] == CLIENT_ID and query["redirect_uri"] == REDIRECT and query["response_type"] == "code"
    assert query["scope"] == "openid"                                             # ★이메일 · 이름 · 사진을 요청하지 않는다
    assert query["state"] == "S1" and query["nonce"] == "N1"
    assert query["code_challenge_method"] == "S256" and query["code_challenge"] == oauth.pkce_challenge("V" * 50)
    assert query["prompt"] == "select_account"                                    # 다른 기기의 다른 계정으로 조용히 들어가지 않게
    assert "secret" not in url                                                    # 비밀값은 주소에 싣지 않는다


def test_a_good_id_token_gives_the_subject_and_the_token_request_has_the_pkce_verifier(keys):
    sub, calls = _exchange(keys)
    assert sub == "1234567890"
    url, data = calls[0]
    assert url == "https://oauth2.googleapis.com/token"
    assert data["grant_type"] == "authorization_code" and data["code"] == "abc" and data["redirect_uri"] == REDIRECT
    assert data["code_verifier"] == "V" * 50 and data["client_id"] == CLIENT_ID and data["client_secret"] == "secret-for-test"


@pytest.mark.parametrize("claims", [
    {"aud": "someone-elses-client"},                                              # 남의 앱용 토큰
    {"iss": "https://evil.example"},                                              # 다른 발급자
    {"exp": int(time.time()) - 600, "iat": int(time.time()) - 900},               # 만료
    {"nonce": "OTHER"},                                                           # 다른 시작에서 온 토큰(재생)
    {"sub": ""},                                                                  # 비어 있는 고유 번호
], ids=["audience", "issuer", "expired", "nonce", "empty-sub"])
def test_a_token_that_is_wrong_in_any_check_is_refused(keys, claims):
    private, _ = keys
    with pytest.raises(oauth.OAuthError):
        _exchange(keys, _token(private, **claims))


def test_a_token_signed_by_another_key_or_with_another_algorithm_is_refused(keys):
    private, other = keys
    with pytest.raises(oauth.OAuthError):
        _exchange(keys, _token(other))                                            # 업체 공개키로 확인이 안 되는 서명
    # 공개키를 HMAC 비밀로 쓴 HS256 위조 — 라이브러리가 만들어 주지 않으니 손으로 짠다(알고리즘 혼동 공격)
    public_pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    body = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1", "iat": int(time.time()),
            "exp": int(time.time()) + 300, "nonce": "N1"}
    signing_input = f"{b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())}.{b64(json.dumps(body).encode())}"
    forged = signing_input + "." + b64(hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest())
    with pytest.raises(oauth.OAuthError):
        _exchange(keys, forged)
    unsigned = jwt.encode({"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1", "iat": int(time.time()),
                           "exp": int(time.time()) + 300, "nonce": "N1"}, None, algorithm="none")
    with pytest.raises(oauth.OAuthError):
        _exchange(keys, unsigned)


@pytest.mark.parametrize("kwargs", [{"status": 400}, {"status": 200, "body": {}}, {"status": 200, "body": {"id_token": ""}},
                                    {"status": 200, "body": {"id_token": "not-a-jwt"}}], ids=["http-400", "no-token", "empty-token", "garbage"])
def test_a_provider_error_or_a_missing_token_is_one_failure(keys, kwargs):
    with pytest.raises(oauth.OAuthError):
        _exchange(keys, **kwargs)


def test_a_network_failure_is_one_failure_and_the_secret_is_not_in_the_error(keys):
    def post(url, data, timeout):
        raise TimeoutError("connection timed out")

    with pytest.raises(oauth.OAuthError) as raised:
        oauth.exchange_code(_provider(), code="abc", verifier="V" * 50, redirect_uri=REDIRECT, nonce="N1", post=post,
                            signing_key=lambda provider, token: None)
    assert "secret-for-test" not in str(raised.value)
