# -*- coding: utf-8 -*-
"""관광공사 장소 목록의 운영시간을 **새벽에 읽어 둔다** — 요청 경로는 이것만 읽는다. `[2026-09-29 사용자 지시]`

☆왜. 활동 「다른 데로 바꿔」가 후보마다 관광공사 운영정보(detailIntro2)를 요청 자리에서 불렀다 — 요청마다 최대 10건,
  몰림(30건) 뒤로는 89초에 1건이라 연달아 요청하면 한도에 걸렸고, 모델로 읽는 곳은 몇 초씩 걸렸다(실측 첫 요청 33초).
  사용자 설계: **「장소 갱신은 매일 새벽 3시에 한 번, 요청은 DB 만 본다」.**
★하는 일(1분 작업이 부르고, 창 밖이면 아무것도 안 한다):
  1. 창 `travel.catalog_hours.start`~`until`(03:00~08:00) 안에서만.
  2. 오늘 밤 이미 읽은 수가 `per_night` 를 넘으면 멈춘다(개발 계정 하루 1,000건 — 낮 몫을 남긴다).
  3. 목록(`place_catalog`)의 활동 중 **처음 보는 곳 · 목록 수정 시각이 읽을 때와 달라진 곳 · 못 읽은 지 `retry_days` 지난 곳**만
     `per_tick` 개씩 — 관광지·문화시설·레포츠 먼저, 쇼핑은 뒤.
  4. 원문을 규칙으로, 안 되면 모델로 읽어(`place_hours.read_hours` — 일정 짜기와 같은 함수) `catalog_hours` 에 적는다.
★「바뀐 것만」은 목록의 수정 시각으로 가린다 — 관광공사의 변경 목록(`areaBasedSyncList2`)은 2026-09-10 에 0건만 돌려줘
  아직 못 쓴다(`catalog_sync.py` 머리). 목록 자체를 새로 받는 일은 `catalog_sync` 몫이다.
★관광공사가 답을 못 주면(속도 제한 · 공급자 문제) **적지 않고 이번 틱을 멈춘다** — 같은 곳을 다음 틱이 다시 본다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import Any

from app.domains.travel_ops.components.planning.planner import KIND_BY_CONTENT_TYPE

log = logging.getLogger(__name__)

#: 먼저 읽는 순서 — 관광지 · 문화시설 · 레포츠 · 쇼핑. ★우리가 고른 순서(여행 활동으로 자주 쓰는 것 먼저)
TYPE_ORDER = ("12", "14", "28", "38")
ACTIVITY_TYPES = [code for code in TYPE_ORDER if KIND_BY_CONTENT_TYPE.get(code) == "activity"]


def _clock(text: str) -> time:
    hour, minute = str(text).split(":")
    return time(int(hour), int(minute))


def prefill(conn, *, tenant_id: str, source: Any, chat: Any, now: datetime, start: str, until: str,
            per_night: int, per_tick: int, retry_days: int) -> dict[str, Any]:
    """한 틱 — 창 안이면 `per_tick` 곳을 읽어 적는다. 돌려주는 것은 세는 칸(작업 출력 JSON 한 줄)."""
    from app.domains.travel_ops.components.places.place_hours import read_hours

    if not (_clock(start) <= now.time() < _clock(until)):
        return {"skipped": "창 밖", "window": f"{start}~{until}"}
    if source is None or not hasattr(source, "operating"):
        return {"skipped": "관광공사 조회가 연결돼 있지 않다"}
    night = now.replace(hour=_clock(start).hour, minute=_clock(start).minute, second=0, microsecond=0)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog_hours WHERE tenant_id=%s AND read_at >= %s", (tenant_id, night))
        done_tonight = int(cur.fetchone()[0])
        room = min(per_tick, per_night - done_tonight)
        if room <= 0:
            return {"skipped": "오늘 밤 몫을 다 썼다", "done_tonight": done_tonight, "per_night": per_night}
        cur.execute(
            "SELECT pc.content_id, pc.content_type_id, pc.title, pc.source_modified_at FROM place_catalog pc "
            "LEFT JOIN catalog_hours ch ON ch.tenant_id = pc.tenant_id AND ch.source = pc.source "
            "  AND ch.content_id = pc.content_id "
            "WHERE pc.tenant_id=%s AND pc.source='tour_api' AND pc.content_type_id = ANY(%s) "
            "AND (ch.content_id IS NULL "
            "     OR ch.source_modified_at IS DISTINCT FROM pc.source_modified_at "
            "     OR (ch.hours_week IS NULL AND ch.read_at < %s)) "
            "ORDER BY (ch.content_id IS NOT NULL), array_position(%s::text[], pc.content_type_id), pc.content_id "
            "LIMIT %s",
            (tenant_id, ACTIVITY_TYPES, now - timedelta(days=retry_days), list(TYPE_ORDER), room))
        rows = cur.fetchall()
    out: dict[str, Any] = {"asked": len(rows), "read": 0, "unknown": 0, "stopped": None,
                           "done_tonight": done_tonight}
    for content_id, type_id, title, modified in rows:
        try:
            intro = source.operating(str(content_id), str(type_id))
        except Exception as exc:                    # noqa: BLE001 — 한도 · 공급자 문제는 이번 틱을 멈춘다(다음 틱이 잇는다)
            out["stopped"] = f"{title}: {type(exc).__name__}"
            break
        if not intro:
            out["stopped"] = f"{title}: 운영정보를 받지 못했다"
            break
        usetime, restdate = intro.get("usetime_text"), intro.get("restdate_text")
        read = read_hours(usetime, restdate, chat)
        record = read.as_record(source="tour_api", read_at=now.isoformat())
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO catalog_hours (tenant_id, source, content_id, content_type_id, hours_week, hours_read, "
                "hours_origin, phone, source_modified_at, read_at) VALUES (%s,'tour_api',%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id, source, content_id) DO UPDATE SET content_type_id=EXCLUDED.content_type_id, "
                "hours_week=EXCLUDED.hours_week, hours_read=EXCLUDED.hours_read, hours_origin=EXCLUDED.hours_origin, "
                "phone=COALESCE(EXCLUDED.phone, catalog_hours.phone), source_modified_at=EXCLUDED.source_modified_at, "
                "read_at=EXCLUDED.read_at",
                (tenant_id, str(content_id), str(type_id),
                 json.dumps(read.week, ensure_ascii=False) if read.week else None,
                 json.dumps(record, ensure_ascii=False, default=str),
                 json.dumps({"usetime": usetime, "restdate": restdate}, ensure_ascii=False),
                 intro.get("info_phone") or None, modified, now))
        out["read" if read.week else "unknown"] += 1
    return out


__all__ = ["ACTIVITY_TYPES", "TYPE_ORDER", "prefill"]
