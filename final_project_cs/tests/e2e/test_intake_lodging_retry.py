"""먼저 채우기의 식당 · 숙소 HTTP 회귀 시험. `[2026-10-26 사용자 지시]` 숙소는 먼저 채우지 않고 묻는다(전: 식당 확정 뒤 숙소를 다시 추천해 채움)."""
from app.domains.travel_ops.components.intake import candidates, lodging_context, pipeline
from app.infrastructure.db.session import get_connection
from psycopg.types.json import Jsonb
import pytest

from .test_intake_candidate_kinds import around  # noqa: F401
from .test_intake_lodging_recommendation import LodgingMap
from .test_intake_review import OPEN_ALL, _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_24 = reldate.day("2026-10-24")
D_2026_10_25 = reldate.day("2026-10-25")



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

def test_first_read_fills_the_meal_place_but_asks_both_hotel_breakfasts(around, meal_place, monkeypatch):
    # `[2026-10-26 사용자 지시 — 호텔 후보는 고객이 고른다]` 먼저 채우기는 이름 없는 호텔을 채우지 않는다(후보가 하나여도) — 그 일정 카드가 후보에서 고르게 묻는다
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
                 f"{D_2026_10_24}\n09:00 호텔 조식\n10:00 경복궁\n12:00 점심 식당\n{D_2026_10_25}\n09:00 호텔 조식\n10:00 경복궁")
    assert view["status"] == "review" and view["stage"] == "review"
    assert any(f["owner"] == "dining_team" for f in view["prefill"]["filled"]), view["prefill"]
    assert any(i["kind"] == "dining" and not i.get("lodging_group") and i.get("place")
               and i["place_state"] == "customer" for i in view["review"]["items"]), view["review"]["items"]
    asked = [q for q in view["prefill"]["questions"] if q["kind"] == "lodging_place"]
    by_id = {i["id"]: i for i in view["review"]["items"]}
    hotels = [by_id[q["item"]] for q in asked]
    assert len(hotels) == 2 and all(item["place"] is None and item["place_state"] == "needs_choice" for item in hotels), view["prefill"]
    assert not any(item["kind"] == "lodging_place" for item in view["prefill"]["kept"])
    assert "rounds" not in view["prefill"] and "proposals" not in view["prefill"], "운영용 시도 원본은 고객 응답에 싣지 않는다"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT value_json FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=%s AND field='reading.prefill'",
                    (around["tenant"], view["intake_id"], view["revision"]))
        record = cur.fetchone()[0]
    attempts = [p for p in record["proposals"] if p["gap"]["kind"] == "lodging_place"]
    assert attempts and all(p["owner"] == "ask_customer" for p in attempts), attempts
