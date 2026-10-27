"""채팅 · 신고 · 진행 · 목적지 저장 중 DB 쓰기 실패 — HTTP 500 대신 명시적 `save_failed` `[2026-10-27 C 전수검사 · 알려진 이슈 (d)]`.

★왜. 승인 경로(`Controller._apply_approved`)와 채팅 고치기(`chat_edit.run` — 묶음 L F03)만 저장소 운영 실패를 다뤘다.
  같은 판 쓰기(`append_version` + `enqueue_notice`)를 하는 다른 길 — `TripDesk._write`(지연 · 닫힘 · 다른 안 · 되돌리기),
  `journey_progress.apply`(도착 · 출발 진행), `requested_destination.apply`(이름만 아는 목적지) — 는 psycopg `OperationalError` 가
  그대로 올라가 일반 500 이었다(화면 · 에이전트는 저장됐는지 모른다).
★규칙(채팅 고치기와 같다): 새 연결로 그 여행 행을 `FOR SHARE` 로 다시 읽어 **기준 판 그대로가 확인될 때만** `escalated · save_failed`
  (「일정은 바꾸지 않았어요」). 다시 읽기 실패 · 판이 바뀜이면 원래 예외(숨기지 않는다). 코드 결함(IntegrityError …)은 잡지 않는다.
  REST 신고(`/v1/trips/{id}/reports`)는 503 `save_failed` 로 낸다. 기록 · 응답에는 예외 종류 이름뿐이다.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from app.domains.travel_ops.components.conversation import chat_edit, journey_progress, requested_destination, storage_failure
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk

PRIVATE = "CONTROLLED_PRIVATE 010-1234-5678"
TRIP = uuid4()


class _Conn:
    @contextmanager
    def transaction(self):
        yield


@contextmanager
def _connect():
    yield _Conn()


def _readback(monkeypatch, unchanged):
    seen = []

    def check(connect, tenant, trip_id, base_version):
        seen.append((tenant, trip_id, base_version))
        return unchanged

    monkeypatch.setattr(storage_failure, "_unchanged_after_failure", check)
    return seen


class _Store:
    tenant_id = "unit-storage"

    def __init__(self, error):
        self.error = error

    def append_version(self, conn, **kw):
        raise self.error

    def enqueue_notice(self, conn, **kw):
        raise AssertionError("not reached")


def _plan():
    return SimpleNamespace(new_items=lambda items: items, reason="r", causes=[], notice={"text": "t"})


def test_trip_desk_write_storage_failure_is_save_failed_when_unchanged(monkeypatch, caplog):
    seen = _readback(monkeypatch, True)
    desk = TripDesk(store=_Store(psycopg.errors.LockNotAvailable(PRIVATE)), connection_factory=_connect)
    outcome = desk._write(TRIP, 7, [], _plan())
    assert outcome == {"status": "escalated", "reason": "save_failed", "text": chat_edit.SAVE_FAILED_TEXT, "version": 7}
    assert seen == [("unit-storage", TRIP, 7)]
    assert "010-1234" not in caplog.text and "CONTROLLED" not in caplog.text


def test_trip_desk_write_storage_failure_is_not_hidden_when_unconfirmed(monkeypatch):
    _readback(monkeypatch, False)
    desk = TripDesk(store=_Store(psycopg.OperationalError(PRIVATE)), connection_factory=_connect)
    with pytest.raises(psycopg.OperationalError):
        desk._write(TRIP, 7, [], _plan())


@pytest.mark.parametrize("error", [psycopg.IntegrityError("dup"), psycopg.ProgrammingError("bad"), RuntimeError("bug")])
def test_trip_desk_write_code_defects_are_not_relabelled(monkeypatch, error):
    seen = _readback(monkeypatch, True)
    desk = TripDesk(store=_Store(error), connection_factory=_connect)
    with pytest.raises(type(error)):
        desk._write(TRIP, 7, [], _plan())
    assert seen == []


class _ProgressStore:
    tenant_id = "unit-storage"

    def version_for_request(self, conn, trip_id, key):
        raise psycopg.errors.QueryCanceled(PRIVATE)


def test_journey_progress_storage_failure_is_save_failed(monkeypatch):
    seen = _readback(monkeypatch, True)
    decision = SimpleNamespace(action="arrive_item", item=None, raw={})
    outcome = journey_progress.apply(store=_ProgressStore(), connect=_connect, trip_id=TRIP, base_version=3,
                                     decision=decision, now=None, request_id="r-1", message="도착")
    assert outcome["status"] == "escalated" and outcome["reason"] == "save_failed" and seen == [("unit-storage", TRIP, 3)]


def test_requested_destination_storage_failure_is_save_failed(monkeypatch):
    seen = _readback(monkeypatch, True)
    decision = SimpleNamespace(action="arrive_item", item=None, raw={"destination_text": "어딘가"})
    outcome = requested_destination.apply(store=_ProgressStore(), connect=_connect, trip_id=TRIP, base_version=4,
                                          decision=decision, now=None, request_id="r-2")
    assert outcome["status"] == "escalated" and outcome["reason"] == "save_failed" and seen == [("unit-storage", TRIP, 4)]


def test_rest_report_save_failed_is_503_without_details():
    from fastapi import HTTPException

    from app.domains.travel_ops.entry import trip_api

    with pytest.raises(HTTPException) as raised:
        trip_api._outcome({"status": "escalated", "reason": "save_failed", "text": chat_edit.SAVE_FAILED_TEXT, "version": 7})
    assert raised.value.status_code == 503
    assert raised.value.detail["error"]["code"] == "save_failed" and raised.value.detail["error"]["version"] == 7
