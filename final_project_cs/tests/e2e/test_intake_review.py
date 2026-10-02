# -*- coding: utf-8 -*-
"""확인 화면의 검사(장소·시간·운영시간·휴무일 + 장소 사이 이동) · 잠금 · 고른 장소 · 대체 후보 · 전체 자동 추천 · 실시간 진행.
`[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`

재현:

    python -m pytest tests/e2e/test_intake_review.py -v

★이 시험이 쓰는 관광공사 · 카카오 · 이동 계산기는 **테스트용 모방**이다(실제 서버가 아니다). 실제 서버 확인은 따로 한다(`wiki/records/reports/`).
  이동 계산기는 꺼 두고(직선 어림값) 계산기 경로는 가짜 계산기로 시험한다 — 실제 시간표 판정은 `tests/unit/travel/test_intake_moves.py` 와 실서버 확인이 본다.
"""
from __future__ import annotations

import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import op_stream
from app.modules.travel_ops.intake import autofix as autofix_module
from app.modules.travel_ops.intake import candidates as candidates_module
from app.modules.travel_ops.intake import review as review_module
from app.modules.travel_ops.trip_api import build_trip_router
from app.presentation.api.app import create_app

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다


class Tour:
    """관광공사 모방 — 이름이 정확히 같은 곳만. 좌표는 실제 서울 위치에 가깝게."""

    PLACES = {"경복궁": ("126508", "12", 37.5796, 126.9770), "광장시장": ("264570", "38", 37.5700, 126.9996),
              "N서울타워": ("126537", "12", 37.5512, 126.9882)}

    def __init__(self):
        self.asked: list = []
        self.misses: dict = {}
        self.image_calls: list = []

    def find(self, name, area_code=None):
        self.asked.append(name)
        if name not in self.PLACES:
            return None
        cid, ctype, lat, lon = self.PLACES[name]
        return {"matched_title": name, "content_id": cid, "content_type_id": ctype, "latitude": lat,
                "longitude": lon, "address": "서울특별시 종로구"}

    def images(self, content_id, limit=8):
        self.image_calls.append(content_id)
        return [{"url": f"https://example.test/{content_id}/1.jpg", "thumb": None, "name": "정문"}] if content_id == "126508" else []


class Kakao:
    """카카오 모방 — 「올리브영」은 지점이 여러 곳이라 이름이 특정되지 않는다. 「광장시장 빈대떡」은 음식점들이 나온다."""

    BRANCHES = [
        {"id": "1", "name": "올리브영 명동 플래그십", "category": "쇼핑 > 화장품", "category_group": "",
         "address": "서울 중구 명동길 53", "latitude": 37.5637, "longitude": 126.9851},
        {"id": "2", "name": "올리브영 광화문점", "category": "쇼핑 > 화장품", "category_group": "",
         "address": "서울 종로구 종로1길 50", "latitude": 37.5717, "longitude": 126.9791},
        {"id": "3", "name": "올리브영 강남타운", "category": "쇼핑 > 화장품", "category_group": "",
         "address": "서울 강남구 강남대로 429", "latitude": 37.5010, "longitude": 127.0265},
    ]
    FOOD = [{"id": "11", "name": "순희네빈대떡", "category": "음식점 > 한식", "category_group": "FD6",
             "address": "서울 종로구 종로32길 5", "latitude": 37.5701, "longitude": 126.9994},
            {"id": "12", "name": "박가네빈대떡", "category": "음식점 > 한식", "category_group": "FD6",
             "address": "서울 종로구 종로32길 6", "latitude": 37.5702, "longitude": 126.9995}]

    def __init__(self):
        self.asked: list = []
        self.misses: dict = {}

    def search(self, query, size=5, near=None):
        self.asked.append((query, near))
        if query.startswith("올리브영"):
            hits = [b for b in self.BRANCHES if query == "올리브영" or query.replace(" ", "") in b["name"].replace(" ", "")]
            if near is not None:
                from app.modules.travel_ops.intake.places import distance_m

                hits = sorted(hits, key=lambda b: distance_m(near[0], near[1], b["latitude"], b["longitude"]))
            return hits
        if query == "광장시장 빈대떡":
            return list(self.FOOD)
        return []


PLAN = ("2026-10-15\n"
        "10시 경복궁 관람 1시간 반\n"
        "11시 올리브영\n"
        "12시 반 광장시장 빈대떡\n"
        "2026-10-16\n"
        "15시 N서울타워")

#: 올리브영 뒤에 여유를 둔 계획 — 전체 자동 추천이 시각을 맞출 수 있는 모양
ROOMY = ("2026-10-15\n"
         "10시 경복궁 관람 1시간 반\n"
         "11시 올리브영\n"
         "13:30 광장시장 빈대떡")


@pytest.fixture()
def rv(api, monkeypatch):  # noqa: F811
    """이동 계산기를 끈 환경(직선 어림값) + 시험이 넣은 관광공사 목록 · 운영시간 정리."""
    for module in (review_module, candidates_module, autofix_module):
        monkeypatch.setattr(module, "default_engine", lambda party=None: None)
    op_stream._OPEN.clear()
    yield api
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for table in ("catalog_hours", "place_catalog"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (api["tenant"],))
    op_stream._OPEN.clear()


def _hours(api, content_id, week):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO catalog_hours (tenant_id, source, content_id, content_type_id, hours_week, hours_read, read_at) "
                    "VALUES (%s,'tour_api',%s,'12',%s,%s, now()) ON CONFLICT DO NOTHING",
                    (api["tenant"], content_id, json.dumps(week), json.dumps({"source": "tour_api", "method": "test"})))


def _catalog(api, content_id, ctype, title, lat, lon, address="서울특별시 종로구 사직로 1"):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, title, address, latitude, longitude) "
                    "VALUES (%s,'tour_api',%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (api["tenant"], content_id, ctype, title, address, lat, lon))


OPEN_ALL = {d: {"open": "09:00", "close": "18:00", "last_entry": "17:30"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
TUE_CLOSED = {**OPEN_ALL, "tue": "closed"}


def _client(tour=None, kakao=None):
    tour, kakao = tour or Tour(), kakao or Kakao()
    return TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(place_factory=lambda: tour, kakao_factory=lambda: kakao)])), tour, kakao


def _key(client) -> dict:
    return {"X-User-Key": client.post("/v1/web/session").json()["user_key"]}


def _send(client, headers, text=PLAN) -> dict:
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
    assert response.status_code == 202, response.text
    return client.get(f"/v1/web/trip-intakes/{response.json()['intake_id']}", headers=headers).json()


def _item(view, title):
    return next(i for i in view["review"]["items"] if i["title"] == title)


def _row(item, name):
    return next(r for r in item["rows"] if r["row"] == name)


def _edit(client, headers, view, *edits, status=200):
    response = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                           json={"revision": view["revision"], "edits": list(edits)})
    assert response.status_code == status, response.text
    return response.json()


def _field(item, name, value):
    return {"source_id": item["source_id"], "field": f"items[{item['index']}].{name}", "value": value}


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        if lines and lines[0].startswith("event: "):
            out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


# ── 검사: 장소 · 시간 · 운영시간 · 휴무일 ────────────────────────────
def test_the_mockup_plan_is_read_and_each_place_is_checked(rv):
    client, tour, kakao = _client()
    headers = _key(client)
    view = _send(client, headers)
    review = view["review"]
    assert view["status"] == "review" and view["review_error"] is None
    assert [(i["starts_at"], i["ends_at"], i["title"]) for i in review["items"]] == [
        ("10:00", "11:30", "경복궁 관람"), ("11:00", "12:30", "올리브영"), ("12:30", "13:30", "광장시장 빈대떡"),
        ("15:00", "16:30", "N서울타워")]
    # ★「1시간 반」을 시각 「1시」로 읽던 결함 — 가짜 항목(「간 반」)이 없고, 소요 시간이 끝 시각이 된다
    assert len(review["items"]) == 4
    first = review["items"][0]
    assert first["place"]["name"] == "경복궁" and first["status"] == "keep" and first["can_lock"] is True
    assert _row(first, "place")["result"] == "ok"
    # ★이름이 여러 곳인 「올리브영」은 빈칸이 아니라 앞뒤 일정에 가까운 한 곳을 먼저 채우고(임시) 확인을 받는다
    oy = _item(view, "올리브영")
    assert oy["place_state"] == "picked_nearest" and oy["place"]["name"] == "올리브영 광화문점"
    assert oy["status"] == "review" and oy["can_lock"] is False and oy["candidates_hint"] == 3
    assert _row(oy, "place")["result"] == "warn" and "임시로" in _row(oy, "place")["text"]
    # 가게 이름 없이 시장까지만 정한 식사는 확인을 재촉하지 않는다
    market = _item(view, "광장시장 빈대떡")
    assert market["kind"] == "dining" and _row(market, "place")["text"] == "가게 이름이 없어 광장시장으로 잡았어요"
    assert market["status"] == "adjusted"
    assert [i["day"] for i in review["items"]] == [1, 1, 1, 2]


def test_between_places_the_move_is_measured_and_a_late_arrival_is_flagged(rv):
    client, _, _ = _client()
    view = _send(client, _key(client))
    moves = view["review"]["moves"]
    assert [(m["from"], m["to"]) for m in moves] == [("0-0", "0-1"), ("0-1", "0-2"), ("0-2", "0-3")][:2]
    first = moves[0]
    # 경복궁이 11:30 에 끝나고 올리브영이 11:00 에 시작한다 — 목업의 「11:30에 나서면 11:42 도착 · 일정보다 42분 늦어요」
    assert (first["depart"], first["arrive"], first["slack_min"], first["status"]) == ("11:30", "11:42", -42, "review")
    assert first["basis"] == "estimate" and "[추정]" in first["summary"]            # 계산기가 꺼져 있으면 어림이라고 적는다
    assert [r["row"] for r in first["rows"]] == ["route", "mode", "arrival"]
    assert first["rows"][2] == {"row": "arrival", "result": "warn", "text": "11:30에 나서면 11:42 도착 · 일정보다 42분 늦어요"}
    assert view["review"]["needs"]["items"] == 1 and view["review"]["needs"]["moves"] == 2
    assert view["review"]["ready"] is False


def test_opening_hours_and_closing_days_come_from_what_is_stored_and_use_the_registration_judge(rv):
    _hours(rv, "126508", TUE_CLOSED)
    client, _, _ = _client()
    headers = _key(client)
    thursday = _send(client, headers, "2026-10-15\n10시 경복궁")
    palace = thursday["review"]["items"][0]
    assert _row(palace, "hours") == {"row": "hours", "result": "ok", "text": "09:00–18:00 안에 머물러요"}
    assert _row(palace, "closed") == {"row": "closed", "result": "ok", "text": "화요일 휴무 · 방문은 목요일"}
    # 화요일 — 쉬는 날이면 고쳐야 하는 항목이다
    tuesday = _send(client, headers, "2026-10-13\n10시 경복궁")
    palace = tuesday["review"]["items"][0]
    assert _row(palace, "closed")["result"] == "bad" and "쉬는 날" in _row(palace, "closed")["text"]
    assert palace["status"] == "review" and tuesday["review"]["needs"]["items"] == 1
    # 열기 전 — 주의(등록 판정기의 before_opening 과 같은 판정)
    early = _send(client, headers, "2026-10-15\n7시 반 경복궁")
    row = _row(early["review"]["items"][0], "hours")
    assert row["result"] == "warn" and row["text"].startswith("09:00에 열어요")
    assert early["review"]["items"][0]["status"] == "review"


def test_unknown_hours_are_said_to_be_unknown_not_open(rv):
    client, _, _ = _client()
    view = _send(client, _key(client), "2026-10-15\n10시 경복궁")
    palace = view["review"]["items"][0]
    assert _row(palace, "hours")["result"] == "unknown" and "읽지 못했어요" in _row(palace, "hours")["text"]
    assert _row(palace, "closed")["result"] == "unknown"
    assert palace["status"] == "adjusted"                   # 끝 시각을 규칙이 채웠을 뿐 — 모르는 운영시간은 「고쳐야 함」이 아니다


def test_a_bad_review_never_blocks_reading_it_and_says_why(rv, monkeypatch):
    client, _, _ = _client()
    headers = _key(client)

    def boom(*a, **k):
        raise RuntimeError("검사 장애")

    monkeypatch.setattr(review_module, "build", boom)
    view = _send(client, headers, "2026-10-15\n10시 경복궁")
    assert view["status"] == "review" and view["review"] is None and view["review_error"] == "review_failed"
    assert view["check"]["ready"] is True                    # 읽은 값 · 등록은 그대로 된다


def test_an_overlap_that_no_move_catches_still_needs_a_look_so_the_plan_is_not_ready(rv):
    """겹침은 보통 앞 구간이 「늦게 닿는다」로 잡히지만, 한쪽 장소가 없어 구간을 못 재면 이동이 확인 필요를 세지 못한다 — 그래도 겹친 일정은 확인 필요다."""
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁 1시간\n10시 반 광장시장 1시간")
    assert view["review"]["needs"]["moves"] == 1                       # 두 곳 다 장소가 있으면 구간이 늦게 닿는다고 센다
    second = _item(view, "광장시장")
    nothing = _edit(client, headers, view, _field(second, "place", {"none": True}))
    moves = nothing["review"]["moves"]
    assert [m["status"] for m in moves] == ["waiting"]                  # 장소가 없으니 구간은 아직 못 쟀다
    late = _item(nothing, "광장시장")
    assert _row(late, "time")["result"] == "warn" and "겹쳐요" in _row(late, "time")["text"]
    assert late["status"] == "review" and nothing["review"]["needs"]["items"] == 1 and nothing["review"]["ready"] is False


# ── 잠금 · 고른 장소 · 빼기 되돌리기 ──────────────────────────────────
def test_lock_pins_a_confirmed_item_and_blocks_changes_until_it_is_unlocked(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    palace, oy = _item(view, "경복궁 관람"), _item(view, "올리브영")
    # 확인이 필요한 일정은 먼저 고쳐야 고정할 수 있다
    refused = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                          json={"revision": view["revision"], "edits": [_field(oy, "locked", True)]})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "lock_needs_confirmed_item"
    locked = _edit(client, headers, view, _field(palace, "locked", True))
    assert _item(locked, "경복궁 관람")["locked"] is True and locked["revision"] == 2
    # 고정한 일정은 바꾸지도 빼지도 못한다 — 409
    for field in (_field(palace, "starts_at", "09:30"), _field(palace, "removed", True), _field(palace, "place", {"name": "광장시장"})):
        again = client.post(f"/v1/web/trip-intakes/{locked['intake_id']}/edits", headers=headers,
                            json={"revision": locked["revision"], "edits": [field]})
        assert again.status_code == 409 and again.json()["error"]["code"] == "item_locked", again.text
    # 칸 이름을 다르게 적어도(앞의 0 · 공백) 같은 항목이라 잠금을 피하지 못한다
    spelled = {"source_id": palace["source_id"], "field": f"items[ 0{palace['index']} ].starts_at", "value": "09:30"}
    dodge = client.post(f"/v1/web/trip-intakes/{locked['intake_id']}/edits", headers=headers,
                        json={"revision": locked["revision"], "edits": [spelled]})
    assert dodge.status_code == 409 and dodge.json()["error"]["code"] == "item_locked"
    # 잠금 풀기와 고치기를 같은 요청에 — 된다
    freed = _edit(client, headers, locked, _field(palace, "locked", False), _field(palace, "starts_at", "09:30"))
    assert _item(freed, "경복궁 관람")["locked"] is False and _item(freed, "경복궁 관람")["starts_at"] == "09:30"


def test_a_locked_item_is_registered_as_customer_pinned(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n13:30 광장시장")
    palace = view["review"]["items"][0]
    locked = _edit(client, headers, view, _field(palace, "locked", True))
    done = client.post(f"/v1/web/trip-intakes/{locked['intake_id']}/confirm", headers=headers,
                       json={"revision": locked["revision"]})
    assert done.status_code == 200, done.text
    from app.modules.travel_ops.itinerary import TripStore

    with get_connection() as conn:
        items = TripStore(rv["tenant"]).latest(conn, UUID(done.json()["trip"]["trip_id"]))[1]
    pinned = {i.title: bool(i.detail.get("customer_pinned")) for i in items}
    assert pinned == {"경복궁": True, "광장시장": False}      # ★감시 루프가 다시 자동으로 바꾸지 않는 일정이 된다


def test_only_existing_items_can_be_edited_and_locking_is_sent_alone(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n13:30 광장시장")
    palace = view["review"]["items"][0]
    # 없는 번호를 보내 일정을 새로 만들지 못한다 — 날짜·장소 없는 항목이 끼어들어 등록 준비를 깨뜨리지 못하게
    ghost = {"source_id": palace["source_id"], "field": "items[500].title", "value": "새 일정"}
    refused = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                          json={"revision": view["revision"], "edits": [ghost]})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "unknown_item"
    assert client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()["revision"] == view["revision"]   # 새 판이 생기지 않았다
    # 고정은 다른 고치기와 한 요청에 섞지 않는다 — 장소를 비우면서 고정하면 고정이 바뀐 값에 걸린다
    mixed = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                        json={"revision": view["revision"], "edits": [_field(palace, "locked", True), _field(palace, "place", {"none": True})]})
    assert mixed.status_code == 422 and mixed.json()["error"]["code"] == "lock_with_changes"
    assert _item(client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json(), "경복궁")["locked"] is False


def test_a_tour_number_the_customer_sends_is_kept_only_when_the_catalog_says_it_is_there(rv):
    _catalog(rv, "900050", "12", "덕수궁", 37.5658, 126.9751)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n13:30 광장시장")
    palace = view["review"]["items"][0]

    def placed(current, content_id, lat, lon):
        got = _edit(client, headers, current, _field(palace, "place", {"name": "덕수궁", "latitude": lat, "longitude": lon,
                                                                      "source": "tour_api", "content_id": content_id}))
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT value_json->>'content_id' FROM intake_claims WHERE intake_id=%s AND revision=%s AND field=%s "
                        "ORDER BY created_at DESC LIMIT 1", (view["intake_id"], got["revision"], f"items[{palace['index']}].place"))
            return cur.fetchone()[0], got

    kept, after = placed(view, "900050", 37.5658, 126.9751)
    assert kept == "900050"                                              # 목록의 그 번호가 이 좌표 500m 안 — 인정
    dropped, _ = placed(after, "900050", 37.5700, 126.9996)               # 같은 번호를 다른 곳(광장시장 쪽 좌표)에 붙였다 — 번호를 뗀다
    assert dropped is None


def test_removing_an_item_can_be_undone(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    market = _item(view, "광장시장 빈대떡")
    gone = _edit(client, headers, view, _field(market, "removed", True))
    assert [i["title"] for i in gone["review"]["items"]] == ["경복궁 관람", "올리브영", "N서울타워"]
    back = _edit(client, headers, gone, _field(market, "removed", False))
    assert [i["title"] for i in back["review"]["items"]] == ["경복궁 관람", "올리브영", "광장시장 빈대떡", "N서울타워"]


def test_a_place_the_customer_picked_is_taken_as_shown_and_stays_private_to_the_trip(rv):
    client, _, kakao = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n11시 올리브영\n14시 광장시장")
    oy = _item(view, "올리브영")
    pick = {"name": "올리브영 명동 플래그십", "latitude": 37.5637, "longitude": 126.9851, "source": "kakao", "kind": "activity"}
    done = _edit(client, headers, view, _field(oy, "place", pick))
    after = _item(done, "올리브영")
    assert after["place_state"] == "customer" and after["place"]["name"] == "올리브영 명동 플래그십"
    assert after["place"]["source"] == "customer_pick"                    # 고객이 보낸 값은 카카오 값으로 위장하지 않는다
    assert _row(after, "place")["result"] == "ok" and after["edited"] is True and after["status"] == "adjusted"
    asked_before = len(kakao.asked)
    assert asked_before >= 1                                              # 읽을 때만 물었고, 고른 값은 다시 찾지 않았다
    # 서울 밖 · 잘못된 값은 거절 — 지어낸 좌표를 받지 않는다
    for bad, code in (({**pick, "latitude": 35.1, "longitude": 129.0}, "place_out_of_seoul"),
                      ({**pick, "latitude": "37.5"}, "invalid_value"), ({**pick, "source": "google"}, "invalid_value"),
                      ({**pick, "content_id": "12ab"}, "invalid_value"), ({**pick, "name": " "}, "invalid_value")):
        response = client.post(f"/v1/web/trip-intakes/{done['intake_id']}/edits", headers=headers,
                               json={"revision": done["revision"], "edits": [_field(after, "place", bad)]})
        assert response.status_code == 422 and response.json()["error"]["code"] == code, (bad, response.text)
    assert len(kakao.asked) == asked_before
    # 등록하면 그 여행 전용 장소 행(customer_pick)이다 — 공용 장소 표에 섞이지 않는다
    registered = client.post(f"/v1/web/trip-intakes/{done['intake_id']}/confirm", headers=headers,
                             json={"revision": done["revision"]})
    assert registered.status_code == 200, registered.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT trip_scope IS NOT NULL, attributes->>'source' FROM places WHERE tenant_id=%s AND name=%s",
                    (rv["tenant"], "올리브영 명동 플래그십"))
        assert cur.fetchall() == [(True, "customer_pick")]


def test_a_second_user_cannot_see_or_change_someone_elses_review(rv):
    client, _, _ = _client()
    mine, other = _key(client), _key(client)
    view = _send(client, mine)
    oy = _item(view, "올리브영")
    path = f"/v1/web/trip-intakes/{view['intake_id']}"
    query = f"source_id={oy['source_id']}&index={oy['index']}"
    assert client.get(f"{path}/candidates?{query}", headers=other).status_code == 404
    assert client.get(f"{path}/place-search?q=올리브영&{query}", headers=other).status_code == 404
    assert client.post(f"{path}/autofix", headers=other, json={"revision": 1}).status_code == 404
    assert client.post(f"{path}/revalidate", headers=other, json={"revision": 1}).status_code == 404
    assert client.get(f"{path}/events", headers=other).status_code == 404
    assert client.get(f"{path}/candidates?{query}").status_code == 401


# ── 대체 후보 · 장소 검색 · 사진 ─────────────────────────────────────
def test_alternatives_for_an_ambiguous_chain_are_the_other_branches_with_a_fit_check(rv):
    client, _, kakao = _client()
    headers = _key(client)
    view = _send(client, headers)
    oy = _item(view, "올리브영")
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={oy['source_id']}&index={oy['index']}"
                     f"&revision={view['revision']}", headers=headers)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["current"]["name"] == "올리브영 광화문점" and body["revision"] == view["revision"]
    names = [c["place"]["name"] for c in body["candidates"]]
    assert names == ["올리브영 명동 플래그십", "올리브영 강남타운"]            # 지금 곳은 빼고, 앞뒤 일정에서 가까운 순
    first = body["candidates"][0]
    assert first["rank"] == 1 and first["reference"] and first["distance_m"] > 0
    assert {"latitude", "longitude", "source", "name"} <= set(first["place"]) and "place_id" not in first["place"]
    assert [r["row"] for r in first["rows"]][0] == "place" and first["fits"] in (True, False)
    # 낡은 판으로 부르면 409
    stale = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={oy['source_id']}&index={oy['index']}"
                       f"&revision=9", headers=headers)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    # 없는 일정은 404
    missing = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={oy['source_id']}&index=99", headers=headers)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "item_not_found"


def test_alternatives_for_an_activity_come_from_the_stored_catalog_with_their_hours(rv):
    _hours(rv, "126508", OPEN_ALL)
    _catalog(rv, "900001", "12", "창덕궁", 37.5794, 126.9910)
    _catalog(rv, "900002", "12", "덕수궁", 37.5658, 126.9751)
    _hours(rv, "900001", TUE_CLOSED)
    _hours(rv, "900002", OPEN_ALL)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-13\n10시 경복궁\n13:30 광장시장")           # 화요일
    palace = view["review"]["items"][0]
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={palace['source_id']}&index={palace['index']}",
                     headers=headers).json()
    by_name = {c["place"]["name"]: c for c in got["candidates"]}
    assert set(by_name) == {"창덕궁", "덕수궁"}
    assert by_name["덕수궁"]["fits"] is True and by_name["창덕궁"]["fits"] is False   # 창덕궁은 화요일 휴무로 읽어 둔 곳
    assert [c["place"]["name"] for c in got["candidates"]][0] == "덕수궁"             # 맞는 곳이 먼저
    assert next(r for r in by_name["창덕궁"]["rows"] if r["row"] == "closed")["result"] == "bad"


def test_place_search_ranks_by_distance_and_attaches_the_check(rv):
    _catalog(rv, "900010", "12", "경복궁 별빛야행", 37.5796, 126.9770)
    _hours(rv, "900010", OPEN_ALL)
    client, _, kakao = _client()
    headers = _key(client)
    view = _send(client, headers)
    oy = _item(view, "올리브영")
    base = f"/v1/web/trip-intakes/{view['intake_id']}/place-search?source_id={oy['source_id']}&index={oy['index']}"
    found = client.get(base + "&q=올리브영", headers=headers).json()
    assert found["query"] == "올리브영" and [r["place"]["name"] for r in found["results"]][:1] == ["올리브영 광화문점"]
    assert all(r["rows"] and {"name", "latitude", "longitude", "source"} <= set(r["place"]) for r in found["results"])
    db = client.get(base + "&q=별빛", headers=headers).json()
    assert [r["place"]["name"] for r in db["results"]] == ["경복궁 별빛야행"]
    assert next(r for r in db["results"][0]["rows"] if r["row"] == "hours")["result"] == "ok"
    assert db["results"][0]["fits"] is False and db["results"][0]["rows"][1]["row"] == "time"   # 올리브영 11:00 은 경복궁이 11:30 에 끝나기 전이라 늦다
    assert client.get(base + "&q=a", headers=headers).status_code == 422             # 두 글자 이상
    blank = client.get(base + "&q=%20%20%20", headers=headers)                       # 공백만이면 모든 장소가 맞는 검색이 된다 — 거절
    assert blank.status_code == 422 and blank.json()["error"]["code"] == "query_too_short"


def test_search_puts_places_that_fit_the_schedule_before_closed_ones_and_keeps_the_current_place(rv):
    _catalog(rv, "900060", "12", "별빛 가까운 곳", 37.5796, 126.9770)          # 경복궁 바로 옆 — 화요일 휴무
    _catalog(rv, "900061", "12", "별빛 조금 먼 곳", 37.5700, 126.9996)
    _hours(rv, "900060", TUE_CLOSED)
    _hours(rv, "900061", OPEN_ALL)
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-13\n13:30 광장시장\n15시 N서울타워")           # 화요일
    market = _item(view, "광장시장")
    base = f"/v1/web/trip-intakes/{view['intake_id']}/place-search?source_id={market['source_id']}&index={market['index']}"
    found = client.get(base + "&q=별빛", headers=headers).json()["results"]
    assert [r["place"]["name"] for r in found] == ["별빛 조금 먼 곳", "별빛 가까운 곳"]       # 가까워도 쉬는 날인 곳은 뒤로
    assert found[0]["status"] != "bad" and found[1]["status"] == "bad"                      # 쉬는 날은 「고쳐야 함」
    # 지금 장소는 검색에서 빠지지 않는다 — 임시로 고른 곳을 「맞아요」로 확정하려고 다시 고르는 길이다
    same = client.get(base + "&q=광장시장", headers=headers).json()["results"]
    assert "광장시장" in [r["place"]["name"] for r in same]


def test_alternatives_never_offer_another_kind_of_place_as_a_replacement(rv):
    _catalog(rv, "900070", "39", "시장 옆 식당", 37.5700, 126.9990)             # 음식점뿐
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n13:30 광장시장")
    palace = view["review"]["items"][0]
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={palace['source_id']}&index={palace['index']}",
                     headers=headers).json()
    assert got["candidates"] == [] and "no_same_kind" in got["notes"]            # 관광지의 대체로 음식점을 끌어오지 않고 이유를 말한다


def test_reading_runs_once_per_intake_and_the_view_never_shows_internal_keys(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    from app.modules.travel_ops.intake import pipeline

    def claim_count():
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s", (view["intake_id"],))
            return cur.fetchone()[0]

    before = claim_count()
    # 이미 읽은 접수를 다시 읽으라고 해도 아무것도 지우거나 되돌리지 않는다(같은 접수를 두 일꾼이 읽는 사고 · 등록된 접수가 확인 화면으로 되돌아가는 사고)
    assert pipeline.process(get_connection, tenant_id=rv["tenant"], intake_id=UUID(view["intake_id"]), blobs={}, see=None) == "review"
    assert claim_count() == before
    assert all("sig" not in m for m in view["review"]["moves"]) and all("place_id" not in (i["place"] or {}) for i in view["review"]["items"])


def test_no_response_shows_the_internal_place_row_number_and_the_reason_a_fix_was_not_possible_is_exact(rv):
    # 공용 장소 표에 있는 곳은 읽을 때 장소 행 번호(`place_id`)로 이어진다 — 이 번호는 서버 안에서만 쓴다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,attributes) VALUES (%s,'경복궁','activity',37.5796,126.9770,%s)",
                    (rv["tenant"], json.dumps({"hours": ["09:00", "18:00"]})))
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n7시 반 경복궁 1시간\n13:30 광장시장")
    palace = view["review"]["items"][0]
    assert palace["place"]["name"] == "경복궁" and "place_id" not in palace["place"]                    # 응답에 장소 행 번호가 없다
    assert _row(palace, "hours")["result"] == "warn"                                                 # 그래도 번호로 운영시간(장소 행 속성)은 찾았다
    cand = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={palace['source_id']}&index={palace['index']}",
                      headers=headers).json()
    assert cand["current"]["name"] == "경복궁" and "place_id" not in cand["current"]
    fixed = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers, json={"revision": view["revision"]}).json()
    assert fixed["applied"] and "place_id" not in fixed["changed"][0]["from"]["place"]
    assert "place_id" not in json.dumps(fixed["view"]["review"], ensure_ascii=False)
    # 후보가 아예 없던 것과 후보를 맞추지 못한 것을 구별한다 — 이름을 못 찾았고 이웃도 없으면 후보 자체가 없다
    lost = _send(client, headers, "2026-10-15\n10시 정체불명장소")
    out = client.post(f"/v1/web/trip-intakes/{lost['intake_id']}/autofix", headers=headers, json={"revision": lost["revision"]}).json()
    assert out["applied"] is False and [k["reason"] for k in out["kept"]] == ["no_candidates"]


def test_only_one_worker_reads_an_intake_and_a_second_start_changes_nothing(rv):
    from app.modules.travel_ops.intake import pipeline

    with get_connection() as conn:
        intake_id = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], text=PLAN, files=[])
    # 다른 일꾼이 이미 맡았다(단계가 받은 직후가 아니다) — 두 번째는 아무것도 읽지도 지우지도 않는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage='reading' WHERE intake_id=%s", (intake_id,))
    assert pipeline.process(get_connection, tenant_id=rv["tenant"], intake_id=intake_id, blobs={}, see=None) == "reading"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s", (intake_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT status FROM trip_intakes WHERE intake_id=%s", (intake_id,))
        assert cur.fetchone()[0] == "reading"                    # 확인 화면으로 바뀌지도 않았다
    # 받은 직후 단계면 맡아서 읽는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage='received' WHERE intake_id=%s", (intake_id,))
    assert pipeline.process(get_connection, tenant_id=rv["tenant"], intake_id=intake_id, blobs={}, see=None,
                            tour=Tour(), kakao=Kakao()) == "review"
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE intake_id=%s", (intake_id,))


def test_an_intake_whose_reader_died_is_closed_as_failed_instead_of_reading_forever(rv):
    from app.modules.travel_ops.intake import pipeline
    from app.modules.travel_ops.web_session import resolve

    client, _, _ = _client()
    headers = _key(client)
    with get_connection() as conn:
        customer = resolve(conn, tenant_id=rv["tenant"], raw=headers["X-User-Key"])           # 이 키의 고객이 접수의 주인이어야 읽힌다
        dead = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=customer, text=PLAN, files=[])
        alive = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=customer, text=PLAN, files=[])
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage='reading', updated_at = now() - interval '10 minutes' WHERE intake_id=%s", (dead,))
        cur.execute("UPDATE trip_intakes SET stage='reading' WHERE intake_id=%s", (alive,))        # 방금 갱신됨 — 느리게 읽는 중
    gone = client.get(f"/v1/web/trip-intakes/{dead}", headers=headers).json()
    assert gone["status"] == "fatal" and gone["fatal"]["code"] == "stalled"                          # 영원히 「읽는 중」으로 두지 않는다
    still = client.get(f"/v1/web/trip-intakes/{alive}", headers=headers).json()
    assert still["status"] == "reading" and still["fatal"] is None


def test_a_worker_that_was_given_up_on_stops_writing_and_a_live_worker_keeps_its_intake_alive(rv):
    import time

    from app.modules.travel_ops.intake import pipeline

    with get_connection() as conn:
        intake_id = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], text=PLAN, files=[])
        source = pipeline._sources(conn, rv["tenant"], intake_id)[0]

    def state():
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT status, stage, extract(epoch FROM (now() - updated_at)) FROM trip_intakes WHERE intake_id=%s", (intake_id,))
            return cur.fetchone()

    # 1) 읽는 중에는 생존 표시가 갱신 시각을 계속 올린다 — 한 번의 긴 호출(사진 받아쓰기) 동안에도 죽은 일꾼으로 오해받지 않는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage='reading', updated_at = now() - interval '5 minutes' WHERE intake_id=%s", (intake_id,))
    assert state()[2] > 250
    with pipeline._Heartbeat(get_connection, rv["tenant"], intake_id, every=0.05):
        time.sleep(0.4)
    assert state()[2] < 5
    # 2) 실패로 확정된 접수에는 일꾼이 값도 단계도 더 쓰지 못하고(물러난다), 생존 표시도 되살리지 않는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='fatal', stage='fatal', fatal_code='stalled' WHERE intake_id=%s", (intake_id,))
    with pytest.raises(pipeline._Abandoned):
        pipeline._stage(get_connection, rv["tenant"], intake_id, "transcribing")
    with pytest.raises(pipeline._Abandoned):
        pipeline._claim_sink(get_connection, rv["tenant"], intake_id, source["source_id"])(
            [{"field": "items[0].title", "value": "경복궁", "method": "rule", "evidence": {"source": "text"}, "needs_review": False, "note": None}])
    with pipeline._Heartbeat(get_connection, rv["tenant"], intake_id, every=0.05):
        time.sleep(0.3)
    status, stage, _ = state()
    assert (status, stage) == ("fatal", "fatal")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s", (intake_id,))
        assert cur.fetchone()[0] == 0
    # 실패 확정 뒤에는 받아쓴 원본도, 읽다 만 값을 지우는 일도 하지 못한다(접수 행을 잠그고 확인한 뒤에만 쓴다)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        with pytest.raises(pipeline._Abandoned):
            pipeline._hold_reading(cur, rv["tenant"], intake_id)
    # 3) 이미 확인 화면인 접수를 늦게 온 실패 처리가 지우거나 바꾸지 않는다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='reading', stage='received', fatal_code=NULL WHERE intake_id=%s", (intake_id,))
    assert pipeline.process(get_connection, tenant_id=rv["tenant"], intake_id=intake_id, blobs={}, see=None,
                            tour=Tour(), kakao=Kakao()) == "review"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s", (intake_id,))
        before = cur.fetchone()[0]
    pipeline._fatal(get_connection, rv["tenant"], intake_id, "reading_failed", "늦게 온 실패")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s", (intake_id,))
        assert cur.fetchone()[0] == before > 0
    assert state()[0] == "review"
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE intake_id=%s", (intake_id,))


def test_a_reused_move_takes_the_current_day_numbers(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁 1시간\n13:30 광장시장\n2026-10-16\n15시 N서울타워")
    assert [m["day"] for m in view["review"]["moves"]] == [1]
    tower = _item(view, "N서울타워")
    moved = _edit(client, headers, view, _field(tower, "date", "2026-10-14"))                       # 더 이른 날이 생겨 앞의 두 일정이 둘째 날이 된다
    assert [i["day"] for i in moved["review"]["items"]] == [1, 2, 2]
    assert [m["day"] for m in moved["review"]["moves"]] == [2]                                      # 같은 구간(좌표·시각 그대로)이지만 일차는 지금 판의 것


def test_photos_come_from_the_tour_service_and_are_not_stored(rv):
    client, tour, _ = _client()
    headers = _key(client)
    got = client.get("/v1/web/places/photos?ref=tour:126508", headers=headers).json()
    assert got["photos"][0]["url"].endswith("/126508/1.jpg") and got["source_note"] == "ⓒ한국관광공사"
    empty = client.get("/v1/web/places/photos?ref=tour:999", headers=headers).json()
    assert empty["photos"] == [] and empty["reason"] == "no_photos"
    other = client.get("/v1/web/places/photos?ref=kakao:12", headers=headers).json()
    assert other["photos"] == [] and other["reason"] == "no_photo_source"              # 지어내지 않는다
    # 후보가 주는 `place:<uuid>`(42자)도 길이 때문에 거절되지 않고 같은 답이다(2026-10-03 실제 화면에서 422 였다)
    own = client.get("/v1/web/places/photos?ref=place:43fd13ce-5030-463d-ab8d-8bdf1a5ffdec", headers=headers)
    assert own.status_code == 200 and own.json()["reason"] == "no_photo_source"
    assert tour.image_calls == ["126508", "999"]
    assert client.get("/v1/web/places/photos?ref=tour:126508").status_code == 401


# ── 전체 자동 추천 · 재검증 ──────────────────────────────────────────
def test_auto_fix_all_picks_a_branch_and_fits_the_times_and_is_one_new_revision(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    assert view["review"]["needs"]["total"] >= 2 and view["review"]["ready"] is False
    got = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers, json={"revision": view["revision"]})
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["applied"] is True and body["revision"] == view["revision"] + 1
    [change] = [c for c in body["changed"] if c["title"] == "올리브영"]
    assert change["to"]["place"]["name"] == "올리브영 광화문점" and change["hours_known"] is False        # 카카오 값이라 운영시간은 모른다 — 열려 있다고 하지 않는다
    assert (change["to"]["starts_at"], change["to"]["ends_at"]) == ("11:45", "13:05")  # 경복궁 11:30 끝 + 도보 12분 → 11:45 · 광장시장 13:30 − 23분
    new = body["view"]
    assert new["revision"] == body["revision"] and new["review"]["needs"]["total"] == 0 and new["review"]["ready"] is True
    oy = _item(new, "올리브영")
    assert oy["place_state"] == "customer" and (oy["starts_at"], oy["ends_at"]) == ("11:45", "13:05")
    # 고객이 직접 고른 값과 같은 길로 저장되며 자동 추천이 낸 값이라는 표시가 남는다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s AND revision=%s AND evidence->>'via'='autofix'",
                    (view["intake_id"], body["revision"]))
        assert cur.fetchone()[0] == 3
    # 더 바꿀 것이 없으면 판을 만들지 않는다
    again = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers,
                        json={"revision": body["revision"]}).json()
    assert again["applied"] is False and again["revision"] == body["revision"] and again["changed"] == []


def test_auto_fix_all_leaves_locked_items_and_says_why_it_kept_what_it_could_not_fit(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    palace = _item(view, "경복궁 관람")
    locked = _edit(client, headers, view, _field(palace, "locked", True))
    body = client.post(f"/v1/web/trip-intakes/{locked['intake_id']}/autofix", headers=headers,
                       json={"revision": locked["revision"]}).json()
    assert body["applied"] is True and all(c["title"] != "경복궁 관람" for c in body["changed"])
    assert _item(body["view"], "경복궁 관람")["starts_at"] == "10:00"              # 고정한 일정은 그대로
    # 맞는 안이 없으면 지어내지 않고 그대로 두고 이유를 말한다 — 이 계획은 광장시장이 12:30 이라 올리브영이 20분밖에 못 머문다
    tight = _send(client, headers, PLAN)
    nothing = client.post(f"/v1/web/trip-intakes/{tight['intake_id']}/autofix", headers=headers,
                          json={"revision": tight["revision"]}).json()
    assert [k["reason"] for k in nothing["kept"] if k["title"] == "올리브영"] == ["no_fitting_time"]       # 후보는 있었지만 머무는 시간이 20분뿐이라
    assert all(c["title"] != "올리브영" for c in nothing["changed"])


def test_auto_fix_moves_the_time_into_the_opening_hours_before_it_swaps_the_place(rv):
    _hours(rv, "126508", OPEN_ALL)                             # 09:00–18:00, 입장 마감 17:30
    client, _, _ = _client()
    headers = _key(client)
    early = _send(client, headers, "2026-10-15\n7시 반 경복궁 1시간")
    palace = early["review"]["items"][0]
    assert palace["status"] == "review" and _row(palace, "hours")["result"] == "warn"
    got = client.post(f"/v1/web/trip-intakes/{early['intake_id']}/autofix", headers=headers, json={"revision": early["revision"]}).json()
    [change] = got["changed"]
    assert change["reason"] == "time" and change["to"]["place"]["name"] == "경복궁" and change["hours_known"] is True   # 장소는 그대로, 시각만
    assert (change["to"]["starts_at"], change["to"]["ends_at"]) == ("09:00", "10:00")            # 여는 시각으로 미루고 머무는 시간은 그대로
    assert got["view"]["review"]["needs"]["total"] == 0 and got["view"]["review"]["ready"] is True
    # 닫기 전에 끝나게 줄인다 — 17:30 부터 1시간 반은 18:00 에 닫는다 → 30분
    late = _send(client, headers, "2026-10-15\n17시 경복궁 1시간 반")
    [shrunk] = client.post(f"/v1/web/trip-intakes/{late['intake_id']}/autofix", headers=headers,
                           json={"revision": late["revision"]}).json()["changed"]
    assert shrunk["to"]["ends_at"] == "18:00" and shrunk["to"]["starts_at"] == "17:00"
    # 쉬는 날은 시각을 옮겨도 못 맞춘다 — 같은 곳에 머물지 않고 다른 후보를 본다(후보가 없으면 그대로 두고 이유)
    _hours(rv, "264570", TUE_CLOSED)
    closed = _send(client, headers, "2026-10-13\n10시 광장시장")
    out = client.post(f"/v1/web/trip-intakes/{closed['intake_id']}/autofix", headers=headers, json={"revision": closed["revision"]}).json()
    assert out["applied"] is False and [k["reason"] for k in out["kept"]] == ["no_candidates"]          # 쉬는 날이고 대신할 곳도 없다


def test_revalidate_recomputes_the_same_revision_without_making_a_new_one(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁")
    assert _row(view["review"]["items"][0], "hours")["result"] == "unknown"
    _hours(rv, "126508", OPEN_ALL)                       # 그 사이 새벽 작업이 운영시간을 읽어 두었다
    stale = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()
    assert _row(stale["review"]["items"][0], "hours")["result"] == "unknown"       # 판마다 한 번 계산해 둔 값 — 조회가 바꾸지 않는다
    fresh = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/revalidate", headers=headers,
                        json={"revision": view["revision"]})
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["revision"] == view["revision"]
    assert _row(fresh.json()["review"]["items"][0], "hours")["result"] == "ok"
    assert client.post(f"/v1/web/trip-intakes/{view['intake_id']}/revalidate", headers=headers,
                       json={"revision": 7}).status_code == 409


# ── 실시간 진행(내용 이벤트) ─────────────────────────────────────────
def test_the_events_stream_replays_lines_items_checks_moves_and_done_before_the_result(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    streamed = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/events", headers=headers)
    assert streamed.status_code == 200 and streamed.headers["content-type"].startswith("text/event-stream")
    events = _events(streamed.text)
    names = [n for n, _ in events]
    assert names[0] == "accepted" and names[-1] == "result" and names[-2] == "done"
    assert names.index("line") < names.index("item") < names.index("check") < names.index("move") < names.index("done")
    lines = [d for n, d in events if n == "line"]
    assert [d["no"] for d in lines] == [1, 2, 3, 4, 5, 6]            # ★두 날짜 줄(같은 칸 이름)도 모두 읽힌 줄이다
    assert [ln["read"] for ln in view["sources"][0]["lines"]] == [True] * 6
    palace_line = next(d for d in lines if d["text"].startswith("10시 경복궁"))
    assert palace_line["found"]["id"] == "0-0" and palace_line["found"]["starts_at"] == "10:00"
    items = {d["id"]: d for n, d in events if n == "item"}
    assert set(items) == {"0-0", "0-1", "0-2", "0-3"} and items["0-1"]["status"] == "review"
    checks = [d for n, d in events if n == "check"]
    assert {(d["item"], d["row"]) for d in checks} >= {("0-0", "place"), ("0-1", "place"), ("0-0", "hours"), ("0-0", "closed")}
    moves = [d for n, d in events if n == "move"]
    assert [(d["from"], d["to"]) for d in moves] == [("0-0", "0-1"), ("0-1", "0-2")] and "sig" not in moves[0]
    done = next(d for n, d in events if n == "done")
    assert done["needs"] == view["review"]["needs"] and done["ready"] is False and done["revision"] == view["revision"]
    assert events[-1][1]["state"]["status"] == "review"


def test_the_feed_works_on_half_read_values_and_never_repeats_what_it_already_sent(rv):
    """읽는 동안(값이 일부만 적힌 상태)에도 내용 이벤트가 예외 없이 만들어지고, 같은 상태는 다시 보내지 않는다."""
    from datetime import date

    from app.modules.travel_ops.intake import pipeline, stream

    tour, kakao = Tour(), Kakao()
    with get_connection() as conn:
        intake_id = pipeline.open_intake(conn, tenant_id=rv["tenant"], customer_id=rv["customer"], text=PLAN, files=[])
        source = pipeline._sources(conn, rv["tenant"], intake_id)[0]
    feed = stream.Feed(rv["tenant"], rv["customer"], intake_id)
    sink = pipeline._claim_sink(get_connection, rv["tenant"], intake_id, source["source_id"])
    state = {"status": "reading", "stage": "reading", "revision": 1}
    seen: list[tuple[str, dict]] = []

    def poll() -> list[tuple[str, dict]]:
        with get_connection() as conn:
            got = feed.poll(conn, state)
        seen.extend(got)
        return got

    assert poll() == []                                              # 아직 아무것도 안 적혔다
    batches: list[int] = []

    def write(batch):
        sink(batch)
        batches.append(len(batch))
        poll()                                                       # 한 묶음이 적힐 때마다 — 중간 상태에서도 터지지 않는다

    pipeline.read_source(PLAN, tour=tour, kakao=kakao, our_places=[], today=date(2026, 10, 3), on_rows=write)
    assert len(batches) >= 5 and poll() == []                        # 끝난 뒤 다시 물어도 새 것이 없다
    names = [n for n, _ in seen]
    assert len({d["no"] for n, d in seen if n == "line"}) == 6 and "check" not in names and "done" not in names     # 검사 전이라 검사 줄은 없다
    dumped = [json.dumps([n, d], sort_keys=True, ensure_ascii=False) for n, d in seen]
    assert len(dumped) == len(set(dumped))                          # ★같은 몸통을 두 번 보내지 않는다(값이 달라진 것만 같은 키로 다시 온다)
    states = [d["place_state"] for n, d in seen if n == "item" and d["id"] == "0-1"]
    assert states[0] == "searching" and states[-1] == "picked_nearest"                    # 찾는 중 → 임시 선택
    assert all(d["status"] is None for n, d in seen if n == "item")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE intake_id=%s", (intake_id,))


def test_the_stream_keeps_the_stage_events_when_the_content_step_fails(rv, monkeypatch):
    from app.modules.travel_ops.intake import stream

    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)

    def boom(self, conn, state):
        raise RuntimeError("내용 이벤트 장애")

    monkeypatch.setattr(stream.Feed, "poll", boom)
    names = [n for n, _ in _events(client.get(f"/v1/web/trip-intakes/{view['intake_id']}/events", headers=headers).text)]
    assert names == ["accepted", "result"]                 # 단계 이벤트는 끝까지 나간다


def test_content_events_are_made_while_reading_not_at_the_end(rv):
    """읽는 동안 값이 **바로바로** 적힌다 — 규칙으로 읽은 줄 → 날짜 → 이름이 특정된 장소가 하나씩 → 모호한 장소는 앞뒤가 다 찾아진 뒤."""
    from datetime import date

    from app.modules.travel_ops.intake.pipeline import read_source

    tour, kakao = Tour(), Kakao()
    batches: list[list[dict]] = []
    rows = read_source(PLAN, tour=tour, kakao=kakao, our_places=[], today=date(2026, 10, 3), on_rows=batches.append)
    flat = [r for batch in batches for r in batch]
    assert len(flat) == len(rows) and {id(r) for r in flat} == {id(r) for r in rows}      # 한 줄도 두 번 알리지 않고 빠짐도 없다
    first_fields = [r["field"] for r in batches[0]]
    assert "items[0].starts_at" in first_fields and not any(f.endswith(".place") for f in first_fields)
    place_batches = [[r["field"] for r in b] for b in batches if any(r["field"].endswith(".place") for r in b)]
    assert len(place_batches) == 4                                                          # 장소가 하나씩 찾아질 때마다 한 묶음
    assert place_batches[0] == ["items[0].place"]                                           # 이름이 특정된 경복궁이 먼저
    assert ["items[1].place"] in place_batches                                              # 모호한 올리브영은 마지막에
    assert place_batches[-1] == ["items[1].place"]
