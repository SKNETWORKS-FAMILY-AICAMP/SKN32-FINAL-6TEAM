"""제안 고르기(`trip_api._choose` → `pending.choose`) 저장 실패 — HTTP 500 대신 명시적 503 `save_failed` `[2026-10-27 C 전수검사 결함 12]`.

★왜. 감시가 낸 「바꿀까요?」 제안을 고객이 웹 · 에이전트 API 로 고를 때(`POST …/proposals/{id}/choose`) 저장소 운영 실패
  (psycopg `OperationalError` — 잠금 초과 · 연결 끊김 · 취소)가 그대로 올라가 일반 500 이었다. 화면은 고른 안이 들어갔는지 모른다.
★규칙(다른 판 쓰기 길 `storage_failure.guarded` 와 같은 생각 · Codex Q3): 판 번호만으로는 모자란다 — 「그대로 둘게요」(kept) ·
  「바꿔 줘」(안 채우기)는 판을 올리지 않고 **제안 행만** 바꾼다. 그래서 새 연결로 그 제안 행을 `FOR SHARE` 로 다시 읽어
  (끊긴 연결의 COMMIT 이 끝날 때까지 기다린다) 이 요청이 잠근 때의 제안(상태 · 사유 · 안 목록 · 결정 시각)과 **그대로일 때만**
  503 `save_failed`(「아무것도 바뀌지 않았어요」). 다시 읽기 실패 · 제안이 바뀜이면 원래 예외(숨기지 않는다). 코드 결함은 잡지 않는다.
  응답 · 기록에는 예외 종류 이름뿐이다(메시지 · SQL 인자는 고객 값을 담을 수 있다).
"""
from __future__ import annotations

from contextlib import nullcontext
from uuid import UUID

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.planning import pending

PRIVATE = "CONTROLLED_PRIVATE 010-1234-5678"
TRIP = UUID("33333333-3333-3333-3333-333333333331")
PROPOSAL = UUID("44444444-4444-4444-4444-444444444441")
ITEM = UUID("55555555-5555-5555-5555-555555555551")
CUSTOMER = UUID("22222222-2222-2222-2222-222222222221")
OPEN = {"proposal_id": PROPOSAL, "trip_id": TRIP, "item_id": ITEM, "base_version": 3, "status": "open",
        "reason": "weather_outdoor", "options_json": [{"key": "a1", "name": "실내 전시관"}], "decided_at": None,
        "expires_at": None, "chosen_key": None}


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def transaction(self):
        return nullcontext(self)


@pytest.fixture
def web(monkeypatch):
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.entry import trip_api

    seen = {"readback": [], "error": None, "unchanged": True}

    def close(self, conn, proposal_id, **kw):
        raise seen["error"]

    def readback(connect, tenant, trip_id, proposal_id, before):
        seen["readback"].append((tenant, trip_id, proposal_id, before))
        return seen["unchanged"]

    monkeypatch.setattr(trip_api, "get_connection", lambda: _Conn())
    monkeypatch.setattr(TripStore, "latest", lambda self, conn, trip_id: ({"customer_id": CUSTOMER, "version": 3}, []))
    monkeypatch.setattr(TripStore, "places", lambda self, conn, trip_id: [])
    monkeypatch.setattr(pending.PendingStore, "get", lambda self, conn, trip_id, proposal_id, **kw: dict(OPEN))
    monkeypatch.setattr(pending.PendingStore, "close", close)
    monkeypatch.setattr(pending, "proposal_unchanged_after_failure", readback, raising=False)
    router = trip_api.build_trip_router()
    endpoint = next(r for r in router.routes if r.path == "/v1/web/trips/{trip_id}/proposals/{proposal_id}/choose")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[endpoint.dependant.dependencies[0].call] = lambda: ("tenant", CUSTOMER)
    return app, seen


def _post(app, *, raise_server_exceptions=True):
    client = TestClient(app, raise_server_exceptions=raise_server_exceptions)
    # key=None — 「그대로 둘게요」: 진짜 `pending.choose` 가 잠근 제안을 닫다가(`close`) 실패한다
    return client.post(f"/v1/web/trips/{TRIP}/proposals/{PROPOSAL}/choose", json={"key": None})


@pytest.mark.parametrize("error", [psycopg.errors.LockNotAvailable(PRIVATE), psycopg.OperationalError(PRIVATE),
                                   psycopg.errors.QueryCanceled(PRIVATE)])
def test_a_choice_storage_failure_is_503_save_failed_when_the_proposal_is_unchanged(web, caplog, error):
    app, seen = web
    seen["error"] = error
    response = _post(app)
    assert response.status_code == 503, response.text
    body = response.json()["detail"]["error"]
    assert body["code"] == "save_failed"
    assert body["message"] == pending.CHOOSE_SAVE_FAILED_TEXT
    assert "아무것도 바뀌지 않았어요" in body["message"]
    assert body["proposal_status"] == "open"
    [(tenant, trip_id, proposal_id, before)] = seen["readback"]
    assert (tenant, trip_id, proposal_id) == ("tenant", TRIP, PROPOSAL)
    assert before["status"] == "open" and before["options_json"] == OPEN["options_json"], "이 요청이 잠근 때의 제안과 비교한다"
    for text in (response.text, caplog.text):
        assert "010-1234" not in text and "CONTROLLED" not in text, "예외 메시지(고객 값)는 응답 · 기록에 싣지 않는다"


def test_a_choice_storage_failure_is_not_hidden_when_the_readback_cannot_confirm(web):
    app, seen = web
    seen["error"], seen["unchanged"] = psycopg.OperationalError(PRIVATE), False
    with pytest.raises(psycopg.OperationalError):
        _post(app)


@pytest.mark.parametrize("error", [psycopg.IntegrityError("dup"), psycopg.ProgrammingError("bad"), RuntimeError("bug")])
def test_code_defects_in_a_choice_are_not_relabelled(web, error):
    app, seen = web
    seen["error"] = error
    with pytest.raises(type(error)):
        _post(app)
    assert seen["readback"] == [], "코드 결함은 다시 읽지도 않는다"


def test_a_failure_before_the_ownership_check_is_not_relabelled(web, monkeypatch):
    """`[2026-10-28 C12 리뷰]` 소유 확인(`_trip_or_404`) 전에 실패하면 다시 읽지 않는다 — 다시 읽기는 고객을 보지 않아 남의 여행 · 열린 제안에도
    503(평소 404)을 낼 수 있었다. 이 요청은 아무것도 쓰지 않았다 — 원래 예외."""
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore

    app, seen = web

    def latest(self, conn, trip_id):
        raise psycopg.OperationalError(PRIVATE)

    monkeypatch.setattr(TripStore, "latest", latest)
    with pytest.raises(psycopg.OperationalError):
        _post(app)
    assert seen["readback"] == []


def test_a_failure_after_the_ownership_check_but_before_the_lock_is_503_with_an_open_proposal(web, monkeypatch):
    """소유는 확인했고 제안은 아직 안 잠갔다(장소 읽기 실패) — 다시 읽어 열려 있으면 503, 본문의 `proposal_status` 는 계약대로 `open`."""
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore

    app, seen = web

    def places(self, conn, trip_id):
        raise psycopg.errors.QueryCanceled(PRIVATE)

    monkeypatch.setattr(TripStore, "places", places)
    response = _post(app)
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"]["proposal_status"] == "open"
    [(_, _, _, before)] = seen["readback"]
    assert before is None


def test_the_refusals_keep_their_codes(web, monkeypatch):
    """거절(`ProposalRefused`)은 그대로 — 저장 실패 처리가 404 · 409 를 가리지 않는다."""
    app, seen = web
    monkeypatch.setattr(pending.PendingStore, "get", lambda self, conn, trip_id, proposal_id, **kw: {**OPEN, "status": "chosen"})
    response = _post(app)
    assert response.status_code == 409 and response.json()["detail"]["error"]["code"] == "already_decided"
    assert seen["readback"] == []


# ── 다시 읽기(`pending.proposal_unchanged_after_failure`) ──────────────────────────


class _Cursor:
    def __init__(self, row, fail):
        self.row, self.fail, self.sql = row, fail, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.sql.append(sql)
        if self.fail and "pending_changes" in sql:
            raise psycopg.OperationalError(PRIVATE)

    def fetchone(self):
        return self.row


class _ReadConn(_Conn):
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def _readback(row, *, fail=False, before=OPEN):
    cursor = _Cursor(row, fail)
    real = pending.__dict__["proposal_unchanged_after_failure"]
    return real(lambda: _ReadConn(cursor), "tenant", TRIP, PROPOSAL, before), cursor


def _row(**changes):
    value = {**OPEN, **changes}
    return (value["status"], value["reason"], value["options_json"], value["decided_at"])


def test_the_readback_waits_for_the_proposal_row_and_says_unchanged_only_when_it_is():
    same, cursor = _readback(_row())
    assert same is True
    assert any("lock_timeout" in s for s in cursor.sql), "끝나지 않는 앞 트랜잭션을 한도 없이 기다리지 않는다"
    assert any("FOR SHARE" in s and "tenant_id" in s for s in cursor.sql), "앞 트랜잭션(FOR UPDATE)이 끝날 때까지 기다리고 · 테넌트 조건"
    assert _readback(_row(status="chosen", decided_at="2030-01-01"))[0] is False, "고른 것이 저장됐으면 「안 바뀜」이 아니다"
    assert _readback(_row(status="kept"))[0] is False, "「그대로 둘게요」가 저장됐으면 「안 바뀜」이 아니다"
    assert _readback(_row(options_json=[{"key": "b1"}], reason="weather_outdoor_options"))[0] is False, \
        "「바꿔 줘」로 안을 채운 것이 저장됐으면(판은 그대로여도) 「안 바뀜」이 아니다"
    assert _readback(_row(options_json=[{"key": "b1"}]))[0] is False, "안 목록만 바뀌어도"
    assert _readback(_row(reason="weather_outdoor_options"))[0] is False, "사유만 바뀌어도"
    assert _readback(_row(decided_at="2030-01-01"))[0] is False, "결정 시각만 찍혀도"
    assert _readback(None)[0] is False, "제안 행이 없으면 모른다"
    assert _readback(_row(), fail=True)[0] is False, "다시 읽기도 실패하면 모른다"


def test_the_readback_without_a_locked_snapshot_needs_a_successful_read_of_a_still_open_proposal():
    """제안을 잠그기 전(연결 · 여행 읽기)에 실패했으면 이 요청은 아무것도 쓰지 않았다 — 다시 읽기가 되고 제안이 아직 열려 있으면 「안 바뀜」.
    그 사이 다른 요청이 정했으면 「다시 골라 주세요」가 거짓이라 원래 예외(Codex 검토 P2)."""
    assert _readback(_row(), before=None)[0] is True
    assert _readback(_row(status="chosen"), before=None)[0] is False
    assert _readback(None, before=None)[0] is False
    assert _readback(_row(), fail=True, before=None)[0] is False


def test_every_saved_consent_write_changes_the_proposal_row():
    """「바꿔 줘」는 판을 올리지 않고 안을 채운다(`set_options` + 안내 메시지) — 그 사유는 늘 원래 사유와 다르다(행 비교로 가려진다)."""
    for reason in (pending.CONSENT_REASON, pending.FORECAST_REASON):
        assert f"{reason}_options" != reason


def test_the_locked_snapshot_is_a_deep_copy_and_only_the_first_locked_read(monkeypatch):
    """`choose` 는 고른 안(dict)에 다시 본 값을 써 넣는다 — 기준이 같이 바뀌면 「바뀐 것」을 「그대로」로 읽는다."""
    rows = [dict(OPEN, options_json=[{"key": "a1", "name": "실내 전시관"}]), dict(OPEN, status="chosen")]
    monkeypatch.setattr(pending.PendingStore, "get", lambda self, conn, trip_id, proposal_id, **kw: rows.pop(0))
    store = pending.SnapshotPendingStore("tenant")
    assert store.get(None, TRIP, PROPOSAL) is not None and store.locked is None, "잠그지 않은 읽기는 기준이 아니다"
    rows.insert(0, dict(OPEN, options_json=[{"key": "a1", "name": "실내 전시관"}]))
    row = store.get(None, TRIP, PROPOSAL, lock=True)
    row["options_json"][0]["price_per_night"] = 171000
    assert store.locked["options_json"] == [{"key": "a1", "name": "실내 전시관"}]
    store.get(None, TRIP, PROPOSAL, lock=True)
    assert store.locked["status"] == "open", "첫 잠금 읽기만 기준이다"
