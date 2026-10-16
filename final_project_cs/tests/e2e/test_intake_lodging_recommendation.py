"""예시의 이틀 호텔 조식을 접수·후보·검색·자동 추천 HTTP 경로로 확인한다."""
from .test_intake_candidate_kinds import _LodgingKakao, around  # noqa: F401
from .test_intake_review import _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401


PLAN = "2026-10-24\n09:00 호텔 조식\n10:00 경복궁\n2026-10-25\n09:00 호텔 조식\n10:00 경복궁"


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


def test_single_hotel_autofix_adjusts_time_and_leaves_the_other_day_unchanged(around):
    client, _, _ = _client(kakao=LodgingMap())
    headers = _key(client)
    view = _send(client, headers, PLAN)
    hotels = [item for item in view["review"]["items"] if (item.get("parts") or {}).get("content_type") == "32"]
    target, other = hotels
    url = f"/v1/web/trip-intakes/{view['intake_id']}/autofix"
    body = {"revision": view["revision"], "item_id": target["id"]}
    preview = client.post(url, headers=headers, json={**body, "dry_run": True})
    assert preview.status_code == 200, preview.text
    assert [row["id"] for row in preview.json()["changed"]] == [target["id"]]
    unchanged = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()
    assert unchanged["revision"] == view["revision"]
    result = client.post(url, headers=headers, json=body)
    assert result.status_code == 200, result.text
    answer = result.json()
    assert [row["id"] for row in answer["changed"]] == [target["id"]]
    selected = next(row for row in answer["view"]["review"]["items"] if row["id"] == target["id"])
    assert selected["kind"] == "dining" and selected["place"]
    assert selected["starts_at"] == "09:00" and selected["ends_at"] < "10:00"
    other_after = next(row for row in answer["view"]["review"]["items"] if row["id"] == other["id"])
    assert other_after["place"] == other["place"] and other_after["ends_at"] == other["ends_at"]
    missing = client.post(url, headers=headers, json={"revision": answer["revision"], "item_id": "99-99"})
    assert missing.status_code == 404
