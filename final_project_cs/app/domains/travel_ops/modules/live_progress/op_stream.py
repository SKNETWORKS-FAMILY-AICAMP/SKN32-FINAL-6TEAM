# -*- coding: utf-8 -*-
"""웹의 오래 걸리는 일을 **실시간 진행(SSE)** 으로 — 멈춘 서버가 사용자를 깜깜하게 두지 않게. `[2026-10-02 사용자 지시]`

☆왜. 웹의 채팅 · 일정 짜기는 한 번의 요청이 끝날 때까지 **아무것도 안 보이는** 호출이었다. 원격 모델이 식었거나(첫 채팅 34초)
  SSH 터널이 끊기면(모델 호출 실패까지 20초+) 사용자는 자기 요청이 **받아졌는지 · 어디서 기다리는지 · 서버가 죽었는지**를 알 길이 없었다.
  변경 초인종(`trip_events.py`)은 「일정이 바뀜」 신호만 흘려서 이 문제를 못 풀었다.

★이 모듈이 내는 이벤트(전부 `text/event-stream`, 한 줄 JSON):

  accepted  `{op, at}`                                 받았다 — **첫 바이트**. 이게 안 오면 서버·연결 문제다
  stage     `{stage, label, waiting_on, elapsed}`      서버가 **실제로 그 단계에 들어갔을 때만**(지어낸 진행률 없음)
  beat      `{elapsed, stage, label, waiting_on, stage_elapsed, slow, server_time}`
                                                       `beat_seconds` 마다 — ★일꾼이 멈춰 있어도 **이벤트 루프가** 낸다
  result    `{…}`                                      끝 — 기존 JSON 응답과 **같은 본문**
  error     `{code, message, retryable, status?, …}`   실패 · 시간 초과(`max_seconds`) — 매달려 있지 않고 끝낸다

★사용자가 상태를 아는 방법(웹이 할 일 — 서버는 재료만 준다).
  - `beat` 가 오는데 `slow=true` → 「모델 응답이 느려요(12초째)」. 서버는 살아 있고 **모델이 느린 것**이다.
  - `beat` 가 **2번(≈6초) 안 오면** → 서버·연결이 죽은 것이다. 웹이 「연결이 끊겼어요 — 다시 연결 중」을 띄운다(워치독은 웹 몫).
  - `error` → 이유와 `retryable`. 다시 시도하면 **같은 request_id 라서 같은 요청**이다(두 번 처리되지 않는다).

★원칙.
  ① **일꾼은 스레드, 생존 신호는 이벤트 루프.** 일꾼이 모델 호출에 막혀 있어도 beat 는 계속 나간다.
  ② **연결이 끊겨도 일은 끝낸다**(처리 중인 요청을 중간에 버리지 않는다) — 응답 뒤로 미룬 일(`defer`)도 정확히 한 번 돈다.
     끊겼을 때 사용자는 다시 연결하면서 **같은 request_id** 로 되묻는다 → 앞 요청의 답은 대화 기록(`/chat`)에서 읽는다.
  ③ 한 사용자가 열 수 있는 실시간 작업 수에 상한이 있다(`max_per_user`) — 자원 보호이지 수신 기록이 아니다.
  ④ 이 모듈은 도메인을 모른다 — `work(progress, defer)` 한 함수와 `limits()` 만 안다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: 단계 이름 → (고객에게 보일 말, 무엇을 기다리나). 이름이 여기 없으면 이름을 그대로 보인다(서버가 새 단계를 더해도 깨지지 않는다).
#: ★`waiting_on` 이 `model`·`place` 인 단계가 오래 걸리면 beat 가 `slow=true` 를 단다.
STAGES: dict[str, tuple[str, str | None]] = {
    "received": ("요청을 받았어요", None),
    "reading": ("여행 일정을 읽는 중이에요", None),
    "understanding": ("요청을 이해하는 중이에요", "model"),
    "classifying": ("요청 종류를 가려내는 중이에요", "model"),
    "extracting": ("요청 내용을 정리하는 중이에요", "model"),
    "looking_up": ("장소 정보를 확인하는 중이에요", "place"),
    "planning": ("일정을 짜는 중이에요", "model"),
    "checking": ("조건을 확인하는 중이에요", None),
    "applying": ("일정에 반영하는 중이에요", None),
    "registering": ("여행으로 등록하는 중이에요", None),
    "writing": ("답을 정리하는 중이에요", None),
}

#: 열린 실시간 작업 수 — (테넌트, 고객) → 수. 자원 보호용이며 누가 받았는지의 기록이 아니다
_OPEN: dict[tuple[str, UUID], int] = {}

_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def limits(op: str = "message") -> dict[str, float]:
    """`config/guardrails.yaml` `travel.op_stream.*` — 시험이 이 함수를 갈아 끼운다. `max_seconds` 는 작업 종류별이다."""
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    cfg = {name: float(guard.get(f"travel.op_stream.{name}")) for name in ("beat_seconds", "slow_seconds", "max_per_user")}
    cfg["max_seconds"] = float(guard.get(f"travel.op_stream.max_seconds.{op}"))
    return cfg


def sse(event: str, data: dict[str, Any] | None = None) -> str:
    return f"event: {event}\ndata: {json.dumps(data or {}, ensure_ascii=False, default=str)}\n\n"


def acquire(tenant_id: str, customer_id: UUID, *, cap: int) -> bool:
    """이 사용자의 열린 실시간 작업이 상한 미만이면 하나 얻는다. ★부르는 쪽이 finally 로 `release` 한다."""
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


def label_of(stage: str) -> tuple[str, str | None]:
    return STAGES.get(stage, (stage, None))


def error_payload(exc: BaseException) -> dict[str, Any]:
    """예외 → `error` 이벤트 몸통. HTTPException(`status_code` + `detail={"error": {...}}`)도 같은 모양으로 푼다
    (FastAPI 를 import 하지 않는다 — 속성으로 알아본다). 모르는 예외는 **원문을 싣지 않는다**(내부 사정 · 키가 샐 수 있다)."""
    status = getattr(exc, "status_code", None)
    detail = getattr(exc, "detail", None)
    if isinstance(status, int) and isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        body = dict(detail["error"])
        body.setdefault("code", "error")
        body.setdefault("message", "요청을 처리하지 못했어요")
        body["status"] = status
        body["retryable"] = bool(body.get("retryable", status in _RETRYABLE_STATUS))
        headers = getattr(exc, "headers", None) or {}
        if "Retry-After" in headers:
            body.setdefault("retry_after_seconds", int(headers["Retry-After"]))
        return body
    if isinstance(status, int):
        return {"code": "error", "message": str(detail or "요청을 처리하지 못했어요"), "status": status,
                "retryable": status in _RETRYABLE_STATUS}
    return {"code": "internal", "message": "일을 처리하다 문제가 생겼어요 — 잠시 뒤 다시 해 주세요", "retryable": True}


class Progress:
    """일꾼(스레드)이 부르는 알림통 — `stage()` 한 줄로 「지금 이 단계」를 알린다. 이벤트 루프 밖에서 불러도 안전하다."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        self._loop, self._queue = loop, queue

    def _put(self, item: tuple[str, Any]) -> None:
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
        except RuntimeError:                      # 서버가 내려가는 중(루프가 닫혔다) — 알릴 곳이 없다
            pass

    def stage(self, name: str) -> None:
        self._put(("stage", name))


class _Run:
    """일꾼과 흐름이 **끝내는 쪽을 서로 모를 때**의 뒷정리 장부 — 응답 뒤 일(`defer`)이 정확히 한 번 돌게 한다."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.done = False
        self.abandoned = False
        self._deferred: list[Callable[[], None]] = []

    def defer(self, fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        """`BackgroundTasks.add_task` 와 같은 모양 — 호출은 일꾼 스레드에서 온다."""
        with self.lock:
            self._deferred.append(lambda: fn(*args, **kwargs))

    def run_deferred(self) -> None:
        with self.lock:
            todo, self._deferred = self._deferred, []
        for fn in todo:
            try:
                fn()
            except Exception:                     # noqa: BLE001 — 뒤에서 도는 일의 실패가 앞의 답을 건드리지 않는다
                log.exception("op_stream: deferred task failed")


def _beat(*, now: float, started: float, stage: str, stage_started: float, slow_after: float,
          clock_now: datetime | None = None) -> dict[str, Any]:
    label, waiting_on = label_of(stage)
    stage_elapsed = now - stage_started
    return {"elapsed": round(now - started, 1), "stage": stage, "label": label, "waiting_on": waiting_on,
            "stage_elapsed": round(stage_elapsed, 1),
            "slow": bool(waiting_on) and stage_elapsed >= slow_after,
            "server_time": (clock_now or datetime.now(KST)).isoformat(timespec="seconds")}


async def run(work: Callable[[Progress, Callable[..., None]], dict[str, Any]], *, op: str,
              is_disconnected: Callable[[], Any], cfg: dict[str, float] | None = None,
              clock: Callable[[], float] = time.monotonic) -> AsyncIterator[str]:
    """`accepted` → (`stage` · `beat`)… → `result` | `error`. `work(progress, defer)` 는 **스레드에서** 돌고 본문(dict)을 돌려준다.

    ★`max_seconds` 가 지나면 `error{code: timeout}` 로 끝낸다 — 일꾼은 **멈추지 않고** 끝까지 돈다(처리 중인 요청을 버리지 않는다).
      사용자는 같은 request_id 로 다시 묻거나 대화 기록에서 답을 읽는다.
    """
    cfg = cfg or limits(op)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    state = _Run()
    progress = Progress(loop, queue)

    def job() -> None:
        try:
            outcome: tuple[str, Any] = ("result", work(progress, state.defer))
        except Exception as exc:                  # noqa: BLE001 — 일꾼의 어떤 실패도 흐름이 `error` 로 알린다
            if getattr(exc, "status_code", None) is None:
                log.exception("op_stream: work failed op=%s", op)
            outcome = ("error", error_payload(exc))
        with state.lock:
            state.done = True
            abandoned = state.abandoned
        if abandoned:                             # 흐름이 이미 떠났다 — 응답 뒤 일은 여기서 끝낸다
            state.run_deferred()
        progress._put(outcome)

    started = clock()
    stage, stage_started = "received", started
    future = loop.run_in_executor(None, job)
    try:
        yield sse("accepted", {"op": op, "at": datetime.now(KST).isoformat(timespec="seconds")})
        while True:
            try:
                kind, data = await asyncio.wait_for(queue.get(), timeout=cfg["beat_seconds"])
            except asyncio.TimeoutError:
                kind, data = "tick", None
            now = clock()
            if kind == "tick":
                if await is_disconnected():
                    return
                if now - started >= cfg["max_seconds"]:
                    yield sse("error", {"code": "timeout", "retryable": True,
                                        "message": "시간이 오래 걸려 기다리기를 멈췄어요 — 같은 요청으로 다시 시도하면 이어서 확인해요",
                                        "elapsed": round(now - started, 1)})
                    return
                yield sse("beat", _beat(now=now, started=started, stage=stage, stage_started=stage_started,
                                        slow_after=cfg["slow_seconds"]))
            elif kind == "stage":
                stage, stage_started = data, now
                label, waiting_on = label_of(stage)
                yield sse("stage", {"stage": stage, "label": label, "waiting_on": waiting_on,
                                    "elapsed": round(now - started, 1)})
            else:                                  # result | error — 끝
                yield sse(kind, data)
                return
    finally:
        with state.lock:
            finished = state.done
            if not finished:
                state.abandoned = True             # 일꾼이 끝나면서 응답 뒤 일을 돌린다
        if finished:
            threading.Thread(target=state.run_deferred, daemon=True).start()
        _ = future                                 # 일꾼 결과는 큐로 온다 — 객체만 붙들어 둔다


async def watch(read: Callable[[], dict[str, Any] | None], *, op: str, done: Callable[[dict[str, Any]], bool],
                stage_of: Callable[[dict[str, Any]], str], label_of_state: Callable[[dict[str, Any]], str] | None = None,
                quiet_for: Callable[[dict[str, Any]], float | None] | None = None,
                is_disconnected: Callable[[], Any], cfg: dict[str, float] | None = None,
                poll_seconds: float = 1.0, stalled_after: float | None = None,
                extra: Callable[[dict[str, Any]], Awaitable[list[str]]] | None = None,
                clock: Callable[[], float] = time.monotonic) -> AsyncIterator[str]:
    """**DB 에 적히는 진행**(접수 읽기 — 뒤에서 도는 일꾼이 `stage` 를 갱신한다)을 흘린다.

    `extra(state)` — **내용 이벤트**(읽은 줄 · 찾은 일정 · 검사 · 이동, `intake/stream.py`)를 만드는 훅. 연결 직후 · 단계 이벤트 뒤 · 끝내기 전에 불러
    돌려준 SSE 조각을 그대로 흘린다. 훅이 실패해도 흐름은 끊기지 않는다(단계 이벤트는 계속 나가고 실패는 로그에 남는다).

    `accepted` `{op, state}` → 단계가 바뀔 때마다 `stage` → 조용하면 `beat`(`state` 포함) → `done(state)` 가 참이면 `result{state}` 후 끝.
    `read()` 가 None 이면(없어졌다) `error{not_found}`. 읽기가 연속으로 실패하면 `error{code: unavailable, retryable}` 로 끝낸다.
    ★`quiet_for(state)` = 그 상태가 **마지막으로 갱신된 뒤 지난 초**. 이것이 `stalled_after` 를 넘으면 뒤에서 읽던 일꾼이 죽은 것이다
      (서버 재시작 · 프로세스 종료) — `error{code: stalled, retryable}` 로 끝낸다. 사용자가 영원히 기다리지 않게.
    """
    cfg = cfg or limits(op)

    async def snapshot() -> dict[str, Any] | None:
        return await asyncio.to_thread(read)

    try:
        state = await snapshot()
    except Exception:                              # noqa: BLE001
        log.warning("op_stream.watch: first read failed op=%s", op, exc_info=True)
        yield sse("error", {"code": "unavailable", "retryable": True, "message": "상태를 읽지 못했어요 — 다시 연결해 주세요"})
        return
    if state is None:
        yield sse("error", {"code": "not_found", "retryable": False, "message": "찾을 수 없어요", "status": 404})
        return
    started = last_beat = stage_started = clock()
    stage = stage_of(state)

    async def content() -> list[str]:
        if extra is None:
            return []
        try:
            return await extra(state)
        except Exception:                          # noqa: BLE001 — 내용 이벤트의 실패가 단계 이벤트를 막지 않는다
            log.warning("op_stream.watch: extra failed op=%s", op, exc_info=True)
            return []

    yield sse("accepted", {"op": op, "state": state, "at": datetime.now(KST).isoformat(timespec="seconds")})
    for chunk in await content():
        yield chunk
    if done(state):
        yield sse("result", {"state": state})
        return
    failures = 0
    while True:
        await asyncio.sleep(poll_seconds)
        if await is_disconnected():
            return
        now = clock()
        if now - started >= cfg["max_seconds"]:
            yield sse("error", {"code": "timeout", "retryable": True, "elapsed": round(now - started, 1),
                                "message": "오래 걸려 기다리기를 멈췄어요 — 다시 연결하면 지금 상태부터 이어서 보여 드려요"})
            return
        try:
            fresh = await snapshot()
            failures = 0
        except Exception:                          # noqa: BLE001 — 읽기 한 번의 실패는 다음 틱에 다시. 연속이면 닫는다
            failures += 1
            log.warning("op_stream.watch: read failed (%s) op=%s", failures, op, exc_info=failures == 1)
            if failures >= 5:
                yield sse("error", {"code": "unavailable", "retryable": True,
                                    "message": "상태를 읽지 못하고 있어요 — 다시 연결해 주세요"})
                return
            fresh = None
        if fresh is None and failures == 0:
            yield sse("error", {"code": "not_found", "retryable": False, "message": "찾을 수 없어요", "status": 404})
            return
        if fresh is not None:
            state = fresh
            new_stage = stage_of(state)
            if new_stage != stage:
                stage, stage_started, last_beat = new_stage, now, now
                yield sse("stage", {"stage": stage, "label": (label_of_state(state) if label_of_state else stage),
                                    "elapsed": round(now - started, 1), "state": state})
            for chunk in await content():
                yield chunk
            if done(state):
                yield sse("result", {"state": state})
                return
            quiet = quiet_for(state) if quiet_for else None
            if stalled_after is not None and quiet is not None and quiet >= stalled_after:
                yield sse("error", {"code": "stalled", "retryable": True, "stage": stage,
                                    "message": "읽는 일이 멈춘 것 같아요 — 다시 올려 주세요", "quiet_seconds": round(quiet, 1)})
                return
        if now - last_beat >= cfg["beat_seconds"]:
            last_beat = now
            label = label_of_state(state) if (label_of_state and state) else stage
            yield sse("beat", {"elapsed": round(now - started, 1), "stage": stage, "label": label,
                               "stage_elapsed": round(now - stage_started, 1),
                               "slow": (now - stage_started) >= cfg["slow_seconds"],
                               "server_time": datetime.now(KST).isoformat(timespec="seconds")})


__all__ = ["STAGES", "Progress", "acquire", "error_payload", "label_of", "limits", "release", "run", "sse", "watch"]
