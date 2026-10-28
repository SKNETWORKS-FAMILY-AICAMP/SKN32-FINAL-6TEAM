"""`op_stream.watch` — 접수 읽기 SSE 의 생존 신호(beat)가 DB 조회 · 내용 계산과 떨어져 나가는지 잰다. `[2026-10-28]`

배경: EKS 실제 브라우저 시험(`wiki/records/reports/2026-10-28_eks-browser-80s-reading-latency-readonly.md`)에서
약 58초에 「연결이 끊겼어요」가 떴지만 접수는 정상 완료됐다. 웹은 7초 동안 이벤트가 없으면 끊김으로 본다
(`STREAM_TIMING.watchdogMs`). 고치기 전 `watch` 는 beat 를 `read()` + `extra()` 가 **끝난 뒤에만** 냈다 —
한 회차가 막히면 서버가 살아 있어도 이벤트가 끊긴다.

★이 시험은 **이벤트 사이 최대 간격**을 실제 시계로 잰다(합성 상태 · DB 없음 · 모델 없음).
시험의 시간 값(beat 0.1초 · 막힘 1초 · 허용 0.15초)은 시험용 축척이지 운영 임계값이 아니다.
운영 값은 `config/guardrails.yaml` `travel.op_stream.*` 그대로다. 처리 속도를 재는 시험이 아니다.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

from app.domains.travel_ops.modules.live_progress import op_stream

BEAT = 0.1
POLL = 0.02
BLOCK = 1.0
#: 시험 스케줄링 여유(스레드 전환 · 윈도 타이머 해상도). 운영 값 아님.
SLACK = 0.15


def _cfg(max_seconds: float = 30.0) -> dict[str, float]:
    return {"beat_seconds": BEAT, "slow_seconds": 8.0, "max_per_user": 3.0, "max_seconds": max_seconds}


def _st(stage: str, status: str = "reading", quiet: float = 0.0) -> dict[str, Any]:
    return {"status": status, "stage": stage, "stage_label": stage, "revision": 1, "fatal_code": None,
            "quiet_seconds": quiet}


def _name_data(chunk: str) -> tuple[str, dict]:
    name = data = None
    for line in chunk.strip().splitlines():
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: "):
            data = json.loads(line[6:])
    return name, data or {}


async def _never() -> bool:
    return False


async def _timed(gen, *, stop_after: float = 20.0) -> list[tuple[float, str, dict]]:
    """조각마다 받은 단조 시각을 남긴다. 시험이 매달리지 않게 전체 상한을 둔다(시험용)."""
    out: list[tuple[float, str, dict]] = []
    t0 = time.monotonic()
    out.append((t0, "_start", {}))

    async def consume():
        async for chunk in gen:
            name, data = _name_data(chunk)
            out.append((time.monotonic(), name, data))

    await asyncio.wait_for(consume(), timeout=stop_after)
    out.append((time.monotonic(), "_end", {}))                     # 흐름이 끝난(생성기가 멈춘) 시각 — 끊김 뒤 이벤트 없이 끝나도 잰다
    return out


def _run_released(gen, gate: threading.Event, *, stop_after: float) -> list[tuple[float, str, dict]]:
    """흐름이 끝나면 막아 둔 조회를 **루프 안에서** 풀어 준다 — 그래야 `asyncio.run` 이 끝날 때 남은 스레드를 기다리지 않는다.
    풀린 조회의 늦은 결과가 이벤트로 나오지 않는지는 각 시험이 본다."""

    async def main():
        try:
            return await _timed(gen, stop_after=stop_after)
        finally:
            gate.set()

    return asyncio.run(main())


def _max_gap(events: list[tuple[float, str, dict]]) -> float:
    times = [t for t, _, _ in events]
    return max(b - a for a, b in zip(times, times[1:]))


def _watch(read, *, extra=None, cfg=None, is_disconnected=_never, stalled_after=None, **kw):
    return op_stream.watch(read, op="intake", cfg=cfg or _cfg(),
                           done=lambda s: s["status"] in ("review", "confirmed", "fatal"),
                           stage_of=lambda s: s["stage"], label_of_state=lambda s: s["stage_label"],
                           quiet_for=lambda s: s["quiet_seconds"], is_disconnected=is_disconnected,
                           poll_seconds=POLL, stalled_after=stalled_after, extra=extra, **kw)


class _Reader:
    """정해 둔 상태를 차례로 돌려준다. `block_on` 번째 호출은 `BLOCK` 초 막힌다(DB 가 느린 회차). 동시 호출 수를 센다."""

    def __init__(self, states: list[dict | None], *, block_on: int | None = None, gate: threading.Event | None = None):
        self.states, self.block_on, self.gate = states, block_on, gate
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            self.calls += 1
            n = self.calls
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.gate is not None and n == self.block_on:
                self.gate.wait(10)
            elif n == self.block_on:
                time.sleep(BLOCK)
            return self.states[min(n - 1, len(self.states) - 1)]
        finally:
            with self.lock:
                self.active -= 1


def test_beats_keep_coming_while_a_state_read_is_slow_and_say_what_is_pending():
    reader = _Reader([_st("reading"), _st("reading"), _st("reading"), _st("review", "review")], block_on=3)
    events = asyncio.run(_timed(_watch(reader)))
    names = [n for _, n, _ in events]
    assert names[1] == "accepted" and names[-2] == "result"
    gap = _max_gap(events)
    assert gap <= BEAT + SLACK, f"이벤트 사이 최대 간격 {gap:.3f}s — beat 가 막힌 조회를 기다렸다"
    pending_beats = [d for _, n, d in events if n == "beat" and d.get("pending") == "read"]
    assert len(pending_beats) >= 3
    assert all(isinstance(d["pending_seconds"], (int, float)) and d["pending_seconds"] >= 0 for d in pending_beats)
    assert max(d["pending_seconds"] for d in pending_beats) >= BLOCK / 2   # 막힌 조회가 이어진 만큼 커진다
    assert reader.max_active == 1                                    # 한 연결에 진행 중인 조회는 하나뿐


def test_beats_keep_coming_while_the_content_hook_is_slow():
    reader = _Reader([_st("reading"), _st("reading"), _st("review", "review")])
    calls = {"n": 0}

    async def extra(state):
        calls["n"] += 1
        if calls["n"] == 2:
            await asyncio.to_thread(time.sleep, BLOCK)
        return []

    events = asyncio.run(_timed(_watch(reader, extra=extra)))
    assert [n for _, n, _ in events][-2] == "result"
    gap = _max_gap(events)
    assert gap <= BEAT + SLACK, f"이벤트 사이 최대 간격 {gap:.3f}s — beat 가 내용 계산을 기다렸다"
    assert any(n == "beat" and d.get("pending") == "content" for _, n, d in events)


def test_a_quiet_beat_with_nothing_pending_says_so():
    reader = _Reader([_st("reading")] * 30 + [_st("review", "review")])
    events = asyncio.run(_timed(_watch(reader)))
    beats = [d for _, n, d in events if n == "beat"]
    assert beats, "조용한 동안 beat 가 와야 한다"
    assert all(set(("elapsed", "stage", "label", "stage_elapsed", "slow", "server_time", "pending", "pending_seconds")) <= set(d)
               for d in beats)
    for d in beats:
        assert d["pending"] in (None, "read", "content")
        assert (d["pending"] is None) == (d["pending_seconds"] is None)
    assert any(d["pending"] is None for d in beats)                  # 조회 사이(쉬는 동안)의 beat 는 기다리는 것이 없다


def test_a_beat_carries_the_latest_state_read_in_the_same_stage():
    """같은 단계에서 이름표만 바뀐 상태도 beat 가 마지막으로 확인한 값을 싣는다(고치기 전 동작 유지 — Codex 검토 지적)."""
    first, renamed = _st("reading"), dict(_st("reading"), stage_label="읽는 중(새 이름표)")
    reader = _Reader([first] + [renamed] * 30 + [_st("review", "review")])
    events = asyncio.run(_timed(_watch(reader)))
    labels = [d["label"] for _, n, d in events if n == "beat"]
    assert labels and labels[-1] == "읽는 중(새 이름표)"
    assert [n for _, n, _ in events].count("stage") == 1               # 같은 단계는 stage 를 다시 내지 않는다(review 로 바뀔 때 한 번)


def test_order_stays_stage_then_its_content_then_result_and_nothing_after_the_result():
    reader = _Reader([_st("received"), _st("reading"), _st("review", "review")], block_on=2)

    async def extra(state):
        return [op_stream.sse("line", {"for": state["stage"]})]

    events = asyncio.run(_timed(_watch(reader, extra=extra)))
    seq = [(n, d.get("for") or d.get("stage")) for _, n, d in events if n not in ("beat", "_start", "_end")]
    assert seq[0][0] == "accepted"
    assert seq[1] == ("line", "received")
    i = seq.index(("stage", "reading"))
    assert seq[i + 1] == ("line", "reading")
    assert seq[-2] == ("line", "review") and seq[-1][0] == "result"
    assert events[-2][1] == "result"


def test_a_read_that_never_returns_ends_at_max_seconds_and_its_late_result_is_dropped():
    gate = threading.Event()
    reader = _Reader([_st("reading"), _st("reading"), _st("review", "review")], block_on=2, gate=gate)
    events = _run_released(_watch(reader, cfg=_cfg(max_seconds=0.6)), gate, stop_after=5)
    names = [n for _, n, _ in events]
    assert names[-2] == "error" and events[-2][2]["code"] == "timeout" and events[-2][2]["retryable"] is True
    assert "result" not in names
    assert _max_gap(events) <= BEAT + SLACK
    time.sleep(0.2)                                                  # 풀린 늦은 조회 뒤에도 새 조회를 시작하지 않는다
    assert reader.calls == 2


def test_the_first_read_is_also_bounded_by_max_seconds():
    gate = threading.Event()
    reader = _Reader([_st("reading")], block_on=1, gate=gate)
    events = _run_released(_watch(reader, cfg=_cfg(max_seconds=0.4)), gate, stop_after=5)
    assert [n for _, n, _ in events][1:] == ["error", "_end"]
    assert events[-2][2]["code"] == "timeout"


def test_a_client_that_leaves_during_a_slow_read_ends_the_stream_within_a_beat():
    gate = threading.Event()
    reader = _Reader([_st("reading"), _st("reading")], block_on=2, gate=gate)
    left = {"at": None}

    async def gone():
        if left["at"] is None:
            left["at"] = time.monotonic() + 0.3
        return time.monotonic() >= left["at"]

    events = _run_released(_watch(reader, is_disconnected=gone), gate, stop_after=5)
    assert events[-1][1] == "_end" and events[-1][0] >= left["at"]
    assert events[-1][0] - left["at"] <= BEAT + SLACK + POLL, f"끊긴 뒤 {events[-1][0] - left['at']:.3f}s 지나 끝났다"
    time.sleep(0.2)
    assert reader.calls == 2


def test_closing_the_generator_cancels_the_background_poller_without_warnings():
    gate = threading.Event()
    reader = _Reader([_st("reading"), _st("reading")], block_on=2, gate=gate)

    async def main():
        loop = asyncio.get_running_loop()
        problems: list[dict] = []
        loop.set_exception_handler(lambda _loop, ctx: problems.append(ctx))
        gen = _watch(reader)
        assert _name_data(await gen.__anext__())[0] == "accepted"
        await asyncio.sleep(0.25)
        await gen.aclose()
        gate.set()
        await asyncio.sleep(0.05)
        return problems, [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    try:
        problems, left = asyncio.run(main())
    finally:
        gate.set()
    assert problems == []
    assert left == []


def test_existing_failure_contracts_hold_stalled_unavailable_not_found_and_hook_failure():
    # 갱신이 stalled_after 넘게 멈춤 → stalled
    events = asyncio.run(_timed(_watch(_Reader([_st("reading"), _st("reading", quiet=200)]), stalled_after=180)))
    assert events[-2][1] == "error" and events[-2][2]["code"] == "stalled"
    # 연속 5회 읽기 실패 → unavailable
    n = {"c": 0}

    def flaky():
        n["c"] += 1
        if n["c"] == 1:
            return _st("reading")
        raise RuntimeError("db down")

    events = asyncio.run(_timed(_watch(flaky)))
    assert events[-2][2]["code"] == "unavailable" and n["c"] == 6
    # 첫 읽기 실패 → 곧바로 unavailable, 없어짐 → not_found
    def broken():
        raise RuntimeError("db down")

    assert [n for _, n, _ in asyncio.run(_timed(_watch(broken)))][1:] == ["error", "_end"]
    events = asyncio.run(_timed(_watch(_Reader([_st("reading"), None]))))
    assert events[-2][2]["code"] == "not_found"
    # 내용 훅 실패는 문서대로 로그만 남기고 흐름은 계속(이번 변경 범위 밖 — 계약 유지)
    async def bad_extra(state):
        raise RuntimeError("hook")

    events = asyncio.run(_timed(_watch(_Reader([_st("reading"), _st("review", "review")]), extra=bad_extra)))
    assert events[-2][1] == "result"


def test_an_unexpected_bug_in_a_state_callback_still_propagates_as_before():
    def stage_of(s):
        if s["stage"] == "boom":
            raise KeyError("stage")
        return s["stage"]

    gen = op_stream.watch(_Reader([_st("reading"), _st("boom")]), op="intake", cfg=_cfg(),
                          done=lambda s: False, stage_of=stage_of, is_disconnected=_never, poll_seconds=POLL)
    try:
        asyncio.run(_timed(gen, stop_after=5))
    except KeyError:
        return
    raise AssertionError("콜백의 버그가 조용히 삼켜졌다")
