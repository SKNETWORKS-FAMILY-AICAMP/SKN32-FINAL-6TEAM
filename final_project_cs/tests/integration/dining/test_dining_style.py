"""음식 결(231)의 회귀 시험. `[2026-10-12]`

막는 것은 규칙이다 — 대표메뉴가 먼저인가, 겹치는 낱말의 순서(갈비탕 · 생선구이 · 등심돈까스 · 회덮밥),
모르는 것을 지어내지 않는가, 사람이 고친 값을 덮지 않는가.

대표 분류 시험(`test_dining_category.py`)처럼 합성 장소에 원문을 직접 붙인다. DB 가 없으면 통째로 건너뛴다.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

KST = timezone(timedelta(hours=9))


@pytest.fixture
def record(conn):
    loads: list[str] = []

    def attach(place_uid: str, raw: dict, *, fetched_at: datetime | None = None) -> None:
        load_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, "
            "schema_version, scope, row_count, status) VALUES "
            "(%s, 'synthetic_scenario', %s, 'test', 'test', 1, 'loaded')",
            (load_id, fetched_at or datetime.now(KST)))
        conn.execute(
            "INSERT INTO dining.dn_source_record (load_id, source_code, external_id, "
            "place_uid, match_status, raw_json) VALUES "
            "(%s, 'synthetic_scenario', %s, %s, 'confirmed', %s::jsonb)",
            (load_id, f"test:{uuid.uuid4()}", place_uid, json.dumps(raw, ensure_ascii=False)))
        loads.append(load_id)

    yield attach
    for load_id in loads:
        conn.execute("DELETE FROM dining.dn_source_record WHERE load_id = %s", (load_id,))
        conn.execute("DELETE FROM dining.dn_load_meta WHERE load_id = %s", (load_id,))


def of_text(conn, text: str | None) -> str | None:
    return conn.execute("SELECT dining.style_of_text(%s)", (text,)).fetchone()[0]


def classify(conn, place_uid: str) -> str | None:
    return conn.execute("SELECT dining.classify_style(%s)", (place_uid,)).fetchone()[0]


def stored(conn, place_uid: str) -> tuple[str | None, str | None]:
    return conn.execute("SELECT style, style_method FROM dining.dn_place WHERE place_uid = %s",
                        (place_uid,)).fetchone()


@pytest.mark.parametrize("text, style", [
    ("한우모듬", "고기구이"),
    ("유황 생삼겹", "고기구이"),
    ("갈비탕", "국물요리"),             # 국물요리가 고기구이보다 먼저
    ("고등어구이", "해산물"),           # 해산물이 고기구이보다 먼저
    ("등심돈까스", "돈가스·튀김"),      # 돈가스가 고기구이보다 먼저
    ("특회덮밥", "해산물"),             # 해산물이 덮밥보다 먼저
    ("삼계탕", "닭요리"),               # 닭요리가 국물요리보다 먼저
    ("양지 쌀국수", "아시아요리"),      # 아시아요리가 면보다 먼저
    ("물냉면", "면"),
    ("간짜장", "면"),
    ("탕수육", "중식요리"),
    ("한정식 코스요리", "한상차림"),
    ("신당동떡볶이", "분식"),
    ("에스프레소", "커피·차"),
    ("공주밤팥빵", "베이커리·디저트"),
    ("봉골레", "이탈리안"),
    ("회관", None),                      # 「회」는 회관이 아니다
    ("코스요리", None),                  # 모르는 것은 비운다
    ("", None),
    (None, None),
])
def test_문장_하나에서_결_하나(conn, text, style):
    assert of_text(conn, text) == style


def test_대표메뉴가_이름보다_먼저다(conn, place, record):
    uid = place("성수 칼국수")
    record(uid, {"firstmenu": "한우곱창", "treatmenu": "칼국수"})
    assert classify(conn, uid) == "고기구이"


def test_대표메뉴가_안_걸리면_이름_다음_취급메뉴(conn, place, record):
    uid = place("노루정")
    record(uid, {"firstmenu": "코스요리", "treatmenu": "물회 / 모둠회"})
    assert classify(conn, uid) == "해산물"
    named = place("청계 냉면")
    record(named, {"firstmenu": "코스요리", "treatmenu": "물회"})
    assert classify(conn, named) == "면"


def test_어디서도_안_걸리면_비운다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "디너코스", "treatmenu": "런치코스"})
    assert classify(conn, uid) is None


def test_다시_돌리면_채우고_두_번째는_아무것도_바꾸지_않는다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "한우모듬"})
    conn.execute("SELECT dining.refresh_style()")
    assert stored(conn, uid) == ("고기구이", "rule")
    conn.execute("SELECT dining.refresh_style()")
    assert stored(conn, uid) == ("고기구이", "rule")


def test_사람이_고친_값은_규칙이_덮지_않는다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "한우모듬"})
    conn.execute("UPDATE dining.dn_place SET style = '한상차림', style_method = 'manual' WHERE place_uid = %s", (uid,))
    conn.execute("SELECT dining.refresh_style()")
    assert stored(conn, uid) == ("한상차림", "manual")


def test_칸에_없는_결은_원장이_받지_않는다(conn, place):
    import psycopg

    uid = place("무명")
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("UPDATE dining.dn_place SET style = '고기', style_method = 'manual' WHERE place_uid = %s", (uid,))
