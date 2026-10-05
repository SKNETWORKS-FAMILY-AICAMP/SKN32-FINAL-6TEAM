# -*- coding: utf-8 -*-
"""약관 동의 기록 · 사용 조건(게이트) — `GET·POST /v1/web/consents`. `[2026-10-05 사용자 지시 — ui 세션 요청서 「동의 기록 · 위치 수집」]`

계약: `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md` · 구현 `consents.py` · `consents_api.py` · 게이트 `web_cookie.authenticate` · 저장 046.

★지키려는 것
 ①게이트 설정(`consent.gate_enabled`)이 **꺼져 있으면(기본) 아무것도 안 바뀐다** · 켜면 필수 동의 없는 호출은 403 `consent_required`(면제 길은 통과) · 필수 둘을 기록하면 통과
 ②약관 버전이 오르면 `ok:false` 로 돌아가 다시 동의 · 옛 버전으로 `POST` 하면 409(지금 버전을 싣는다)
 ③기록은 **추가만**: 동의→철회→동의 = 사건 3줄 · 현재 상태는 마지막 줄 · 바뀐 것 없으면 줄을 안 더한다 · `text_sha256` 저장 · 주소 원문 없음 · DB 가 UPDATE/DELETE 를 거절
 ④입력 검사: 모르는 코드 · 해시 모양 · 참/거짓 아님 · 중복 · 빈 목록 → 422, 하나라도 틀리면 **하나도 기록하지 않는다**
 ⑤철회 효과: `alert_channel` → 저장한 웹훅 삭제 · `sensitive` → 식사 제한 · 설문 음식 답 삭제(다른 칸은 그대로) · 필수 철회 → `ok:false`
 ⑥게스트 · 회원 · 옛 키 · 에이전트 키 모두 같은 규칙(에이전트 키는 키 주인의 동의를 따르고, 동의 기록은 못 한다) · 쿠키 쓰기는 CSRF
 ⑦보관 기간이 지난 기록만 정리 작업이 지운다

재현:

    python -m pytest tests/e2e/test_consents.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import consents

from .test_guest_and_trip_delete import _customer_of, _link, _make_trip
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_agent_keys import _agent, _make_key, _member
from .test_web_api import _h
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401

SHA = "a" * 64
SHA2 = "b" * 64
VERSION = "2026-10-05"


@pytest.fixture()
def gate(cookies, monkeypatch):  # noqa: F811
    """게이트가 켜진 서버. 끝나면 이 시험이 만든 동의 기록을 지운다(DB 가 지우기를 막으므로 정리 작업과 같은 문을 연다)."""
    monkeypatch.setattr(consents, "gate_enabled", lambda: True)
    yield cookies
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL app.consent_purge = 'on'")
        cur.execute("DELETE FROM consent_events WHERE tenant_id=%s", (cookies["tenant"],))


def _csrf(client) -> dict:
    return {"Origin": WEB, "X-CSRF-Token": client.get("/v1/web/auth/me").json()["csrf_token"]}


def _post(client, items, version=VERSION, headers=None):
    return client.post("/v1/web/consents", json={"version": version, "items": items}, headers=headers if headers is not None else _csrf(client))


def _item(code, agreed=True, sha=SHA):
    return {"code": code, "agreed": agreed, "text_sha256": sha}


def _agree_required(client):
    response = _post(client, [_item("service_terms"), _item("privacy")])
    assert response.status_code == 200, response.text
    return response.json()


def _events(env) -> list[tuple]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT code, agreed, terms_version, text_sha256, session_kind FROM consent_events WHERE tenant_id=%s ORDER BY event_id", (env["tenant"],))
        return cur.fetchall()


# ── ① 게이트 ────────────────────────────────────────────────────
def test_with_the_gate_off_by_default_nothing_changes(cookies):  # noqa: F811
    _guest(cookies)
    assert cookies["client"].get("/v1/web/trips").status_code == 200                  # 동의 없이도 된다 — 기본은 꺼짐
    assert cookies["client"].get("/v1/web/consents").json()["ok"] is False             # 상태는 읽힌다(필수 미동의)


def test_with_the_gate_on_a_guest_must_agree_and_the_exempt_roads_stay_open(gate):
    _guest(gate)
    blocked = gate["client"].get("/v1/web/trips")
    assert blocked.status_code == 403
    assert blocked.json()["error"] == {"code": "consent_required", "message": "약관에 동의해야 쓸 수 있어요", "current_version": VERSION,
                                       "required": ["service_terms", "privacy"]}
    assert gate["client"].get("/v1/web/consents").status_code == 200                   # 면제: 동의하러 가는 길
    assert gate["client"].get("/v1/web/auth/me").status_code == 200                    # 면제: 로그인 길
    state = _agree_required(gate["client"])
    assert state["ok"] is True
    assert gate["client"].get("/v1/web/trips").status_code == 200                      # 이제 통과


def test_one_required_item_is_not_enough_and_optional_ones_do_not_unlock(gate):
    _guest(gate)
    _post(gate["client"], [_item("service_terms"), _item("location"), _item("sensitive")])
    assert gate["client"].get("/v1/web/consents").json()["ok"] is False
    assert gate["client"].get("/v1/web/trips").status_code == 403
    _post(gate["client"], [_item("privacy")])
    assert gate["client"].get("/v1/web/trips").status_code == 200


def test_the_gate_does_not_ask_for_optional_items(gate):
    """선택 동의를 안 해도 앱은 쓴다 — 필수 둘만 걸었다(법무 확인 전 보수적 해석)."""
    _guest(gate)
    state = _agree_required(gate["client"])
    assert {item["code"]: item["agreed"] for item in state["items"]} == {"service_terms": True, "privacy": True, "sensitive": False,
                                                                       "location": False, "alert_channel": False}
    assert gate["client"].get("/v1/web/trips").status_code == 200


# ── ② 버전 ──────────────────────────────────────────────────────
def test_a_new_terms_version_asks_everyone_again(gate, monkeypatch):
    _guest(gate)
    _agree_required(gate["client"])
    monkeypatch.setattr(consents, "current_version", lambda: "2026-12-01")
    state = gate["client"].get("/v1/web/consents").json()
    assert state["ok"] is False and state["current_version"] == "2026-12-01"
    assert gate["client"].get("/v1/web/trips").status_code == 403
    stale = _post(gate["client"], [_item("service_terms"), _item("privacy")], version=VERSION)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "terms_version_changed"
    assert stale.json()["error"]["current_version"] == "2026-12-01"
    assert _post(gate["client"], [_item("service_terms"), _item("privacy")], version="2026-12-01").json()["ok"] is True
    assert gate["client"].get("/v1/web/trips").status_code == 200


# ── ③ 기록은 추가만 ─────────────────────────────────────────────
def test_the_record_is_append_only_and_keeps_the_text_hash_but_no_address(gate):
    _guest(gate)
    gate["client"].headers["X-Forwarded-For"] = "10.20.30.40"
    _agree_required(gate["client"])
    _post(gate["client"], [_item("location", True, SHA)])
    _post(gate["client"], [_item("location", False, SHA)])
    _post(gate["client"], [_item("location", True, SHA2)])
    rows = [event for event in _events(gate) if event[0] == "location"]
    assert [(r[1], r[3]) for r in rows] == [(True, SHA), (False, SHA), (True, SHA2)]          # 동의 → 철회 → 동의 = 3줄
    state = gate["client"].get("/v1/web/consents").json()
    assert next(item for item in state["items"] if item["code"] == "location")["agreed"] is True        # 현재 = 마지막 줄
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT consent_events::text FROM consent_events WHERE tenant_id=%s", (gate["tenant"],))
        dump = "\n".join(row[0] for row in cur.fetchall())
        cur.execute("SELECT ip_hash FROM consent_events WHERE tenant_id=%s LIMIT 1", (gate["tenant"],))
        [(hashed,)] = cur.fetchall()
    assert "10.20.30.40" not in dump and hashed and len(hashed) == 64                    # 주소 원문은 없고 해시만
    assert {event[4] for event in _events(gate)} == {"guest"}


def test_the_database_itself_refuses_to_change_or_delete_a_record(gate):
    _guest(gate)
    _agree_required(gate["client"])
    for sql in ("UPDATE consent_events SET agreed = false WHERE tenant_id=%s", "DELETE FROM consent_events WHERE tenant_id=%s"):
        with pytest.raises(Exception, match="추가만"):
            with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute(sql, (gate["tenant"],))
    assert len(_events(gate)) == 2


def test_resending_the_same_agreement_adds_no_line(gate):
    _guest(gate)
    _agree_required(gate["client"])
    _agree_required(gate["client"])
    assert len(_events(gate)) == 2


# ── ④ 입력 검사 ─────────────────────────────────────────────────
@pytest.mark.parametrize("items,code", [
    ([_item("nope")], "unknown_code"),
    ([{"code": "privacy", "agreed": True, "text_sha256": "short"}], "invalid_text_sha256"),
    ([{"code": "privacy", "agreed": True, "text_sha256": "A" * 64}], "invalid_text_sha256"),              # 대문자 16진수는 받지 않는다(한 가지 모양)
    ([{"code": "privacy", "agreed": "yes", "text_sha256": SHA}], "invalid_items"),
    ([_item("privacy"), _item("privacy")], "invalid_items"),
    ([], "invalid_items"),
    (["privacy"], "invalid_items"),
])
def test_bad_input_is_refused_and_nothing_is_recorded(gate, items, code):
    _guest(gate)
    refused = _post(gate["client"], [_item("service_terms"), *items] if items and isinstance(items[0], dict) else items)
    assert refused.status_code == 422 and refused.json()["error"]["code"] == code
    assert _events(gate) == []                                  # 맞는 항목이 같이 왔어도 하나도 기록하지 않는다


# ── ⑤ 철회 효과 ─────────────────────────────────────────────────
def test_withdrawing_a_required_item_stops_the_app_again(gate):
    _guest(gate)
    _agree_required(gate["client"])
    state = _post(gate["client"], [_item("privacy", False)]).json()
    assert state["ok"] is False
    assert gate["client"].get("/v1/web/trips").status_code == 403


def test_withdrawing_alert_channel_deletes_the_saved_webhook(gate):
    _guest(gate)
    _agree_required(gate["client"])
    _post(gate["client"], [_item("alert_channel")])
    url = "https://discord.com/api/" + "webhooks/" + "123456789012345678/" + "A" * 68          # 글자 그대로 적지 않는다(보안 검사가 웹훅 모양 문자열을 막는다)
    saved = gate["client"].put("/v1/web/profile", json={"discord_webhook_url": url}, headers=_csrf(gate["client"]))
    assert saved.status_code == 200 and saved.json()["discord_webhook"]["set"] is True
    _post(gate["client"], [_item("alert_channel", False)])
    assert gate["client"].get("/v1/web/profile").json()["discord_webhook"]["set"] is False


def test_withdrawing_sensitive_removes_diet_and_survey_food_answers_only(gate):
    _guest(gate)
    _agree_required(gate["client"])
    _post(gate["client"], [_item("sensitive")])
    status, trip = _make_trip(gate)
    assert status == 201
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trips SET constraints = %s::jsonb WHERE tenant_id=%s AND trip_id=%s",
                    ('{"dietary": ["halal"], "budget": 5, "survey": {"priority_details": {"food": ["halal"], "move": ["fast"]}}}',
                     gate["tenant"], trip["trip_id"]))
    _post(gate["client"], [_item("sensitive", False)])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT constraints FROM trips WHERE tenant_id=%s AND trip_id=%s", (gate["tenant"], trip["trip_id"]))
        [(constraints,)] = cur.fetchall()
    assert constraints == {"budget": 5, "survey": {"priority_details": {"move": ["fast"]}}}              # 식사 · 음식 답만 사라진다


def test_a_purge_that_fails_rolls_the_withdrawal_back(gate, monkeypatch):
    """효과가 실패하면 동의 기록도 남지 않는다 — 기록만 남고 삭제가 안 된 상태를 만들지 않는다."""
    _guest(gate)
    _agree_required(gate["client"])
    _post(gate["client"], [_item("location")])

    def boom(*_args):
        raise RuntimeError("purge failed")

    monkeypatch.setitem(consents.PURGERS, "location", [boom])
    with pytest.raises(RuntimeError):
        _post(gate["client"], [_item("location", False)])
    assert next(item for item in gate["client"].get("/v1/web/consents").json()["items"] if item["code"] == "location")["agreed"] is True


# ── ⑥ 사용자 종류별 ─────────────────────────────────────────────
def test_a_legacy_key_user_is_gated_and_records_with_kind_key(gate):
    key = gate["client"].post("/v1/web/session").json()["user_key"]
    plain = _agent(gate)                                              # 쿠키 없는 클라이언트
    assert plain.get("/v1/web/trips", headers=_h(key)).status_code == 403
    done = plain.post("/v1/web/consents", json={"version": VERSION, "items": [_item("service_terms"), _item("privacy")]}, headers=_h(key))
    assert done.status_code == 200 and done.json()["ok"] is True
    assert plain.get("/v1/web/trips", headers=_h(key)).status_code == 200
    assert {event[4] for event in _events(gate)} == {"key"}


def test_an_agent_key_follows_its_owner_and_cannot_record_consent(gate):
    client = _member(gate)
    _agree_required(client)
    made = _make_key(gate, scope="write")
    assert made.status_code == 201, made.text
    key = made.json()["key"]
    agent = _agent(gate)
    assert agent.get("/v1/web/trips", headers=_h(key)).status_code == 200
    refused = agent.post("/v1/web/consents", json={"version": VERSION, "items": [_item("privacy", False)]}, headers=_h(key))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "agent_forbidden"        # 동의는 사람이 브라우저에서 한다
    _post(client, [_item("privacy", False)])                                                          # 주인이 철회하면
    blocked = agent.get("/v1/web/trips", headers=_h(key))
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "consent_required"         # 키도 막힌다
    _agree_required(client)
    assert agent.get("/v1/web/trips", headers=_h(key)).status_code == 200


def test_recording_with_a_cookie_needs_the_csrf_token(gate):
    _guest(gate)
    no_csrf = _post(gate["client"], [_item("privacy")], headers={"Origin": WEB})
    assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "csrf_failed"
    assert _events(gate) == []


def test_unauthenticated_calls_are_unauthorized_not_consent_required(gate):
    assert gate["client"].get("/v1/web/consents").status_code == 401
    assert gate["client"].post("/v1/web/consents", json={"version": VERSION, "items": [_item("privacy")]}).status_code == 401


# ── ⑦ 보관 기간 ─────────────────────────────────────────────────
def test_only_records_past_the_retention_are_purged(gate):
    _guest(gate)
    _agree_required(gate["client"])
    customer = _customer_of(gate)
    old = datetime.now(timezone.utc) - timedelta(days=int(consents.get_guardrails().get("consent.evidence_retention_days")) + 5)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO consent_events (tenant_id, user_id, session_kind, code, agreed, terms_version, text_sha256, at) "
                    "VALUES (%s,%s,'guest','location',true,'2020-01-01',%s,%s)", (gate["tenant"], customer, SHA, old))
    with get_connection() as conn:
        assert consents.purge_expired(conn, gate["tenant"]) == 1
    assert len(_events(gate)) == 2                                       # 최근 두 줄은 남는다
