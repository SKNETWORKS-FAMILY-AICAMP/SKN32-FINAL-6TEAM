# -*- coding: utf-8 -*-
"""관광공사 장소 목록의 운영시간을 **새벽에 읽어 둔다** — 요청 경로는 이것만 읽는다. `[2026-09-29 사용자 지시]`

☆왜. 활동 「다른 데로 바꿔」가 후보마다 관광공사 운영정보(detailIntro2)를 요청 자리에서 불렀다 — 요청마다 최대 10건,
  몰림(30건) 뒤로는 89초에 1건이라 연달아 요청하면 한도에 걸렸고, 모델로 읽는 곳은 몇 초씩 걸렸다(실측 첫 요청 33초).
  사용자 설계: **「장소 갱신은 매일 새벽 3시에 한 번, 요청은 DB 만 본다」.**
★하는 일(1분 작업이 부르고, 창 밖이면 아무것도 안 한다):
  1. `travel.catalog_hours.start`(03:00)부터. ★`[2026-10-14 사용자 지시]` 일일 정기점검은 03시 시작 · 마감 없음 — `until` 을 비웠다(전에는 08:00).  2. 오늘 밤 이미 읽은 수가 `per_night` 를 넘으면 멈춘다(개발 계정 하루 1,000건 — 낮 몫을 남긴다).
  3. 목록(`place_catalog`)의 활동 중 **처음 보는 곳 · 목록 수정 시각이 읽을 때와 달라진 곳 · 못 읽은 지 `retry_days` 지난 곳**만
     `per_tick` 개씩 — 관광지·문화시설·레포츠 먼저, 쇼핑은 뒤.
  4. 원문을 규칙으로, 안 되면 모델로 읽어(`place_hours.read_hours` — 일정 짜기와 같은 함수) `catalog_hours` 에 적는다.
★「바뀐 것만」은 목록의 수정 시각으로 가린다 — 관광공사의 변경 목록(`areaBasedSyncList2`)은 2026-09-10 에 0건만 돌려줘
  아직 못 쓴다(`catalog_sync.py` 머리). 목록 자체를 새로 받는 일은 `catalog_sync` 몫이다.
★관광공사가 답을 못 주면(속도 제한 · 공급자 문제) **적지 않고 이번 틱을 멈춘다** — 같은 곳을 다음 틱이 다시 본다.
★`[2026-10-12 사용자]` 사람이 공식 페이지에서 확인한 운영시간(`hours_read.source = "official_web"`, 활동 CSV `field_sources`)은
  **관광공사 응답이 채워진 칸만** 관광공사 값으로 바꾸고 그 칸의 출처를 지운다(`merge_official_web`). 두 칸 다 비어 오면 사람 값을
  그대로 두고 목록 수정 시각만 맞춘다 — 안 맞추면 수정 시각이 계속 달라 매 틱 다시 읽는다. 관광공사 원문 행은 전처럼 덮어쓴다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from typing import Any, Callable

from app.domains.travel_ops.components.planning.planner import KIND_BY_CONTENT_TYPE

log = logging.getLogger(__name__)

#: 먼저 읽는 순서 — 관광지 · 문화시설 · 레포츠 · 쇼핑. ★우리가 고른 순서(여행 활동으로 자주 쓰는 것 먼저)
TYPE_ORDER = ("12", "14", "28", "38")
ACTIVITY_TYPES = [code for code in TYPE_ORDER if KIND_BY_CONTENT_TYPE.get(code) == "activity"]


def _clock(text: str) -> time:
    hour, minute = str(text).split(":")
    return time(int(hour), int(minute))


#: `field_sources` 칸 → 관광공사 원문 칸(`hours_origin`)
_ORIGIN_KEY = {"business_hours": "usetime", "closed_days": "restdate"}


def merge_official_web(read: dict[str, Any] | None, origin: dict[str, Any] | None, usetime: str | None,
                       restdate: str | None) -> tuple[str | None, str | None, dict[str, Any]] | None:
    """사람이 확인한 운영시간 행에 관광공사 응답을 합친다. 그 행이 아니면 None(= 응답으로 덮어쓴다).

    돌려주는 것: (운영시간 글, 휴무 글, 남은 사람 출처). 관광공사 응답이 **채워진 칸만** 관광공사 글을 쓰고, 빈 칸은 사람 글과
    출처를 그대로 둔다. 남은 출처가 없으면 그 행은 이제 관광공사 원문이다.
    """
    from app.domains.travel_ops.components.places.place_hours import clean

    sources = (read or {}).get("field_sources") if (read or {}).get("source") == "official_web" else None
    if not isinstance(sources, dict) or not sources:
        return None
    tour = {"usetime": usetime, "restdate": restdate}
    texts = dict(tour)
    remaining: dict[str, Any] = {}
    for column, key in _ORIGIN_KEY.items():
        if column in sources and not clean(tour[key]):
            texts[key] = (origin or {}).get(key)
            remaining[column] = sources[column]
    return texts["usetime"], texts["restdate"], remaining


#: 관광공사가 **정상으로 답했지만** 운영정보 칸이 없는 경우(`tour_api.operating`) — 호출 실패(한도 · 공급자 문제)와 다르다
_EMPTY_ANSWERS = ("no_intro", "no_operating_fields")


def _answered_without_hours(source: Any, before: dict[str, int]) -> bool:
    """방금 `operating` 이 `None` 을 돌려준 까닭이 「답은 정상인데 운영정보가 없다」인가 — 소스의 이유 세는 칸(`misses`)이 그 이유만 늘었을 때."""
    after = getattr(source, "misses", None)
    if not after:
        return False
    grown = {reason for reason, count in dict(after).items() if count > before.get(reason, 0)}
    return bool(grown) and grown <= set(_EMPTY_ANSWERS)


def day_start(now: datetime, start: str) -> datetime:
    """`now` 가 속한 정기점검 회차의 시작 — 오늘 `start` 가 지났으면 오늘, 아니면 어제의 `start`."""
    begun = now.replace(hour=_clock(start).hour, minute=_clock(start).minute, second=0, microsecond=0)
    return begun if now >= begun else begun - timedelta(days=1)


def prefill(conn, *, tenant_id: str, source: Any, chat: Any, now: datetime, start: str, until: str | None,
            per_night: int, per_tick: int, retry_days: int,
            pace: Callable[[int], int] | None = None) -> dict[str, Any]:
    """한 틱 — 창 안이면 `per_tick` 곳을 읽어 적는다. 돌려주는 것은 세는 칸(작업 출력 JSON 한 줄).

    ★`[2026-10-14 사용자 지시]` 일일 정기점검은 **03시 시작 · 가능하면 03:30 까지 끝냄 · 08:00 에 모두 멈춤**(`daily_check.py`).
      하루 몫(`per_night`)은 그날 03시부터 센다(03시 전이면 어제 03시부터). `until` 이 비어 있으면 끝을 두지 않는다(시험용).
    ★`pace(남은 수) -> 이번에 읽을 수` 를 주면 03:30 까지 끝나도록 한 번에 읽는 양을 늘린다. 결과의 `remaining` 은
      이번 회차 뒤에도 오늘 읽어야 할 곳의 수다 — 03:30 이 지났는데 0 보다 크면 실행기가 관리자 웹앱에 보고한다."""
    from app.domains.travel_ops.components.places.place_hours import clean, read_hours

    if until and not (_clock(start) <= now.time() < _clock(until)):
        return {"skipped": "창 밖", "window": f"{start}~{until}"}
    if source is None or not hasattr(source, "operating"):
        return {"skipped": "관광공사 조회가 연결돼 있지 않다"}
    night = day_start(now, start)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog_hours WHERE tenant_id=%s AND read_at >= %s", (tenant_id, night))
        done_tonight = int(cur.fetchone()[0])
        if per_night - done_tonight <= 0:
            return {"skipped": "오늘 밤 몫을 다 썼다", "done_tonight": done_tonight, "per_night": per_night}
        due = ("FROM place_catalog pc "
               "LEFT JOIN catalog_hours ch ON ch.tenant_id = pc.tenant_id AND ch.source = pc.source "
               "  AND ch.content_id = pc.content_id "
               "WHERE pc.tenant_id=%s AND pc.source='tour_api' AND pc.content_type_id = ANY(%s) "
               "AND (ch.content_id IS NULL "
               "     OR ch.source_modified_at IS DISTINCT FROM pc.source_modified_at "
               "     OR (ch.hours_week IS NULL AND ch.read_at < %s)) ")
        args = (tenant_id, ACTIVITY_TYPES, now - timedelta(days=retry_days))
        cur.execute("SELECT count(*) " + due, args)
        left = min(int(cur.fetchone()[0]), per_night - done_tonight)        # 오늘 읽어야 할 곳 — 하루 몫을 넘지 않는다
        room = min(pace(left) if pace else per_tick, per_night - done_tonight)
        cur.execute(
            "SELECT pc.content_id, pc.content_type_id, pc.title, pc.source_modified_at, ch.hours_read, ch.hours_origin "
            + due + "ORDER BY (ch.content_id IS NOT NULL), array_position(%s::text[], pc.content_type_id), pc.content_id "
            "LIMIT %s", (*args, list(TYPE_ORDER), room))
        rows = cur.fetchall()
    out: dict[str, Any] = {"asked": len(rows), "read": 0, "unknown": 0, "stopped": None,
                           "done_tonight": done_tonight, "remaining": left}
    for content_id, type_id, title, modified, old_read, old_origin in rows:
        before = dict(getattr(source, "misses", None) or {})
        try:
            intro = source.operating(str(content_id), str(type_id))
        except Exception as exc:                    # noqa: BLE001 — 한도 · 공급자 문제는 이번 틱을 멈춘다(다음 틱이 잇는다)
            out["stopped"] = f"{title}: {type(exc).__name__}"
            break
        if not intro and _answered_without_hours(source, before):
            # ★`[2026-10-15 x600 서버 실측]` 관광공사가 **정상으로 답했는데** 운영정보 칸이 하나도 없는 곳(동상 · 기념비 · 사당)에서 이 작업이 멈춰 있었다 —
            #   멈추면 그 곳이 다음 틱에도 맨 앞이라 **같은 곳만 매 분 다시 부르고(하룻밤 300번) 뒤로 못 나갔다**(09-30 이후 읽은 곳 0).
            #   없는 것을 「운영시간 모름」 행으로 적어 두고 다음 곳으로 간다(`retry_days` 뒤에 한 번 다시 본다)
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO catalog_hours (tenant_id, source, content_id, content_type_id, hours_week, hours_read, hours_origin, "
                    "phone, source_modified_at, read_at) VALUES (%s,'tour_api',%s,%s,NULL,%s,%s,NULL,%s,%s) "
                    "ON CONFLICT (tenant_id, source, content_id) DO UPDATE SET content_type_id=EXCLUDED.content_type_id, "
                    "hours_week=NULL, hours_read=EXCLUDED.hours_read, hours_origin=EXCLUDED.hours_origin, "
                    "source_modified_at=EXCLUDED.source_modified_at, read_at=EXCLUDED.read_at",
                    (tenant_id, str(content_id), str(type_id),
                     json.dumps({"source": "tour_api", "method": "none", "quotes": [], "conditions": [], "dropped": ["관광공사에 운영정보가 없다"],
                                 "read_at": now.isoformat()}, ensure_ascii=False),
                     json.dumps({"usetime": None, "restdate": None}, ensure_ascii=False), modified, now))
            out["unknown"] += 1
            out["no_operating_info"] = out.get("no_operating_info", 0) + 1
            continue
        if not intro:
            out["stopped"] = f"{title}: 운영정보를 받지 못했다"
            break
        usetime, restdate = intro.get("usetime_text"), intro.get("restdate_text")
        merged = merge_official_web(old_read, old_origin, usetime, restdate)
        remaining: dict[str, Any] = {}
        if merged is not None:
            if not clean(usetime) and not clean(restdate):          # 관광공사가 두 칸 다 비어 왔다 — 사람 값을 둔다
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute("UPDATE catalog_hours SET source_modified_at=%s "
                                "WHERE tenant_id=%s AND source='tour_api' AND content_id=%s",
                                (modified, tenant_id, str(content_id)))
                out["kept_official_web"] = out.get("kept_official_web", 0) + 1
                continue
            usetime, restdate, remaining = merged
            replaced = len(old_read["field_sources"]) - len(remaining)
            out["official_web_replaced"] = out.get("official_web_replaced", 0) + replaced
        read = read_hours(usetime, restdate, chat)
        record = read.as_record(source="official_web" if remaining else "tour_api", read_at=now.isoformat())
        if remaining:
            record["field_sources"] = remaining
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
    out["remaining"] = max(0, left - out["read"] - out["unknown"] - out.get("kept_official_web", 0))
    return out


__all__ = ["ACTIVITY_TYPES", "TYPE_ORDER", "prefill"]
