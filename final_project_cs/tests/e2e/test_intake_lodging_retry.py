"""식당 확정으로 동선이 바뀐 뒤 최초 숙소 추천을 다시 보는 HTTP 회귀 시험."""
from app.domains.travel_ops.components.intake import candidates, lodging_context, pipeline
from app.infrastructure.db.session import get_connection
from psycopg.types.json import Jsonb
import pytest

from .test_intake_candidate_kinds import around  # noqa: F401
from .test_intake_lodging_recommendation import LodgingMap
from .test_intake_review import OPEN_ALL, _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401



class MealMap:
    def search(self, query, size=5, near=None, **kwargs):
        return [{'id': 'meal-1', 'name': '광화문식당', 'category': '음식점 > 한식', 'category_group': 'FD6',
                 'address': '서울 종로구 사직로 161', 'latitude': 37.5795, 'longitude': 126.9769}]


@pytest.fixture
def meal_place(around):
    with get_connection() as conn, conn.transaction():
        identity = conn.execute(
            "INSERT INTO places (tenant_id,name,kind,latitude,longitude,source_name,attributes) "
            "VALUES (%s,%s,'dining',%s,%s,'dining_ledger',%s) RETURNING place_id",
            (around['tenant'], '광화문식당', 37.5795, 126.9769, Jsonb({'source': 'dining_ledger'}))).fetchone()[0]
        conn.execute("INSERT INTO catalog_hours (tenant_id,source,content_id,content_type_id,hours_week,hours_read,read_at) "
                     "VALUES (%s,'tour_api','920004','39',%s,%s,now()) ON CONFLICT DO NOTHING",
                     (around['tenant'], Jsonb(OPEN_ALL), Jsonb({'source': 'tour_api', 'method': 'test'})))
    yield
    with get_connection() as conn, conn.transaction():
        conn.execute('DELETE FROM places WHERE tenant_id=%s AND place_id=%s', (around['tenant'], identity))

def test_first_read_revisits_a_common_hotel_after_filling_a_meal_place(around, meal_place, monkeypatch):
    config, alternatives = pipeline.agent_reader_config, candidates.alternatives
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant: {**config(tenant), "mode": "on", "prefill": "on"})
    searched = []

    def after_meal(*args, **kwargs):
        if not lodging_context.is_stay(kwargs["item"]) and kwargs["item"]["kind"] == "dining":
            kwargs = {**kwargs, "kakao": MealMap()}
        result = alternatives(*args, **kwargs)
        if lodging_context.is_stay(kwargs["item"]):
            meal_ready = any(i["kind"] == "dining" and i.get("place") and not lodging_context.is_stay(i)
                             for i in kwargs["review"]["items"])
            searched.append(meal_ready)
            if not meal_ready:
                return {**result, "candidates": []}
        return result

    monkeypatch.setattr(candidates, "alternatives", after_meal)
    client, _, _ = _client(kakao=LodgingMap())
    view = _send(client, _key(client),
                 "2026-10-24\n09:00 호텔 조식\n10:00 경복궁\n12:00 점심 식당\n2026-10-25\n09:00 호텔 조식\n10:00 경복궁")
    assert view["status"] == "review" and view["stage"] == "review"
    assert any(f["owner"] == "dining_team" for f in view["prefill"]["filled"]), view["prefill"]
    assert any(i["kind"] == "dining" and not i.get("lodging_group") and i.get("place")
               and i["place_state"] == "customer" for i in view["review"]["items"]), view["review"]["items"]
    assert searched[0] is False and True in searched, {"revision": view["revision"], "items": [{k:i.get(k) for k in ("title","kind","place_state","place")} for i in view["review"]["items"]], "prefill": view["prefill"]}
    hotels = [item for item in view["review"]["items"] if item.get("lodging_group")]
    assert len(hotels) == 2 and all(item["place"] and item["kind"] == "dining" for item in hotels)
    assert len({(item["place"]["name"], item["place"]["latitude"], item["place"]["longitude"]) for item in hotels}) == 1
    assert all(item["starts_at"] == "09:00" and item["ends_at"] < "10:00" for item in hotels)
    assert not any(item["kind"] == "lodging_place" for item in view["prefill"]["kept"])
    assert "rounds" not in view["prefill"] and "proposals" not in view["prefill"], "운영용 시도 원본은 고객 응답에 싣지 않는다"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT value_json FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=%s AND field='reading.prefill'",
                    (around["tenant"], view["intake_id"], view["revision"]))
        record = cur.fetchone()[0]
    assert len(record["rounds"]) == 2 and len(record["rounds"][0]["retried_gaps"]) == 2
    attempts = [p for p in record["proposals"] if p["gap"]["kind"] == "lodging_place"]
    assert len(attempts) == 4 and not attempts[0]["candidates"] and attempts[-1]["candidates"]
