# -*- coding: utf-8 -*-
"""접수에서 문제 난 일정의 대안을 **미리 준비**하고 「바꾸기」가 그것을 계산 없이 보인다. `[2026-10-19 사용자 지시]`

구현 `components/intake/prepared.py` · 저장 061 `intake_alternatives` · 계약 `wiki/external/rest-endpoints/web-intakes.md` 「대안 미리 준비」.
모델 · 카카오 · 관광공사는 메모리 대역이다(mock 서버 시험 — 실제 바깥 서비스 확인은 따로).

★지키려는 것
 ①접수 검사가 끝나면 문제 난 일정(휴무 · 운영시간 · 장소 모호 …)마다 완성본이 저장된다 — 문제 없는 일정은 저장하지 않는다
 ②「바꾸기」(JSON)는 저장분이 맞으면 **계산하지 않고** 그대로 돌려준다(`prepared` 칸) — 이동 계산기 · 팀 대안을 부르지 않는다
 ③앞뒤 일정만 바뀌면 그쪽 구간만 낡은 것으로 보고 다시 잰다(`prepared.stale`) — 후보를 다시 모으지 않는다
 ④그 일정 자체가 바뀌면 저장분을 쓰지 않는다 · 새 판 뒤에는 뒤에서 다시 준비한다
 ⑤실시간 진행(SSE): 저장분이 맞으면 곧바로 `result`, 없으면 `candidates`(어림 · `pending`) → `candidate` … → `result`
 ⑥카카오에서 온 후보가 섞인 일정은 저장하지 않는다(약관)
 ⑦후보마다 앞 · 뒤 구간의 이동(`legs` — 상대 장소 이름 · 분 · 수단 · 어림 여부)이 실린다

재현:

    python -m pytest tests/e2e/test_intake_prepared_alternatives.py -v
"""
from __future__ import annotations

import json

from app.domains.travel_ops.components.intake import candidates as candidates_module
from app.domains.travel_ops.components.intake import prepared
from app.infrastructure.db.session import get_connection

from .test_intake_review import OPEN_ALL, TUE_CLOSED, _catalog, _client, _edit, _hours, _item, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

PLAN = "2026-10-13\n10시 경복궁\n13:30 광장시장"          # 화요일 — 경복궁을 화요일 휴무로 읽어 둔다


def _world(rv):  # noqa: F811
    _hours(rv, "126508", TUE_CLOSED)
    _catalog(rv, "900001", "12", "창덕궁", 37.5794, 126.9910)
    _catalog(rv, "900002", "12", "덕수궁", 37.5658, 126.9751)
    _hours(rv, "900001", OPEN_ALL)
    _hours(rv, "900002", OPEN_ALL)


def _rows(rv, intake_id):  # noqa: F811
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_id::text, item_index, revision, body FROM intake_alternatives WHERE tenant_id=%s AND intake_id=%s",
                    (rv["tenant"], intake_id))
        return cur.fetchall()


def _path(view, item):
    return f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={item['source_id']}&index={item['index']}"


def test_reading_prepares_the_alternatives_of_the_items_with_a_problem_only(rv):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    assert any(r["row"] == "closed" and r["result"] == "bad" for r in palace["rows"])
    rows = _rows(rv, view["intake_id"])
    assert [(s, i) for s, i, _r, _b in rows] == [(palace["source_id"], palace["index"])]       # ①문제 난 일정만
    body = rows[0][3]
    assert {c["place"]["name"] for c in body["candidates"]} == {"창덕궁", "덕수궁"}
    first = body["candidates"][0]
    assert set(first["legs"]) == {"before", "after"} and first["legs"]["after"]["with"] == "광장시장"      # ⑦
    assert first["legs"]["after"]["minutes"] > 0 and first["legs"]["after"]["estimated"] is True       # 이 시험은 계산기를 끈다(어림)


def test_the_change_screen_shows_the_prepared_alternatives_without_computing(rv, monkeypatch):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    called = []
    monkeypatch.setattr(candidates_module, "gather", lambda *a, **k: called.append("gather"))
    monkeypatch.setattr(candidates_module, "alternatives", lambda *a, **k: called.append("alternatives"))
    got = client.get(_path(view, palace), headers=headers)
    assert got.status_code == 200, got.text
    body = got.json()
    assert called == []                                                                   # ②계산하지 않는다
    assert body["prepared"]["stale"] == [] and body["prepared"]["revision"] == view["revision"]
    assert {c["place"]["name"] for c in body["candidates"]} == {"창덕궁", "덕수궁"}
    assert body["revision"] == view["revision"]


def test_a_neighbour_change_makes_only_that_leg_stale_and_it_is_measured_again(rv, monkeypatch):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace, market = _item(view, "경복궁"), _item(view, "광장시장")
    monkeypatch.setattr(prepared, "prepare", lambda *a, **k: {"skipped": "test"})   # 새 판 뒤 준비를 막아 「낡은 구간」을 본다
    after = _edit(client, headers, view, {"source_id": market["source_id"], "field": f"items[{market['index']}].starts_at", "value": "15:00"})
    gathered = []
    real = candidates_module.gather
    monkeypatch.setattr(candidates_module, "gather", lambda *a, **k: gathered.append(1) or real(*a, **k))
    got = client.get(_path(after, palace), headers=headers).json()
    assert got["prepared"]["stale"] == ["after"] and gathered == []                     # ③후보는 다시 모으지 않는다
    assert {c["place"]["name"] for c in got["candidates"]} == {"창덕궁", "덕수궁"}
    again = client.get(_path(after, palace), headers=headers).json()                    # 다시 잰 결과를 저장했다
    assert again["prepared"]["stale"] == []


def test_a_new_revision_prepares_again_in_the_background(rv):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace, market = _item(view, "경복궁"), _item(view, "광장시장")
    after = _edit(client, headers, view, {"source_id": market["source_id"], "field": f"items[{market['index']}].starts_at", "value": "15:00"})
    got = client.get(_path(after, palace), headers=headers).json()
    assert got["prepared"]["stale"] == []                                               # ④뒤에서 이미 다시 준비했다


def test_changing_the_item_itself_drops_the_prepared_alternatives(rv):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    first = client.get(_path(view, palace), headers=headers).json()
    pick = next(c for c in first["candidates"] if c["place"]["name"] == "덕수궁")["place"]
    after = _edit(client, headers, view, {"source_id": palace["source_id"], "field": f"items[{palace['index']}].place", "value": pick})
    changed = _item(after, palace["title"]) if any(i["title"] == palace["title"] for i in after["review"]["items"]) else after["review"]["items"][0]
    got = client.get(_path(after, changed), headers=headers).json()
    assert got["prepared"] is None or got["prepared"]["revision"] == after["revision"]   # ④바꾼 일정은 지난 저장분을 쓰지 않는다
    assert "덕수궁" not in {c["place"]["name"] for c in got["candidates"]}               # 지금 장소는 후보에서 빠진다


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.split("\n\n"):
        name = next((line[7:] for line in block.splitlines() if line.startswith("event: ")), None)
        data = next((line[6:] for line in block.splitlines() if line.startswith("data: ")), None)
        if name:
            out.append((name, json.loads(data or "{}")))
    return out


def test_the_stream_answers_at_once_from_the_prepared_alternatives(rv):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    got = client.get(_path(view, palace), headers={**headers, "Accept": "text/event-stream"})
    names = [n for n, _b in _events(got.text)]
    assert names[0] == "accepted" and names[-1] == "result" and "candidates" not in names        # ⑤곧바로 결과
    result = _events(got.text)[-1][1]
    assert result["prepared"]["stale"] == [] and {c["place"]["name"] for c in result["candidates"]} == {"창덕궁", "덕수궁"}


def test_the_stream_shows_estimates_first_then_each_measured_line(rv):  # noqa: F811
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM intake_alternatives WHERE tenant_id=%s AND intake_id=%s", (rv["tenant"], view["intake_id"]))
    got = client.get(_path(view, palace), headers={**headers, "Accept": "text/event-stream"})
    events = _events(got.text)
    names = [n for n, _b in events]
    assert names[0] == "accepted" and names[1] == "candidates" and names[-1] == "result"          # ⑤어림 먼저
    first = events[1][1]
    assert first["prepared"] is None and all(c["pending"]["after"] is True for c in first["candidates"])
    updates = [b for n, b in events if n == "candidate"]
    assert {u["rank"] for u in updates} == {c["rank"] for c in first["candidates"]}
    assert all(u["pending"] == {"before": False, "after": False} for u in updates if "rows" in u)
    result = events[-1][1]
    assert {c["place"]["name"] for c in result["candidates"]} == {"창덕궁", "덕수궁"}
    assert _rows(rv, view["intake_id"])                                                         # 끝난 결과를 저장했다


def test_kakao_candidates_are_not_stored(rv):  # noqa: F811
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)                       # 기본 계획 — 올리브영(이름 모호 · 다른 지점은 카카오에서 온다)
    oy = _item(view, "올리브영")
    assert oy["place_state"] == "picked_nearest"
    stored = {(s, i) for s, i, _r, _b in _rows(rv, view["intake_id"])}
    assert (oy["source_id"], oy["index"]) not in stored                                         # ⑥
    got = client.get(_path(view, oy), headers=headers).json()
    assert got["prepared"] is None and got["candidates"]                                         # 「바꾸기」 때 계산한다


def test_registering_keeps_the_other_prepared_alternatives_and_the_chat_swap_uses_them(rv):  # noqa: F811
    """⑧등록 — 고객이 저장된 대안 하나(덕수궁)로 바꾸고 등록하면, 나머지 대안이 그 일정 항목의 「다른 안」(`detail.alternates`)으로 남고
    채팅 「바꿔 줘」가 쓰는 교체(`plan_swap`)가 그 안으로 바로 바꾼다."""
    from uuid import UUID

    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from app.domains.travel_ops.components.itinerary.itinerary_changes import plan_swap

    _world(rv)
    _catalog(rv, "900003", "12", "창경궁", 37.5788, 126.9948)
    _hours(rv, "900003", OPEN_ALL)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    first = client.get(_path(view, palace), headers=headers).json()
    names = [c["place"]["name"] for c in first["candidates"]]
    pick = first["candidates"][0]["place"]
    after = _edit(client, headers, view, {"source_id": palace["source_id"], "field": f"items[{palace['index']}].place", "value": pick})
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": after["revision"]})
    assert done.status_code == 200, done.text
    trip_id = UUID(done.json()["trip"]["trip_id"])
    store = TripStore(rv["tenant"])
    with get_connection() as conn:
        trip, items = store.latest(conn, trip_id)
        places = store.places(conn, trip_id)
    target = next(i for i in items if (i.place or {}).get("name") == pick["name"])
    alternates = target.detail.get("alternates") or []
    assert [a["name"] for a in alternates] == [n for n in names if n != pick["name"]][:3]           # 고른 곳을 뺀 나머지
    assert target.detail.get("alternates_from") == "intake"
    by_id = {p["place_id"]: p for p in places}
    assert all(a["place_id"] in by_id for a in alternates)                                         # 장소 행이 있다(그 여행 전용)
    plan = plan_swap(trip_version=trip["version"], base_version=trip["version"], items=items, places_by_id=by_id, item_id=target.item_id,
                     choice=None, message="다른 데로 바꿔 줘", request_id=None, check=None)
    assert type(plan).__name__ != "NoChange", plan


def test_a_reason_without_waiting_returns_at_once_and_is_not_queued_twice(rv):  # noqa: F811
    """⑨실시간 「바꾸기」의 이유 문장 — 기다리지 않고(`wait_seconds=0`) 틀 문장으로 먼저, 모델 문장은 뒤에서 저장 · 쓰는 중인 같은 사실은 다시 맡기지 않는다."""
    import time

    from app.domains.travel_ops.components.intake import reasons

    from .test_candidate_reasons import FakeChat, _candidate

    chat = FakeChat(lambda: "다음 일정까지 25분 여유가 있어요", delay=0.8)
    with get_connection() as conn:
        started = time.perf_counter()
        first = [_candidate()]
        out = reasons.polish(conn, rv["tenant"], first, "경복궁", chat, wait_seconds=0)
        assert time.perf_counter() - started < 0.5 and out["pending"] == 1 and first[0]["reason_by"] == "template"
        again = [_candidate()]
        assert reasons.polish(conn, rv["tenant"], again, "경복궁", chat, wait_seconds=0)["pending"] == 1
    time.sleep(1.5)
    assert chat.calls == 1
    with get_connection() as conn:
        later = [_candidate()]
        assert reasons.polish(conn, rv["tenant"], later, "경복궁", chat, wait_seconds=0)["cached"] == 1
    assert later[0]["reason_by"] == "model" and chat.calls == 1


def test_while_the_preparation_still_runs_the_change_screen_shows_guesses_and_takes_its_result(rv, monkeypatch):  # noqa: F811
    """⑩접수 뒤 준비가 아직 도는 중에 「바꾸기」를 누르면 — 어림 카드(모든 줄 「계산 중」)를 먼저 보이고 **같은 계산을 다시 돌리지 않고** 준비 결과를 기다려 이어 받는다."""
    import threading
    import time
    from concurrent.futures import Future

    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, PLAN)
    palace = _item(view, "경복궁")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM intake_alternatives WHERE tenant_id=%s AND intake_id=%s", (rv["tenant"], view["intake_id"]))
    found = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()["review"]
    item = next(i for i in found["items"] if i["id"] == palace["id"])
    key = prepared._item_key(view["intake_id"], item)
    running: Future = Future()
    prepared._preparing[key] = running                                  # 준비가 도는 중인 상태를 만든다

    def finish_later():
        time.sleep(1.0)
        try:
            prepared._prepare_one(get_connection, tenant_id=rv["tenant"], intake_id=view["intake_id"], review={**found, "revision": view["revision"]},
                                  item=item, chat=None, started=time.monotonic())
        finally:
            prepared._preparing.pop(key, None)
            running.set_result(True)

    from contextvars import copy_context

    worker = threading.Thread(target=copy_context().run, args=(finish_later,))      # 조립 상태(팀 자리)를 넘긴다 — 실제 준비도 문맥을 복사해 돈다
    worker.start()
    live = []
    real = prepared.judge_in_turn
    monkeypatch.setattr(prepared, "judge_in_turn", lambda *a, **k: live.append(1) or real(*a, **k))
    got = client.get(_path(view, palace), headers={**headers, "Accept": "text/event-stream"})
    worker.join()
    events = _events(got.text)
    names = [n for n, _b in events]
    assert names[:2] == ["accepted", "candidates"] and names[-1] == "result"
    assert events[1][1]["waiting"] == "prepare" and all(c["pending"]["after"] for c in events[1][1]["candidates"])     # 어림 먼저 · 계산 중
    result = events[-1][1]
    assert result["prepared"] is not None and live == []                                       # 준비 결과를 이어 받았다 — 다시 계산하지 않았다
    assert {c["place"]["name"] for c in result["candidates"]} == {"창덕궁", "덕수궁"}


def test_a_risky_activity_is_not_prepared_and_takes_the_safety_path_first(rv, monkeypatch):  # noqa: F811
    """⑪위험 날짜(날씨 등)로 문제가 난 활동은 **미리 준비하지 않고**, 「바꾸기」(JSON · SSE)는 안전 대안 경로(`risks.alternatives`)가 먼저 낸다 —
    일반 대안을 먼저 내지 않는다(`[faabcd92]` 오라클 판의 순서를 지킨다)."""
    from app.domains.travel_ops.components.intake import risks

    real = risks.decorate

    def risky(conn, *, review, **kw):
        out = real(conn, review=review, **kw)
        for item in out.get("items") or []:
            if item.get("title") == "경복궁":
                item["risk"] = {"status": "problem", "problems": [{"category": "weather"}]}
        return out

    safe_calls = []

    def safety(conn, *, item, **kw):
        if (item.get("risk") or {}).get("status") != "problem":
            return None
        safe_calls.append(item["title"])
        return {"item": item["id"], "current": None, "reference": {}, "candidates": [], "notes": ["risk_alternatives"]}

    monkeypatch.setattr(risks, "decorate", risky)
    monkeypatch.setattr(risks, "alternatives", safety)
    _world(rv)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n13:30 광장시장")
    palace = _item(view, "경복궁")
    assert (palace.get("risk") or {}).get("status") == "problem"
    assert (palace["source_id"], palace["index"]) not in {(s, i) for s, i, _r, _b in _rows(rv, view["intake_id"])}     # 미리 준비하지 않았다
    gathered = []
    monkeypatch.setattr(candidates_module, "gather", lambda *a, **k: gathered.append(1))
    got = client.get(_path(view, palace), headers=headers).json()
    assert got["notes"] == ["risk_alternatives"] and got["prepared"] is None and gathered == []
    streamed = client.get(_path(view, palace), headers={**headers, "Accept": "text/event-stream"})
    names = [n for n, _b in _events(streamed.text)]
    assert "candidates" not in names and _events(streamed.text)[-1][1]["notes"] == ["risk_alternatives"]
    assert safe_calls and gathered == []
