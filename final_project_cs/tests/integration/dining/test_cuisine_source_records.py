"""ST4F-597: menu evidence must survive unrelated source rows and reloads."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tests.integration.dining.test_dining_category import record as record

NOW = datetime(2026, 10, 29, 12, tzinfo=timezone(timedelta(hours=9)))


def tags(conn, uid):
    return conn.execute("SELECT dining.cuisine_tags(%s)", (uid,)).fetchone()[0]


def test_menu_after_unrelated_source_is_used(conn, place, record):
    uid = place()
    record(uid, {"address": "서울"}, fetched_at=NOW)
    record(uid, {"firstmenu": "갈비"}, fetched_at=NOW + timedelta(seconds=1))
    assert tags(conn, uid) == ["고기"]


def test_latest_menu_replaces_old_tags(conn, place, record):
    uid = place()
    record(uid, {"firstmenu": "갈비"}, fetched_at=NOW)
    record(uid, {"firstmenu": "파스타"}, fetched_at=NOW + timedelta(seconds=1))
    assert tags(conn, uid) == ["면"]


def test_newer_non_menu_record_does_not_hide_menu(conn, place, record):
    uid = place()
    record(uid, {"treatmenu": "파스타"}, fetched_at=NOW)
    record(uid, {"address": "서울"}, fetched_at=NOW + timedelta(seconds=1))
    assert tags(conn, uid) == ["면"]


def test_explicitly_empty_latest_menu_stays_unknown(conn, place, record):
    uid = place()
    record(uid, {"firstmenu": "갈비"}, fetched_at=NOW)
    record(uid, {"firstmenu": None, "treatmenu": ""}, fetched_at=NOW + timedelta(seconds=1))
    assert tags(conn, uid) is None


def test_missing_menu_is_unknown_not_zero_similarity(conn, place, record):
    uid = place()
    record(uid, {"address": "서울"}, fetched_at=NOW)
    assert tags(conn, uid) is None
    assert tags(conn, str(uuid4())) is None
    assert conn.execute("SELECT dining.cuisine_similarity(%s,%s)", (uid, uid)).fetchone()[0] is None


def test_similarity_axis_receives_available_menu_evidence(conn, place, record):
    origin, candidate = place(lat=37.5, lng=127), place(lat=37.5001, lng=127)
    record(origin, {"address": "서울"}, fetched_at=NOW)
    record(origin, {"firstmenu": "갈비"}, fetched_at=NOW + timedelta(seconds=1))
    record(candidate, {"firstmenu": "갈비"}, fetched_at=NOW)
    assert conn.execute("SELECT dining.cuisine_similarity(%s,%s)", (origin, candidate)).fetchone()[0] == 1
    row = conn.execute("SELECT place_uid, reason FROM dining.suggest_alternatives(%s,%s) WHERE axis='similar'",
                       (origin, NOW)).fetchone()
    assert str(row[0]) == candidate
    assert row[1]["원래 종류"] == ["고기"]
