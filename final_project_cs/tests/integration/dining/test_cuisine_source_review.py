"""Independent edge cases for source ordering and treating menu text as data."""
from tests.integration.dining.test_cuisine_source_records import NOW, record as record, tags


def test_equal_fetch_times_choose_first_record_id(conn, place, record):
    uid = place()
    record(uid, {"firstmenu": "갈비"}, fetched_at=NOW)
    record(uid, {"firstmenu": "파스타"}, fetched_at=NOW)
    assert tags(conn, uid) == ["고기"]
    assert conn.execute("SELECT dining.classify_category(%s)", (uid,)).fetchone()[0] == "한식"


def test_menu_sql_metacharacters_are_only_text(conn, place, record):
    uid = place()
    record(uid, {"firstmenu": "'); DROP TABLE dining.dn_place; -- 갈비"}, fetched_at=NOW)
    assert tags(conn, uid) == ["고기"]
    assert conn.execute("SELECT count(*) FROM dining.dn_place WHERE place_uid=%s", (uid,)).fetchone()[0] == 1


def test_unrecognized_menu_does_not_resurrect_old_tags(conn, place, record):
    from datetime import timedelta
    uid = place()
    record(uid, {"firstmenu": "갈비"}, fetched_at=NOW)
    record(uid, {"treatmenu": "계절 특별 정식"}, fetched_at=NOW + timedelta(seconds=1))
    assert tags(conn, uid) is None
