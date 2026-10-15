"""조립이 활동 팀에 저장된 운영 상태 읽기 함수를 꽂는다 — `[2026-10-15]` 활동 → 코어 전달 1번 (TeamFlow ST4F-533).

배치가 `activity.ac_live_status` 에 저장한 웹 확인 결과를 고객 요청은 `team.live_lookup` 으로 **읽기만** 한다.
팀은 DB 를 직접 열지 않으므로 조립(`build_registry`)이 꽂아 주어야 한다. 안 꽂으면 모든 결과가 `unchecked`(`lookup_not_wired`) 가 된다.
  - 운영 조립(도구를 직접 만드는 경로) — 꽂는다.
  - 시험 조립(`tools` 를 주입) — 꽂지 않는다(`judge_llm` 과 같은 이유: 시험이 조용히 DB 를 타지 않게).
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.composition import build_registry
from app.domains.travel_ops.instances.activity import live_store
from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ReadToolbox


def test_production_assembly_wires_the_stored_live_status_reader():
    team = build_registry().get("activity").module
    assert callable(team.live_lookup)


def test_test_assembly_with_injected_tools_does_not_wire_it():
    team = build_registry(tools=ReadToolbox(get_connection)).get("activity").module
    assert team.live_lookup is None


def test_the_wired_reader_reads_the_stored_row_so_the_status_is_not_lookup_not_wired():
    """꽂힌 함수가 실제로 저장된 줄을 읽는다 — 줄이 없으면 `None`(아직 안 봤다), 있으면 값 · 인용 · 확인 시각을 돌려준다."""
    lookup = build_registry().get("activity").module.live_lookup
    tenant, content_id, day = "livewire_" + uuid4().hex[:8], "T" + uuid4().hex[:12], date(2026, 11, 10)
    load_id = None
    try:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('t', %s, 1) RETURNING load_id",
                        ("0" * 64,))
            load_id = cur.fetchone()[0]
            cur.execute("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, lcls1, lcls2, load_id) "
                        "VALUES (%s, '12', '시험궁', '시험궁', 'HS', 'HS01', %s)", (content_id, load_id))
            cur.execute("INSERT INTO places (tenant_id, name, kind, source_name, source_content_id) "
                        "VALUES (%s, '시험궁', 'activity', 'tour_api', %s) RETURNING place_id", (tenant, content_id))
            place_id = str(cur.fetchone()[0])
        assert lookup(tenant, place_id, day) is None                              # 아직 안 봤다 — 「열었다」로 풀어 주지 않는다
        with get_connection() as conn, conn.transaction():
            live_store.record(conn, content_id, day, "closed", citations=[{"url": "https://example.test/n", "quote": "임시 휴관"}])
        found = lookup(tenant, place_id, day)
        assert found["value"] == "closed" and found["citations"][0]["quote"] == "임시 휴관" and found["checked_at"] is not None
        assert lookup(tenant, place_id, date(2026, 11, 11)) is None               # 다른 날짜는 따로다
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM activity.ac_live_status WHERE content_id = %s", (content_id,))
            cur.execute("DELETE FROM places WHERE tenant_id = %s", (tenant,))
            cur.execute("DELETE FROM activity.ac_place WHERE content_id = %s", (content_id,))
            if load_id is not None:
                cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id = %s", (load_id,))
