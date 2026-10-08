# -*- coding: utf-8 -*-
"""약관의 보관 기간 — 공개 읽기 · 관리 화면에서 바꾸기(감사 · 약관 버전) · 회원 자료 정리(세기만 / 지움). `[2026-10-07 사용자 결정 — uiux 전달]`

계약 `wiki/external/rest-endpoints.md` 「약관 보관 기간」 · 구현 `components/customer/retention.py` · `modules/web_account/retention_api.py` · `member_cleanup.py`.

★지키려는 것
 ①공개 읽기는 키 없이 되고 다섯 칸의 값 · 한 · 영 문장이 값에서 만들어진다(1년 · 5년 · 7일 · 6개월), 개인 정보는 없다
 ②운영자가 바꾸면 revision 이 오르고 약관 버전이 `…+ret{N}` 이 된다 — 옛 버전으로 동의하면 409 `terms_version_changed`. 이력에 누가 · 왜가 남고 지우거나 고칠 수 없다
 ③기본값과 같은 값은 「바꿈」이 아니다(revision 불변) · 모르는 칸 · 범위 밖 · 숫자 아님 · 운영자 · 이유 없음은 422 · 옛 판은 409
 ④동의 기록 보관 일수는 바꾼 값이 정리에 쓰인다
 ⑤회원 자료 정리: 기본 모드(dry_run)는 **아무것도 안 지우고 건수만** 남긴다 · off 는 안 한다 · on 만 지운다 · 아직 이용 중인 회원 · 게스트 · 동의 기록은 안 건드린다

재현:

    python -m pytest tests/e2e/test_legal_retention.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.customer import consents, retention
from app.domains.travel_ops.modules.web_account import member_cleanup, web_guard
from app.infrastructure.db.session import get_connection

from .test_guest_and_trip_delete import _count, _exists, _link, _new_guest_with_trip, cookies  # noqa: F401
from .test_trip_api import api  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_cache():
    web_guard.clear_cache()
    yield
    web_guard.clear_cache()


def _client() -> TestClient:
    from app.domains.travel_ops.modules.web_account.retention_api import build_public_retention_router
    from app.domains.travel_ops.modules.web_account.web_limits_api import build_limits_router, build_retention_ops_router
    from app.presentation.api.app import create_app

    return TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                 domain_routers=[build_public_retention_router(), build_retention_ops_router(), build_limits_router()]))


def _patch(client, api, expected, changes, *, actor="op-kim", reason="시험"):
    return client.patch("/admin/retention", headers=api["auth"]("limits:write"),
                        json={"expected_revision": expected, "actor": actor, "reason": reason, "changes": changes})


def _cell(view, key):
    return next(cell for cell in view["cells"] if cell["key"] == key)


# ── ① 공개 읽기 ───────────────────────────────────────────────────
def test_the_public_view_needs_no_key_and_builds_both_languages_from_the_values(api):
    view = _client().get("/v1/web/legal/retention")
    assert view.status_code == 200, view.text
    body = view.json()
    assert body["revision"] == 0 and body["terms_version"] == consents.current_version()      # 안 바꿨으면 기본 버전 그대로
    assert [cell["key"] for cell in body["cells"]] == ["member_idle_days", "case_follows_trip", "consent_days", "location_points_days", "location_proof_months"]
    assert _cell(body, "member_idle_days")["text_ko"] == "회원이 지우거나 탈퇴를 요청할 때까지, 마지막 이용 후 1년이 지나면 파기"
    assert _cell(body, "member_idle_days")["text_en"].endswith("destroyed once 1 year have passed since your last use")
    assert _cell(body, "case_follows_trip")["text_ko"] == "여행 · 게스트 자료가 지워질 때 함께 파기" and _cell(body, "case_follows_trip")["editable"] is False
    assert _cell(body, "consent_days")["text_ko"] == "기록한 때부터 5년"
    assert _cell(body, "location_points_days")["text_ko"] == "여행 종료 후 7일"
    assert _cell(body, "location_proof_months")["text_ko"] == "기록한 때부터 6개월" and _cell(body, "location_proof_months")["text_en"] == "6 months from the time it was recorded"
    assert all("customer" not in str(cell).lower() for cell in body["cells"])                # 개인 정보 칸이 없다


@pytest.mark.parametrize("value, unit, ko, en", [(365, "days", "1년", "1 year"), (730, "days", "2년", "2 years"), (180, "days", "6개월", "6 months"),
                                                (45, "days", "45일", "45 days"), (6, "months", "6개월", "6 months"), (24, "months", "2년", "2 years")])
def test_the_span_reads_naturally(value, unit, ko, en):
    assert retention.span_ko(value, unit) == ko and retention.span_en(value, unit) == en


# ── ② 바꾸기 · 약관 버전 · 감사 ────────────────────────────────────
def test_an_operator_change_raises_the_revision_and_the_terms_version_and_is_audited(api):
    client = _client()
    read = client.get("/admin/retention", headers=api["auth"]("limits:read")).json()
    assert read["revision"] == 0 and read["purge"]["mode"] == "dry_run"
    changed = _patch(client, api, 0, {"member_idle_days": 730}, reason="2년으로 늘림")
    assert changed.status_code == 200, changed.text
    after = changed.json()
    assert after["revision"] == 1 and after["changed"] == {"member_idle_days": [365, 730]}
    assert after["terms_version"] == consents.current_version() + "+ret1"
    assert _cell(after, "member_idle_days")["text_ko"].endswith("마지막 이용 후 2년이 지나면 파기") and _cell(after, "member_idle_days")["value"] == 730
    assert after["history"][0]["actor"] == "op-kim" and after["history"][0]["reason"] == "2년으로 늘림" and after["history"][0]["key_id"]
    # 같은 값을 다시 보내면 「바꿈」이 아니다 — 판도 이력도 그대로
    again = _patch(client, api, 1, {"member_idle_days": 730})
    assert again.json()["revision"] == 1 and again.json()["changed"] == {} and len(again.json()["history"]) == 1
    # 기본값으로 되돌림(null)
    back = _patch(client, api, 1, {"member_idle_days": None}, reason="원복")
    assert back.json()["revision"] == 2 and back.json()["changed"] == {"member_idle_days": [730, 365]}
    assert back.json()["terms_version"] == consents.current_version() + "+ret2"          # 값은 돌아왔어도 글이 한 번 바뀐 적 있으니 버전은 계속 오른다


def test_an_old_terms_version_is_refused_after_the_values_change(api):
    client = _client()
    with get_connection() as conn:
        assert consents.current_version(conn, api["tenant"]) == consents.current_version()
    assert _patch(client, api, 0, {"consent_days": 2000}).status_code == 200
    with get_connection() as conn:
        now_version = consents.current_version(conn, api["tenant"])
        assert now_version.endswith("+ret1")
        user = uuid4()
        with pytest.raises(consents.ConsentError) as old:
            consents.record(conn, tenant_id=api["tenant"], user_id=user, session_kind="guest", version=consents.current_version(),
                            items=[{"code": "service_terms", "agreed": True, "text_sha256": "a" * 64}], ip=None, user_agent=None)
        assert old.value.status == 409 and old.value.code == "terms_version_changed" and old.value.extra["current_version"] == now_version
        state = consents.record(conn, tenant_id=api["tenant"], user_id=user, session_kind="guest", version=now_version,
                                items=[{"code": "service_terms", "agreed": True, "text_sha256": "a" * 64}], ip=None, user_agent=None)
        assert state["current_version"] == now_version


def test_the_history_cannot_be_edited_or_deleted(api):
    client = _client()
    assert _patch(client, api, 0, {"location_proof_months": 12}).status_code == 200
    for sql in ("UPDATE legal_retention_history SET reason='x'", "DELETE FROM legal_retention_history"):
        with pytest.raises(Exception) as refused:
            with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute(sql + " WHERE tenant_id=%s", (api["tenant"],))
        assert "append-only" in str(refused.value)


@pytest.mark.parametrize("body, status, code", [
    ({"changes": {"member_idle_days": 10}}, 422, "out_of_range"),                         # 하한 30일 밖
    ({"changes": {"member_idle_days": 99999}}, 422, "out_of_range"),
    ({"changes": {"member_idle_days": "365"}}, 422, None),                                # 숫자가 아님(요청 모양 검사)
    ({"changes": {"case_follows_trip": 1}}, 422, "unknown_cell"),                         # 고정 문장 칸은 못 바꾼다
    ({"changes": {"nope": 3}}, 422, "unknown_cell"),
    ({"actor": "", "changes": {"member_idle_days": 400}}, 422, "actor_required"),
    ({"reason": " ", "changes": {"member_idle_days": 400}}, 422, "reason_required"),
])
def test_a_bad_change_is_refused_and_nothing_is_written(api, body, status, code):
    client = _client()
    payload = {"expected_revision": 0, "actor": "op", "reason": "r", **body}
    response = client.patch("/admin/retention", headers=api["auth"]("limits:write"), json=payload)
    assert response.status_code == status, response.text
    if code:
        assert response.json()["error"]["code"] == code
    assert client.get("/admin/retention", headers=api["auth"]("limits:read")).json()["revision"] == 0
    assert _count("SELECT count(*) FROM legal_retention_history WHERE tenant_id=%s", api["tenant"]) == 0


def test_a_stale_revision_is_a_conflict_and_the_scopes_are_split(api):
    client = _client()
    assert _patch(client, api, 0, {"member_idle_days": 400}).status_code == 200
    stale = _patch(client, api, 0, {"member_idle_days": 500})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision" and stale.json()["error"]["revision"] == 1
    assert client.get("/admin/retention").status_code == 401
    assert client.get("/admin/retention", headers=api["auth"]("trip:read")).status_code == 403
    assert client.patch("/admin/retention", headers=api["auth"]("limits:read"),
                        json={"expected_revision": 1, "actor": "a", "reason": "r", "changes": {"member_idle_days": 400}}).status_code == 403


# ── ④ 동의 기록 보관 일수는 바꾼 값이 쓰인다 ─────────────────────────
def test_the_consent_purge_uses_the_value_the_operator_set(api):
    client = _client()
    user = uuid4()
    old = datetime.now(timezone.utc) - timedelta(days=400)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO consent_events (tenant_id, user_id, session_kind, code, agreed, terms_version, text_sha256, at) VALUES (%s,%s,'guest','privacy',true,'v',%s,%s)",
                    (api["tenant"], user, "a" * 64, old))
    with get_connection() as conn:
        assert consents.purge_expired(conn, api["tenant"]) == 0                    # 기본 5년 — 400일 된 줄은 남는다
    assert _patch(client, api, 0, {"consent_days": 365}).status_code == 200
    with get_connection() as conn:
        assert consents.purge_expired(conn, api["tenant"]) == 1                    # 1년으로 줄이면 지워진다


# ── ⑤ 회원 자료 정리 ───────────────────────────────────────────────
def _member(env, *, idle_days: float):
    customer = _new_guest_with_trip(env, days_idle=idle_days)
    _link(env, customer)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_social_links SET linked_at = now() - make_interval(days => %s) WHERE tenant_id=%s AND customer_id=%s",
                    (int(idle_days), env["tenant"], customer))
        cur.execute("INSERT INTO customer_profiles (tenant_id, customer_id, recovery_email) VALUES (%s,%s,'m@example.com')", (env["tenant"], customer))
        cur.execute("INSERT INTO user_activity_events (tenant_id, customer_id, kind) VALUES (%s,%s,'t')", (env["tenant"], customer))
        cur.execute("INSERT INTO customer_cases (tenant_id, customer_id, status, subject, state_json, version) VALUES (%s,%s,'resolved','t','{}'::jsonb,1)",
                    (env["tenant"], customer))
        cur.execute("INSERT INTO consent_events (tenant_id, user_id, session_kind, code, agreed, terms_version, text_sha256) VALUES (%s,%s,'member','privacy',true,'v',%s)",
                    (env["tenant"], customer, "b" * 64))
    return customer


def _set_mode(env, mode):
    from psycopg.types.json import Json

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,'retention.purge_mode',%s,'test') "
                    "ON CONFLICT (tenant_id, name) DO UPDATE SET value=EXCLUDED.value", (env["tenant"], Json(mode)))
    web_guard.clear_cache()


def test_the_default_mode_only_counts_and_deletes_nothing(cookies):
    old = _member(cookies, idle_days=400)
    with get_connection() as conn:
        result = member_cleanup.run(conn, cookies["tenant"])
    assert result["mode"] == "dry_run" and result["would_delete"]["members"] == 1, result
    assert result["would_delete"]["trips"] == 1 and result["would_delete"]["customer_cases"] == 1 and result["would_delete"]["customer_profiles"] == 1
    assert _exists(cookies, old) and _count("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s", cookies["tenant"], old) == 1   # 아무것도 안 지웠다
    runs = _count("SELECT count(*) FROM retention_runs WHERE tenant_id=%s AND mode='dry_run'", cookies["tenant"])
    assert runs == 1


def test_off_does_nothing_and_on_deletes_only_members_idle_past_the_period(cookies):
    old = _member(cookies, idle_days=400)
    recent = _member(cookies, idle_days=100)                                                      # 아직 1년이 안 됐다
    guest = _new_guest_with_trip(cookies, days_idle=400)                                          # 게스트는 게스트 정리 몫
    _set_mode(cookies, "off")
    with get_connection() as conn:
        assert member_cleanup.run(conn, cookies["tenant"]) == {"skipped": "off"}
    assert _exists(cookies, old)
    _set_mode(cookies, "on")
    with get_connection() as conn:
        result = member_cleanup.run(conn, cookies["tenant"])
    assert result["mode"] == "on" and result["members"] == 1 and result["customers_deleted"] == 1 and result["trips"] == 1 and result["cases"] == 1 and result["errored"] == 0, result
    assert not _exists(cookies, old) and _exists(cookies, recent) and _exists(cookies, guest)
    for sql in ("SELECT count(*) FROM customer_cases WHERE tenant_id=%s AND customer_id=%s", "SELECT count(*) FROM customer_profiles WHERE tenant_id=%s AND customer_id=%s",
                "SELECT count(*) FROM user_activity_events WHERE tenant_id=%s AND customer_id=%s", "SELECT count(*) FROM web_social_links WHERE tenant_id=%s AND customer_id=%s"):
        assert _count(sql, cookies["tenant"], old) == 0, sql
    assert _count("SELECT count(*) FROM consent_events WHERE tenant_id=%s AND user_id=%s", cookies["tenant"], old) == 1      # 동의 기록은 증빙이라 따로 보관 기간을 따른다
    assert _count("SELECT count(*) FROM retention_runs WHERE tenant_id=%s AND mode='on'", cookies["tenant"]) == 1


def test_a_shorter_period_set_by_the_operator_widens_the_candidates(cookies):
    member = _member(cookies, idle_days=100)
    with get_connection() as conn:
        assert member_cleanup.candidates(conn, cookies["tenant"]) == []
        retention.update(conn, cookies["tenant"], expected_revision=0, changes={"member_idle_days": 60}, actor="op", key_id="k", reason="시험")
        assert member_cleanup.candidates(conn, cookies["tenant"]) == [member]
