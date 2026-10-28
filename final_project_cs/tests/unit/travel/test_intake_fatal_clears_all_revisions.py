# -*- coding: utf-8 -*-
"""`[2026-10-28 라우팅 전수검사 A15]` 실패 확정(`_fatal` · `reap_stalled`)은 **모든 판**의 읽은 값을 지운다(고객이 고친 값은 남긴다).

☆먼저 채우기로 2판이 생긴 뒤 일꾼이 죽어 `stalled`/`fatal` 이 되면 전에는 1판 값만 지워, 조회 응답(`view` 는 현재 판을 읽는다)의
  `sources[].items` · `needs_review` 에 실패한 접수의 값이 남았다(웹은 `fatal.detail` 만 그리지만 API · 개인 AI 입구에는 보인다).
"""
from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from app.domains.travel_ops.components.intake import pipeline


class _Cur:
    def __init__(self, log):
        self.log, self.rowcount = log, 1

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        self.log.append((" ".join(sql.split()), params))


class _Conn:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @contextmanager
    def transaction(self):
        yield

    def cursor(self):
        return _Cur(self.log)


def _deletes(log):
    return [sql for sql, _ in log if sql.startswith("DELETE FROM intake_claims")]


def test_fatal_clears_every_revision_but_keeps_customer_values():
    log: list = []

    @contextmanager
    def connect():
        yield _Conn(log)

    pipeline._fatal(connect, "unit", uuid4(), "reading_failed", "x")       # noqa: SLF001
    (sql,) = _deletes(log)
    assert "revision" not in sql and "method <> 'customer'" in sql


def test_reaping_a_stalled_intake_clears_every_revision(monkeypatch):
    import app.core.settings as settings

    monkeypatch.setattr(settings, "get_guardrails", lambda: {"travel.op_stream.intake_stalled_seconds": 60})
    log: list = []
    pipeline.reap_stalled(_Conn(log), tenant_id="unit", intake_id=uuid4())
    (sql,) = _deletes(log)
    assert "revision" not in sql and "method <> 'customer'" in sql
