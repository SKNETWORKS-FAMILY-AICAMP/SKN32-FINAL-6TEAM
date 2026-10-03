# -*- coding: utf-8 -*-
"""끝난 여행의 **전용 장소 행** 정리. `[2026-09-28]` 설계서 §4-5 3번 「여행이 끝나면 지운다」 · 마이그레이션 029

★왜. 관광공사·카카오에서 받은 장소 값은 그 여행 동안 감시를 돌리려고만 싣는다(콘텐츠랩 「로컬서버 저장 금지」 ·
  카카오 운영정책 제5조). 여행이 끝나면 쓸 데가 없다 — 남겨 두면 그 자체가 쌓아 둔 사본이다.
★「끝남」 = 그 여행 **최신 판의 마지막 일정**(끝 시각, 없으면 시작 시각)이 지나고 `travel.trip_place_retention_hours`
  만큼 더 지남. ☆`trips.status` 를 「끝남」으로 바꾸는 곳이 없어(코드 검색 0건) 시각으로 정한다.
★무엇을 지우나 — 좌표 · 외부 식별자(`source_content_id` 등 속성 전부). **이름은 남긴다** — 고객 자신의 지난 여행
  기록(계획서 링크의 이력)이 이 행을 가리킨다. 행 자체를 지우면 일정 항목의 `place_id` 가 끊긴다.
★공용 행(`trip_scope IS NULL`)과 끝나지 않은 여행은 건드리지 않는다. 다시 돌려도 같은 행을 두 번 비우지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def scrub_ended(conn, *, tenant_id: str, now: datetime, retention_hours: float) -> dict[str, Any]:
    cutoff = now - timedelta(hours=retention_hours)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "SELECT p.place_id FROM places p JOIN trips t ON t.tenant_id = p.tenant_id AND t.trip_id = p.trip_scope "
            "WHERE p.tenant_id = %s AND p.trip_scope IS NOT NULL AND NOT (p.attributes ? 'scrubbed_at') "
            "AND (SELECT max(coalesce(i.ends_at, i.starts_at)) FROM itinerary_items i "
            "     WHERE i.tenant_id = t.tenant_id AND i.trip_id = t.trip_id AND i.version = t.latest_version) < %s",
            (tenant_id, cutoff))
        ids = [row[0] for row in cur.fetchall()]
        if ids:
            cur.execute(
                "UPDATE places SET latitude = NULL, longitude = NULL, "
                "attributes = jsonb_build_object('source', attributes->'source', 'scrubbed_at', %s::text) "
                "WHERE tenant_id = %s AND place_id = ANY(%s)",
                (now.isoformat(), tenant_id, ids))
    return {"scrubbed": len(ids), "cutoff": cutoff.isoformat()}


__all__ = ["scrub_ended"]
