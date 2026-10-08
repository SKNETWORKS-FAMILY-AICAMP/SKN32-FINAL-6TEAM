# -*- coding: utf-8 -*-
"""활동 「다른 데로 바꿔」 — 후보를 **관광공사 목록**에서 넓히고, 그 시각에 없으면 **안 셋**을 묻는다.
`[2026-09-29 사용자 요구 — ui 세션 전달]`
★`[2026-09-29 사용자 지시]` 운영시간은 **새벽 작업**(`catalog_hours.prefill`)이 읽어 두고, 요청 자리에서는 관광공사를 부르지 않는다.

☆「10:10에 갈 수 있는 활동이 3km 안에 없어요(살펴본 2곳 …)」로 끝났다. 바꾸기 계산은 장소 표의 활동(서울 전체 12곳)만 봤다 —
  일정 짜기는 관광공사 목록을 쓰는데 바꾸기는 안 썼다. 이유 문구도 「살펴본 2곳 중 1곳은 …」처럼 일부만 말했다.
★좌표는 서울 밖 바다 위다 — 기본 테넌트의 실제 목록(서울)이 섞이지 않게 한다.
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.planning.pending import PendingStore
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk

KST = ZoneInfo("Asia/Seoul")
LAT, LON = 34.0000, 124.0000          # 서울 밖(바다) — 실제 목록과 안 겹친다


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2030, 1, 1, hour, minute, tzinfo=KST)


class _Tour:
    """관광공사 운영정보 자리 — 목록 id 마다 원문 운영시간을 준다(규칙으로 읽히는 단순한 원문)."""

    def __init__(self, hours: dict[str, str]):
        self.hours, self.asked = hours, []

    def operating(self, content_id, content_type_id):
        self.asked.append(content_id)
        text = self.hours.get(content_id)
        return {"content_id": content_id, "usetime_text": text, "restdate_text": None} if text else None


def _drop(tenant: str) -> None:
    # ★`cleanup_tenant` 은 장소 목록 표를 안 지운다 — 이 시험이 넣은 목록 행을 먼저 지운다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM place_catalog WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM catalog_hours WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def _setup(tenant: str, catalog: list[tuple[str, str, float, float]]):
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'pool')", (tenant,))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') RETURNING customer_id", (tenant,))
            customer = cur.fetchone()[0]
            ids = {}
            for key, name, kind, dlat, hours in (
                    ("park", "원래 공원", "activity", 0.0, ["09:00", "18:00"]),
                    ("shut", "닫힌 전시관", "activity", 0.003, ["14:00", "18:00"]),
                    ("lunch", "점심집", "dining", 0.005, ["11:00", "21:00"])):
                cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                            "VALUES (%s,%s,%s,%s,%s,false,%s) RETURNING place_id",
                            (tenant, name, kind, LAT + dlat, LON, json.dumps({"hours": hours, "payment": ["card"]})))
                ids[key] = cur.fetchone()[0]
            for content_id, title, dlat, dlon in catalog:
                cur.execute("INSERT INTO place_catalog (tenant_id,source,content_id,content_type_id,title,latitude,longitude,"
                            "source_modified_at) VALUES (%s,'tour_api',%s,'14',%s,%s,%s,'20260901000000')",
                            (tenant, content_id, title, LAT + dlat, LON + dlon))
        store = TripStore(tenant)
        items = [Item(item_id=uuid4(), seq=1, kind="activity", title="원래 공원", place_id=ids["park"],
                      starts_at=_at(10, 10), ends_at=_at(11, 40), detail={}),
                 Item(item_id=uuid4(), seq=2, kind="dining", title="점심집", place_id=ids["lunch"],
                      starts_at=_at(13), ends_at=_at(14), detail={})]
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title="t", locale="ko", party_size=2,
                                           items=items, constraints={})
    return store, trip_id, items


NIGHT = datetime(2030, 1, 1, 3, 30, tzinfo=KST)


def _night(tenant, tour, *, now=NIGHT, per_night=600, per_tick=10, chat=None):
    """새벽 작업 한 틱 — 설정값은 가드레일과 같은 모양."""
    from app.domains.travel_ops.components.places.catalog_hours import prefill

    with get_connection() as conn:
        return prefill(conn, tenant_id=tenant, source=tour, chat=chat, now=now, start="03:00", until="08:00",
                       per_night=per_night, per_tick=per_tick, retry_days=7)


def _desk(store):
    return TripDesk(store=store, connection_factory=get_connection, dining_ledger=False, catalog_pool=True)


def test_another_activity_comes_from_the_tour_catalog_read_at_night():
    tenant = "pool_" + uuid4().hex[:8]
    try:
        store, trip_id, items = _setup(tenant, [("9001", "목록 미술관", 0.004, 0.0)])
        tour = _Tour({"9001": "09:00~18:00"})
        assert _night(tenant, tour)["read"] == 1 and tour.asked == ["9001"]      # 새벽에 읽었다
        done = _desk(store).fresh_alternate(trip_id=trip_id, item_id=items[0].item_id, base_version=1,
                                            message="활동 다른 데로 바꿔", request_id="r1")
        assert done["status"] == "adjusted" and done["notice"]["changed"]["to"] == "목록 미술관", done
        with get_connection() as conn:
            scoped = [p for p in store.places(conn, trip_id) if p["name"] == "목록 미술관"]
            assert len(scoped) == 1 and scoped[0]["trip_scope"] == str(trip_id)   # 그 여행 전용 행이다
            assert "목록 미술관" not in {p["name"] for p in store.places(conn)}
    finally:
        _drop(tenant)


def test_a_place_not_read_yet_is_not_a_candidate_and_nothing_is_called():
    """☆요청마다 관광공사를 최대 10번 불렀다(첫 요청 33초 · 연달아 요청하면 한도). 이제 읽어 두지 않은 곳은 후보가 아니다
    — 요청 자리에는 관광공사 원천이 아예 넘어가지 않는다(`TripDesk` 는 원천을 받지 않는다)."""
    tenant = "pool_" + uuid4().hex[:8]
    try:
        store, trip_id, items = _setup(tenant, [("9011", "아직 안 읽은 관", 0.004, 0.0)])
        done = _desk(store).fresh_alternate(trip_id=trip_id, item_id=items[0].item_id, base_version=1,
                                            message="활동 다른 데로 바꿔", request_id="r1")
        assert "아직 안 읽은 관" not in str(done), done
    finally:
        _drop(tenant)


def test_nothing_open_then_three_options_are_asked_with_every_reason():
    tenant = "pool_" + uuid4().hex[:8]
    try:
        # 3km 안 목록 활동은 오후에만 열고, 5km 안(넓힌 반경)에 오전에 여는 곳이 둘 있다
        store, trip_id, items = _setup(tenant, [("9101", "오후 박물관", 0.006, 0.0),
                                                ("9102", "먼 과학관", 0.036, 0.0),
                                                ("9103", "먼 식물원", 0.0, 0.045)])
        _night(tenant, _Tour({"9101": "10:40~18:00", "9102": "09:00~18:00", "9103": "09:00~18:00"}))
        asked = _desk(store).fresh_alternate(trip_id=trip_id, item_id=items[0].item_id, base_version=1,
                                             message="활동 다른 데로 바꿔", request_id="r1")
        assert asked["status"] == "asked", asked
        text = asked["text"]
        assert text.startswith("3km 안에서 10:10에 갈 수 있는 활동이 없어요"), text
        # ★살펴본 곳마다 이유를 적는다(일부만 말하지 않는다)
        assert "닫힌 전시관 — 그 시각 영업하지 않는다" in text and "오후 박물관 — 그 시각 영업하지 않는다" in text, text
        assert "대신 이런 곳이 있어요 — 1)" in text and "3)" in text, text
        for name in ("오후 박물관", "먼 과학관", "먼 식물원"):
            assert name in text.split("대신 이런 곳이 있어요")[1], text
        with get_connection() as conn:
            trip, _ = store.latest(conn, trip_id)
            assert trip["version"] == 1                                          # 묻기만 했다
            open_ = PendingStore(tenant).list(conn, trip_id, only_open=True)
        assert [p["reason"] for p in open_] == ["relaxed"] and len(open_[0]["options_json"]) == 3
    finally:
        _drop(tenant)


def test_hours_read_for_another_trip_are_reused():
    """다른 여행이 읽어 둔 장소 행(같은 관광공사 id)도 DB 값이라 쓴다."""
    tenant = "pool_" + uuid4().hex[:8]
    try:
        store, trip_id, items = _setup(tenant, [("9201", "읽어 둔 기념관", 0.004, 0.0)])
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            # 다른 여행이 읽어 둔 행 — 이름·자리가 달라 후보로는 안 보인다(관광공사 id 만 같다)
            cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,attributes) VALUES (%s,'기념관(옛 표기)',"
                        "'dining',%s,%s,%s)",
                        (tenant, LAT + 1.0, LON, json.dumps({
                            "source_content_id": "9201",
                            "hours_week": {d: {"open": "09:00", "close": "18:00", "last_entry": None}
                                           for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
                            "hours_read": {"source": "tour_api", "method": "model",
                                           "read_at": datetime.now(KST).isoformat()}})))
        done = _desk(store).fresh_alternate(trip_id=trip_id, item_id=items[0].item_id, base_version=1,
                                            message="활동 다른 데로 바꿔", request_id="r1")
        assert done["status"] == "adjusted" and done["notice"]["changed"]["to"] == "읽어 둔 기념관", done
    finally:
        _drop(tenant)


def test_the_night_job_reads_only_new_or_changed_places_within_its_window_and_budget():
    """새벽 작업 — 창 밖이면 안 한다 · 하룻밤 몫을 넘지 않는다 · 목록 수정 시각이 바뀐 곳만 다시 읽는다 ·
    관광공사가 답을 못 주면 적지 않고 멈춘다(다음 틱이 잇는다)."""
    tenant = "pool_" + uuid4().hex[:8]
    try:
        _setup(tenant, [("9401", "가 관", 0.004, 0.0), ("9402", "나 관", 0.005, 0.0), ("9403", "다 관", 0.006, 0.0)])
        tour = _Tour({"9401": "09:00~18:00", "9402": "09:00~18:00", "9403": "09:00~18:00"})
        assert _night(tenant, tour, now=datetime(2030, 1, 1, 14, 0, tzinfo=KST))["skipped"] == "창 밖"
        assert tour.asked == []
        first = _night(tenant, tour, per_night=2)
        assert first["read"] == 2 and len(tour.asked) == 2
        assert _night(tenant, tour, per_night=2)["skipped"] == "오늘 밤 몫을 다 썼다"
        second = _night(tenant, tour, now=datetime(2030, 1, 2, 3, 30, tzinfo=KST))
        assert second["read"] == 1 and tour.asked[-1] == "9403"               # 남은 한 곳만
        assert _night(tenant, tour, now=datetime(2030, 1, 3, 3, 30, tzinfo=KST))["asked"] == 0   # 바뀐 것이 없다
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE place_catalog SET source_modified_at='20300102000000' "
                        "WHERE tenant_id=%s AND content_id='9402'", (tenant,))
        changed = _night(tenant, tour, now=datetime(2030, 1, 3, 3, 40, tzinfo=KST))
        assert changed["read"] == 1 and tour.asked[-1] == "9402"               # 목록에서 바뀐 곳만 다시 읽었다
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE place_catalog SET source_modified_at='20300103000000' WHERE tenant_id=%s", (tenant,))
        broken = _night(tenant, _Tour({}), now=datetime(2030, 1, 4, 3, 30, tzinfo=KST))
        assert broken["read"] == 0 and broken["stopped"], broken               # 답이 없으면 적지 않고 멈춘다
    finally:
        _drop(tenant)


def test_scenario_seed_places_are_not_candidates_in_the_service_tenant(monkeypatch):
    """☆`[2026-09-29 ui 세션 지적]` 대본의 가짜 지점(「명동 대형마트(시나리오 지점)」)이 실제 고객의 바꾸기에 뽑혔다.
    실서비스 테넌트에서는 뺀다 — 이미 그 여행 일정에 든 것은 남긴다. 시나리오 · 시험 테넌트는 그대로."""
    from app.domains.travel_ops.components.itinerary import itinerary

    tenant = "pool_" + uuid4().hex[:8]
    try:
        store, trip_id, items = _setup(tenant, [])
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                        "VALUES (%s,'대형마트(시나리오 지점)','activity',%s,%s,false,%s)",
                        (tenant, LAT + 0.002, LON, json.dumps({"hours": ["08:00", "23:00"], "scenario_seed": True})))
        with get_connection() as conn:
            assert "대형마트(시나리오 지점)" in {p["name"] for p in store.places(conn, trip_id)}    # 시험 테넌트는 그대로
        monkeypatch.setattr(itinerary, "hides_scenario_places", lambda t: t == tenant)
        with get_connection() as conn:
            names = {p["name"] for p in store.places(conn, trip_id)}
            shared = {p["name"] for p in store.places(conn)}
        assert "대형마트(시나리오 지점)" not in names and "대형마트(시나리오 지점)" not in shared
        with get_connection() as conn:
            every = [p["name"] for p in itinerary.visible_to(store.places(conn, every_trip=True), trip_id)]
        assert "대형마트(시나리오 지점)" not in every                     # 여러 여행을 도는 감시도 같다
        desk = TripDesk(store=store, connection_factory=get_connection, dining_ledger=False)
        done = desk.fresh_alternate(trip_id=trip_id, item_id=items[0].item_id, base_version=1,
                                    message="활동 다른 데로 바꿔", request_id="r1")
        assert "대형마트(시나리오 지점)" not in str(done), done
        # 대본 여행(처음 등록한 판이 시연 장소를 쓴 여행)에는 보인다 — 대본이 그 장소로 돈다
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE places SET attributes = attributes || '{\"scenario_seed\": true}'::jsonb "
                        "WHERE tenant_id=%s AND name='원래 공원'", (tenant,))
        with get_connection() as conn:
            assert "대형마트(시나리오 지점)" in {p["name"] for p in store.places(conn, trip_id)}
            every = [p["name"] for p in itinerary.visible_to(store.places(conn, every_trip=True), trip_id)]
        assert "대형마트(시나리오 지점)" in every
    finally:
        _drop(tenant)
