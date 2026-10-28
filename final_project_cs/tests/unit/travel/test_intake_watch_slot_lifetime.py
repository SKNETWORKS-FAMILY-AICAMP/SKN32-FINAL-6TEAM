"""접수 읽기 SSE — 연결이 끊긴 뒤에도 **도는 DB 조회 · 내용 계산이 끝날 때까지** 사용자당 슬롯 · 전역 스레드 상한이 그것을 묶는지 잰다. `[2026-10-28]`

배경: beat 분리 후보(35e1b0259) 독립 검토(`wiki/records/reports/2026-10-28_접수SSE_슬롯수명_후속.md`).
`watch` 가 뒤의 작업을 `cancel()` 하면 native asyncio 취소가 `starlette.run_in_threadpool`(anyio shield)까지 뚫어,
스레드 · psycopg 연결은 계속 도는데 사용자 슬롯(`op_stream.release`)과 anyio limiter 토큰이 먼저 돌아왔다 —
끊고 다시 붙기를 되풀이하면 `max_per_user` · 전역 스레드 상한 밖에서 DB 연결이 늘었다.

★고친 뒤 계약: 끊김 · 닫힘에도 **응답은 곧바로 끝난다**(스레드를 기다리지 않는다). 슬롯 · 토큰은 그 스레드가 끝날 때 돌아온다.
  바깥 취소는 그대로 올라간다. 늦게 온 결과 · 예외는 이벤트로 나오지 않고 「꺼내지 않은 예외」 경고도 없다.

실제 nested endpoint(`build_trip_router` 의 `/v1/web/trip-intakes/{id}/events`)와 실제 Starlette `StreamingResponse` 를 쓰고,
DB 연결 · 내용 계산(`Feed`) · 설정만 메모리 대역으로 바꾼다(DB · 소켓 · 모델 없음). 시간 값은 시험용 축척이다(운영 값 아님).
"""
from __future__ import annotations

import asyncio
import gc
import threading
import time
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import anyio
import anyio.to_thread
import pytest
from fastapi import HTTPException

from app.domains.travel_ops.components.intake import stream as intake_stream
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.modules.live_progress import op_stream
from app.domains.travel_ops.modules.web_account import web_guard

BEAT = 0.1
POLL = 0.02
#: 시험 스케줄링 여유(스레드 전환 · 윈도 타이머 해상도). 운영 값 아님.
SLACK = 0.15
TENANT = "slot-proof"
CUSTOMER = UUID(int=4242)
INTAKE = UUID(int=4343)


def _cfg(max_seconds: float = 30.0, cap: float = 3.0) -> dict[str, float]:
    return {"beat_seconds": BEAT, "slow_seconds": 8.0, "max_per_user": cap, "max_seconds": max_seconds}


def _st(stage: str = "reading", status: str = "reading") -> dict[str, Any]:
    return {"status": status, "stage": stage, "stage_label": stage, "revision": 1, "fatal_code": None, "quiet_seconds": 0.0}


class _Db:
    """`get_connection` 대역 — 열린 연결 수를 센다. `block_read_on` 번째 상태 조회는 `gate` 가 열릴 때까지 막힌다(DB 가 멈춘 회차)."""

    def __init__(self, gate: threading.Event, *, block_read_on: int | None = None) -> None:
        self.gate, self.block_read_on = gate, block_read_on
        self.lock = threading.Lock()
        self.open = self.max_open = self.reads = 0

    @contextmanager
    def connection(self):
        with self.lock:
            self.open += 1
            self.max_open = max(self.max_open, self.open)
        try:
            yield _Conn(self)
        finally:
            with self.lock:
                self.open -= 1


class _Conn:
    def __init__(self, db: _Db) -> None:
        self.db = db

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql: str, params: Any = None) -> None:
        assert sql.lstrip().upper().startswith("SELECT")         # 읽기 전용 경로만 — 쓰기가 섞이면 시험이 잡는다
        with self.db.lock:
            self.db.reads += 1
            n = self.db.reads
        if n == self.db.block_read_on:
            self.db.gate.wait(10)

    def fetchone(self):
        return ("reading", "reading", 1, None, 0.0)


def _feed_class(gate: threading.Event, *, block_poll_from: int | None):
    class Feed:
        """`intake.stream.Feed` 대역 — 연결마다 하나. `block_poll_from` 번째 내용 계산부터 `gate` 까지 막힌다."""

        def __init__(self, *args: Any) -> None:
            self.polls = 0

        def poll(self, conn, state):
            self.polls += 1
            if block_poll_from is not None and self.polls >= block_poll_from:
                gate.wait(10)
            return []

    return Feed


class _Http:
    """endpoint 가 쓰는 `Request` 의 한 부분(`is_disconnected`)만 — 끊김은 ASGI receive 대역과 같은 깃발을 본다."""

    def __init__(self) -> None:
        self.gone = False

    async def is_disconnected(self) -> bool:
        return self.gone


class _Guard:
    def get(self, key: str):
        return {"travel.op_stream.intake_stalled_seconds": 180.0, "travel.op_stream.intake_poll_seconds": POLL}[key]


@pytest.fixture
def events_endpoint(monkeypatch):
    gate = threading.Event()
    box: dict[str, Any] = {"cap": 3.0}

    def install(*, block_read_on: int | None = None, block_poll_from: int | None = None, cap: float = 3.0) -> _Db:
        db = _Db(gate, block_read_on=block_read_on)
        monkeypatch.setattr(trip_api, "get_connection", db.connection)
        monkeypatch.setattr(intake_stream, "Feed", _feed_class(gate, block_poll_from=block_poll_from))
        box["cap"] = cap
        return db

    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    router = trip_api.build_trip_router()
    route = next(r for r in router.routes if getattr(r, "path", "") == "/v1/web/trip-intakes/{intake_id}/events")
    monkeypatch.setattr(op_stream, "limits", lambda op="message": _cfg(cap=box["cap"]))
    monkeypatch.setattr(trip_api.settings_module, "get_guardrails", lambda: _Guard())
    monkeypatch.setattr(op_stream, "_OPEN", {})
    try:
        yield route.endpoint, install, gate
    finally:
        gate.set()


def _slots() -> int:
    return op_stream._OPEN.get((TENANT, CUSTOMER), 0)


async def _serve(endpoint, *, leave_after: float, spec: str = "2.0") -> dict[str, Any]:
    """endpoint 를 부르고 실제 StreamingResponse 를 ASGI 로 돌린다. `leave_after` 초 뒤 브라우저가 떠난다(탭 닫기).
    spec 2.0 = `http.disconnect` 수신(task group 취소) · 2.4 = 떠난 뒤 send 가 OSError(Starlette 가 ClientDisconnect)."""
    http = _Http()
    try:
        response = await endpoint(intake_id=INTAKE, http=http, who=(TENANT, CUSTOMER))
    except HTTPException as refused:
        return {"status": refused.status_code}
    names: list[str] = []
    marks: dict[str, float] = {}

    async def receive():
        if spec == "2.4":                                          # 2.4 경로는 receive 를 듣지 않는다 — 떠남은 아래 타이머가 표시한다
            await asyncio.Event().wait()
        await asyncio.sleep(leave_after)
        marks["left"] = time.monotonic()
        http.gone = True
        return {"type": "http.disconnect"}

    def leave() -> None:
        marks["left"] = time.monotonic()
        http.gone = True

    async def send(message):
        if spec == "2.4" and http.gone:
            raise OSError("client gone")
        if message["type"] == "http.response.body" and message.get("body"):
            names.extend(line[7:] for line in message["body"].decode().splitlines() if line.startswith("event: "))

    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": spec}, "method": "GET", "path": "/", "headers": []}
    if spec == "2.4":
        asyncio.get_running_loop().call_later(leave_after, leave)
    try:
        await response(scope, receive, send)
    except Exception as exc:                                       # noqa: BLE001 — 2.4 ClientDisconnect 기록
        marks["raised"] = type(exc).__name__
    returned = time.monotonic()
    del response
    gc.collect()                                                   # 2.4 경로: 닫히지 않은 본문 생성기의 마무리를 지금 돌린다(asyncgen hook)
    await asyncio.sleep(0)
    return {"status": 200, "names": names, "raised": marks.get("raised"),
            "returned_after_leave": (returned - marks["left"]) if "left" in marks else None}   # None = 떠나기 전에 끝났다


async def _until(pred, timeout: float = 3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        await asyncio.sleep(0.01)
    return pred()


def _others() -> list[asyncio.Task]:
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]


# ------------------------------------------------------------------------------------------------ 실제 endpoint
@pytest.mark.parametrize("spec", ["2.0", "2.4"])
@pytest.mark.parametrize("where", ["content", "read"])
def test_a_browser_that_leaves_mid_query_gets_its_response_ended_at_once_but_the_slot_waits_for_the_thread(events_endpoint, where, spec):
    endpoint, install, gate = events_endpoint
    # read: 앞선 404 확인(1) · 첫 조회(2) 뒤 폴링 조회(3) 가 막힘 / content: 두 번째 내용 계산부터 막힘
    db = install(block_read_on=3) if where == "read" else install(block_poll_from=2)

    async def main():
        problems: list[dict] = []
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: problems.append(ctx))
        out = await _serve(endpoint, leave_after=0.4, spec=spec)
        limiter = anyio.to_thread.current_default_thread_limiter()
        during = {"slots": _slots(), "open": db.open, "tokens": limiter.borrowed_tokens}
        gate.set()
        settled = await _until(lambda: _slots() == 0 and db.open == 0 and limiter.borrowed_tokens == 0)
        await asyncio.sleep(0.05)
        return out, during, settled, problems, _others()

    out, during, settled, problems, left = asyncio.run(main())
    assert out["status"] == 200 and "result" not in out["names"]
    assert out["returned_after_leave"] <= BEAT + SLACK, f"응답이 떠난 뒤 {out['returned_after_leave']:.3f}s 지나 끝났다(스레드를 기다렸다)"
    assert during["open"] == 1, during                                      # 멈춘 DB 조회는 실제로 아직 열려 있다
    assert during["slots"] == 1, f"연결은 열려 있는데 슬롯이 먼저 돌아왔다: {during}"
    if where == "content":                                                   # run_in_threadpool — 전역 스레드 상한 토큰도 스레드와 함께
        assert during["tokens"] == 1, f"anyio 토큰이 스레드보다 먼저 돌아왔다: {during}"
    assert settled and problems == [] and left == []


def test_a_reconnect_storm_while_the_db_hangs_is_held_to_the_per_user_cap(events_endpoint):
    """탭 닫기 · 다시 열기를 5번 — 내용 계산이 매번 멈춘다. 상한 3 이면 4 · 5번째는 429 이고 동시에 열린 DB 연결은 3 을 넘지 않는다."""
    endpoint, install, gate = events_endpoint
    db = install(block_poll_from=2, cap=3.0)

    async def main():
        problems: list[dict] = []
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: problems.append(ctx))
        limiter = anyio.to_thread.current_default_thread_limiter()
        statuses, peak_tokens = [], 0
        for _ in range(5):
            out = await _serve(endpoint, leave_after=0.25)
            statuses.append(out["status"])
            peak_tokens = max(peak_tokens, limiter.borrowed_tokens)
        held = {"slots": _slots(), "open": db.open, "max_open": db.max_open, "tokens": limiter.borrowed_tokens}
        gate.set()
        settled = await _until(lambda: _slots() == 0 and db.open == 0 and limiter.borrowed_tokens == 0)
        after = await _serve(endpoint, leave_after=0.05)                 # 다 끝난 뒤에는 다시 열린다
        gate.set()
        await _until(lambda: _slots() == 0 and db.open == 0)
        await asyncio.sleep(0.05)
        return statuses, held, peak_tokens, settled, after["status"], problems, _others()

    statuses, held, peak_tokens, settled, after, problems, left = asyncio.run(main())
    assert statuses == [200, 200, 200, 429, 429], statuses
    assert held == {"slots": 3, "open": 3, "tokens": 3, "max_open": held["max_open"]}, held
    # 거절된 요청도 429 전에 404 확인 조회(`run_in_threadpool(read)`, 짧게 끝남)를 한 번 한다 — 그 한 개만 상한 위에 잠깐 겹친다(기존 순서)
    assert held["max_open"] <= 3 + 1, held
    assert peak_tokens <= 3
    assert settled and after == 200 and problems == [] and left == []


def test_a_normal_end_gives_the_slot_back_before_the_response_finishes(events_endpoint):
    endpoint, install, gate = events_endpoint
    db = install()
    rows = {"n": 0}

    def fetchone(self):                                            # 404 확인 · 첫 조회는 읽는 중, 다음 폴링에서 확인 화면
        rows["n"] += 1
        return ("reading", "reading", 1, None, 0.0) if rows["n"] <= 2 else ("review", "review", 1, None, 0.0)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_Conn, "fetchone", fetchone)

        async def main():
            out = await _serve(endpoint, leave_after=5.0)
            return out, _slots(), db.open

        out, slots, opened = asyncio.run(main())
    assert out["names"][0] == "accepted" and out["names"][-1] == "result"
    assert slots == 0 and opened == 0


# ------------------------------------------------------------------------------------------------ watch 자체
def _watch(read, *, extra=None, settle=None, cfg=None, is_disconnected=None):
    async def never():
        return False

    return op_stream.watch(read, op="intake", cfg=cfg or _cfg(), done=lambda s: s["status"] in ("review", "confirmed", "fatal"),
                           stage_of=lambda s: s["stage"], label_of_state=lambda s: s["stage_label"],
                           quiet_for=lambda s: s["quiet_seconds"], is_disconnected=is_disconnected or never,
                           poll_seconds=POLL, extra=extra, settle=settle)


def _gated_reader(gate: threading.Event, *, block_on: int, then: Any = None):
    n = {"c": 0}

    def read():
        n["c"] += 1
        if n["c"] == block_on:
            gate.wait(10)
            if isinstance(then, BaseException):
                raise then
        return _st()

    return read, n


def test_an_outer_cancel_propagates_at_once_and_the_slot_is_settled_only_after_the_thread():
    gate = threading.Event()
    read, _ = _gated_reader(gate, block_on=2)
    settled: list[float] = []

    async def main():
        problems: list[dict] = []
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: problems.append(ctx))

        async def consume():
            async for _ in _watch(read, settle=lambda: settled.append(time.monotonic())):
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.3)                                               # 두 번째 조회가 막혀 있다
        t0 = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        took = time.monotonic() - t0
        before = list(settled)
        released = time.monotonic()
        gate.set()
        await _until(lambda: bool(settled))
        await asyncio.sleep(0.05)
        return took, before, released, problems, _others(), task.cancelled()

    try:
        took, before, released, problems, left, cancelled = asyncio.run(main())
    finally:
        gate.set()
    assert cancelled and took <= SLACK, took                                  # 취소는 삼키지 않고 곧바로 올라간다
    assert before == [] and len(settled) == 1 and settled[0] >= released
    assert problems == [] and left == []


def test_aclose_and_an_anyio_cancel_scope_do_not_wait_for_the_thread_and_settle_exactly_once():
    for how in ("aclose", "scope"):
        gate = threading.Event()
        read, _ = _gated_reader(gate, block_on=2)
        settled: list[str] = []

        async def main():
            problems: list[dict] = []
            asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: problems.append(ctx))
            gen = _watch(read, settle=lambda: settled.append(how))
            if how == "aclose":
                await gen.__anext__()
                await asyncio.sleep(0.25)
                t0 = time.monotonic()
                await gen.aclose()
                took = time.monotonic() - t0
            else:
                t0 = time.monotonic()
                with anyio.move_on_after(0.3):
                    async for _ in gen:
                        pass
                took = time.monotonic() - t0 - 0.3                 # 시한(0.3초) 뒤 얼마나 더 걸렸나
            mid = list(settled)
            gate.set()
            await _until(lambda: bool(settled))
            await asyncio.sleep(0.05)
            return took, mid, problems, _others()

        try:
            took, mid, problems, left = asyncio.run(main())
        finally:
            gate.set()
        assert took <= SLACK, (how, took)
        assert mid == [] and settled == [how], (how, mid, settled)
        assert problems == [] and left == [], how


def test_a_late_failure_of_an_abandoned_read_is_dropped_without_unretrieved_exception_warnings():
    gate = threading.Event()
    read, _ = _gated_reader(gate, block_on=2, then=RuntimeError("db went away late"))
    settled: list[int] = []

    async def main():
        problems: list[dict] = []
        asyncio.get_running_loop().set_exception_handler(lambda _l, ctx: problems.append(ctx))
        gen = _watch(read, settle=lambda: settled.append(1))
        await gen.__anext__()
        await asyncio.sleep(0.25)
        await gen.aclose()
        gate.set()
        await _until(lambda: bool(settled))
        await asyncio.sleep(0.05)
        gc.collect()
        await asyncio.sleep(0)
        return problems, _others()

    try:
        problems, left = asyncio.run(main())
    finally:
        gate.set()
    assert settled == [1] and problems == [] and left == []


def test_settle_runs_exactly_once_on_every_kind_of_end():
    def run(read, **kw) -> tuple[list[str], int]:
        settled: list[int] = []

        async def main():
            names = []
            async for chunk in _watch(read, settle=lambda: settled.append(1), **kw):
                names.append(chunk.split("\n", 1)[0][7:])
            await asyncio.sleep(0.02)
            return names

        return asyncio.run(main()), len(settled)

    seq = iter([_st(), _st("review", "review")])
    assert run(lambda: next(seq)) == (["accepted", "stage", "result"], 1)
    assert run(lambda: None) == (["error"], 1)                                # not_found

    def broken():
        raise RuntimeError("db down")

    assert run(broken) == (["error"], 1)                                      # 첫 조회 실패 → unavailable

    gate = threading.Event()
    read, _ = _gated_reader(gate, block_on=1)
    settled: list[int] = []

    async def timeout_then_release():
        names = [c.split("\n", 1)[0][7:] async for c in _watch(read, settle=lambda: settled.append(1), cfg=_cfg(max_seconds=0.3))]
        mid = len(settled)
        gate.set()
        await _until(lambda: bool(settled))
        return names, mid

    try:
        names, mid = asyncio.run(timeout_then_release())
    finally:
        gate.set()
    assert names == ["error"] and mid == 0 and settled == [1]                # 시한으로 끝나도 막힌 첫 조회가 끝날 때 돌려준다


def test_a_failure_before_the_poller_starts_still_settles(monkeypatch):
    def broken_limits(op="message"):
        raise KeyError("travel.op_stream.max_seconds.intake")

    monkeypatch.setattr(op_stream, "limits", broken_limits)
    settled: list[int] = []

    async def main():
        gen = op_stream.watch(lambda: _st(), op="intake", done=lambda s: False, stage_of=lambda s: s["stage"],
                              is_disconnected=lambda: False, settle=lambda: settled.append(1))
        with pytest.raises(KeyError):
            await gen.__anext__()

    asyncio.run(main())
    assert settled == [1]
