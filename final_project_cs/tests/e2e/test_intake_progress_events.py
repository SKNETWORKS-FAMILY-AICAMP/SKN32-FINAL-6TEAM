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
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_15 = reldate.day("2026-10-15")


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
    # 「n/m」 — 운영시간은 일정마다, 이동은 구간마다 0 부터 1씩 늘어 total 에서 끝난다
    # ★`[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` `current` 는 **지금 보는** 일정 · 구간(보기 전에 알린다) — 끝에 `current: null`
    hours = [b for n, b in events if n == "progress" and b["phase"] == "hours"]
    moves = [b for n, b in events if n == "progress" and b["phase"] == "moves"]
    assert [b["done"] for b in hours] == list(range(0, len(built["items"]) + 1)) and {b["total"] for b in hours} == {len(built["items"])}
    assert [b["done"] for b in moves] == list(range(0, len(built["moves"]) + 1)) and {b["total"] for b in moves} == {len(built["moves"])}
    assert hours[0]["current"] == {"id": built["items"][0]["id"], "title": built["items"][0]["title"]}      # 지금 무엇을 확인하나
    assert moves[0]["current"]["title"].count("→") == 1 and moves[0]["current"]["id"].count(">") == 1
    assert hours[-1]["current"] is None and moves[-1]["current"] is None                                   # 끝났다
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


class _Pointer:
    """남은 줄마다 장소 하나를 가리키는 모델(시험용) — 답을 조각으로 나눠 준다(`json_stream`). 받은 줄 번호를 남긴다."""

    PLACES = ("경복궁", "광장시장", "북촌한옥마을", "남산타워", "망원시장", "서울숲")

    def __init__(self) -> None:
        self.calls: list[list[int]] = []

    def json(self, system, user):
        rows = [row.split(": ", 1) for row in user.splitlines()]
        self.calls.append([int(n) for n, _ in rows])
        return {"spans": [{"line": int(n), "quote": next(p for p in self.PLACES if p in text), "role": "place"} for n, text in rows]}

    def json_stream(self, system, user, *, on_piece=None, first_wait, stall, max_seconds, max_tokens):
        import json as _json

        answer = self.json(system, user)
        text = _json.dumps(answer, ensure_ascii=False)
        for cut in range(40, len(text) + 40, 40):                  # 40자씩 조금씩
            on_piece(text[:cut], "local")
        self.budget = max_tokens
        return answer


def test_the_reading_worker_reports_lines_read_while_the_model_writes(rv, monkeypatch):
    """`[2026-10-16 2회차 합의]` 남은 줄을 한 번에 보내고 답을 조금씩 받는다 — 「읽는 중 n/m 줄」(`phase: reading`)이 장소 찾기보다 먼저 쌓인다.
    `done` 은 원문 검사를 통과한 서로 다른 줄 수, `total` 은 보낸 줄 수다(지어낸 진행률이 아니다)."""
    tour, kakao = Tour(), Kakao()
    text = "\n".join([D_2026_10_15, *[f"오후엔 {p} 가 보고 싶어" for p in _Pointer.PLACES]])
    with get_connection() as conn:
        intake_id = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], text=text, files=[])
    kept: list[tuple[str, dict]] = []
    real_clear = progress.clear

    def spy_clear(key):
        kept.extend(progress.drain(str(key), 0)[0])
        real_clear(key)

    monkeypatch.setattr(progress, "clear", spy_clear)
    real_stream = pipeline._reading_stream
    monkeypatch.setattr(pipeline, "_reading_stream", lambda given: {**real_stream(None), "progress_seconds": 0})   # 조각마다 알림(시험)
    chat = _Pointer()
    assert pipeline.process(get_connection, tenant_id=rv["tenant"], intake_id=intake_id, blobs={}, see=None, chat=chat,
                            tour=tour, kakao=kakao) == "review"
    assert chat.calls == [[1, 2, 3, 4, 5, 6]]                                                         # 한 번에, 번호는 보낸 목록 안 순서(원래 2~7줄)
    assert chat.budget == 1024                                                                        # max(1024, 40 × 6)
    progress_events = [b for n, b in kept if n == "progress"]
    reading = [b for b in progress_events if b["phase"] == "reading"]
    assert reading[0] == {"phase": "reading", "done": 0, "total": 6} and reading[-1] == {"phase": "reading", "done": 6, "total": 6, "final": True}
    dones = [b["done"] for b in reading]
    assert dones == sorted(dones) and len(set(dones)) > 2                                             # 받는 동안 늘어난다
    first_place = next(i for i, b in enumerate(progress_events) if b["phase"] == "places")
    assert max(i for i, b in enumerate(progress_events) if b["phase"] == "reading") < first_place     # 모델 답이 끝난 뒤 장소 찾기
    with get_connection() as conn:
        claims = pipeline._claims(conn, rv["tenant"], intake_id, 1)
    titles = sorted(c["value"] for c in claims if c["field"].endswith(".title"))
    assert titles == sorted(_Pointer.PLACES)
    report = next(c["value"] for c in claims if c["field"] == "reading.llm")
    assert report["asked_lines"] == 6 and report["accepted"] == 6 and report["output_tokens"] == 1024 and "error" not in report
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
