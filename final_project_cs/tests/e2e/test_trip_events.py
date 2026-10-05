# -*- coding: utf-8 -*-
"""변경 초인종 — `GET /v1/web/trips/{id}/events`. `[2026-09-30 사용자 승인 — ui 세션 전달]`

서버는 내용이 아니라 「이 여행 바뀜」 신호만 보낸다. 시험 세 가지(요청): ①변경 뒤 신호가 오는가 ②남의 키면 막히는가 ③신호가 실패해도 변경이
막히지 않는가. ★TestClient 는 응답을 끝까지 모아 돌려주므로, 연결이 짧게(`max_seconds`) 끝나게 하고 그 사이 다른 스레드가 변경을 일으킨다.

재현:

    python -m pytest tests/e2e/test_trip_events.py -v
"""
from __future__ import annotations

import ast
import threading
import time
from pathlib import Path
from uuid import UUID

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.watch import trip_events
from app.domains.travel_ops.components.itinerary.itinerary import TripStore

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _fresh_limit_cache, _h, _session, _web_body  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
FAST = {"poll_seconds": 0.1, "ping_seconds": 0.3, "max_seconds": 1.6, "max_per_user": 4, "max_failures": 2}


@pytest.fixture()
def fast(monkeypatch):
    monkeypatch.setattr(trip_events, "limits", lambda: dict(FAST))
    trip_events._OPEN.clear()
    yield
    trip_events._OPEN.clear()


def _trip(api, me, request_id="ev-1") -> str:
    made = api["client"].post("/v1/web/trips", json=_web_body(api, request_id=request_id), headers=_h(me["user_key"]))
    assert made.status_code == 201, made.text
    return made.json()["trip_id"]


def _events(body: str) -> list[tuple[str, dict]]:
    import json

    out = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        if lines and lines[0].startswith("event: "):
            out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


def _later(delay: float, work) -> threading.Thread:
    def run():
        time.sleep(delay)
        work()

    thread = threading.Thread(target=run)
    thread.start()
    return thread


def test_a_change_after_connecting_sends_a_signal_with_no_content(api, fast):
    """①: 연결 직후 `ready`, 알림이 생기면 `notice`, 새 판이 생기면 `itinerary` — 내용 · 키는 싣지 않는다."""
    me = _session(api)
    trip_id = _trip(api, me)
    tenant = api["tenant"]
    store = TripStore(tenant)

    def notice():
        with get_connection() as conn, conn.transaction():
            trip, _ = store.latest(conn, UUID(trip_id))
            store.enqueue_notice(conn, trip_id=UUID(trip_id), version=trip["version"] + 100,
                                 payload={"type": "guidance", "text": "비밀 알림 문장 XYZ", "kind": "day_start"})

    def bump():
        with get_connection() as conn, conn.transaction():
            trip, items = store.latest(conn, UUID(trip_id))
            store.append_version(conn, trip_id=UUID(trip_id), base_version=trip["version"], items=items,
                                 reason="customer_request", causes=[])

    threads = [_later(0.35, notice), _later(0.8, bump)]
    response = api["client"].get(f"/v1/web/trips/{trip_id}/events", headers=_h(me["user_key"]))
    for thread in threads:
        thread.join()
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache" and response.headers["x-accel-buffering"] == "no"
    events = _events(response.text)
    assert events[0][0] == "ready" and events[0][1]["trip_id"] == trip_id and events[0][1]["version"] == 1
    changed = [data for name, data in events if name == "trip.changed"]
    assert any("notice" in c["kinds"] for c in changed), events
    assert any("itinerary" in c["kinds"] and c["version"] == 2 for c in changed), events
    assert all(set(c) == {"trip_id", "kinds", "version"} for c in changed)        # 이 세 칸뿐 — 내용은 웹이 다시 읽는다
    assert "비밀 알림 문장" not in response.text and me["user_key"] not in response.text
    assert ": ping" in response.text                                                # 조용한 사이 연결 유지


def test_a_proposal_that_is_decided_or_expires_also_sends_a_signal(api, fast):
    """알림이 안 생기는 변화(제안 선택 · 만료)도 신호가 난다 — Codex 가 짚은 점."""
    me = _session(api)
    trip_id = _trip(api, me, "ev-2")
    tenant = api["tenant"]
    with get_connection() as conn:
        _, items = TripStore(tenant).latest(conn, UUID(trip_id))
    item = next(i for i in items if i.kind == "activity")

    def open_then_expire():
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO pending_changes (tenant_id, trip_id, item_id, base_version, reason, status) "
                        "VALUES (%s,%s,%s,1,'ask_first','open') RETURNING proposal_id", (tenant, trip_id, item.item_id))
            proposal = cur.fetchone()[0]
        time.sleep(0.5)
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE pending_changes SET status='expired', decided_at=now() WHERE proposal_id=%s", (proposal,))

    thread = _later(0.3, open_then_expire)
    response = api["client"].get(f"/v1/web/trips/{trip_id}/events", headers=_h(me["user_key"]))
    thread.join()
    changed = [data for name, data in _events(response.text) if name == "trip.changed"]
    assert len([c for c in changed if c["kinds"] == ["proposal"]]) >= 2, changed      # 생성 한 번 · 만료 한 번


def test_someone_elses_key_or_no_key_gets_the_same_answer_as_other_reads(api, fast):
    """②"""
    mine, other = _session(api), _session(api)
    trip_id = _trip(api, mine, "ev-3")
    client = api["client"]
    assert client.get(f"/v1/web/trips/{trip_id}/events", headers=_h(other["user_key"])).status_code == 404
    assert client.get(f"/v1/web/trips/{trip_id}", headers=_h(other["user_key"])).status_code == 404   # 다른 조회와 같은 응답
    assert client.get(f"/v1/web/trips/{trip_id}/events").status_code == 401
    assert client.get(f"/v1/web/trips/{'0' * 8}-0000-0000-0000-{'0' * 12}/events",
                      headers=_h(mine["user_key"])).status_code == 404
    assert trip_events._OPEN == {}                         # 거절한 요청이 연결 수를 쥐고 있지 않다


def test_too_many_open_streams_for_one_user_are_refused(api, fast, monkeypatch):
    me = _session(api)
    trip_id = _trip(api, me, "ev-4")
    monkeypatch.setattr(trip_events, "limits", lambda: {**FAST, "max_per_user": 1})
    customer = UUID(str(me["customer_id"]))
    assert trip_events.acquire(api["tenant"], customer, cap=1)             # 다른 탭이 이미 하나 열어 둠
    refused = api["client"].get(f"/v1/web/trips/{trip_id}/events", headers=_h(me["user_key"]))
    assert refused.status_code == 429 and refused.headers["retry-after"] == "5"
    assert refused.json()["error"]["code"] == "too_many_streams"
    trip_events.release(api["tenant"], customer)
    ok = api["client"].get(f"/v1/web/trips/{trip_id}/events", headers=_h(me["user_key"]))
    assert ok.status_code == 200 and trip_events._OPEN == {}               # 끝나면 돌려준다


def test_a_failing_signal_does_not_stop_the_change_and_the_stream_just_closes(api, fast, monkeypatch):
    """③: 신호를 읽다 실패해도 일정 변경은 그대로 되고, 스트림은 조용히 닫힌다(웹이 다시 붙고 전부 다시 읽는다)."""
    me = _session(api)
    trip_id = _trip(api, me, "ev-5")
    store = TripStore(api["tenant"])
    real = trip_events.snapshot
    calls = {"n": 0}

    def flaky(conn, tenant_id, trip):
        calls["n"] += 1
        if calls["n"] > 1:                                  # 첫 번째(ready)만 성공
            raise RuntimeError("signal read failed")
        return real(conn, tenant_id, trip)

    monkeypatch.setattr(trip_events, "snapshot", flaky)

    def bump():
        with get_connection() as conn, conn.transaction():
            trip, items = store.latest(conn, UUID(trip_id))
            store.append_version(conn, trip_id=UUID(trip_id), base_version=trip["version"], items=items,
                                 reason="customer_request", causes=[])

    thread = _later(0.2, bump)
    response = api["client"].get(f"/v1/web/trips/{trip_id}/events", headers=_h(me["user_key"]))
    thread.join()
    assert response.status_code == 200 and [n for n, _ in _events(response.text)] == ["ready"]   # 조용히 닫혔다
    detail = api["client"].get(f"/v1/web/trips/{trip_id}", headers=_h(me["user_key"])).json()
    assert detail["version"] == 2                                                  # 변경은 일어났다
    assert trip_events._OPEN == {}


def test_the_change_paths_never_import_the_signal_module():
    """③의 구조 보장 — 일정을 바꾸는 코드(감시 · 되돌리기 · 고르기 · 채팅)는 초인종 모듈을 모른다. 신호가 변경을 막을 길이 없다."""
    # ★`[2026-10-06]` 여행 폴더를 칸으로 나눠(D-CS-013) 파일 이름만으로는 못 찾는다 — 칸 경로까지 적는다.
    changers = ["components/watch/trip_watch.py", "components/watch/trip_watch_cases.py",
                "components/conversation/trip_desk.py", "components/planning/pending.py",
                "components/itinerary/itinerary.py", "components/itinerary/itinerary_changes.py",
                "components/conversation/trip_messages.py", "components/watch/dawn_check.py",
                "components/watch/trip_reminders.py", "scenarios/case_engine.py"]
    for name in changers:
        tree = ast.parse((ROOT / "app/domains/travel_ops" / name).read_text(encoding="utf-8"))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        assert not any("trip_events" in i for i in imported), name


def test_changed_kinds_only_names_what_differs():
    base = {"version": 1, "notices": (0, None), "proposals": ""}
    assert trip_events.changed_kinds(base, dict(base)) == []
    assert trip_events.changed_kinds(base, {**base, "version": 2}) == ["itinerary"]
    assert trip_events.changed_kinds(base, {**base, "notices": (1, "t")}) == ["notice"]
    assert trip_events.changed_kinds(base, {**base, "proposals": "x"}) == ["proposal"]
    assert trip_events.changed_kinds(base, {"version": 2, "notices": (1, "t"), "proposals": "x"}) == \
        ["itinerary", "notice", "proposal"]
