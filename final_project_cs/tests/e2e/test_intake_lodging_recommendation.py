"""예시의 이틀 호텔 조식을 접수·후보·검색·자동 추천 HTTP 경로로 확인한다."""
import pytest

from .test_intake_candidate_kinds import _LodgingKakao, around  # noqa: F401
from .test_intake_review import _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401


PLAN = "2026-10-24\n09:00 호텔 조식\n10:00 경복궁\n2026-10-25\n09:00 호텔 조식\n10:00 경복궁"


@pytest.fixture(autouse=True)
def manual_recommendation_baseline(monkeypatch):
    from app.domains.travel_ops.components.intake import pipeline
    real = pipeline.agent_reader_config
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant: {**real(tenant), "prefill": "off"})


def test_fresh_example_asks_both_hotels_instead_of_prefilling_them(around, monkeypatch):
    # `[2026-10-26 사용자 지시 — 호텔 후보는 고객이 고른다]` 먼저 채우기는 이름 없는 호텔을 채우지 않는다(후보가 하나여도) — 그 일정 카드가 후보에서 고르게 묻는다
    from app.domains.travel_ops.components.intake import pipeline
    from app.infrastructure.db.session import get_connection

    real_config, real_prefill = pipeline.agent_reader_config, pipeline._prefill
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant: {**real_config(tenant), "mode": "on", "prefill": "on"})
    pending = []

    def fill(connect, tenant_id, intake_id, **kwargs):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT customer_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
            owner = cur.fetchone()[0]
            snapshot = pipeline.view(conn, tenant_id=tenant_id, customer_id=owner, intake_id=intake_id)
            pending.append(snapshot["status"])
            assert snapshot["review"] is None
        real_prefill(connect, tenant_id, intake_id, **kwargs)

    monkeypatch.setattr(pipeline, "_prefill", fill)
    client, _, _ = _client(kakao=LodgingMap())
    view = _send(client, _key(client), PLAN)
    assert pending == ["reading"]
    assert view["status"] == "review" and view["stage"] == "review"
    hotels = [i for i in view["review"]["items"] if i["title"] == "호텔 조식"]
    assert len(hotels) == 2 and all(i["place"] is None and i["place_state"] == "needs_choice" and i["kind"] == "dining" for i in hotels)
    assert not any(f["owner"] == "lodging_team" for f in view["prefill"]["filled"]), view["prefill"]
    asked = [q for q in view["prefill"]["questions"] if q["kind"] == "lodging_place"]
    assert sorted(q["item"] for q in asked) == sorted(i["id"] for i in hotels), view["prefill"]
    assert not any(q["kind"] == "lodging_name" for q in view["prefill"]["questions"])


def test_interrupted_prefill_is_reaped_instead_of_remaining_publicly_reading_forever(around):
    from app.infrastructure.db.session import get_connection
    client, _, _ = _client(kakao=LodgingMap())
    headers = _key(client)
    view = _send(client, headers, PLAN)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='review', stage='checking', updated_at=now()-interval '1 day' WHERE intake_id=%s", (view["intake_id"],))
    shown = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()
    assert shown["status"] == "fatal" and shown["fatal"]["code"] == "stalled"


def test_intake_events_wait_for_prefill_with_the_same_status_as_the_get(around, monkeypatch):
    from app.infrastructure.db.session import get_connection
    from app.domains.travel_ops.modules.live_progress import op_stream
    client, _, _ = _client(kakao=LodgingMap())
    headers = _key(client)
    view = _send(client, headers, PLAN)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage='checking' WHERE intake_id=%s", (view["intake_id"],))
    assert client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()["status"] == "reading"

    async def watch(read, *, done, **kwargs):
        pending = read()
        assert pending["status"] == "reading" and not done(pending)
        yield op_stream.sse("accepted", {"state": pending})
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE trip_intakes SET stage='review' WHERE intake_id=%s", (view["intake_id"],))
        ready = read()
        assert ready["status"] == "review" and done(ready)
        yield op_stream.sse("result", {"state": ready})

    monkeypatch.setattr(op_stream, "watch", watch)
    response = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/events", headers=headers)
    assert response.status_code == 200 and "event: accepted" in response.text and "event: result" in response.text


class LodgingMap(_LodgingKakao):
    def search(self, query, size=5, near=None):
        hits = super().search(query, size=size, near=near)
        return [*hits, {**self.LODGING, "id": "23", "name": "호텔 앞 생활용품점",
                       "category": "가정,생활 > 생활용품점", "category_group": ""}]


def _candidates(client, headers, view, item):
    response = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates", headers=headers,
                          params={"source_id": item["source_id"], "index": item["index"], "revision": view["revision"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_two_day_example_uses_the_following_stop_and_keeps_lodging_after_selection(around):
    client, _, kakao = _client(kakao=LodgingMap())
    headers = _key(client)
    view = _send(client, headers, PLAN)
    hotels = [item for item in view["review"]["items"] if (item.get("parts") or {}).get("content_type") == "32"]
    assert len(hotels) == 2
    for item in hotels:
        got = _candidates(client, headers, view, item)
        assert got["reference"]["after"] == "경복궁"
        assert got["candidates"] and all("생활용품점" not in row["place"]["name"] for row in got["candidates"])
    assert all(near == (37.5796, 126.9770) for query, near in kakao.asked if query == "숙소")
    item = hotels[0]
    meal = next(row["place"] for row in _candidates(client, headers, view, item)["candidates"]
                if row["basis"] == "lodging_meal")
    response = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                           json={"revision": view["revision"], "edits": [
                               {"source_id": item["source_id"], "field": f"items[{item['index']}].place", "value": meal}]})
    assert response.status_code == 200, response.text
    view = response.json()
    selected = next(row for row in view["review"]["items"] if row["id"] == item["id"])
    assert selected["kind"] == "dining" and selected["parts"] is None
    linked = [row for row in view["review"]["items"] if row["id"] in {x["id"] for x in hotels}]
    assert {row["place"]["name"] for row in linked} == {meal["name"]}
    assert all(row["kind"] == "dining" and row["place"]["category"] == "숙소 안 식사" for row in linked)
    got = _candidates(client, headers, view, selected)
    assert got["candidates"] and {row["basis"] for row in got["candidates"]} == {"lodging", "lodging_meal"}, got
    response = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/place-search", headers=headers,
                          params={"source_id": selected["source_id"], "index": selected["index"],
                                  "revision": view["revision"], "q": "숙소"})
    assert response.status_code == 200, response.text
    assert response.json()["results"]
    assert all("생활용품점" not in row["place"]["name"] for row in response.json()["results"])


def test_example_autofix_keeps_both_hotel_breakfasts_as_meals(around):
    client, _, _ = _client(kakao=LodgingMap())
    headers = _key(client)
    view = _send(client, headers, PLAN)
    hotel_ids = {item["id"] for item in view["review"]["items"] if (item.get("parts") or {}).get("content_type") == "32"}
    response = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers,
                           json={"revision": view["revision"]})
    assert response.status_code == 200, response.text
    result = response.json()
    changed = {row["id"] for row in result["changed"]}
    assert hotel_ids <= changed, result
    hotels = [item for item in result["view"]["review"]["items"] if item["id"] in hotel_ids]
    assert len(hotels) == 2 and all(item["kind"] == "dining" and item["place"] for item in hotels)
    assert len({(item["place"]["name"], item["place"]["latitude"], item["place"]["longitude"]) for item in hotels}) == 1


def test_single_hotel_autofix_connects_both_days_and_adjusts_their_times(around):
    client, _, _ = _client(kakao=LodgingMap())
    headers = _key(client)
    view = _send(client, headers, PLAN)
    hotels = [item for item in view["review"]["items"] if (item.get("parts") or {}).get("content_type") == "32"]
    target, other = hotels
    url = f"/v1/web/trip-intakes/{view['intake_id']}/autofix"
    body = {"revision": view["revision"], "item_id": target["id"]}
    preview = client.post(url, headers=headers, json={**body, "dry_run": True})
    assert preview.status_code == 200, preview.text
    assert {row["id"] for row in preview.json()["changed"]} == {target["id"], other["id"]}
    unchanged = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()
    assert unchanged["revision"] == view["revision"]
    result = client.post(url, headers=headers, json=body)
    assert result.status_code == 200, result.text
    answer = result.json()
    assert {row["id"] for row in answer["changed"]} == {target["id"], other["id"]}
    selected = next(row for row in answer["view"]["review"]["items"] if row["id"] == target["id"])
    assert selected["kind"] == "dining" and selected["place"]
    assert selected["starts_at"] == "09:00" and selected["ends_at"] < "10:00"
    other_after = next(row for row in answer["view"]["review"]["items"] if row["id"] == other["id"])
    assert other_after["place"]["name"] == selected["place"]["name"]
    assert other_after["ends_at"] < "10:00"
    assert selected["lodging_group"]["place"]["name"] == selected["place"]["name"]
    assert other_after["lodging_group"] == selected["lodging_group"]
    missing = client.post(url, headers=headers, json={"revision": answer["revision"], "item_id": "99-99"})
    assert missing.status_code == 404


def test_hotel_undo_restores_both_dates_and_preserves_later_unrelated_change(around):
    client, _, _ = _client(kakao=LodgingMap())
    headers = _key(client)
    original = _send(client, headers, PLAN)
    target = original["review"]["items"][0]
    base = f"/v1/web/trip-intakes/{original['intake_id']}"
    response = client.post(base + "/autofix", headers=headers,
                           json={"revision": original["revision"], "item_id": target["id"]})
    assert response.status_code == 200, response.text
    current = response.json()["view"]
    other = current["review"]["items"][1]
    response = client.post(base + "/edits", headers=headers, json={"revision": current["revision"], "edits": [
        {"source_id": other["source_id"], "field": f"items[{other['index']}].title", "value": "관광 일정 메모 수정"}]})
    assert response.status_code == 200, response.text
    current = response.json()
    response = client.post(base + "/restore", headers=headers, json={"revision": current["revision"],
        "restore_revision": original["revision"], "item": {"source_id": target["source_id"], "index": target["index"]}})
    assert response.status_code == 200, response.text
    final = response.json()
    hotel_ids = {x["id"] for x in original["review"]["items"] if x["title"] == "호텔"}
    restored = [x for x in final["review"]["items"] if x["id"] in hotel_ids]
    assert len(restored) == 2 and all(x["place"] is None for x in restored)
    assert next(x for x in final["review"]["items"] if x["id"] == other["id"])["title"] == "관광 일정 메모 수정"
