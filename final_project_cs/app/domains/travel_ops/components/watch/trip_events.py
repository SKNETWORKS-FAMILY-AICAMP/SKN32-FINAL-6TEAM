# -*- coding: utf-8 -*-
"""변경 초인종 — 웹 화면에 「이 여행 바뀜」 신호만 흘린다. `[2026-09-30 사용자 승인 — ui 세션 전달]`

☆왜. 웹은 알림 · 제안만 30초마다 다시 읽고 일정 본문은 사용자가 직접 뭔가 할 때만 읽었다. 감시 루프가 일정을 바꾸면 알림은
  뜨는데 일정표는 새로고침 전까지 옛날 그대로였다.
★원칙(사용자와 정한 것).
  ① 서버는 **내용이 아니라 신호**만 보낸다 — `{trip_id, kinds, version}`. 사용자 키 · 알림 본문 · 장소 내용은 싣지 않는다.
     웹은 받으면 지금 있는 조회(여행 본문 · notices · proposals)로 다시 읽는다.
  ② **신호가 실패해도 일정 변경은 실패하지 않는다.** 이 모듈은 DB 를 **읽기만** 한다 — 변경 경로(감시 · 되돌리기 · 고르기)는 이 모듈을
     import 하지 않는다(`tests/e2e/test_trip_events.py` 가 검사한다). 디스코드 발송과도 서로 독립이다.
  ③ 놓친 신호를 다시 보내는 장치(커서 재생)는 없다 — 웹이 재연결하거나 화면이 돌아오면 전부 다시 읽는다. 원본은 DB 다.
  ④ 서버는 누가 받았는지 기억하지 않는다. (연결 수 상한만 프로세스 안에서 센다 — 자원 보호이지 수신 기록이 아니다.)
★발행 방식: 연결마다 `poll_seconds` 간격으로 DB 의 **커밋된 값**(여행 판 · 알림 수와 마지막 시각 · 제안 상태 지문)을 읽어 **달라졌을 때만**
  보낸다. 재시작 · 여러 일꾼에서도 맞다(상태가 DB 에만 있다). LISTEN/NOTIFY 는 쓰지 않았다 — 단순함이 먼저다.
  ☆신호가 나가야 하는 변화 중 「제안 만료 · 선택」은 바깥함에 알림이 안 생기는 변화라, 알림 수가 아니라 **제안 상태 지문**으로 본다(Codex 짚음).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

log = logging.getLogger(__name__)

#: 연결 수를 프로세스 안에서 센다 — (테넌트, 고객) → 열린 연결 수. 자원 보호용이며 누가 받았는지의 기록이 아니다
_OPEN: dict[tuple[str, UUID], int] = {}

KINDS = ("itinerary", "notice", "proposal")


def limits() -> dict[str, float]:
    """`config/guardrails.yaml` `travel.trip_events.*` — 시험이 이 함수를 갈아 끼운다."""
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    return {name: float(guard.get(f"travel.trip_events.{name}"))
            for name in ("poll_seconds", "ping_seconds", "max_seconds", "max_per_user", "max_failures")}


def snapshot(conn, tenant_id: str, trip_id: UUID) -> dict[str, Any] | None:
    """그 여행의 지금 상태 지문. 없는 여행이면 None. ★읽기만 한다 — 쓰지 않는다.

    - `version`   여행의 최신 판 (`trips.latest_version`)
    - `notices`   그 여행에 나간 알림의 (수, 마지막 시각) — 새 알림이 생기면 달라진다
    - `proposals` 제안들의 (id, 상태) 지문 — 생성 · 만료 · 선택이 모두 달라진다(알림이 안 생기는 변화도 잡는다)
    ★알림 조회는 `dedupe_key` 앞부분 검색이다 — 연결마다 자주 읽으므로 인덱스가 받쳐야 한다(마이그레이션 037). `prepare=False` 로 보내
      실제 값으로 계획을 세우게 한다(준비된 문장의 일반 계획은 앞부분 검색에 인덱스를 못 쓴다).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT latest_version FROM trips WHERE tenant_id=%s AND trip_id=%s", (tenant_id, trip_id),
                    prepare=False)
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("SELECT count(*), max(available_at) FROM outbox "
                    "WHERE tenant_id=%s AND topic='trip.notice' AND dedupe_key LIKE %s",
                    (tenant_id, f"{trip_id}:%"), prepare=False)
        count, latest = cur.fetchone()
        cur.execute("SELECT coalesce(md5(string_agg(proposal_id::text || ':' || status, ',' ORDER BY proposal_id)), '') "
                    "FROM pending_changes WHERE tenant_id=%s AND trip_id=%s", (tenant_id, trip_id), prepare=False)
        proposals = cur.fetchone()[0]
    return {"version": int(row[0]), "notices": (int(count), latest.isoformat() if latest else None),
            "proposals": proposals}


def changed_kinds(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """두 지문의 차이 → 웹이 다시 읽을 것의 힌트. ★힌트일 뿐이다 — 모르겠으면 셋 다 넣어도 된다."""
    kinds = []
    if before["version"] != after["version"]:
        kinds.append("itinerary")
    if before["notices"] != after["notices"]:
        kinds.append("notice")
    if before["proposals"] != after["proposals"]:
        kinds.append("proposal")
    return kinds


def sse(event: str | None, data: dict[str, Any] | None = None) -> str:
    """한 이벤트 글. `event=None` 이면 주석 한 줄(연결 유지용 `: ping`)."""
    if event is None:
        return ": ping\n\n"
    return f"event: {event}\ndata: {json.dumps(data or {}, ensure_ascii=False)}\n\n"


def acquire(tenant_id: str, customer_id: UUID, *, cap: int) -> bool:
    """이 사용자의 열린 연결이 상한 미만이면 하나 얻는다. ★놓치면 `release` 가 안 불려 상한이 새므로 부르는 쪽이 finally 로 돌려준다."""
    key = (tenant_id, customer_id)
    if _OPEN.get(key, 0) >= cap:
        return False
    _OPEN[key] = _OPEN.get(key, 0) + 1
    return True


def release(tenant_id: str, customer_id: UUID) -> None:
    key = (tenant_id, customer_id)
    left = _OPEN.get(key, 0) - 1
    if left > 0:
        _OPEN[key] = left
    else:
        _OPEN.pop(key, None)


async def stream(*, tenant_id: str, trip_id: UUID, connect: Callable[[], Any],
                 is_disconnected: Callable[[], Any], cfg: dict[str, float] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> AsyncIterator[str]:
    """`ready` → (달라질 때마다 `trip.changed`) · 조용하면 `: ping`. 최대 `max_seconds` 뒤에 닫는다(웹이 다시 붙는다).

    ★DB 읽기는 스레드에서 한다 — 이벤트 루프를 막지 않는다. 읽기가 실패하면 그 틱만 건너뛴다(일정 변경과 무관).
      연속 `max_failures` 번 실패하면 닫는다 — 웹이 재연결하면서 전부 다시 읽는다.
    """
    cfg = cfg or limits()

    def read() -> dict[str, Any] | None:
        with connect() as conn:
            return snapshot(conn, tenant_id, trip_id)

    try:
        state = await asyncio.to_thread(read)
    except Exception:                                       # noqa: BLE001 — 신호를 못 열어도 일정 변경과 무관하다. 닫으면 웹이 다시 붙는다
        log.warning("trip events: first snapshot failed trip=%s", trip_id, exc_info=True)
        return
    if state is None:
        return
    yield sse("ready", {"trip_id": str(trip_id), "version": state["version"]})
    started = last_sent = clock()
    failures = 0
    while True:
        await asyncio.sleep(cfg["poll_seconds"])
        if await is_disconnected():
            return
        now = clock()
        if now - started >= cfg["max_seconds"]:
            return
        try:
            fresh = await asyncio.to_thread(read)
            failures = 0
        except Exception:                                   # noqa: BLE001 — 신호가 실패해도 일정 변경은 실패하지 않는다
            failures += 1
            log.warning("trip events: snapshot failed (%s/%s) trip=%s", failures, int(cfg["max_failures"]), trip_id,
                        exc_info=failures == 1)
            if failures >= cfg["max_failures"]:
                return
            fresh = None
        if fresh is None and failures == 0:
            return                                          # 여행이 없어졌다
        if fresh is not None:
            kinds = changed_kinds(state, fresh)
            if kinds:
                state, last_sent = fresh, now
                yield sse("trip.changed", {"trip_id": str(trip_id), "kinds": kinds, "version": fresh["version"]})
                continue
        if now - last_sent >= cfg["ping_seconds"]:
            last_sent = now
            yield sse(None)


__all__ = ["KINDS", "acquire", "changed_kinds", "limits", "release", "snapshot", "sse", "stream"]
