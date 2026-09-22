"""판정 SQL 의 회귀 시험.

왜 필요한가.
    판정 규칙이 전부 SQL 에 있는데 시험이 없었다. 파서는 회귀 시험 34개가
    막고 있지만 open_at_slot 은 맨몸이라, 021 을 고치면 아무도 모른다.

    여기서 막는 것은 규칙이다 — 모름을 없음으로 바꾸지 않는가,
    자정을 넘긴 영업을 전날에서 찾는가, 브레이크 사이를 닫힘으로 보는가,
    물러난 규칙이 되살아나지 않는가.

적재한 200건에 기대지 않는다.
    자료는 바뀐다. 「대돈집이 화요일에 연다」로 시험을 쓰면 자료를 갈 때마다
    시험이 깨진다. 여기서는 합성 장소를 직접 세워 쓴다. 규칙만 본다.

돌리는 법
    DB 가 있어야 한다. 없으면 통째로 건너뛴다.

        python -m pytest tests/integration/dining -q

    DINING_TEST_DSN 으로 접속을 정할 수 있다. 없으면 5433 의 postgres 에
    붙어 시험용 DB 를 만들고 끝나면 지운다.
"""
from __future__ import annotations

import glob
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
MIGRATIONS = os.path.join(ROOT, "app", "infrastructure", "db", "migrations")

#: 022 는 코어 places 표가 있어야 올라간다. 판정과 무관하므로 뺀다.
SKIP = {"022_dining_matcher.sql"}

TENANT = "test"
#: 2026-09-21 은 월요일이다. 요일 계산이 섞이지 않게 고정한다.
MONDAY = date(2026, 9, 21)


def _admin_dsn() -> str:
    port = os.environ.get("DINING_PG_PORT", "5433")
    user = os.environ.get("DINING_DB_USER", "postgres")
    return f"postgresql://{user}@localhost:{port}/postgres"


def at(day_offset: int, hhmm: str) -> datetime:
    """월요일 기준 며칠 뒤 몇 시. 시험을 읽기 쉽게 하려는 것뿐이다."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    return datetime.combine(MONDAY + timedelta(days=day_offset),
                            datetime.min.time(), tzinfo=KST).replace(
        hour=hour % 24, minute=minute) + timedelta(days=hour // 24)


@pytest.fixture(scope="session")
def conn():
    psycopg = pytest.importorskip("psycopg", reason="psycopg 가 없다")
    dsn = os.environ.get("DINING_TEST_DSN")
    made = None
    if dsn is None:
        name = f"dining_test_{os.getpid()}"
        try:
            admin = psycopg.connect(_admin_dsn(), connect_timeout=5, autocommit=True)
        except Exception as exc:                        # noqa: BLE001
            pytest.skip(f"DB 에 붙지 못했다: {str(exc).splitlines()[0]}")
        with admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            admin.execute(f'CREATE DATABASE "{name}"')
        made = name
        dsn = _admin_dsn().rsplit("/", 1)[0] + "/" + name

    conn = psycopg.connect(dsn, autocommit=True)
    for path in sorted(glob.glob(os.path.join(MIGRATIONS, "[0-9]*_dining_*.sql"))):
        if os.path.basename(path) in SKIP:
            continue
        conn.execute(open(path, encoding="utf-8").read())
    yield conn
    conn.close()
    if made:
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{made}"')


@pytest.fixture
def place(conn):
    """합성 장소를 하나 만들고 시험이 끝나면 지운다."""
    made: list[str] = []

    def make(name: str = "시험식당", lat=37.5, lng=127.0) -> str:
        uid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO dining.dn_place (place_uid, name_ko, area, record_status, "
            "is_synthetic, lat, lng) VALUES (%s, %s, '시험', 'active', true, %s, %s)",
            (uid, f"{name}-{uid[:8]}", lat, lng))
        made.append(uid)
        return uid

    yield make
    for uid in made:
        conn.execute("DELETE FROM dining.dn_hours_interval i USING dining.dn_hours_rule r "
                     "WHERE i.rule_id = r.rule_id AND r.place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_hours_rule WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_closure_rule WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_attribute WHERE place_uid = %s", (uid,))
        # 관측과 휴무 범위도 장소를 붙들고 있다. 빼먹으면 지우다 외래키에 걸린다.
        conn.execute("DELETE FROM dining.dn_live_check WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_closure_coverage WHERE place_uid = %s", (uid,))
        conn.execute("DELETE FROM dining.dn_place WHERE place_uid = %s", (uid,))


def add_hours(conn, place_uid: str, weekday: int, spans, *, retired=False) -> str:
    """그 요일의 영업 구간. spans 는 (여는 분, 닫는 분, 라스트오더) 목록."""
    rule_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO dining.dn_hours_rule (rule_id, place_uid, source_code, entered_by, "
        "verified_at, rule_kind, weekday, coverage, break_state, extract_method, "
        "rules_version, valid_from, retired_at) VALUES "
        "(%s, %s, 'synthetic_scenario', 'test', now(), 'weekly', %s, 'intervals', "
        "%s, 'synthetic', 'test', %s, %s)",
        (rule_id, place_uid, weekday, "present" if len(spans) > 1 else "none",
         MONDAY - timedelta(days=30), datetime.now(KST) if retired else None))
    for seq, (open_min, close_min, lo) in enumerate(spans, 1):
        conn.execute(
            "INSERT INTO dining.dn_hours_interval (rule_id, seq, open_min, close_min, "
            "last_order_min, last_order_state) VALUES (%s, %s, %s, %s, %s, %s)",
            (rule_id, seq, open_min, close_min, lo,
             "present" if lo is not None else "unknown"))
    return rule_id


def add_closure(conn, place_uid: str, **kw) -> None:
    conn.execute(
        "INSERT INTO dining.dn_closure_rule (place_uid, source_code, entered_by, "
        "verified_at, pattern_kind, weekday, holiday_name, holiday_scope, "
        "extract_method, valid_from) VALUES "
        "(%s, 'synthetic_scenario', 'test', now(), %s, %s, %s, %s, 'synthetic', %s)",
        (place_uid, kw["pattern_kind"], kw.get("weekday"), kw.get("holiday_name"),
         kw.get("holiday_scope"), MONDAY - timedelta(days=30)))


def open_at(conn, place_uid: str, start, end=None):
    return conn.execute("SELECT dining.open_at_slot(%s, %s, %s)",
                        (place_uid, start, end)).fetchone()[0]


# ── 모름을 없음으로 바꾸지 않는다 ─────────────────────────────

def test_규칙이_없는_요일은_모름이지_닫힘이_아니다(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])          # 월요일만 있다
    assert open_at(conn, uid, at(1, "12:00")) is None     # 화요일은 모름


def test_장소는_있는데_규칙이_하나도_없으면_모름(conn, place):
    uid = place()
    assert open_at(conn, uid, at(0, "12:00")) is None


def test_휴무로_확인된_날은_닫힘이다(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])
    add_closure(conn, uid, pattern_kind="weekly", weekday=1)
    assert open_at(conn, uid, at(0, "12:00")) is False    # 모름이 아니라 닫힘


# ── 구간 판정 ────────────────────────────────────────────────

def test_여는_시각(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])          # 11:00~22:00
    assert open_at(conn, uid, at(0, "12:00"), at(0, "13:00")) is True


def test_열기_전과_닫은_뒤(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])
    assert open_at(conn, uid, at(0, "10:00")) is False
    assert open_at(conn, uid, at(0, "23:00")) is False


def test_식사가_영업_종료를_넘기면_닫힘(conn, place):
    """도착만 보지 않는다. 21시 30분에 들어가 두 시간 먹을 수는 없다."""
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])          # 22:00 종료
    assert open_at(conn, uid, at(0, "21:30"), at(0, "23:30")) is False


def test_브레이크_사이는_닫힘(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 900, None), (1020, 1320, None)])
    assert open_at(conn, uid, at(0, "16:00")) is False
    assert open_at(conn, uid, at(0, "13:00")) is True
    assert open_at(conn, uid, at(0, "18:00")) is True


def test_라스트오더를_넘기면_닫힘(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, 1290)])          # LO 21:30
    assert open_at(conn, uid, at(0, "21:00")) is True
    assert open_at(conn, uid, at(0, "21:45")) is False


def test_라스트오더를_모르면_판정에서_뺀다(conn, place):
    """P-02. 값이 없다고 위반으로 만들지 않는다. 경고는 따로 낸다."""
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])
    assert open_at(conn, uid, at(0, "21:45")) is True


# ── 자정 넘김 ────────────────────────────────────────────────

def test_새벽_방문은_전날_영업의_연장이다(conn, place):
    """기능정의서 F-01. 새벽 한 시는 그날 규칙이 아니라 전날 구간이다."""
    uid = place()
    add_hours(conn, uid, 1, [(1080, 1560, None)])         # 월 18:00 ~ 화 02:00
    assert open_at(conn, uid, at(1, "01:00")) is True     # 화요일 새벽


def test_전날이_휴무면_새벽도_닫힘(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(1080, 1560, None)])
    add_closure(conn, uid, pattern_kind="weekly", weekday=1)
    assert open_at(conn, uid, at(1, "01:00")) is not True


def test_전날_구간을_넘긴_새벽은_모름(conn, place):
    """02:00 에 끝나는데 03:00 에 물으면 그날 규칙이 없으므로 모름이다."""
    uid = place()
    add_hours(conn, uid, 1, [(1080, 1560, None)])
    assert open_at(conn, uid, at(1, "03:00")) is None


def test_자정을_넘는_날은_코어_형식으로_내보내지_않는다(conn, place):
    """코어 open_during 은 두 값을 같은 날짜에 붙여 02:00 을 오전으로 읽는다.
    잘라 내보내면 실제보다 좁아 멀쩡한 집을 거른다. 둘 다 틀리므로 비운다."""
    uid = place()
    add_hours(conn, uid, 1, [(1080, 1560, None)])
    got = conn.execute("SELECT dining.core_attributes(%s, %s)", (uid, MONDAY)).fetchone()[0]
    assert got == {}


# ── 종료 임박 경고 ───────────────────────────────────────────

def test_라스트오더를_모르고_종료가_임박하면_경고(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])          # 22:00 종료
    check = conn.execute("SELECT dining.needs_last_order_check(%s, %s, %s)",
                         (uid, at(0, "21:30"), at(0, "21:50"))).fetchone()[0]
    assert check is True


def test_이른_시각에는_경고하지_않는다(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(660, 1320, None)])
    check = conn.execute("SELECT dining.needs_last_order_check(%s, %s, %s)",
                         (uid, at(0, "12:00"), at(0, "13:00"))).fetchone()[0]
    assert check is False


# ── 물러난 규칙 ──────────────────────────────────────────────

def test_물러난_규칙은_판정에_쓰이지_않는다(conn, place):
    """사람이 확인한 값으로 갈아끼울 때 옛 규칙이 되살아나면 안 된다."""
    uid = place()
    add_hours(conn, uid, 1, [(0, 1439, None)], retired=True)   # 하루 종일 (물러남)
    assert open_at(conn, uid, at(0, "12:00")) is None


def test_물러나지_않은_규칙만_보인다(conn, place):
    uid = place()
    add_hours(conn, uid, 1, [(0, 1439, None)], retired=True)
    add_hours(conn, uid, 1, [(660, 1320, None)])
    rows = conn.execute("SELECT count(*) FROM dining.day_intervals(%s, %s)",
                        (uid, MONDAY)).fetchone()[0]
    assert rows == 1


# ── 겹침 방지 ────────────────────────────────────────────────

def test_한_규칙_안에서_구간이_겹치면_막는다(conn, place):
    """EXCLUDE 제약. 겹친 구간이 들어가면 판정이 두 번 참이 된다."""
    import psycopg
    uid = place()
    with pytest.raises(psycopg.errors.ExclusionViolation):
        add_hours(conn, uid, 1, [(660, 1320, None), (1000, 1400, None)])


# ── 조건 ────────────────────────────────────────────────────

def test_모르는_조건은_참도_거짓도_아니다(conn, place):
    uid = place()
    got = conn.execute("SELECT dining.meets_condition(%s, 'card_payment')",
                       (uid,)).fetchone()[0]
    assert got is None


def test_불가로_확인된_조건은_거짓(conn, place):
    uid = place()
    conn.execute(
        "INSERT INTO dining.dn_attribute (place_uid, source_code, entered_by, "
        "verified_at, attr_code, value_state, extract_method, valid_from) VALUES "
        "(%s, 'synthetic_scenario', 'test', now(), 'card_payment', 'no', "
        "'synthetic', %s)", (uid, MONDAY))
    got = conn.execute("SELECT dining.meets_condition(%s, 'card_payment')",
                       (uid,)).fetchone()[0]
    assert got is False


# ── 대체 후보 ────────────────────────────────────────────────

def test_닫힌_곳은_후보에서_빠지고_모르는_곳은_남는다(conn, place):
    """좁게 잡는 오류가 더 나쁘다. 모르는 곳을 걸러내면 사용자가 아예 안 간다."""
    origin = place("원래", lat=37.5000, lng=127.0000)
    add_hours(conn, origin, 1, [(660, 1320, None)])

    near_open = place("여는곳", lat=37.5010, lng=127.0000)     # 약 110m
    add_hours(conn, near_open, 1, [(660, 1320, None)])

    near_closed = place("닫는곳", lat=37.5011, lng=127.0000)
    add_hours(conn, near_closed, 1, [(660, 1320, None)])
    add_closure(conn, near_closed, pattern_kind="weekly", weekday=1)

    near_unknown = place("모르는곳", lat=37.5012, lng=127.0000)  # 규칙 없음

    rows = conn.execute(
        "SELECT name_ko, open_state FROM dining.alternative_pool(%s, %s, %s)",
        (origin, at(0, "12:00"), at(0, "13:00"))).fetchall()
    names = {name.split("-")[0]: state for name, state in rows}

    assert names.get("여는곳") is True
    assert "닫는곳" not in names
    assert "모르는곳" in names and names["모르는곳"] is None


# ──────────────────────────────────────────────────────────────
# 시험 갈래와 재질문 (031)
# ──────────────────────────────────────────────────────────────
#
# 026 은 「판정에 쓸 수 있나」 하나로 재질문까지 판단했다. 그래서 시험 출처의
# 답도 실패한 조회도 영영 「안 물었다」로 남았다. 손으로 돌 때는 안 보이지만
# 감시 틱에 물리면 같은 곳을 끝없이 다시 묻는다.

def record(conn, place_uid, source, topic, outcome="ok", state="yes"):
    return conn.execute(
        "SELECT dining.record_live_check(%s, %s, %s, %s, %s)",
        (place_uid, source, topic, outcome, state)).fetchone()[0]


def test_시험_출처는_본_갈래_판정에_닿지_않는다(conn, place):
    uid = place()
    record(conn, uid, "catchtable_trial", "waiting")
    got = conn.execute("SELECT dining.live_state(%s, 'waiting')", (uid,)).fetchone()[0]
    assert got is None


def test_시험_갈래에서는_같은_값이_보인다(conn, place):
    uid = place()
    record(conn, uid, "catchtable_trial", "waiting")
    got = conn.execute("SELECT dining.live_state(%s, 'waiting', true)",
                       (uid,)).fetchone()[0]
    assert got is not None
    assert got["state"] == "yes"
    assert got["source"] == "catchtable_trial"


def test_시험_갈래도_실패한_조회는_값으로_쓰지_않는다(conn, place):
    uid = place()
    # 갈래가 갈린 것은 출처 등급 하나뿐이다. 성패는 양쪽 다 따진다.
    record(conn, uid, "catchtable_trial", "vacancy", outcome="blocked", state="unknown")
    got = conn.execute("SELECT dining.live_state(%s, 'vacancy', true)",
                       (uid,)).fetchone()[0]
    assert got is None


def test_막힌_조회도_잠시_재질문을_막는다(conn, place):
    uid = place()
    # 실패의 TTL 은 120초다. 영영 막는 것이 아니라 잠깐 쉰다.
    before = conn.execute("SELECT dining.check_prompt(%s, %s, true)",
                          (uid, at(1, "12:00"))).fetchone()[0]
    assert "waiting" in before["topics"]

    record(conn, uid, "catchtable_trial", "waiting", outcome="blocked", state="unknown")
    after = conn.execute("SELECT dining.check_prompt(%s, %s, true)",
                         (uid, at(1, "12:00"))).fetchone()[0]
    assert after is None or "waiting" not in after["topics"]


def test_시험_출처의_답도_재질문을_막는다(conn, place):
    uid = place()
    record(conn, uid, "catchtable_trial", "waiting")
    after = conn.execute("SELECT dining.check_prompt(%s, %s, true)",
                         (uid, at(1, "12:00"))).fetchone()[0]
    assert after is None or "waiting" not in after["topics"]
