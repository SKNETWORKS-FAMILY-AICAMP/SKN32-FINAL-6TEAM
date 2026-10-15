# -*- coding: utf-8 -*-
"""걸러진 「기타」 재난 문자 기록 — **실제 DB** 로 `[2026-10-13 사용자 결정]`.

지키려는 것: 같은 일련번호는 한 번만 쓴다 · 같은 본문은 묶어서 건수를 센다 · 관리자 조회가 건수 많은 순으로 준다.
★일련번호 · 본문은 시험마다 새로 만들고 끝나면 그 줄만 지운다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.watch import notice_exclusions
from app.infrastructure.db.session import get_connection


@pytest.fixture()
def tag():
    value = uuid4().hex[:10]
    yield value
    with get_connection() as conn:
        conn.execute("DELETE FROM notice_excluded_messages WHERE serial LIKE %s", (f"t{value}%",))
        conn.commit()


def _item(tag, n, body):
    return {"serial": f"t{tag}-{n}", "text": body, "kind": "기타", "step": "안전안내",
            "regions": ["서울특별시 종로구"], "created_at": datetime.now(timezone.utc).isoformat(), "model_checked": n % 2 == 0,
            "prompt_version": "notice_impact.v1-2026-10-13"}


def test_records_once_per_serial_and_groups_by_body(tag):
    body_a, body_b = f"물놀이 수칙 안내 {tag}", f"병원 안내 {tag}"
    assert notice_exclusions.record(_item(tag, 1, body_a), connection_factory=get_connection) is True
    assert notice_exclusions.record(_item(tag, 1, body_a), connection_factory=get_connection) is False      # 같은 일련번호
    notice_exclusions.record(_item(tag, 2, body_a), connection_factory=get_connection)
    notice_exclusions.record(_item(tag, 3, body_b), connection_factory=get_connection)
    with get_connection() as conn:
        got = notice_exclusions.summary(conn, days=1, limit=500)
    mine = {i["body"]: i for i in got["items"] if tag in i["body"]}
    assert mine[body_a]["count"] == 2 and mine[body_b]["count"] == 1
    assert set(mine[body_a]["judged_by"]) == {"rule", "rule+model"}
    order = [i["body"] for i in got["items"] if tag in i["body"]]
    assert order.index(body_a) < order.index(body_b)
