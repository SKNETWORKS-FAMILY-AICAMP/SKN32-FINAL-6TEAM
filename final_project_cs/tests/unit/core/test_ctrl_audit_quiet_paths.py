# -*- coding: utf-8 -*-
"""`[2026-10-28 라우팅 전수검사 C 후속]` 조용히 바뀌거나 삼켜지던 길 네 곳(C 보고서 #18 · #20 · #21 · #22).

- #18 outbox 재시도 간격 `or 60.0` — 설정 0 이 조용히 60초가 되고, 값이 없어도 60초로 돌았다.
- #20 outbox `last_error` — 일반 실패 · 시간 초과 갈래만 길이 제한이 없었다(건너뜀 · 429 는 500자).
- #21 채팅 진행 알림 실패를 `pass` 로 삼켜 원인 기록이 없었다(처리는 계속돼야 한다).
- #22 정책 검색 예외가 기록 없이 `retrieval_failed` 신호만 남았다(신호는 그대로 남아야 한다).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.infrastructure.messaging import worker as worker_module
from app.infrastructure.messaging.worker import OutboxWorker


def _rails(monkeypatch, values: dict) -> None:
    monkeypatch.setattr(worker_module, "get_guardrails", lambda: values)


def test_retry_gap_zero_from_settings_is_kept(monkeypatch):
    _rails(monkeypatch, {"reliability.outbox_retry_seconds": 0})
    assert OutboxWorker._retry_seconds() == 0.0          # noqa: SLF001


@pytest.mark.parametrize("value", [None, -1, "soon", float("nan"), float("inf"), False, [60], {"s": 60}])
def test_retry_gap_missing_or_invalid_is_an_error_not_sixty(monkeypatch, value):
    _rails(monkeypatch, {"reliability.outbox_retry_seconds": value} if value is not None else {})
    with pytest.raises(ValueError):
        OutboxWorker._retry_seconds()                    # noqa: SLF001


class _Cursor:
    def __init__(self, log, row):
        self.log, self.row = log, row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.log.append((sql, params))

    def fetchone(self):
        return self.row


class _Conn:
    def __init__(self, log, row):
        self.log, self.row = log, row

    @contextmanager
    def transaction(self):
        yield

    def cursor(self):
        return _Cursor(self.log, self.row)


def _run(monkeypatch, exc: Exception) -> list:
    _rails(monkeypatch, {"reliability.outbox_retry_seconds": 60, "reliability.outbox_stale_processing_seconds": 300})
    log: list = []
    row = ("m1", "trip.notice", {}, 0, "t1", "k1")

    @contextmanager
    def factory():
        yield _Conn(log, row)

    def publisher(_message):
        raise exc

    assert OutboxWorker(factory, publisher).process_once() is True
    return log


@pytest.mark.parametrize("exc", [RuntimeError("x" * 5000), TimeoutError("y" * 5000), ConnectionError("z" * 5000)])
def test_outbox_last_error_is_capped_like_the_other_branches(monkeypatch, exc):
    log = _run(monkeypatch, exc)
    sql, params = log[-1]
    assert "last_error" in sql
    errors = [p for p in params if isinstance(p, str) and p[:1] in "xyz" and len(set(p)) == 1]
    assert errors and all(len(p) <= 500 for p in errors)


def test_progress_notice_failure_is_logged_and_work_continues(caplog):
    from app.domains.travel_ops.components.conversation import trip_messages

    def broken(_name):
        raise RuntimeError("progress sink down")

    with caplog.at_level(logging.WARNING, logger=trip_messages.logger.name):
        trip_messages._stage(broken, "reading")       # noqa: SLF001 — 예외가 올라오지 않는다
    assert any("reading" in r.getMessage() and r.exc_info for r in caplog.records)


def test_policy_search_failure_is_logged_and_still_signalled(caplog):
    from app.application import controller as controller_module

    def broken(*_a, **_kw):
        raise RuntimeError("vector store down")

    fake = SimpleNamespace(policy_search=broken)
    with caplog.at_level(logging.WARNING, logger=controller_module.logger.name):
        hits, failed = controller_module.Controller._policy(fake, "t1", "환불", ["travel"])   # noqa: SLF001
    assert hits == [] and failed is True
    assert any(r.exc_info for r in caplog.records)
