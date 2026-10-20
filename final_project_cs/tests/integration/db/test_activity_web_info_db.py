# -*- coding: utf-8 -*-
"""웹 검색으로 채운 장소 정보(`ac_place_web_info`)를 **실 PostgreSQL** 로 본다 — 저장 · 읽기 · 판정에서 합치기 · 파이프라인 왕복. `[2026-10-19]`

★LLM · 카카오 · 브이월드는 가짜다(실제 호출 없음). DB 에 못 붙거나 마이그레이션 307 이 없으면 건너뛴다.
★시험 행은 시험마다 다른 표시를 붙여 실데이터와 섞이지 않게 하고, 끝나면 지운다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest

from app.domains.travel_ops.instances.activity import geocode as g
from app.domains.travel_ops.instances.activity import ledger
from app.domains.travel_ops.instances.activity import place_enrichment as pe
from app.domains.travel_ops.instances.activity import web_info as wi
from app.domains.travel_ops.instances.activity.db_search import web_info_store as store
from app.infrastructure.db.session import database_dsn, get_connection

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc
URL = "https://www.example.go.kr/info"


def _reachable() -> str | None:
    try:
        with psycopg.connect(database_dsn(), connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('activity.ac_place'), to_regclass('activity.ac_place_web_info')")
            ledger_table, web_table = cur.fetchone()
            if ledger_table is None or web_table is None:
                return "activity.ac_place · ac_place_web_info 가 없다 — migrate 먼저"
    except Exception as exc:  # noqa: BLE001
        return f"DB 에 연결할 수 없다: {type(exc).__name__}"
    return None


_SKIP = _reachable()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")


def _entry(field, value, *, days=30, source="web"):
    return wi.Entry(field, value, source, f"원문 {value}" if source == "web" else None, URL if source == "web" else None,
                    None, datetime.now(UTC) + timedelta(days=days))


@pytest.fixture()
def world():
    """원장 행 셋(운영시간 비어 있음 · 있음 · 비어 있음) + 코어 장소 넷(그 셋 + 원장 밖 하나). 끝나면 웹 정보 줄까지 지운다."""
    tag = "zw" + uuid4().hex[:8]
    tenant = "test_" + uuid4().hex
    cid_empty, cid_full, cid_old = ("T" + uuid4().hex[:12] for _ in range(3))
    off_name = f"{tag}외딴카페"
    off_key = wi.place_key(None, off_name)
    keys = [cid_empty, cid_full, cid_old, off_key]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('test', %s, 3) RETURNING load_id",
                    ("0" * 64,))
        load_id = cur.fetchone()[0]
        ids = {}
        for label, cid, name, use, rest in (("empty", cid_empty, tag + "빈궁", None, None),
                                            ("full", cid_full, tag + "찬궁", "10:00~12:00", "매주 월요일"),
                                            ("old", cid_old, tag + "옛궁", None, None)):
            cur.execute("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, usetime_text, restdate_text, load_id) "
                        "VALUES (%s,'12',%s,%s,%s,%s,%s)", (cid, name, name, use, rest, load_id))
            cur.execute("INSERT INTO places (tenant_id, name, kind, source_name, source_content_id) "
                        "VALUES (%s,%s,'activity','tour_api',%s) RETURNING place_id", (tenant, name, cid))
            ids[label] = str(cur.fetchone()[0])
        cur.execute("INSERT INTO places (tenant_id, name, kind) VALUES (%s,%s,'activity') RETURNING place_id", (tenant, off_name))
        ids["off"] = str(cur.fetchone()[0])
    try:
        yield SimpleNamespace(tenant=tenant, ids=ids, cids={"empty": cid_empty, "full": cid_full, "old": cid_old},
                              off_name=off_name, off_key=off_key)
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM activity.ac_place_web_info WHERE place_key = ANY(%s)", (keys,))
            cur.execute("DELETE FROM places WHERE tenant_id = %s", (tenant,))
            cur.execute("DELETE FROM activity.ac_place WHERE content_id = ANY(%s)", ([cid_empty, cid_full, cid_old],))
            cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id = %s", (load_id,))


def _save(key, *entries):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        assert store.save_entries(cur, key, entries, model="fake", now=datetime.now(UTC)) is True


TUESDAY, WEDNESDAY = datetime(2026, 10, 13, 10, tzinfo=KST), datetime(2026, 10, 14, 10, tzinfo=KST)


def test_empty_ledger_hours_are_filled_from_unexpired_web_values(world):
    _save(world.cids["empty"], _entry("business_hours", "09:00~18:00"), _entry("closed_days", "매주 화요일"))
    with get_connection() as conn:
        tue = ledger.state(conn, world.tenant, world.ids["empty"], TUESDAY)
        wed = ledger.state(conn, world.tenant, world.ids["empty"], WEDNESDAY)
    assert tue["closed"] is True and set(tue["web_info"]) == {"business_hours", "closed_days"}
    assert tue["web_info"]["closed_days"]["url"] == URL and tue["web_info"]["closed_days"]["quote"]
    assert (wed["closed"], wed["within_hours"]) == (False, True)


def test_ledger_values_win_over_web_values(world):
    _save(world.cids["full"], _entry("business_hours", "00:00~01:00"), _entry("closed_days", "매주 화요일"))
    with get_connection() as conn:
        tue = ledger.state(conn, world.tenant, world.ids["full"], TUESDAY)
    assert tue["closed"] is False and tue["within_hours"] is True and "web_info" not in tue     # 원장 값(월요일 휴무 · 10~12시)이 이긴다


def test_expired_web_values_and_not_found_markers_are_not_used(world):
    _save(world.cids["old"], _entry("business_hours", "09:00~18:00", days=-1), _entry("closed_days", "", source="none"))
    with get_connection() as conn:
        out = ledger.state(conn, world.tenant, world.ids["old"], TUESDAY)
    assert out is not None and "web_info" not in out and out["closed"] is not True


def test_a_place_outside_the_ledger_is_judged_from_its_web_values_only_when_they_exist(world):
    with get_connection() as conn:
        assert ledger.state(conn, world.tenant, world.ids["off"], TUESDAY) is None        # 웹 값이 없으면 모름 — 예전과 같다
    _save(world.off_key, _entry("business_hours", "10:00~20:00"), _entry("closed_days", "매주 화요일"))
    with get_connection() as conn:
        tue = ledger.state(conn, world.tenant, world.ids["off"], TUESDAY)
    assert tue["closed"] is True and tue["content_id"] is None and tue["name"] == world.off_name and "business_hours" in tue["web_info"]


def test_web_evidence_is_required_for_web_rows_by_the_database_itself():
    with get_connection() as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute("INSERT INTO activity.ac_place_web_info (place_key, field, value, source, expires_at) "
                        "VALUES ('web:zw-bad','fee','x','web', now())")


# ── 파이프라인 왕복(가짜 카카오 · LLM · 지오코더 + 실제 DB) ──────────

class Kakao:
    """카카오는 「있다」만 안다 — 이름이 맞는 곳 하나. 좌표 · 주소를 줘도 저장되지 않는다는 것을 아래에서 본다."""
    misses: dict = {}

    def __init__(self, name):
        self.name, self.asked = name, []

    def search(self, query, **kw):
        self.asked.append(query)
        return [{"name": self.name, "category_group": "CE7", "category": "음식점 > 카페", "latitude": 37.1, "longitude": 127.1,
                 "address": "카카오가 준 주소 - 저장하면 안 된다"}]


class WebLLM:
    def __init__(self, output):
        self.output, self.calls = output, 0

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None, instructions=None, run_id=None):
        self.calls += 1
        return SimpleNamespace(output=self.output, sources=[URL], model="fake-web")


class Geo:
    def geocode(self, address):
        return g.GeoResult(g.OK, 37.5758, 126.9769, "road")


def _item(value, quote=None):
    return {"value": value, "quote": quote or value, "url": URL, "published_at": "2026-10-01"}


def test_pipeline_round_trip_off_ledger_place_never_stores_kakao_values(world):
    answer = {f: None for f in wi.FIELDS}
    answer.update(address=_item("서울특별시 종로구 사직로 161"), business_hours=_item("10:00~20:00", "영업시간 10:00~20:00"),
                  closed_days=_item("매주 화요일"))
    llm, kakao = WebLLM(answer), Kakao(world.off_name)
    io = pe.PlaceIO(get_connection, world.tenant, kakao)
    kw = dict(timeout=10, wait=1, concurrent=1, max_age_days=3650)
    first = pe.enrich_place(world.off_name, io, llm, Geo(), **kw)
    assert first["status"] == pe.ENRICHED and first["in_ledger"] is False and first["place_key"] == world.off_key
    assert first["coords"] == {"latitude": 37.5758, "longitude": 126.9769} and llm.calls == 1

    with get_connection() as conn, conn.cursor() as cur:
        rows = store.read_entries(cur, [world.off_key])[world.off_key]
    assert {"address", "business_hours", "closed_days", "lat_lng", "name"} <= set(rows)
    assert rows["lat_lng"].source == "vworld" and rows["name"].value == world.off_name and rows["address"].url == URL
    assert rows["fee"].source == "none"                                  # 검색했지만 못 찾은 칸 — 짧은 만료 표시
    stored_text = " ".join(f"{r.value} {r.quote}" for r in rows.values())
    assert "카카오가 준" not in stored_text and "37.1" not in stored_text    # 카카오 응답은 어디에도 저장되지 않았다

    # 두 번째에는 다시 검색하지 않는다 — 찾은 칸은 값이, 못 찾은 칸은 표시가 만료 전이다
    second = pe.enrich_place(world.off_name, io, llm, Geo(), **kw)
    assert second["status"] == pe.COMPLETE and llm.calls == 1

    # 그리고 그 장소(코어 장소 행)의 운영 판정이 웹 값으로 돈다
    with get_connection() as conn:
        tue = ledger.state(conn, world.tenant, world.ids["off"], TUESDAY)
    assert tue["closed"] is True and "closed_days" in tue["web_info"]
