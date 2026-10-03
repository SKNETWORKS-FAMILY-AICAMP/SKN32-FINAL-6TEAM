# -*- coding: utf-8 -*-
"""이름 없이 **종류 + 지역만** 적은 줄(「성수 예약 식당」) — 가게로 찾지 않고, 지역 둘레의 같은 종류만 권하고, 예약한 일정은 안 바꾼다. `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]`

☆왜: 계획 글의 한 줄 「13:00 성수 예약 식당 · 예약 있음」을 서버가 **가게 이름**으로만 봐서 세 가지가 한꺼번에 틀렸다(실서버 실측).
  ①이름을 글자 줄여 가며 찾다 실패 ②종류를 활동으로 읽고 후보를 앞뒤 일정의 한가운데(동대문 근처)에서 찾아 활동 「랩포터리」가 권해짐 ③예약했다고 읽고도 검사 줄 · 후보 · 자동 추천에 안 써서
  예약한 식당을 다른 곳으로 바꾸자고 함. 같은 계획의 「호텔 조식」 · 「성수동 쇼핑」 · 「서울역 인근 저녁 식당」도 같은 뿌리로 틀렸다.

★지키려는 것
 ①이름 없는 줄은 **가게 이름으로 찾지 않는다**(관광공사 · 카카오에 그 문구를 묻지 않는다) — 장소 상태 `needs_choice`(예약 모름 · 없음) · `needs_name`(예약 있음), 일정 종류는 식당 · 끼니 말이면 식사
 ②**후보 · 검색 결과의 종류는 일정의 종류와 같다** — 다른 종류로 채우지 않는다(맞는 것이 없으면 빈 목록 + `no_same_kind`)
 ③후보의 중심은 **줄에 적힌 지역**이다(성수 식당은 성수에서, 앞뒤 일정의 한가운데가 아니라)
 ④예약했다고 적힌 줄은 후보를 권하지 않고(`booked_needs_name`) 전체 자동 추천이 **바꾸지 않는다**(`kept: booked`) · 검사 줄에 `booking` 행이 있다
 ⑤고객이 고른 곳 문장은 어디서 찾았는지를 쓴다 · 후보 · 검색 · 현재 장소에 종류 이름(`category`)이 있다

★이 시험의 지명 사전은 시험이 정한 작은 사전이다(실제 DB 의 허브 · 동이 아니다 — 환경에 따라 값이 달라 시험이 흔들리지 않게). 관광공사 목록 · 요식 원장 장소는 시험이 이 테넌트에 넣는다.

재현:

    python -m pytest tests/e2e/test_intake_nameless_lines.py -v
"""
from __future__ import annotations

from uuid import UUID

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.intake import areas as areas_module
from app.modules.travel_ops.intake import pipeline, stream
from app.modules.travel_ops.intake.areas import AreaIndex

from .test_intake_review import OPEN_ALL, _catalog, _client, _edit, _field, _hours, _item, _key, _row, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

ROWS = [("hub", "성수", 37.5449, 127.0512), ("hub", "서울역", 37.5569, 126.9749), ("dong", "성수동", 37.5440, 127.0560),
        ("district", "성동구", 37.5630, 127.0370)]

PLAN = ("2026-10-15\n"
        "09:00 호텔 조식\n"
        "11:00 성수동 쇼핑\n"
        "13:00 성수 예약 식당 · 예약 있음\n"
        "15:00 성수 식당\n"
        "16:30 경복궁 · 예약 있음\n"
        "18:00 서울역 인근 저녁 식당")

#: 성수 쪽 가게들(우리 목록) — 같은 종류만 후보로 나와야 한다. 동대문 쪽 가게는 지역 밖이다
SHOPS_SEONGSU = [("910001", "성수소품가게", 37.5445, 127.0555), ("910002", "성수편집숍", 37.5450, 127.0540),
                 ("910003", "성수기념품점", 37.5438, 127.0570)]
LEDGER_SEONGSU = [("성수가든", 37.5452, 127.0510), ("성수국수", 37.5447, 127.0525), ("성수스시", 37.5460, 127.0500)]
FAR_DONGDAEMUN = ("동대문한식", 37.5710, 127.0090)
SEONGSU_ADDRESS = "서울특별시 성동구 성수이로 1 (성수동2가)"


@pytest.fixture()
def seongsu(rv, monkeypatch):  # noqa: F811
    """성수 둘레의 관광공사 목록 · 요식 원장 장소를 넣고, 지명 사전을 시험의 작은 사전으로 바꾼다."""
    monkeypatch.setattr(pipeline, "areas_for", lambda conn, tenant_id, terms=None: AreaIndex.from_rows(ROWS))
    areas_module.reset()
    for cid, title, lat, lon in SHOPS_SEONGSU:
        _catalog(rv, cid, "38", title, lat, lon, SEONGSU_ADDRESS)
    _catalog(rv, "910009", "38", "동대문랩", 37.5712, 127.0092, "서울특별시 종로구 종로 1")        # 지역 밖 쇼핑
    _catalog(rv, "910010", "39", "성수식당카탈로그", 37.5446, 127.0550, SEONGSU_ADDRESS)           # 같은 지역의 음식점 — 쇼핑 줄에는 안 나와야 한다
    _catalog(rv, "910011", "12", "성수서울숲", 37.5447, 127.0450, SEONGSU_ADDRESS)                 # 관광지 — 쇼핑 줄에는 안 나와야 한다(분류가 다르다)
    _hours(rv, "126508", OPEN_ALL)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for name, lat, lon in [*LEDGER_SEONGSU, FAR_DONGDAEMUN]:
            cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) "
                        "VALUES (%s,%s,'dining',%s,%s,'dining_ledger','{\"source\": \"dining_ledger\"}')", (rv["tenant"], name, lat, lon))
    yield rv
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM places WHERE tenant_id=%s AND source_name='dining_ledger'", (rv["tenant"],))
    areas_module.reset()


def _view(seongsu_env):
    client, tour, kakao = _client()
    headers = _key(client)
    return client, headers, tour, kakao, _send(client, headers, PLAN)


def _candidates(client, headers, view, item):
    return client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={item['source_id']}&index={item['index']}"
                      f"&revision={view['revision']}", headers=headers).json()


def _search(client, headers, view, item, q):
    return client.get(f"/v1/web/trip-intakes/{view['intake_id']}/place-search?source_id={item['source_id']}&index={item['index']}"
                      f"&revision={view['revision']}&q={q}", headers=headers).json()


def test_a_line_with_only_a_kind_and_an_area_is_never_looked_up_as_a_shop_name(seongsu):
    client, headers, tour, kakao, view = _view(seongsu)
    asked = [str(q) for q in tour.asked] + [str(q[0] if isinstance(q, tuple) else q) for q in kakao.asked]
    assert not any(word in q for q in asked for word in ("식당", "쇼핑", "호텔", "성수")), asked              # ★그 문구를 바깥에 묻지 않았다
    items = {i["title"]: i for i in view["review"]["items"]}
    hotel, shop, booked, plain, palace, station = (items["호텔"], items["성수동 쇼핑"], items["성수 예약 식당"], items["성수 식당"],
                                                  items["경복궁"], items["서울역 인근 저녁 식당"])
    # ①장소는 비어 있고 상태가 새 값이다 — 가게를 지어내지 않는다
    assert [i["place"] for i in (hotel, shop, booked, plain, station)] == [None] * 5
    assert [i["place_state"] for i in (hotel, shop, booked, plain, station)] == [
        "needs_choice", "needs_choice", "needs_name", "needs_choice", "needs_choice"]
    assert palace["place_state"] == "found"                                                                 # 이름이 있는 줄은 지금 그대로
    # ②일정 종류 — 식당 · 끼니 말은 식사, 쇼핑은 활동
    assert [i["kind"] for i in (hotel, shop, booked, plain, station)] == ["dining", "activity", "dining", "dining", "dining"]
    # ③읽힌 조각
    assert shop["parts"]["label"] == "쇼핑" and shop["parts"]["content_type"] == "38" and shop["parts"]["area"]["name"] == "성수동"
    assert station["parts"]["area"]["name"] == "서울역" and station["parts"]["meal"] == "저녁" and station["parts"]["near"] is True
    assert booked["parts"]["area"]["name"] == "성수" and hotel["parts"]["area"] is None and palace["parts"] is None
    # ④예약
    assert booked["booked"] is True and plain["booked"] is None and palace["booked"] is True
    assert (_row(booked, "booking")["result"], _row(plain, "booking")["result"], _row(palace, "booking")["result"]) == ("warn", "unknown", "ok")
    assert "예약하신 식당의 이름이 적혀 있지 않아요" in _row(booked, "place")["text"]
    assert "성수 지역 식당의 이름이 적혀 있지 않아요" in _row(plain, "place")["text"] and _row(plain, "place")["result"] == "bad"
    assert "booking" not in [r["row"] for r in shop["rows"]]                                                  # 예약 말이 없는 활동 줄에는 예약 행이 없다
    assert view["review"]["ready"] is False                                                                    # 고르기 전에는 등록할 수 없다


def test_candidates_are_the_same_kind_around_the_area_named_in_the_line(seongsu):
    client, headers, _, _, view = _view(seongsu)
    shop = _item(view, "성수동 쇼핑")
    got = _candidates(client, headers, view, shop)
    names = {c["place"]["name"] for c in got["candidates"]}
    assert names and names <= {n for _, n, _, _ in SHOPS_SEONGSU}, names                                      # ★성수 쇼핑만 — 동대문랩 · 음식점 · 관광지는 안 나온다
    assert all(c["place"]["kind"] == "activity" and c["place"]["category"] == "쇼핑" for c in got["candidates"])
    assert got["reference"]["area"] == "성수동" and all(c["reference"] == "성수동" and c["distance_m"] < 1200 for c in got["candidates"])
    # 식당 줄 — 요식 원장의 성수 식당만(동대문 식당 · 카탈로그 음식점이 아니라)
    plain = _item(view, "성수 식당")
    dining = _candidates(client, headers, view, plain)
    dnames = {c["place"]["name"] for c in dining["candidates"]}
    assert dnames and dnames <= {n for n, _, _ in LEDGER_SEONGSU}, dnames
    assert all(c["place"]["kind"] == "dining" and c["place"]["category"].startswith("음식점") for c in dining["candidates"])
    assert dining["reference"]["area"] == "성수" and all(c["distance_m"] < 1500 for c in dining["candidates"])    # 지역 중심에서 반경 안
    # 지역 둘레에 같은 종류가 하나도 없으면 다른 곳으로 채우지 않고 이유를 말한다(서울역 둘레에는 시험이 넣은 식당이 없다)
    station = _candidates(client, headers, view, _item(view, "서울역 인근 저녁 식당"))
    assert station["candidates"] == [] and "no_candidates_in_area" in station["notes"] and station["reference"]["area"] == "서울역"


def test_a_booked_nameless_line_gets_no_candidates_only_the_question_for_a_name(seongsu):
    client, headers, _, _, view = _view(seongsu)
    booked = _item(view, "성수 예약 식당")
    got = _candidates(client, headers, view, booked)
    assert got["candidates"] == [] and "booked_needs_name" in got["notes"]
    # 이름을 알려 주는 길(검색)은 그대로 열려 있고, 같은 종류만 나온다
    found = _search(client, headers, view, booked, "성수")
    names = {r["place"]["name"] for r in found["results"]}
    assert names & {"성수가든", "성수국수", "성수스시", "성수식당카탈로그"} and "성수서울숲" not in names and "성수소품가게" not in names
    assert all(r["place"]["kind"] == "dining" for r in found["results"])


def test_search_never_mixes_another_kind_in_and_says_why_when_nothing_of_the_kind_matches(seongsu):
    client, headers, _, _, view = _view(seongsu)
    shop = _item(view, "성수동 쇼핑")
    found = _search(client, headers, view, shop, "성수")
    assert found["results"] and all(r["place"]["kind"] == "activity" for r in found["results"])
    names = {r["place"]["name"] for r in found["results"]}
    assert "성수소품가게" in names and "성수가든" not in names and "성수식당카탈로그" not in names
    empty = _search(client, headers, view, shop, "성수가든")                       # 식당만 맞는 검색어 — 쇼핑 자리에 식당으로 채우지 않는다
    assert empty["results"] == [] and "no_same_kind" in empty["notes"]


def test_auto_fix_never_changes_a_booked_item_and_fills_the_others_with_the_same_kind(seongsu):
    client, headers, _, _, view = _view(seongsu)
    booked, palace = _item(view, "성수 예약 식당"), _item(view, "경복궁")
    response = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers, json={"revision": view["revision"]})
    assert response.status_code == 200, response.text
    body = response.json()
    reasons = {k["id"]: k["reason"] for k in body["kept"]}
    assert reasons[booked["id"]] == "booked"                                                                   # ★예약한 일정은 그대로 두고 이유를 말한다
    changed = {c["id"]: c for c in body["changed"]}
    assert booked["id"] not in changed and palace["id"] not in changed
    assert changed, body["kept"]                                                                              # 고를 수 있는 줄은 실제로 채웠다
    after = {i["id"]: i for i in body["view"]["review"]["items"]}
    assert after[booked["id"]]["place"] is None and after[booked["id"]]["place_state"] == "needs_name"       # 아무것도 바뀌지 않았다
    allowed = {"activity": {n for _, n, _, _ in SHOPS_SEONGSU}, "dining": {n for n, _, _ in LEDGER_SEONGSU}}
    for change in changed.values():
        item = after[change["id"]]
        assert item["kind"] in allowed and change["to"]["place"]["name"] in allowed[item["kind"]], change    # ★같은 종류 · 같은 지역의 곳으로만


def test_the_customers_pick_sentence_says_where_it_was_found_and_keeps_the_kind_name(seongsu):
    client, headers, _, _, view = _view(seongsu)
    shop = _item(view, "성수동 쇼핑")
    pick = _candidates(client, headers, view, shop)["candidates"][0]["place"]
    done = _edit(client, headers, view, _field(shop, "place", pick))
    chosen = _item(done["view"] if "view" in done else client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json(), shop["title"])
    assert chosen["place_state"] == "customer" and chosen["place"]["name"] == pick["name"] and chosen["place"]["category"] == "쇼핑"
    assert _row(chosen, "place")["text"] == "직접 고른 곳이에요 · 관광공사에서 찾았어요"                       # 「직접 고른 곳이에요 · 직접 고른 곳」이 아니다
    assert chosen["parts"] is None                                                                           # 고른 뒤에는 이름 없는 줄이 아니다


def test_the_live_feed_carries_the_new_item_fields(seongsu):
    client, headers, _, _, view = _view(seongsu)
    booked = _item(view, "성수 예약 식당")
    feed = stream.Feed(seongsu["tenant"], seongsu["customer"], UUID(view["intake_id"]))
    with get_connection() as conn:
        events = feed.poll(conn, {"status": "review", "stage": "review", "revision": view["revision"]})
    body = next(b for n, b in events if n == "item" and b["id"] == booked["id"])
    assert body["place_state"] == "needs_name" and body["booked"] is True and body["parts"]["area"]["name"] == "성수"
    checks = [b for n, b in events if n == "check" and b["item"] == booked["id"]]
    assert {c["row"] for c in checks} == {"place", "booking", "hours", "closed"} | ({"time"} if any(c["row"] == "time" for c in checks) else set())
