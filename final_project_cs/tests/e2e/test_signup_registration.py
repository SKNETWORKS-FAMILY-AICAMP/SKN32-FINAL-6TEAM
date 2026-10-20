"""격리 DB에서 기존 로그인·가입 대기·필수 동의 완료·점검 예외를 확인한다."""
from uuid import uuid4
import pytest

from app.domains.travel_ops.components.customer import consents, registration
from app.infrastructure.db.session import get_connection

from .test_trip_api import api  # noqa: F401
from .test_web_social_login import social, _flow, _exchange, _session  # noqa: F401
from .test_web_cookie_session import cookies, _guest, WEB  # noqa: F401


@pytest.fixture(autouse=True)
def cleanup_registration_test_settings(api):  # noqa: F811
    yield
    # 이 시험의 고유 tenant에 만든 점검 설정만 정리한다. 추가 전용 감사 기록은 보존한다. 운영 DB는 쓰지 않는다.
    with get_connection() as conn, conn.transaction():
        conn.execute("DELETE FROM admin_records WHERE tenant_id=%s AND kind='settings' AND id='maintenance'", (api["tenant"],))


def agree(client, *, headers=None, codes=("service_terms", "privacy"), version=None):
    current = client.get("/v1/web/consents", headers=headers or {}).json()["current_version"]
    return client.post("/v1/web/consents", headers=headers or {}, json={
        "version": version or current,
        "items": [{"code": code, "agreed": True, "text_sha256": "a" * 64} for code in codes],
    })


def test_new_identity_stays_pending_across_login_until_required_consent(social):
    client = social["client"]
    first = _exchange(client, _flow(client, "sub-new-signup")["ticket"]).json()
    assert first["outcome"] == "created" and first["registration_required"] is True
    headers = {"X-User-Key": first["user_key"]}
    assert client.get("/v1/web/trips", headers=headers).json()["error"]["code"] == "consent_required"
    again = _exchange(client, _flow(client, "sub-new-signup")["ticket"]).json()
    assert again["outcome"] == "signed_in" and again["registration_required"] is True
    assert agree(client, headers=headers, codes=("service_terms",)).json()["ok"] is False
    assert client.get("/v1/web/trips", headers=headers).status_code == 403
    assert agree(client, headers=headers, codes=("privacy",)).json()["ok"] is True
    assert client.get("/v1/web/trips", headers=headers).status_code == 200
    done = _exchange(client, _flow(client, "sub-new-signup")["ticket"]).json()
    assert done["outcome"] == "signed_in" and done["registration_required"] is False


def test_signup_is_enforced_when_ordinary_gate_is_off(social, monkeypatch):
    monkeypatch.setattr(consents, "gate_enabled", lambda: False)
    client = social["client"]
    first = _exchange(client, _flow(client, "sub-gate-off")["ticket"]).json()
    headers = {"X-User-Key": first["user_key"]}
    assert first["registration_required"] is True
    assert client.get("/v1/web/trips", headers=headers).status_code == 403
    assert agree(client, headers=headers).json()["ok"] is True
    assert client.get("/v1/web/trips", headers=headers).status_code == 200


def test_existing_member_is_not_retroactively_marked_as_signup(social):
    client = social["client"]
    headers = _session(client)
    with get_connection() as conn, conn.transaction():
        from app.domains.travel_ops.modules.web_account.web_session import resolve
        customer = resolve(conn, tenant_id=social["tenant"], raw=headers["X-User-Key"])
        from app.domains.travel_ops.modules.web_account.web_auth import subject_hash
        conn.execute("INSERT INTO web_social_links(tenant_id,provider,subject_hash,customer_id) VALUES(%s,'google',%s,%s)",
                     (social["tenant"], subject_hash("google", "old-member"), customer))
    signed = _exchange(client, _flow(client, "sub-old-member")["ticket"]).json()
    assert signed["outcome"] == "signed_in" and signed["registration_required"] is False


def test_current_guest_consent_satisfies_first_social_signup(social):
    client = social["client"]
    headers = _session(client)
    assert agree(client, headers=headers).json()["ok"] is True
    signed = _exchange(client, _flow(client, "sub-consented-guest", headers=headers)["ticket"]).json()
    assert signed["outcome"] == "created" and signed["registration_required"] is False


def test_other_customer_consent_does_not_complete_pending_signup(social):
    client = social["client"]
    first = _exchange(client, _flow(client, "sub-target-new")["ticket"]).json()
    target = {"X-User-Key": first["user_key"]}
    other = _session(client)
    assert agree(client, headers=other).json()["ok"] is True
    assert client.get("/v1/web/trips", headers=target).status_code == 403


def test_wrong_version_and_invalid_payload_never_complete_signup(social):
    client = social["client"]
    first = _exchange(client, _flow(client, "sub-bad-consent")["ticket"]).json()
    headers = {"X-User-Key": first["user_key"]}
    assert agree(client, headers=headers, version="old").status_code == 409
    assert agree(client, headers=headers, codes=("unknown",)).status_code == 422
    assert client.get("/v1/web/trips", headers=headers).status_code == 403


def test_cookie_signup_me_reports_pending_then_complete(cookies):
    from .test_web_cookie_session import _login_with_cookie
    client = cookies["client"]
    result = _login_with_cookie(cookies, client, "cookie-signup")
    assert result.status_code == 200 and result.json()["registration_required"] is True
    me = client.get("/v1/web/auth/me").json()
    assert me["registration_required"] is True
    headers = {"Origin": WEB, "X-CSRF-Token": me["csrf_token"]}
    assert agree(client, headers=headers).json()["ok"] is True
    assert client.get("/v1/web/auth/me").json()["registration_required"] is False
    assert client.get("/v1/web/trips").status_code == 200


def test_maintenance_keeps_login_and_consent_open_but_blocks_trips(cookies):
    from psycopg.types.json import Jsonb
    client = cookies["client"]
    _guest(cookies)
    with get_connection() as conn, conn.transaction():
        # 운영자 쓰기 경로 대신 이 시험의 입력 상태만 준비한다. 운영 점검 전환은 별도 실제 UI로 확인했다.
        conn.execute("INSERT INTO admin_records(tenant_id,kind,id,value) VALUES(%s,'settings','maintenance',%s)",
                     (cookies["tenant"], Jsonb({"enabled": True, "message": "격리 시험 점검", "endsAt": "2099-01-01T23:59"})))
    assert client.get("/v1/web/auth/me").status_code == 200
    assert client.get("/v1/web/consents").status_code == 200
    blocked = client.get("/v1/web/trips")
    assert blocked.status_code == 503 and blocked.json()["error"]["code"] == "maintenance"


def test_registration_marker_is_bound_to_tenant_and_customer(social):
    customer = uuid4()
    with get_connection() as conn, conn.transaction():
        assert registration.pending(conn, social["tenant"], customer) is False
        assert registration.pending(conn, "unrelated-tenant", customer) is False


@pytest.mark.parametrize("member", [False, True])
def test_notification_entry_checks_current_trip_owner_before_terms(cookies, member, monkeypatch):
    monkeypatch.setattr(consents, "gate_enabled", lambda: True)
    from .test_web_cookie_session import _login_with_cookie
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    client = cookies["client"]
    if member:
        _login_with_cookie(cookies, client, "entry-owner")
    else:
        _guest(cookies)
    with get_connection() as conn, conn.transaction():
        customer = conn.execute("SELECT customer_id FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],)).fetchone()[0]
        store = TripStore(cookies["tenant"])
        own, _ = store.create_trip(conn, customer_id=customer, title="알림 링크 시험", locale="ko", party_size=1, items=[], constraints={})
        other, _ = store.create_trip(conn, customer_id=cookies["customer"], title="다른 계정 여행", locale="ko", party_size=1, items=[], constraints={})
    ordinary = client.get("/v1/web/auth/me")
    assert "trip_access" not in ordinary.json()
    owned = client.get(f"/v1/web/auth/me?trip_id={own}")
    assert owned.status_code == 200 and owned.json()["trip_access"] is True
    assert owned.headers["cache-control"] == "no-store"
    for trip in (other, uuid4()):
        assert client.get(f"/v1/web/auth/me?trip_id={trip}").json()["trip_access"] is False
    assert client.get("/v1/web/auth/me?trip_id=invalid").status_code == 422
    # 소유권 확인은 필수 동의를 우회하는 이용 권한이 아니다.
    assert client.get(f"/v1/web/trips/{own}").status_code == 403
