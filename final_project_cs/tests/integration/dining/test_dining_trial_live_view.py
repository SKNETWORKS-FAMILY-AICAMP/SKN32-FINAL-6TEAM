# -*- coding: utf-8 -*-
"""등록 여행 식당 카드의 캐치테이블 시험 값 읽기(`ledger.trial_live`) — 실제 뷰 `v_live_check_fresh_trial` 로 본다.

`[2026-10-19 사용자 지시]` 계획: `wiki/records/plans/2026-10-16_catchtable_trial_live_card.md`.
지키는 것: 시험 출처의 지금 값만 · 낡은 값 · 실패 · 모름은 안 실림 · 다른 출처는 안 실림 · 원장과 안 이어진 장소는 빈 목록.

    python -m pytest tests/integration/dining/test_dining_trial_live_view.py -q
"""
from __future__ import annotations

import uuid

import pytest

from app.domains.travel_ops.instances.dining.ledger import trial_live

TENANT = "test"


def record(conn, place_uid, topic, *, source="catchtable_trial", outcome="ok", state="yes", num=None, detail=None):
    return conn.execute("SELECT dining.record_live_check(%s, %s, %s, %s, %s, %s, %s)",
                        (place_uid, source, topic, outcome, state, num, detail)).fetchone()[0]


@pytest.fixture
def link(conn):
    """코어 장소 ↔ 원장 가게 연결을 만들고 시험이 끝나면 지운다 — 공용 `place` 정리가 가게를 지우기 전에."""
    made: list[str] = []

    def make(tenant: str, place_uid: str) -> str:
        core_id = str(uuid.uuid4())
        conn.execute("INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by) "
                     "VALUES (%s, %s, %s, 'test')", (tenant, core_id, place_uid))
        made.append(core_id)
        return core_id

    yield make
    for core_id in made:
        conn.execute("DELETE FROM dining.dn_core_place_link WHERE core_place_id = %s", (core_id,))


def test_웨이팅과_빈자리를_주제_순서로_싣는다(conn, place):
    uid = place()
    record(conn, uid, "vacancy", state="no")
    record(conn, uid, "waiting", num=41, detail="현재 웨이팅 41팀")

    [got] = trial_live(conn, TENANT, [{"attributes": {"dining_place_uid": uid}}])

    assert [row["topic"] for row in got] == ["waiting", "vacancy"]
    assert got[0]["state"] == "yes" and got[0]["num"] == 41 and got[0]["detail"] == "현재 웨이팅 41팀"
    assert got[0]["source"] == "catchtable_trial" and got[0]["asked_at"].endswith("+09:00")
    assert got[1]["state"] == "no"


def test_같은_주제는_가장_최근_하나만(conn, place):
    uid = place()
    record(conn, uid, "waiting", num=12)
    record(conn, uid, "waiting", num=30)

    [got] = trial_live(conn, TENANT, [{"attributes": {"dining_place_uid": uid}}])

    assert [row["num"] for row in got] == [30]


def test_낡은_값은_안_실린다(conn, place):
    uid = place()
    check = record(conn, uid, "waiting", num=41)
    conn.execute("UPDATE dining.dn_live_check SET asked_at = now() - interval '10 minutes' WHERE check_id=%s", (check,))

    assert trial_live(conn, TENANT, [{"attributes": {"dining_place_uid": uid}}]) == [[]]


def test_실패한_조회와_모름은_안_실린다(conn, place):
    uid = place()
    record(conn, uid, "waiting", outcome="blocked", state="unknown")
    record(conn, uid, "vacancy", state="unknown")

    assert trial_live(conn, TENANT, [{"attributes": {"dining_place_uid": uid}}]) == [[]]


def test_다른_출처는_안_실린다(conn, place):
    uid = place()
    record(conn, uid, "waiting", source="auto_map_check", num=5)

    assert trial_live(conn, TENANT, [{"attributes": {"dining_place_uid": uid}}]) == [[]]


def test_코어_장소는_원장_연결로_찾고_안_이어진_장소는_빈_목록(conn, place, link):
    linked_uid = place()
    core_id = link(TENANT, linked_uid)
    record(conn, linked_uid, "waiting", num=7)

    got = trial_live(conn, TENANT, [{"place_id": core_id}, {"place_id": str(uuid.uuid4())}, None])

    assert [len(rows) for rows in got] == [1, 0, 0]
    assert got[0][0]["num"] == 7


def test_다른_테넌트의_연결로는_찾지_않는다(conn, place, link):
    uid = place()
    core_id = link("other", uid)
    record(conn, uid, "waiting", num=7)

    assert trial_live(conn, TENANT, [{"place_id": core_id}]) == [[]]
