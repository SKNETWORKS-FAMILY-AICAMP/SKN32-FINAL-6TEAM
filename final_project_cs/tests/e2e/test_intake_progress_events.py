# -*- coding: utf-8 -*-
"""검사 진행 알림 — 계산이 끝나는 대로 일정 · 검사 줄 · 이동 · 「n/m」 이 나간다. `[2026-10-03 ui 세션 요청서 2번]`

☆왜: 검사는 한 트랜잭션 안에서 돌고 끝나 커밋돼야 DB 에 보여서, 실시간 진행이 검사 줄 56개 · 이동 12개를 끝난 4.9초에 한꺼번에 냈다(실서버 실측). 이동 계산이 시간의 대부분인데
그동안 화면은 아무것도 몰랐다. 웹은 가짜 진행 연출 없이 **이 이벤트가 오는 만큼만** 진행 막대를 그린다.

★지키려는 것
 ①검사(`review.build`)가 **일정마다** `item` · `check` 를 이동 계산 **전에** 내보낸다 — 이동이 오래 걸려도 일정 검사는 먼저 보인다
 ②이동은 **구간마다** `move` + `progress{moves}`, 운영시간은 **일정마다** `progress{hours}` — `done` 이 1씩 늘어 `total` 에서 끝난다
 ③읽기 일꾼(`process`)이 읽는 동안 「장소 n/m」·검사 이벤트를 보관소에 쌓고, 끝나면 비운다(최종 값은 DB 에서 읽힌다)
 ④SSE(`Feed`)가 보관소를 비워 내보내되, DB 에서 읽은 덜 채운 값으로 **퇴보시키지 않는다**(검사 줄까지 정해 준 일정을 `status: null` 로 덮지 않는다)
 ⑤이벤트가 달라도 **결과는 같다** — 알림은 부가 기능이다(던져도 검사가 계속된다 · 알림이 없어도 최종 검사는 같다)

재현:

    python -m pytest tests/e2e/test_intake_progress_events.py -v
"""
from __future__ import annotations

import json
from uuid import UUID

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.intake import pipeline, progress, stream
from app.domains.travel_ops.components.intake import review as review_module

from .test_intake_review import PLAN, ROOMY, Kakao, Tour, _client, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처


def _build(rv_env, view, events):
    """접수의 지금 판을 `on_event` 를 달아 다시 계산한다(저장하지 않는다)."""
    with get_connection() as conn:
        sources = pipeline._sources(conn, rv_env["tenant"], UUID(view["intake_id"]))
        claims = pipeline.effective(pipeline._claims(conn, rv_env["tenant"], UUID(view["intake_id"]), view["revision"]))
        return review_module.build(conn, tenant_id=rv_env["tenant"], intake_id=UUID(view["intake_id"]), revision=view["revision"],
                                   sources=sources, claims=claims, use_engine=False, on_event=lambda n, b: events.append((n, b)))


def test_each_item_is_reported_before_the_slow_moves_and_the_counts_climb_to_the_total(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    events: list[tuple[str, dict]] = []
    built = _build(rv, view, events)
    names = [n for n, _ in events]
    first_move = names.index("move")
    assert all(n in ("progress", "item", "check") for n in names[:first_move])                    # ★이동 앞에는 일정 · 검사 줄만 있다
    assert names.count("item") == len(built["items"]) and names.count("move") == len(built["moves"]) > 0
    last_item = max(i for i, n in enumerate(names) if n == "item")
    assert last_item < first_move                                                                   # 모든 일정이 첫 이동보다 먼저 나간다
    # 「n/m」 — 운영시간은 일정마다, 이동은 구간마다 1씩 늘어 total 에서 끝난다
    hours = [b for n, b in events if n == "progress" and b["phase"] == "hours"]
    moves = [b for n, b in events if n == "progress" and b["phase"] == "moves"]
    assert [b["done"] for b in hours] == list(range(1, len(built["items"]) + 1)) and {b["total"] for b in hours} == {len(built["items"])}
    assert [b["done"] for b in moves] == list(range(1, len(built["moves"]) + 1)) and {b["total"] for b in moves} == {len(built["moves"])}
    assert hours[0]["current"] == {"id": built["items"][0]["id"], "title": built["items"][0]["title"]}      # 지금 무엇을 확인하나
    assert moves[0]["current"]["title"].count("→") == 1 and moves[0]["current"]["id"].count(">") == 1
    # 이벤트의 값이 최종 검사와 같다(같은 키로 DB 의 최종 값이 와서 덮어도 되는 모양)
    by_id = {b["id"]: b for n, b in events if n == "item"}
    for item in built["items"]:
        got = by_id[item["id"]]
        assert {k: got[k] for k in ("title", "kind", "starts_at", "ends_at", "place_state")} == {k: item[k] for k in ("title", "kind", "starts_at", "ends_at", "place_state")}
        assert got["place"] is None or "place_id" not in got["place"]                               # 내부 칸(장소 행 번호)은 싣지 않는다
    checks = [(b["item"], b["row"]) for n, b in events if n == "check"]
    assert len(checks) == len(set(checks)) == sum(len(i["rows"]) for i in built["items"])


def test_building_with_and_without_a_listener_gives_the_same_review(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    with_events = _build(rv, view, [])
    without = _build(rv, view, [])
    for part in ("items", "moves", "needs", "ready"):
        assert with_events[part] == without[part], part
    # 알림이 던져도 검사는 계속된다
    def boom(*_a):
        raise RuntimeError("알림 장애")

    with get_connection() as conn:
        survived = review_module.build(conn, tenant_id=rv["tenant"], intake_id=UUID(view["intake_id"]), revision=view["revision"],
                                       sources=pipeline._sources(conn, rv["tenant"], UUID(view["intake_id"])),
                                       claims=pipeline.effective(pipeline._claims(conn, rv["tenant"], UUID(view["intake_id"]), view["revision"])),
                                       use_engine=False, on_event=boom)
    assert survived["items"] == without["items"]


def test_the_reading_worker_stores_progress_while_it_reads_and_clears_it_at_the_end(rv, monkeypatch):
    tour, kakao = Tour(), Kakao()
    with get_connection() as conn:
        intake_id = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], text=PLAN, files=[])
    kept: list[tuple[str, dict]] = []
    real_clear = progress.clear

    def spy_clear(key):                                           # 비우기 직전의 보관소를 본다
        kept.extend(progress.drain(str(key), 0)[0])
        real_clear(key)

    monkeypatch.setattr(progress, "clear", spy_clear)
    assert pipeline.process(get_connection, tenant_id=rv["tenant"], intake_id=intake_id, blobs={}, see=None, tour=tour, kakao=kakao) == "review"
    phases = [(b["phase"], b["done"], b["total"]) for n, b in kept if n == "progress"]
    places = [p for p in phases if p[0] == "places"]
    assert places == [("places", n, 4) for n in range(1, 5)]                                          # 읽는 동안 「장소 n/4」
    assert any(p[0] == "hours" for p in phases) and any(p[0] == "moves" for p in phases)             # 이어서 운영시간 · 이동
    names = [n for n, _ in kept]
    assert names.index("progress") == 0 and "item" in names and "check" in names and "move" in names
    assert progress.drain(str(intake_id), 0) == ([], 0)                                                # 끝났으니 비었다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE intake_id=%s", (intake_id,))


def test_the_feed_sends_stored_progress_first_and_never_regresses_an_item_the_store_already_completed(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    intake_id = UUID(view["intake_id"])
    item = view["review"]["items"][0]
    rich = {k: item[k] for k in ("id", "source_id", "index", "title", "kind", "day", "date", "starts_at", "ends_at", "locked", "status",
                                 "can_lock", "place_state", "place", "candidates_hint")}
    progress.reset()
    progress.emit(str(intake_id), "progress", {"phase": "moves", "done": 1, "total": 2, "current": {"id": "0-0>0-1", "title": "A → B"}})
    progress.emit(str(intake_id), "item", rich)
    feed = stream.Feed(rv["tenant"], rv["customer"], intake_id)
    reading = {"status": "reading", "stage": "checking", "revision": view["revision"]}           # 검사 계산 중 — DB 에는 아직 검사가 없다고 본다
    with get_connection() as conn:
        first = feed.poll(conn, reading)
        again = feed.poll(conn, reading)
    assert first[0][0] == "progress" and first[0][1]["current"]["title"] == "A → B"               # 보관소가 먼저
    mine = [b for n, b in first if n == "item" and b["id"] == item["id"]]
    assert len(mine) == 1 and mine[0]["status"] == item["status"] and mine[0]["status"] is not None   # ★DB 의 덜 채운 값(status 없음)으로 되돌리지 않는다
    others = [b for n, b in first if n == "item" and b["id"] != item["id"]]
    assert others and all(b["status"] is None for b in others)                                    # 보관소가 모르는 일정은 DB 값 그대로
    assert [n for n, _ in again if n in ("progress", "item")] == []                                # 두 번째 질문에는 새 것이 없다(각자 cursor)
    progress.emit(str(intake_id), "move", {"from": "0-0", "to": "0-1", "status": "keep"})
    with get_connection() as conn:
        later = feed.poll(conn, reading)
    assert [n for n, _ in later] == ["move"]                                                      # 새로 쌓인 것만
    other_viewer = stream.Feed(rv["tenant"], rv["customer"], intake_id)
    with get_connection() as conn:
        everything = other_viewer.poll(conn, reading)                                              # 다시 연결하면 처음부터
    assert {"progress", "move"} <= {n for n, _ in everything}


def test_a_finished_intake_streams_the_same_events_as_before_with_an_empty_store(rv):
    """보관소가 비어 있으면(다른 프로세스 · 서버 재시작 · 이미 끝난 접수) 전과 같다 — 최종 값은 늘 DB 에서 읽힌다."""
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    progress.reset()
    feed = stream.Feed(rv["tenant"], rv["customer"], UUID(view["intake_id"]))
    done = {"status": "review", "stage": "review", "revision": view["revision"]}
    with get_connection() as conn:
        events = feed.poll(conn, done)
    names = [n for n, _ in events]
    assert "progress" not in names and {"line", "item", "check", "move", "done"} <= set(names)
    dumped = [json.dumps([n, d], sort_keys=True, ensure_ascii=False) for n, d in events]
    assert len(dumped) == len(set(dumped))                                                          # 같은 몸통을 두 번 보내지 않는다
