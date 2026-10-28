"""DB: 실패 확정(`reap_stalled`)은 먼저 채우기로 생긴 **뒤 판**의 읽은 값도 지운다 — 고객이 고친 값은 남긴다. `[2026-10-28 전수검사 A15]`

실제 접수 입구(`POST /v1/web/trip-intakes`) → 뒤에서 읽기 → 확인 화면(1판). 먼저 채우기가 2판을 만든 것과 같은 저장 모양(1판 값을 2판으로 복사 ·
고객이 고친 값 1줄)을 만든 뒤, 확인 화면 공개 전(`review`/`checking`)에 일꾼이 멈춘 것으로 두고 조회(`GET`)가 실패 확정을 부른다.
☆전에는 1판만 지워 현재 판(2판) 값이 조회 응답 `sources[].items` 에 남았다.
"""
from __future__ import annotations

import pytest  # noqa: F401

from app.infrastructure.db.session import get_connection

from .test_intake_review import Kakao, Tour, _client, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처

TEXT = "2032-05-09\n10시 경복궁 관람 1시간 반\n15시 N서울타워"


def _counts(intake_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT revision, method = 'customer', count(*) FROM intake_claims WHERE intake_id=%s "
                    "GROUP BY 1, 2 ORDER BY 1, 2", (intake_id,))
        return {(r, bool(c)): n for r, c, n in cur.fetchall()}


def test_a_stalled_second_revision_keeps_only_customer_values(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, text=TEXT)
    assert view["status"] == "review", view["status"]
    intake_id = view["intake_id"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cols = "intake_id, tenant_id, source_id, field, value_json, evidence, needs_review, note"
        cur.execute(f"INSERT INTO intake_claims (revision, method, {cols}) SELECT 2, method, {cols} FROM intake_claims "
                    "WHERE intake_id=%s AND revision=1", (intake_id,))
        cur.execute(f"INSERT INTO intake_claims (revision, method, {cols}) SELECT 2, 'customer', {cols} FROM intake_claims "
                    "WHERE intake_id=%s AND revision=1 AND field LIKE 'items[%%].title' LIMIT 1", (intake_id,))
        cur.execute("UPDATE trip_intakes SET status='review', stage='checking', revision=2, "
                    "updated_at=now() - interval '1 day' WHERE intake_id=%s", (intake_id,))
    before = _counts(intake_id)
    assert before[(2, False)] > 0 and before[(2, True)] == 1
    got = client.get(f"/v1/web/trip-intakes/{intake_id}", headers=headers).json()   # 조회가 실패 확정(`reap_stalled`)을 부른다
    assert got["status"] == "fatal" and got["fatal"]["code"] == "stalled"
    after = _counts(intake_id)
    assert after.get((1, False), 0) == 0 and after.get((2, False), 0) == 0
    assert after.get((2, True)) == 1                                # 고객이 고친 값은 남긴다
    titles = [i for s in got["sources"] for i in s["items"]]
    assert len(titles) <= 1                                         # 남은 것은 고객이 고친 한 줄뿐
