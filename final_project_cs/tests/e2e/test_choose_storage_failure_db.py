# -*- coding: utf-8 -*-
"""제안 고르기 저장 실패 — **실제 PostgreSQL** 로 `[2026-10-27 C 전수검사 결함 12]`.

단위 시험(`tests/unit/travel/test_choose_storage_failure.py`)은 가짜 연결이다. 여기서는 고르기 트랜잭션 안에서 진짜 서버 오류
(`statement_timeout` 으로 끊긴 `QueryCanceled` — `OperationalError` 계열)를 내 본다: 제안을 `FOR UPDATE` 로 잠근 **뒤**
(①「그대로 둘게요」를 닫을 때 ②고른 안의 새 판을 쓴 **뒤** 제안을 닫을 때) 실패한다. 트랜잭션이 통째로 되돌아가므로
제안은 열린 채 · 판은 그대로여야 하고, 응답은 일반 500 이 아니라 503 `save_failed` 다. 같은 안을 다시 고르면 된다.

재현:

    python -m pytest tests/e2e/test_choose_storage_failure_db.py -v
"""
from __future__ import annotations

from app.domains.travel_ops.components.planning import pending
from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION
from app.infrastructure.db.session import get_connection

from .test_trip_api import _body, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _h, _member, _session, _web_body


def _fail_once_when_closing(monkeypatch, status):
    """`PendingStore.close(status=…)` 를 처음 한 번 진짜 서버 오류로 끊는다(그 트랜잭션 안에서)."""
    real = pending.PendingStore.close
    fired = []

    def close(self, conn, proposal_id, **kw):
        if kw.get("status") == status and not fired:
            fired.append(proposal_id)
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '50ms'")
                cur.execute("SELECT pg_sleep(1)")              # → psycopg.errors.QueryCanceled
        return real(self, conn, proposal_id, **kw)

    monkeypatch.setattr(pending.PendingStore, "close", close)
    return fired


def _row(api, proposal_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, chosen_key, decided_at FROM pending_changes WHERE tenant_id=%s AND proposal_id=%s",
                    (api["tenant"], proposal_id))
        return cur.fetchone()


def _version(api, trip_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT latest_version FROM trips WHERE tenant_id=%s AND trip_id=%s", (api["tenant"], trip_id))
        return cur.fetchone()[0]


def test_keeping_the_plan_fails_to_save_with_503_and_the_same_choice_works_again(api, monkeypatch):
    body = _body(api["customer"], request_id="choose-storage-kept")
    body["constraints"] = {**body["constraints"], "survey": {"version": SURVEY_VERSION, "on_disruption": "ask_first"}}
    trip_id = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write")).json()["trip_id"]
    api["tick"]("09:00")
    [proposal] = api["client"].get(f"/v1/trips/{trip_id}/proposals", headers=api["auth"]("trip:read")).json()["proposals"]
    url = f"/v1/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose"
    before = _version(api, trip_id)
    fired = _fail_once_when_closing(monkeypatch, "kept")

    failed = api["client"].post(url, json={"key": None}, headers=api["auth"]("trip:write"))
    assert fired, "실패 주입이 실제로 돌았다"
    assert failed.status_code == 503, failed.text
    error = failed.json()["error"]
    assert error["code"] == "save_failed" and error["message"] == pending.CHOOSE_SAVE_FAILED_TEXT
    assert error["proposal_status"] == "open"
    assert "canceling statement" not in failed.text and "pg_sleep" not in failed.text, "서버 오류 문장은 응답에 싣지 않는다"
    assert _row(api, proposal["proposal_id"]) == ("open", None, None) and _version(api, trip_id) == before

    again = api["client"].post(url, json={"key": None}, headers=api["auth"]("trip:write"))
    assert again.status_code == 200 and again.json() == {"status": "kept"}
    assert _row(api, proposal["proposal_id"])[0] == "kept"


def test_choosing_an_option_fails_after_the_new_version_and_nothing_is_kept_then_the_retry_applies(api, monkeypatch):
    me = _session(api)
    _member(api, me["user_key"])
    body = _web_body(api, request_id="choose-storage-chosen",
                     survey={"version": SURVEY_VERSION, "on_disruption": "ask_first"})
    trip_id = api["client"].post("/v1/web/trips", json=body, headers=_h(me["user_key"])).json()["trip_id"]
    api["tick"]("09:00")
    [asked] = api["client"].get(f"/v1/web/trips/{trip_id}/proposals", headers=_h(me["user_key"])).json()["proposals"]
    url = f"/v1/web/trips/{trip_id}/proposals/{asked['proposal_id']}/choose"
    assert api["client"].post(url, json={"key": "change"}, headers=_h(me["user_key"])).json()["status"] == "options"
    [proposal] = api["client"].get(f"/v1/web/trips/{trip_id}/proposals", headers=_h(me["user_key"])).json()["proposals"]
    key = proposal["options"][0]["key"]
    before = _version(api, trip_id)
    fired = _fail_once_when_closing(monkeypatch, "chosen")          # 새 판(`append_version`) · 변경 알림을 쓴 **뒤** 실패

    failed = api["client"].post(url, json={"key": key}, headers=_h(me["user_key"]))
    assert fired
    assert failed.status_code == 503, failed.text
    assert failed.json()["error"]["code"] == "save_failed"
    assert _row(api, proposal["proposal_id"]) == ("open", None, None)
    assert _version(api, trip_id) == before, "같은 트랜잭션의 새 판도 함께 되돌아갔다"

    chosen = api["client"].post(url, json={"key": key}, headers=_h(me["user_key"]))
    assert chosen.status_code == 200 and chosen.json()["version"] == before + 1, chosen.text
    assert _row(api, proposal["proposal_id"])[:2] == ("chosen", key)


def test_asking_for_options_fails_to_save_and_the_proposal_still_has_no_options_then_the_retry_fills_them(api, monkeypatch):
    """「바꿔 줘」(`_consented` — 판은 그대로 · 제안 행에 안을 채우고 안내 메시지)가 저장 중 끊기면 안 · 사유 · 메시지 모두 되돌아간다."""
    me = _session(api)
    _member(api, me["user_key"])
    body = _web_body(api, request_id="choose-storage-options",
                     survey={"version": SURVEY_VERSION, "on_disruption": "ask_first"})
    trip_id = api["client"].post("/v1/web/trips", json=body, headers=_h(me["user_key"])).json()["trip_id"]
    api["tick"]("09:00")
    [asked] = api["client"].get(f"/v1/web/trips/{trip_id}/proposals", headers=_h(me["user_key"])).json()["proposals"]
    url = f"/v1/web/trips/{trip_id}/proposals/{asked['proposal_id']}/choose"
    real = pending.PendingStore.set_options
    fired = []

    def set_options(self, conn, proposal_id, **kw):
        result = real(self, conn, proposal_id, **kw)                # 안을 채운 **뒤** 끊는다
        if not fired:
            fired.append(proposal_id)
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '50ms'")
                cur.execute("SELECT pg_sleep(1)")
        return result

    monkeypatch.setattr(pending.PendingStore, "set_options", set_options)
    failed = api["client"].post(url, json={"key": "change"}, headers=_h(me["user_key"]))
    assert fired and failed.status_code == 503 and failed.json()["error"]["code"] == "save_failed", failed.text
    [still] = api["client"].get(f"/v1/web/trips/{trip_id}/proposals", headers=_h(me["user_key"])).json()["proposals"]
    assert still["status"] == "open" and still["reason"] == asked["reason"] and still["options"] == []
    again = api["client"].post(url, json={"key": "change"}, headers=_h(me["user_key"]))
    assert again.status_code == 200 and again.json()["status"] == "options", again.text
