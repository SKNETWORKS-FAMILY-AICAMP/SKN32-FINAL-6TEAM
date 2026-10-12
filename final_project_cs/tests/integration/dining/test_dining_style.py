"""음식 결(231)의 회귀 시험. `[2026-10-12]`

막는 것은 규칙이다 — 미쉐린 요리 종류 · 대표메뉴가 먼저인가, 겹치는 낱말의 순서(갈비탕 · 생선구이 · 등심돈까스 · 회덮밥),
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

    def attach(place_uid: str, raw: dict, *, fetched_at: datetime | None = None,
               source: str = "synthetic_scenario") -> None:
        load_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, "
            "schema_version, scope, row_count, status) VALUES "
            "(%s, %s, %s, 'test', 'test', 1, 'loaded')",
            (load_id, source, fetched_at or datetime.now(KST)))
        conn.execute(
            "INSERT INTO dining.dn_source_record (load_id, source_code, external_id, "
            "place_uid, match_status, raw_json) VALUES "
            "(%s, %s, %s, %s, 'confirmed', %s::jsonb)",
            (load_id, source, f"test:{uuid.uuid4()}", place_uid, json.dumps(raw, ensure_ascii=False)))
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
    ("대인 뷔페", "뷔페"),
    ("무한리필 샤부샤부", "국물요리"),   # 무한리필은 뷔페가 아니다
    ("흑돼지 오겹살", "고기구이"),
    ("세종정찬", "한상차림"),
    ("에스프레소", "커피·차"),           # 「스프」를 넣지 않는다 — 에스프레소가 국물요리가 됐다(2026-10-12)
    ("각시정식", None),                  # 「정식」은 결을 말하지 않는다
    ("전통주 페어링", None),
    ("코스요리", None),                  # 코스는 여기서 내지 않는다(course_of_text)
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
    record(uid, {"firstmenu": "오감", "treatmenu": "따동 / 펑요우"})
    assert classify(conn, uid) is None


def test_무엇의_코스인지_모르면_코스다이닝(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "디너코스", "treatmenu": "런치코스"})
    assert classify(conn, uid) == "코스·다이닝"


def test_코스여도_결이_보이면_그_결이_먼저다(conn, place, record):
    """대표메뉴가 「코스 메뉴」여도 취급메뉴에 초밥이 보이면 초밥 — 코스는 마지막 근거다."""
    uid = place("무명")
    record(uid, {"firstmenu": "코스 메뉴", "treatmenu": "오토로초밥 / 아카미초밥"})
    assert classify(conn, uid) == "초밥"
    named = place("삼호복집")
    record(named, {"firstmenu": "코스요리"})
    assert classify(conn, named) == "해산물"


@pytest.mark.parametrize("cuisine, style", [
    ("바비큐", "고기구이"),
    ("메밀국수", "면"),
    ("돼지국밥", "국물요리"),
    ("스시", "초밥"),
    ("이탤리언", "이탈리안"),
    ("타이", "아시아요리"),
    ("쿠시아게", "돈가스·튀김"),
    ("프렌치", None),                    # 코스인지 가이드가 말하지 않는다 — 사람이 정한다
    ("이탤리언 컨템퍼러리", None),
    ("한식, 클래식 퀴진", None),
    ("한식", None),                      # 나라만 말한다
    (None, None),
])
def test_미쉐린_요리_종류에서_결_하나(conn, cuisine, style):
    assert conn.execute("SELECT dining.style_of_guide(%s)", (cuisine,)).fetchone()[0] == style


def test_미쉐린_요리_종류가_대표메뉴보다_먼저다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "코스요리", "treatmenu": "물회"})
    record(uid, {"상호": "무명", "요리": "냉면"}, source="michelin_guide")
    assert classify(conn, uid) == "면"


def test_미쉐린_요리_종류가_애매하면_원래_순서대로(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "코스요리"})
    record(uid, {"상호": "무명", "요리": "프렌치 컨템퍼러리"}, source="michelin_guide")
    assert classify(conn, uid) == "코스·다이닝"
    bare = place("무명")
    record(bare, {"상호": "무명", "요리": "한식"}, source="michelin_guide")
    assert classify(conn, bare) is None


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
