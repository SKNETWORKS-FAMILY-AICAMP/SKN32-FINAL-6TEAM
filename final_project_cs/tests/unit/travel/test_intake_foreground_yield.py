"""`[2026-10-27 서빙 속도]` 뒤에서 미리 준비하는 대안(`prepared.prepare`)이 다른 고객의 「읽는 중」을 늦췄다.

x600 실측(2026-10-20~26 채팅 접수 148건): 다른 접수의 대안 준비가 도는 동안 읽기(접수 → 이해 에이전트 끝) p50 12.6초 · p95 27.2초(17건),
아무것도 안 돌 때 p50 7.5초 · p95 16.6초(120건). 한 GPU 모델 · 한 API 프로세스를 같이 쓴다.

바꾼 것: 접수가 「읽는 중」(받기 → 확인 화면으로 넘기기 전까지, 먼저 채우기 포함)인 동안은 앞단(`intake/foreground.active`)으로 센다.
뒤의 미리 준비는 일정 하나를 **맡기 전에** 앞단이 빌 때까지 기다린다 — 가드레일 `travel.candidates.prepare_yield_seconds` 까지만(넘으면 로그를 남기고 진행).
맡기 전에 기다리므로 그동안 「바꾸기」는 준비를 기다리지 않고 그 자리에서 계산한다(`prepared.wait_preparing` 은 맡은 일정만 기다린다).
"""
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core import settings as settings_module
from app.domains.travel_ops.components.intake import foreground, pipeline, prepared

KST = ZoneInfo("Asia/Seoul")


def test_the_config_names_how_long_background_work_yields():
    value = settings_module.get_guardrails().get("travel.candidates.prepare_yield_seconds")
    assert isinstance(value, (int, float)) and value > 0


def test_wait_returns_at_once_when_nobody_is_reading():
    started = time.perf_counter()
    assert foreground.wait_idle(5.0) == pytest.approx(0.0, abs=0.05)
    assert time.perf_counter() - started < 0.1


def test_wait_holds_until_the_reading_ends():
    entered, release = threading.Event(), threading.Event()

    def reading():
        with foreground.active():
            entered.set()
            release.wait(2)

    t = threading.Thread(target=reading)
    t.start()
    entered.wait(2)
    threading.Timer(0.3, release.set).start()
    waited = foreground.wait_idle(5.0)
    t.join(2)
    assert 0.2 <= waited < 2.0
    assert foreground.busy() == 0


def test_wait_is_bounded_when_reading_does_not_end():
    entered, release = threading.Event(), threading.Event()

    def reading():
        with foreground.active():
            entered.set()
            release.wait(5)

    t = threading.Thread(target=reading)
    t.start()
    entered.wait(2)
    try:
        started = time.perf_counter()
        foreground.wait_idle(0.3)
        assert 0.25 <= time.perf_counter() - started < 1.5
    finally:
        release.set()
        t.join(2)


# ── 미리 준비가 일정을 맡기 전에 기다린다 ─────────────────────────────
class _Cur:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return []


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _Cur()


def _item(n):
    return {"id": f"1-{n}", "source_id": str(uuid4()), "index": n, "title": f"일정 {n}", "kind": "activity",
            "place_state": "unresolved", "place": None, "rows": []}


def test_background_preparation_waits_for_a_reading_before_claiming_items(monkeypatch):
    review = {"revision": 1, "items": [_item(0), _item(1)]}
    monkeypatch.setattr(prepared, "_current", lambda conn, tenant_id, intake_id: review)
    calls: list[tuple[float, int]] = []

    def fake_one(connect, *, tenant_id, intake_id, review, item, kakao=None, chat=None):
        calls.append((time.perf_counter(), foreground.busy()))
        return "saved"

    monkeypatch.setattr(prepared, "prepare_one", fake_one)
    entered, release = threading.Event(), threading.Event()

    def reading():
        with foreground.active():
            entered.set()
            release.wait(3)

    t = threading.Thread(target=reading)
    t.start()
    entered.wait(2)
    released_at = []

    def end_reading():
        released_at.append(time.perf_counter())
        release.set()

    threading.Timer(0.4, end_reading).start()
    out = prepared.prepare(lambda: _Conn(), tenant_id="unit", intake_id=uuid4(), which="all")
    t.join(3)
    assert out.get("saved") == 2, out
    assert len(calls) == 2
    assert all(busy == 0 for _at, busy in calls), calls           # 읽는 중에는 한 일정도 맡지 않았다
    assert all(at >= released_at[0] for at, _busy in calls)


def test_background_preparation_runs_at_once_when_idle(monkeypatch):
    review = {"revision": 1, "items": [_item(0)]}
    monkeypatch.setattr(prepared, "_current", lambda conn, tenant_id, intake_id: review)
    monkeypatch.setattr(prepared, "prepare_one", lambda connect, **kw: "saved")
    started = time.perf_counter()
    out = prepared.prepare(lambda: _Conn(), tenant_id="unit", intake_id=uuid4(), which="all")
    assert out.get("saved") == 1 and time.perf_counter() - started < 1.0


# ── 접수 처리는 확인 화면으로 넘길 때까지 앞단이다 ──────────────────────
def test_intake_processing_counts_as_foreground_while_reading(monkeypatch):
    seen: dict[str, int] = {}

    class Tx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Cur(_Cur):
        def __init__(self):
            self.rows = [(datetime(2030, 1, 1, 9, tzinfo=KST),), ("owner",)]

        def fetchone(self):
            return self.rows.pop(0) if self.rows else ("owner",)

    class Conn(_Conn):
        def transaction(self):
            return Tx()

        def cursor(self):
            return Cur()

    @contextmanager
    def connect():
        yield Conn()

    class Beat:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def stop_reading(*a, **k):
        seen["busy"] = foreground.busy()
        raise pipeline._Abandoned()

    monkeypatch.setattr(pipeline, "_Heartbeat", Beat)
    monkeypatch.setattr(pipeline, "_sources", lambda conn, tenant_id, intake_id: [
        {"source_id": "s", "position": 0, "transcript": "10:00 경복궁", "differs_json": None, "filename": None}])
    monkeypatch.setattr(pipeline, "_stage", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "with_catalog", lambda tour, connect, tenant_id: tour)
    monkeypatch.setattr(pipeline, "_our_places", lambda conn, tenant_id: [])
    monkeypatch.setattr(pipeline, "load_aliases", lambda conn, tenant_id, owner: {})
    monkeypatch.setattr(pipeline, "areas_for", lambda conn, tenant_id: {})
    monkeypatch.setattr(pipeline, "_hold_reading", lambda cur, tenant_id, intake_id: None)
    monkeypatch.setattr(pipeline, "read_source", stop_reading)
    assert pipeline.process(connect, tenant_id="unit", intake_id=uuid4(), blobs={}, see=None) == "fatal"
    assert seen["busy"] == 1
    assert foreground.busy() == 0
