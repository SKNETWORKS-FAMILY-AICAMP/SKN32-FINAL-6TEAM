"""대표 분류(034)의 회귀 시험.

막는 것은 규칙이다 — 대표메뉴가 먼저인가, 모르는 것을 기타로 떨어뜨리지 않는가,
메뉴 없는 원문이 새로 붙어도 분류가 뒤집히지 않는가, 사람이 고친 값을 덮지 않는가.

판정 시험처럼 적재한 200건에 기대지 않는다. 합성 장소에 원문을 직접 붙인다.

돌리는 법은 판정 시험과 같다. DB 가 없으면 통째로 건너뛴다.

    python -m pytest tests/integration/dining -q
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

KST = timezone(timedelta(hours=9))


@pytest.fixture
def record(conn):
    """장소에 원문을 붙인다. 붙인 적재 기록은 시험이 끝나면 지운다.

    원문 자체는 place 픽스처가 장소와 함께 지운다.
    """
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


def classify(conn, place_uid: str) -> str | None:
    return conn.execute("SELECT dining.classify_category(%s)", (place_uid,)).fetchone()[0]


def of_text(conn, text: str | None) -> str | None:
    return conn.execute("SELECT dining.category_of_text(%s)", (text,)).fetchone()[0]


def stored(conn, place_uid: str) -> tuple[str | None, str | None]:
    return conn.execute(
        "SELECT category, category_method FROM dining.dn_place WHERE place_uid = %s",
        (place_uid,)).fetchone()


# ── 칸은 일곱 개다 ──────────────────────────────────────────────

def test_일곱_칸_밖의_값은_DB가_거부한다(conn, place):
    psycopg = pytest.importorskip("psycopg")
    uid = place()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE dining.dn_place SET category = '분식', category_method = 'manual' "
                     "WHERE place_uid = %s", (uid,))


def test_분류와_출처는_함께_비거나_함께_찬다(conn, place):
    psycopg = pytest.importorskip("psycopg")
    uid = place()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE dining.dn_place SET category = '한식' WHERE place_uid = %s", (uid,))


# ── 모르는 것은 기타가 아니다 ────────────────────────────────────

def test_안_걸리면_NULL이지_미상이_아니다(conn):
    # 미상은 세 곳을 다 본 뒤에 붙인다. 한 문장이 미상을 말하면 다음을 볼 수 없다.
    assert of_text(conn, "코스요리") is None
    assert of_text(conn, "") is None
    assert of_text(conn, None) is None


def test_근거가_없으면_미상이다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "코스요리", "treatmenu": ""})
    assert classify(conn, uid) == "미상"


def test_원문이_아예_없어도_미상이다(conn, place):
    assert classify(conn, place("무명")) == "미상"


def test_여섯_칸_밖의_음식은_기타다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "소고기 쌀국수"})
    assert classify(conn, uid) == "기타"


# ── 무엇을 먼저 보는가 ──────────────────────────────────────────

def test_대표메뉴가_취급메뉴를_이긴다(conn, place, record):
    # 오프트: 떡볶이가 대표이고 뇨끼도 판다.
    uid = place("무명")
    record(uid, {"firstmenu": "떡볶이", "treatmenu": "트러플크림뇨끼"})
    assert classify(conn, uid) == "한식"


def test_대표메뉴가_안_걸리면_이름이_취급메뉴보다_먼저다(conn, place, record):
    # 호랑이 초밥: 대표메뉴 「호랑이모듬」은 안 걸리고, 취급메뉴의 짬뽕으로 가면 중식이 된다.
    uid = place("호랑이 초밥")
    record(uid, {"firstmenu": "호랑이모듬", "treatmenu": "짬뽕 / 우동"})
    assert classify(conn, uid) == "일식"


def test_대표메뉴도_이름도_안_걸리면_취급메뉴를_본다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "시그니처세트", "treatmenu": "양지 쌀국수 / 분짜"})
    assert classify(conn, uid) == "기타"


def test_한_문장_안에서는_중식이_한식보다_먼저다(conn):
    # 「탕」이 한식에 있어도 탕수육은 중식이어야 한다.
    assert of_text(conn, "육즙돼지고기탕수육") == "중식"


def test_만두는_한식이다(conn):
    # 개성만두, 이북만두 집이 딤섬 집보다 많다.
    assert of_text(conn, "고기만두전골") == "한식"
    assert of_text(conn, "딤섬") == "중식"


def test_회관은_회가_아니다(conn):
    assert of_text(conn, "진주회관") is None
    assert of_text(conn, "가진항 물회") == "한식"


def test_베이커리는_커리가_아니다(conn):
    # 비건 목록의 「스왈로베이커리카페」가 기타로 떨어졌다.
    assert of_text(conn, "스왈로베이커리카페") == "카페디저트"
    assert of_text(conn, "치킨 커리") == "기타"


def test_타코야키는_타코가_아니다(conn):
    assert of_text(conn, "타코야키") == "일식"
    assert of_text(conn, "비리아 타코") == "기타"


# ── 원문이 새로 붙어도 뒤집히지 않는다 ───────────────────────────

def test_메뉴_없는_원문이_나중에_붙어도_대표메뉴를_잃지_않는다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "돈코츠라멘"}, fetched_at=datetime.now(KST) - timedelta(days=30))
    # 운영자 영업시간 확인처럼 메뉴 칸이 없는 원문. 더 최근이다.
    record(uid, {"월": "11:00-21:00", "확인일": "2026-09-23"})
    assert classify(conn, uid) == "일식"


def test_메뉴_원문이_여럿이면_최근_것을_본다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "짬뽕"}, fetched_at=datetime.now(KST) - timedelta(days=30))
    record(uid, {"firstmenu": "돈코츠라멘"})
    assert classify(conn, uid) == "일식"


# ── 다시 돌리기 ─────────────────────────────────────────────────

def test_다시_돌리면_채우고_두_번째는_아무것도_바꾸지_않는다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "돈코츠라멘"})
    conn.execute("SELECT dining.refresh_category()")
    assert stored(conn, uid) == ("일식", "rule")
    # migrate.py 는 매번 전부 다시 적용한다. 같은 결과여야 하고 헛되이 쓰지 않아야 한다.
    conn.execute("SELECT dining.refresh_category()")
    assert stored(conn, uid) == ("일식", "rule")


def test_사람이_고친_값은_규칙이_덮지_않는다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "돈코츠라멘"})
    conn.execute("UPDATE dining.dn_place SET category = '기타', category_method = 'manual' "
                 "WHERE place_uid = %s", (uid,))
    conn.execute("SELECT dining.refresh_category()")
    assert stored(conn, uid) == ("기타", "manual")


def test_규칙_값은_원문이_바뀌면_따라간다(conn, place, record):
    uid = place("무명")
    record(uid, {"firstmenu": "짬뽕"}, fetched_at=datetime.now(KST) - timedelta(days=30))
    conn.execute("SELECT dining.refresh_category()")
    assert stored(conn, uid) == ("중식", "rule")
    record(uid, {"firstmenu": "돈코츠라멘"})
    conn.execute("SELECT dining.refresh_category()")
    assert stored(conn, uid) == ("일식", "rule")
