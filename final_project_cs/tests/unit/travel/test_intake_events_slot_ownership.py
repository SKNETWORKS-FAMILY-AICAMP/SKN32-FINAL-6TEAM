"""접수 읽기 SSE — 사용자 슬롯(`op_stream.acquire`)을 잡은 **뒤 본문이 돌기 전**의 길에서도 슬롯이 돌아오는지. `[2026-10-28]`

배경: role-manager 위 SSE beat 후보(35e1b0259 + 20a9a2bdf) Codex 검토 — 슬롯은 본문 생성기(`flow`)가 돌아야 돌려주는데,
 ①`acquire` 와 응답 반환 사이의 실패(설정 · `Feed` 만들기),
 ②본문이 첫 순회도 하기 전에 브라우저가 떠남(spec 2.0 — `http.disconnect` 가 먼저 와 task group 이 `stream_response` 를 취소),
에서는 슬롯이 그대로 남았다(①② RED). 사용자당 3개(`travel.op_stream.max_per_user`)가 차면 그 사용자는 프로세스가 끝날 때까지 429 다.
 ③spec 2.4 의 send 실패(`ClientDisconnect`) 뒤 멈춘 본문 생성기는 GC 없이도 이미 슬롯이 돌아왔다(watch 가 `is_disconnected` 로 끝낸다) — 회귀 감시로 둔다.

★계약: 위 세 길(①②③)에서 슬롯은 정확히 한 번 돌아온다. 본문이 돈 경우는 기존대로 그 연결의 조회 · 내용 계산이 끝날 때(`settle`).
실제 nested endpoint 와 실제 Starlette `StreamingResponse` 를 쓰고 DB · `Feed` · 설정만 메모리 대역(`test_intake_watch_slot_lifetime` 의 것).
"""

from __future__ import annotations

import asyncio
import gc

import pytest
from fastapi import HTTPException

from app.domains.travel_ops.components.intake import stream as intake_stream
from app.domains.travel_ops.modules.live_progress import op_stream

from .test_intake_watch_slot_lifetime import (  # noqa: F401 — 같은 대역 · 픽스처
    CUSTOMER,
    INTAKE,
    TENANT,
    _Http,
    _slots,
    _until,
    events_endpoint,
)


def _scope(spec: str) -> dict:
    return {"type": "http", "asgi": {"version": "3.0", "spec_version": spec}, "method": "GET", "path": "/", "headers": []}


def test_a_failure_after_the_slot_is_taken_gives_it_back(events_endpoint, monkeypatch):
    endpoint, install, _gate = events_endpoint
    install()

    class Broken:
        def __init__(self, *args):
            raise RuntimeError("feed construction failed")

    monkeypatch.setattr(intake_stream, "Feed", Broken)

    async def main():
        with pytest.raises(RuntimeError):
            await endpoint(intake_id=INTAKE, http=_Http(), who=(TENANT, CUSTOMER))
        return _slots()

    assert asyncio.run(main()) == 0


def test_a_browser_gone_before_the_body_starts_does_not_keep_the_slot(events_endpoint):
    """spec 2.0 — `http.disconnect` 가 곧바로 오고 첫 send(응답 머리)가 늦으면 task group 이 본문 첫 순회 전에 취소한다."""
    endpoint, install, _gate = events_endpoint
    install()

    async def main():
        http = _Http()
        response = await endpoint(intake_id=INTAKE, http=http, who=(TENANT, CUSTOMER))
        held = _slots()
        bodies: list[bytes] = []

        async def receive():
            http.gone = True
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.start":
                await asyncio.sleep(1.0)  # 느린 망 — 머리를 보내는 동안 떠남이 먼저 처리된다
            elif message.get("body"):
                bodies.append(message["body"])

        await response(_scope("2.0"), receive, send)
        back = await _until(lambda: _slots() == 0, timeout=1.0)
        return held, back, bodies

    held, back, bodies = asyncio.run(main())
    assert held == 1 and bodies == []  # 본문은 정말 한 번도 돌지 않았다
    assert back, f"본문이 돌기 전에 떠난 연결의 슬롯이 남았다: {_slots()}"


def test_a_2_4_send_failure_settles_without_waiting_for_garbage_collection(events_endpoint):
    """spec 2.4 — 떠난 뒤 send 가 OSError(Starlette 가 ClientDisconnect). 응답 객체를 붙든 채(GC 없음) 막힌 내용 계산이 풀리면 슬롯이 돌아온다."""
    endpoint, install, gate = events_endpoint
    db = install(block_poll_from=2)

    async def main():
        http = _Http()
        response = await endpoint(intake_id=INTAKE, http=http, who=(TENANT, CUSTOMER))

        async def receive():
            await asyncio.Event().wait()

        async def send(message):
            if http.gone:
                raise OSError("client gone")

        asyncio.get_running_loop().call_later(0.3, lambda: setattr(http, "gone", True))
        raised = None
        try:
            await response(_scope("2.4"), receive, send)
        except Exception as exc:  # noqa: BLE001 — ClientDisconnect 기록
            raised = type(exc).__name__
        during = _slots()
        gate.set()
        back = await _until(lambda: _slots() == 0 and db.open == 0, timeout=2.0)
        keep = response  # 응답(과 그 본문 생성기)을 끝까지 붙든다 — GC 로 닫히는 길을 막는다
        return raised, during, back, keep is not None

    gc.disable()
    try:
        raised, during, back, _ = asyncio.run(main())
    finally:
        gc.enable()
    assert raised == "ClientDisconnect"
    assert during == 1  # 막힌 내용 계산이 아직 돈다 — 슬롯은 그것을 묶는다
    assert back, f"send 실패 뒤 본문 생성기가 닫히지 않아 슬롯이 남았다: {_slots()}"


def test_a_refused_429_does_not_touch_other_slots(events_endpoint):
    """상한에서 거절된 요청은 슬롯을 잡지 않았다 — 돌려주지도 않는다(남의 슬롯을 깎지 않는다)."""
    endpoint, install, _gate = events_endpoint
    install(cap=1.0)

    async def main():
        op_stream._OPEN[(TENANT, CUSTOMER)] = 1
        with pytest.raises(HTTPException) as refused:
            await endpoint(intake_id=INTAKE, http=_Http(), who=(TENANT, CUSTOMER))
        return refused.value.status_code, _slots()

    assert asyncio.run(main()) == (429, 1)
