# -*- coding: utf-8 -*-
"""웹 실시간 진행(SSE) — `op_stream.py`, 채팅 · 일정 짜기 · 접수 읽기. `[2026-10-02 사용자 지시]`

☆지키려는 것: 서버·모델이 멈춰도 사용자가 **자기 요청의 상태를 안다.** 그래서 시험이 보는 것은 ①받자마자 첫 신호가 오는가
②일꾼이 막혀 있어도 생존 신호(beat)가 계속 오는가 ③시간이 넘으면 매달리지 않고 error 로 끝나는가 ④끊겨도 응답 뒤 일이 **정확히 한 번** 도는가
⑤결과 본문이 기존 JSON 응답과 같은가 ⑥남의 것은 404 · 열린 연결 상한은 429 · 읽는 일꾼이 죽으면 stalled 로 끝나는가.

재현:

    python -m pytest tests/e2e/test_op_stream.py -v
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import op_stream

# ★픽스처가 둘이다 — 일정 짜기는 장소가 심어진 플래너 쪽(`plan_api`), 채팅은 Case 를 지우는 정리가 있는 여행 API 쪽(`trip_api`)
from .test_trip_api import api as trip_api  # noqa: F401
from .test_trip_planner import START, api as plan_api  # noqa: F401
from .test_web_api import _web_body  # noqa: F401

FAST = {"beat_seconds": 0.05, "slow_seconds": 0.12, "max_seconds": 5.0, "max_per_user": 3}


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        if lines and lines[0].startswith("event: "):
            out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


def _parse(chunks: list[str]) -> list[tuple[str, dict]]:
    return _events("".join(chunks))


async def _never() -> bool:
    return False


async def _collect(gen) -> list[str]:
    return [chunk async for chunk in gen]


def _run(work, *, cfg=None, disconnect_after: float | None = None, op="message") -> list[tuple[str, dict]]:
    started = time.monotonic()

    async def gone() -> bool:
        return disconnect_after is not None and time.monotonic() - started >= disconnect_after

    chunks = asyncio.run(_collect(op_stream.run(work, op=op, is_disconnected=gone, cfg={**FAST, **(cfg or {})})))
    return _parse(chunks)


# ── 흐름(도메인 없이) ─────────────────────────────────────────────

def test_the_first_signal_comes_at_once_then_stages_then_the_result():
    """①⑤ 받자마자 `accepted`, 일꾼이 단계에 들어갈 때 `stage`(이름 + 고객에게 보일 말), 끝나면 `result` 본문 그대로."""
    def work(progress, defer):
        progress.stage("understanding")
        progress.stage("applying")
        return {"status": "answered", "answer": "안녕"}

    events = _run(work)
    names = [name for name, _ in events]
    assert names[0] == "accepted" and names[-1] == "result"
    stages = [data for name, data in events if name == "stage"]
    assert [s["stage"] for s in stages] == ["understanding", "applying"]
    assert stages[0]["label"] == "요청을 이해하는 중이에요" and stages[0]["waiting_on"] == "model"
    assert events[-1][1] == {"status": "answered", "answer": "안녕"}


# invariant: INV-CS-RT-021
def test_beats_keep_coming_while_the_worker_is_blocked_and_flag_a_slow_model():
    """② 일꾼이 모델 호출에 막혀 있어도 **이벤트 루프가** beat 를 낸다 — 이게 끊기면 서버·연결이 죽은 것이다.
    모델을 기다리는 단계가 `slow_seconds` 를 넘으면 `slow=true` 로 「서버는 살아 있고 모델이 느리다」를 알린다."""
    def work(progress, defer):
        progress.stage("understanding")
        time.sleep(0.5)
        return {"ok": True}

    events = _run(work)
    beats = [data for name, data in events if name == "beat"]
    assert len(beats) >= 4, events
    assert all(b["stage"] == "understanding" and b["waiting_on"] == "model" and b["server_time"] for b in beats)
    assert not beats[0]["slow"] and beats[-1]["slow"] and beats[-1]["stage_elapsed"] >= 0.12
    assert events[-1][0] == "result"


def test_an_unknown_stage_name_is_shown_as_it_is():
    """서버가 새 단계를 더해도 웹이 깨지지 않는다 — 이름이 표에 없으면 이름을 그대로 보인다."""
    events = _run(lambda progress, defer: (progress.stage("brand_new_step"), {"x": 1})[1])
    [stage] = [data for name, data in events if name == "stage"]
    assert stage["label"] == "brand_new_step" and stage["waiting_on"] is None


def test_past_max_seconds_it_ends_with_a_timeout_error_and_the_worker_still_finishes():
    """③ 매달려 있지 않고 `error{timeout, retryable}` 로 끝낸다 — 일꾼은 **멈추지 않고** 끝까지 돈다(처리 중인 요청을 버리지 않는다)."""
    finished = threading.Event()

    def work(progress, defer):
        progress.stage("understanding")
        time.sleep(0.6)
        finished.set()
        return {"late": True}

    events = _run(work, cfg={"max_seconds": 0.25})
    assert events[-1][0] == "error" and events[-1][1]["code"] == "timeout" and events[-1][1]["retryable"] is True
    assert "result" not in [name for name, _ in events]
    assert finished.wait(2), "일꾼이 끝까지 돌지 않았다"


class _Refused(Exception):
    """HTTPException 모양(`status_code` + `detail={"error": …}`)."""
    status_code = 422
    headers: dict[str, str] = {}

    def __init__(self):
        self.detail = {"error": {"code": "too_many_places", "message": "장소가 너무 많다", "relax": ["days"]}}


def test_a_refusal_becomes_an_error_event_with_its_reason_and_an_unknown_failure_hides_its_text():
    """못 짠 이유 · 완화 조건은 `error` 몸통에 그대로. 모르는 예외는 원문(키 · 내부 사정)을 싣지 않는다."""
    def refuse(progress, defer):
        raise _Refused()

    [*_, (name, data)] = _run(refuse)
    assert name == "error" and data["code"] == "too_many_places" and data["status"] == 422
    assert data["relax"] == ["days"] and data["retryable"] is False

    def boom(progress, defer):
        raise RuntimeError("password=hunter2 host=db.internal")

    [*_, (name, data)] = _run(boom)
    assert name == "error" and data["code"] == "internal" and data["retryable"] is True
    assert "hunter2" not in json.dumps(data) and "db.internal" not in json.dumps(data)


def test_a_busy_backend_error_is_retryable_with_its_wait():
    class Busy(_Refused):
        status_code = 503
        headers = {"Retry-After": "30"}

        def __init__(self):
            self.detail = {"error": {"code": "source_busy", "message": "잠시 뒤 다시"}}

    def busy(progress, defer):
        raise Busy()

    [*_, (name, data)] = _run(busy)
    assert data["retryable"] is True and data["retry_after_seconds"] == 30


def test_deferred_work_runs_exactly_once_after_the_result():
    """④ 응답 뒤로 미룬 일(`defer`)은 결과가 나간 **뒤** 정확히 한 번 돈다."""
    ran: list[str] = []
    done = threading.Event()

    def work(progress, defer):
        defer(lambda: (ran.append("a"), done.set()))
        return {"ok": True}

    events = _run(work)
    assert events[-1][0] == "result"
    assert done.wait(2)
    time.sleep(0.1)
    assert ran == ["a"]


# invariant: INV-CS-RT-022
def test_if_the_client_leaves_midway_the_work_and_its_deferred_part_still_finish_once():
    """④ 연결이 끊겨도 일은 끝나고(처리 중인 요청을 버리지 않는다) 응답 뒤 일은 일꾼이 끝나면서 **정확히 한 번** 돈다."""
    ran: list[str] = []
    done = threading.Event()

    def work(progress, defer):
        progress.stage("understanding")
        time.sleep(0.4)
        defer(lambda: (ran.append("late"), done.set()))
        return {"ok": True}

    events = _run(work, disconnect_after=0.15)
    assert "result" not in [name for name, _ in events]          # 떠난 사용자에게는 더 안 보낸다
    assert done.wait(2), "끊긴 뒤 응답 뒤 일이 돌지 않았다"
    time.sleep(0.1)
    assert ran == ["late"]


def test_a_failing_deferred_task_does_not_break_the_answer():
    def work(progress, defer):
        defer(lambda: 1 / 0)
        return {"ok": True}

    assert _run(work)[-1][0] == "result"
    time.sleep(0.2)                                              # 뒤에서 터져도 로그만 남고 앞의 답은 그대로


# ── 읽기 진행(DB 가 정본) ─────────────────────────────────────────

def _watch(states: list[dict | None], *, cfg=None, **kw) -> list[tuple[str, dict]]:
    """`states` 를 한 틱에 하나씩 읽어 주는 가짜 읽기 — 끝나면 마지막 값을 되풀이."""
    it = iter(states)
    last: dict[str, Any] = {}

    def read():
        nonlocal last
        try:
            last = next(it)
        except StopIteration:
            pass
        return last

    chunks = asyncio.run(_collect(op_stream.watch(
        read, op="intake", is_disconnected=_never, cfg={**FAST, **(cfg or {})}, poll_seconds=0.02,
        done=lambda s: s["status"] in ("review", "confirmed", "fatal"), stage_of=lambda s: s["stage"],
        label_of_state=lambda s: s.get("stage_label", s["stage"]), **kw)))
    return _parse(chunks)


def test_watch_reports_each_stage_change_then_the_end():
    received = {"status": "reading", "stage": "received", "stage_label": "받았어요"}
    reading = {"status": "reading", "stage": "reading", "stage_label": "읽는 중이에요"}
    review = {"status": "review", "stage": "review", "stage_label": "확인해 주세요"}
    events = _watch([received, received, reading, reading, review])
    names = [n for n, _ in events]
    assert names[0] == "accepted" and names[-1] == "result"
    assert [d["stage"] for n, d in events if n == "stage"] == ["reading", "review"]   # 바뀔 때만(received 는 처음이라 accepted 가 말했다)
    assert events[-1][1]["state"]["status"] == "review"


def test_watch_ends_at_once_when_it_is_already_done_and_404s_when_it_is_gone():
    review = {"status": "review", "stage": "review"}
    assert [n for n, _ in _watch([review])] == ["accepted", "result"]
    [(name, data)] = _watch([None])
    assert name == "error" and data["code"] == "not_found" and data["status"] == 404


def test_watch_gives_up_when_the_background_reader_has_gone_quiet_too_long():
    """⑥ 뒤에서 읽던 일꾼이 죽어(서버 재시작) 갱신이 멈추면 영원히 「읽는 중」으로 두지 않는다."""
    quiet = {"status": "reading", "stage": "reading", "quiet_seconds": 400.0}
    events = _watch([quiet, quiet], quiet_for=lambda s: s["quiet_seconds"], stalled_after=180)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "stalled" and events[-1][1]["retryable"] is True


def test_watch_closes_with_unavailable_after_repeated_read_failures():
    calls = {"n": 0}

    def read():
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "reading", "stage": "reading"}
        raise RuntimeError("db down")

    chunks = asyncio.run(_collect(op_stream.watch(
        read, op="intake", is_disconnected=_never, cfg=dict(FAST), poll_seconds=0.01,
        done=lambda s: False, stage_of=lambda s: s["stage"])))
    events = _parse(chunks)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "unavailable" and events[-1][1]["retryable"] is True


# ── 웹 입구(실제 라우트) ──────────────────────────────────────────

SSE = {"Accept": "text/event-stream"}


@pytest.fixture()
def fast_stream(monkeypatch):
    monkeypatch.setattr(op_stream, "limits", lambda op="message": dict(FAST))
    op_stream._OPEN.clear()
    yield
    op_stream._OPEN.clear()


def _key(api) -> dict:
    return {"X-User-Key": api["client"].post("/v1/web/session").json()["user_key"]}


def _web_trip(api, key, request_id="op-1") -> dict:
    made = api["client"].post("/v1/web/trips", json=_web_body(api, request_id=request_id), headers=key)
    assert made.status_code == 201, made.text
    return made.json()


MESSAGE = {"message": "식당이 휴무예요", "at": "2030-01-01T12:00:00+09:00"}   # 모델 없이 끝나는 문장(`no_meal`) — 웹 시험과 같다


def test_planning_over_sse_streams_stages_and_ends_with_the_same_body_as_json(plan_api, fast_stream):
    """⑤ 일정 짜기를 SSE 로 — `planning` → `registering` 단계 뒤 `result` 가 JSON 응답과 같은 모양(`trip` 등록)."""
    client = plan_api["client"]
    key = _key(plan_api)
    intake = client.post("/v1/web/trip-intakes", headers=key, data={"text": ""}).json()["intake_id"]
    view = client.get(f"/v1/web/trip-intakes/{intake}", headers=key).json()
    body = {"revision": view["revision"], "start_date": START.isoformat(), "days": 2, "party_size": 2}
    streamed = client.post(f"/v1/web/trip-intakes/{intake}/plan", headers={**key, **SSE}, json=body)
    assert streamed.status_code == 200 and streamed.headers["content-type"].startswith("text/event-stream")
    events = _events(streamed.text)
    names = [n for n, _ in events]
    assert names[0] == "accepted" and names[-1] == "result"
    stages = [d["stage"] for n, d in events if n == "stage"]
    assert stages[:1] == ["planning"] and "registering" in stages
    final = events[-1][1]
    assert final["status"] == "confirmed" and final["trip"]["created"] is True and "planner" in final
    # 같은 접수·같은 판을 다시 → 이미 등록된 여행을 곧바로(`accepted` → `result`) — 두 번 짜지 않는다
    again = _events(client.post(f"/v1/web/trip-intakes/{intake}/plan", headers={**key, **SSE}, json=body).text)
    assert [n for n, _ in again] == ["accepted", "result"]
    assert again[-1][1]["trip"]["created"] is False and again[-1][1]["trip"]["trip_id"] == final["trip"]["trip_id"]


def test_a_refusal_before_the_stream_opens_is_a_normal_http_error(plan_api, fast_stream):
    """스트림이 열리기 **전**의 거절(남의 접수 404)은 SSE 여도 보통의 HTTP 오류다 — 웹이 한 길로 처리한다."""
    client = plan_api["client"]
    mine, other = _key(plan_api), _key(plan_api)
    intake = client.post("/v1/web/trip-intakes", headers=mine, data={"text": ""}).json()["intake_id"]
    body = {"revision": 1, "start_date": START.isoformat(), "days": 1, "party_size": 2}
    assert client.post(f"/v1/web/trip-intakes/{intake}/plan", headers={**other, **SSE}, json=body).status_code == 404
    assert client.get(f"/v1/web/trip-intakes/{intake}/events", headers=other).status_code == 404


def test_chat_over_sse_ends_with_the_same_answer_as_json(trip_api, fast_stream):
    """⑤ 채팅을 SSE 로 — 같은 문장은 `result` 의 `answer` 가 JSON 응답과 같다. 첫 신호는 `accepted`, 단계는 서버가 실제로 들어간 것만."""
    client = trip_api["client"]
    key = _key(trip_api)
    trip = _web_trip(trip_api, key)
    path = f"/v1/web/trips/{trip['trip_id']}/messages"
    as_json = client.post(path, headers=key, json={"request_id": "json-1", **MESSAGE})
    assert as_json.status_code == 200, as_json.text
    streamed = client.post(path, headers={**key, **SSE}, json={"request_id": "sse-1", **MESSAGE})
    assert streamed.status_code == 200 and streamed.headers["content-type"].startswith("text/event-stream")
    events = _events(streamed.text)
    assert events[0][0] == "accepted" and events[-1][0] == "result"
    assert events[-1][1]["status"] == as_json.json()["status"] == "no_meal"
    assert events[-1][1]["answer"] == as_json.json()["answer"]
    assert "reading" in [d["stage"] for n, d in events if n == "stage"]


def test_chat_over_sse_for_someone_elses_trip_is_404_and_a_repeated_request_is_marked_duplicate(trip_api, fast_stream):
    client = trip_api["client"]
    mine, other = _key(trip_api), _key(trip_api)
    trip = _web_trip(trip_api, mine)
    path = f"/v1/web/trips/{trip['trip_id']}/messages"
    assert client.post(path, headers={**other, **SSE}, json={"request_id": "x", **MESSAGE}).status_code == 404
    body = {"request_id": "same-1", **MESSAGE}
    first = _events(client.post(path, headers={**mine, **SSE}, json=body).text)
    second = _events(client.post(path, headers={**mine, **SSE}, json=body).text)
    assert first[-1][0] == "result" and second[-1][0] == "result"
    assert second[-1][1]["status"] == "duplicate"               # 같은 request_id 는 두 번 처리되지 않는다 — 다시 연결해도 안전하다


def test_too_many_open_streams_is_429(trip_api, monkeypatch):
    monkeypatch.setattr(op_stream, "limits", lambda op="message": {**FAST, "max_per_user": 0})
    op_stream._OPEN.clear()
    client = trip_api["client"]
    key = _key(trip_api)
    trip = _web_trip(trip_api, key)
    refused = client.post(f"/v1/web/trips/{trip['trip_id']}/messages", headers={**key, **SSE},
                          json={"request_id": "cap-1", **MESSAGE})
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "too_many_streams"
    assert refused.headers["retry-after"] == "5"


def test_the_open_stream_count_is_given_back_when_the_stream_ends(trip_api, fast_stream):
    client = trip_api["client"]
    key = _key(trip_api)
    trip = _web_trip(trip_api, key)
    for i in range(5):                                          # 상한 3 보다 많이 연달아 — 돌려주지 않으면 4번째부터 429
        done = client.post(f"/v1/web/trips/{trip['trip_id']}/messages", headers={**key, **SSE},
                           json={"request_id": f"loop-{i}", **MESSAGE})
        assert done.status_code == 200, (i, done.text)
    assert op_stream._OPEN == {}


def test_intake_events_end_at_once_for_a_review_intake_and_close_as_stalled_for_a_dead_reader(plan_api, fast_stream):
    """⑥ 접수 읽기 진행 — 확인 화면 상태면 곧바로 끝, 읽는 중인데 갱신이 `intake_stalled_seconds` 넘게 멈췄으면 `stalled`."""
    client = plan_api["client"]
    key = _key(plan_api)
    intake = client.post("/v1/web/trip-intakes", headers=key, data={"text": ""}).json()["intake_id"]
    ended = _events(client.get(f"/v1/web/trip-intakes/{intake}/events", headers=key).text)
    assert [n for n, _ in ended] == ["accepted", "result"]
    state = ended[-1][1]["state"]
    assert state["status"] == "review" and state["stage"] == "review" and set(state) >= {"stage_label", "revision", "quiet_seconds"}
    assert "claims" not in state and "sources" not in state     # 읽은 값은 싣지 않는다 — 웹이 GET 으로 읽는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='reading', stage='reading', updated_at = now() - interval '1000 seconds' "
                    "WHERE intake_id=%s", (intake,))
    dead = _events(client.get(f"/v1/web/trip-intakes/{intake}/events", headers=key).text)
    assert dead[0][0] == "accepted" and dead[-1][0] == "error" and dead[-1][1]["code"] == "stalled"
    assert dead[-1][1]["retryable"] is True


def test_the_json_entrances_still_answer_json_without_the_sse_header(trip_api):
    """Accept 가 없으면 전과 같은 JSON 한 번 — 에이전트 입구 · 기존 웹 시험이 안 깨진다."""
    client = trip_api["client"]
    key = _key(trip_api)
    trip = _web_trip(trip_api, key)
    plain = client.post(f"/v1/web/trips/{trip['trip_id']}/messages", headers=key, json={"request_id": "plain-1", **MESSAGE})
    assert plain.headers["content-type"].startswith("application/json") and "answer" in plain.json()
