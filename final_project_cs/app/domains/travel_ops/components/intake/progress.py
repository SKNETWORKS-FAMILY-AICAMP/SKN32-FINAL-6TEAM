# -*- coding: utf-8 -*-
"""검사 **진행 알림** 보관소 — 계산이 끝나는 대로 이벤트를 쌓아 두고, 실시간 진행(SSE)이 1초마다 비워 내보낸다. `[2026-10-03 ui 세션 요청서 2번]`

☆왜: 검사(`review.build`)는 한 트랜잭션 안에서 돌고 **끝나 커밋돼야** DB 에 보인다. 실시간 진행(`stream.Feed`)은 DB 를 읽어 이벤트를 만들므로 검사 줄 56개 · 이동 12개가 계산이 끝난
4.9초에 한꺼번에 나갔다 — 이동 계산(시간표)이 대부분의 시간인데 그동안 화면은 아무것도 몰랐다. 여기에 **일정 하나 · 구간 하나가 끝나는 대로** 쌓으면 SSE 가 곧바로 내보낼 수 있다.

★쌓는 것(이름 · 몸통 모양은 SSE 이벤트 그대로):
    progress  {phase: places|hours|moves, done, total, current: {id, title}}   「3/14 · 광장시장 운영시간 확인 중」
    item      찾은 일정 한 건 — 검사 줄이 정해진 뒤의 모양(status 포함)
    check     {item, row, result, text}
    move      장소 사이 이동 한 구간
★**이벤트는 상태의 복사본이다**(`stream.py` 머리말) — 같은 키가 다시 와도 덮으면 되고, 끝나면 DB 에서 읽은 최종 값이 같은 키로 와서 덮는다. 그래서 이 보관소는 **정본이 아니다**:
  비어 있어도(다른 프로세스 · 서버 재시작 · 상한을 넘겨 버려짐) 결과는 같고 **중간 진행만 안 보인다**.
★**프로세스 안**이다(DB 에 쓰지 않는다 — 접수 하나에 이벤트 150개 안팎을 DB 로 쓰면 읽기 속도만 느려진다). 읽는 일꾼(스레드)과 SSE 연결이 **같은 프로세스**일 때만 중간 진행이 보인다 —
  여러 프로세스로 띄우면(`--workers N`) 다른 프로세스의 연결은 전처럼 끝에서 한꺼번에 받는다(깨지지 않는다). 배포는 한 프로세스다.
★접수 하나당 상한 `MAX_EVENTS`(앞에서부터 버린다 — 가장 새 상태가 중요하다) · 마지막 쓰기 뒤 `TTL_SECONDS` 지나면 버린다. 이벤트 하나 약 0.2KB — 접수 하나 최대 120KB.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

log = logging.getLogger(__name__)

#: 접수 하나에 쌓는 이벤트 상한. 일정 14개 기준 약 150개(일정 14 · 검사 56 · 이동 12 · 진행 몇십)라 넉넉하다. ★우리가 고른 값
MAX_EVENTS = 600
#: 마지막으로 쓴 뒤 이만큼(초) 지나면 버린다 — 끝낸 접수가 쌓이지 않게(읽기는 길어야 몇 분). ★우리가 고른 값
TTL_SECONDS = 900

_lock = threading.Lock()
#: 접수 id → {"events": [(번호, 이름, 몸통)], "seq": 지금까지 쌓은 수, "touched": 마지막 쓴 시각}
_store: dict[str, dict[str, Any]] = {}

#: `(이름, 몸통)` 을 받는 쪽 — 읽기 · 검사가 부른다. 실패해도 안 던진다(`sink`)
Sink = Callable[[str, dict[str, Any]], None]


def emit(intake_id: str, name: str, body: dict[str, Any]) -> None:
    now = time.monotonic()
    with _lock:
        for key in [k for k, v in _store.items() if now - v["touched"] > TTL_SECONDS]:
            del _store[key]                                  # 오래 안 쓴 접수를 치운다
        entry = _store.setdefault(intake_id, {"events": [], "seq": 0, "touched": now})
        entry["seq"] += 1
        entry["touched"] = now
        entry["events"].append((entry["seq"], name, body))
        if len(entry["events"]) > MAX_EVENTS:
            del entry["events"][:len(entry["events"]) - MAX_EVENTS]


def drain(intake_id: str, after: int) -> tuple[list[tuple[str, dict[str, Any]]], int]:
    """`after` 번호 **뒤에** 쌓인 이벤트와 새 cursor. 연결마다 자기 cursor 를 들고 있다(서버는 누가 어디까지 받았는지 모른다 — 변경 초인종과 같은 방식)."""
    with _lock:
        entry = _store.get(intake_id)
        if entry is None:
            return [], after
        fresh = [(name, body) for seq, name, body in entry["events"] if seq > after]
        return fresh, entry["seq"]


def clear(intake_id: str) -> None:
    with _lock:
        _store.pop(intake_id, None)


def reset() -> None:
    """시험용 — 보관소를 비운다."""
    with _lock:
        _store.clear()


def sink(intake_id: Any) -> Sink:
    """접수 하나의 쌓기 함수. ★**어떤 일이 있어도 안 던진다** — 진행 알림은 부가 기능이라 읽기 · 검사를 막으면 안 된다."""
    key = str(intake_id)

    def push(name: str, body: dict[str, Any]) -> None:
        try:
            emit(key, name, body)
        except Exception:                                    # noqa: BLE001
            log.warning("intake progress emit failed intake=%s", key, exc_info=True)

    return push


def key_of(name: str, body: dict[str, Any]) -> str:
    """이벤트의 **상태 키** — 같은 키는 나중 것이 앞 것을 덮는다(`stream.py` 의 키와 같은 규칙)."""
    if name == "item":
        return f"item:{body['id']}"
    if name == "check":
        return f"check:{body['item']}:{body['row']}"
    if name == "move":
        return f"move:{body['from']}:{body['to']}"
    return f"{name}:{body.get('phase', '')}"


__all__ = ["MAX_EVENTS", "TTL_SECONDS", "Sink", "clear", "drain", "emit", "key_of", "reset", "sink"]
