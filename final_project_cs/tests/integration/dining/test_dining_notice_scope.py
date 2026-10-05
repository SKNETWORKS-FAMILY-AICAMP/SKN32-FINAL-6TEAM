"""요식 알림 — 여행마다 한 번, 기록과 알림함은 한 트랜잭션 (2026-09-28 cs, 마이그레이션 220).

- 두 여행자가 같은 식당·같은 시각이면 **둘 다** 받는다(전에는 뒤 사람이 못 받았다)
- 같은 여행에는 한 번만 간다
- 알림함에 넣다 실패하면 기록도 되돌려 다음 틱에 다시 말한다(전에는 영영 안 갔다)
"""
from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

KST = timezone(timedelta(hours=9))
_TICK = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "app", "domains", "travel_ops", "instances", "dining", "tick.py")
_spec = importlib.util.spec_from_file_location("dining_tick_scope", _TICK)
tick = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tick)


def _closed_reader(place_uid, name, sentence):
    return "https://example/shop", {"closure": {"state": "yes"}}


@pytest.fixture
def tx_conn(conn):
    """트랜잭션을 쓰는 연결 — 공용 픽스처는 autocommit 이라 되돌림을 볼 수 없다."""
    psycopg = pytest.importorskip("psycopg")
    other = psycopg.connect(conn.info.dsn)
    yield other
    other.rollback()
    other.close()


def _scope(trip):
    return {"tenant_id": "test", "trip_id": trip, "item_id": str(uuid.uuid4())}


def _notices(conn, uid):
    return conn.execute("SELECT trip_id FROM dining.dn_notice WHERE place_uid = %s",
                        (uid,)).fetchall()


def test_두_여행자가_같은_식당_같은_시각이면_둘_다_받는다(conn, tx_conn, place):
    uid = place()
    now = datetime.now(KST)
    at = now + timedelta(minutes=58)
    trip_a, trip_b = str(uuid.uuid4()), str(uuid.uuid4())
    a = tick.tick_one(tx_conn, now, uid, at, fetch=_closed_reader, trial=True, scope=_scope(trip_a))
    b = tick.tick_one(tx_conn, now, uid, at, fetch=_closed_reader, trial=True, scope=_scope(trip_b))
    assert a["notice"] is not None and b["notice"] is not None
    assert {str(r[0]) for r in _notices(conn, uid)} == {trip_a, trip_b}


def test_같은_여행에는_한_번만_간다(conn, tx_conn, place):
    uid = place()
    now = datetime.now(KST)
    at, scope = now + timedelta(minutes=58), _scope(str(uuid.uuid4()))
    first = tick.tick_one(tx_conn, now, uid, at, fetch=_closed_reader, trial=True, scope=scope)
    again = tick.tick_one(tx_conn, now, uid, at, fetch=_closed_reader, trial=True, scope=scope)
    assert first["notice"] is not None
    assert again["notice"] is None and again["reason"] == "이미 말했다"


def test_알림함에_넣다_실패하면_기록도_되돌리고_다음에_다시_말한다(conn, tx_conn, place):
    uid = place()
    now = datetime.now(KST)
    at, scope = now + timedelta(minutes=58), _scope(str(uuid.uuid4()))

    def broken(_conn, _notice):
        raise RuntimeError("알림함 연결 끊김")

    failed = tick.tick_one(tx_conn, now, uid, at, fetch=_closed_reader, trial=True,
                           scope=scope, on_notice=broken)
    assert failed["notice"] is None and "되돌렸다" in failed["reason"]
    assert _notices(conn, uid) == []                     # ★기록이 남으면 다음 틱이 「이미 말했다」에 막힌다

    sent: list[dict] = []
    retried = tick.tick_one(tx_conn, now, uid, at, fetch=_closed_reader, trial=True,
                            scope=scope, on_notice=lambda _c, n: sent.append(n))
    assert retried["notice"] is not None and len(sent) == 1
    assert len(_notices(conn, uid)) == 1


def test_여행_없는_옛_호출도_그대로_돈다(conn, place):
    uid = place()
    now = datetime.now(KST)
    got = tick.tick_one(conn, now, uid, now + timedelta(minutes=58), fetch=_closed_reader, trial=True)
    assert got["notice"]["kind"] == "closed"


def test_알림함_쪽은_여행_없는_알림을_버리지_않고_거절한다():
    put = tick.outbox_notice(store=object())
    with pytest.raises(ValueError):
        put(None, {"place_uid": "p", "kind": "closed", "body": "b", "window": "T-60"})
