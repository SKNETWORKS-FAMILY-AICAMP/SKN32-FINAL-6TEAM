# -*- coding: utf-8 -*-
"""`POST /v1/trips/plan` — 요청 → 초안 → **판정 통과** → 등록을 HTTP 로 흘린다.

★★이 경로는 **v11 §4-A 를 뒤집는다**(「계획 생성은 우리 일이 아니다」). 사용자 지시로 만든
  것이고, 계획서는 읽기 전용이라 고치지 않았다 — 리포트
  `wiki/records/reports/2026-09-22_2205_일정생성기_v11-4A를_뒤집는다.md` 에 적었다.

★시험이 보는 것 여섯:
    ① 초안이 **등록이 쓰는 그 판정기**를 통과하는가
    ② 선호가 반영되는가(실내 위주 → 실내가 더 많다 · 싫다고 한 곳은 안 들어간다)
    ③ 후보가 모자라면 **거절**하는가(짧게 줄여서 내주지 않는다)
    ④ 모델이 없어도/모델이 죽어도 도는가(그 사실을 결과에 적는가)
    ⑤ 같은 요청을 두 번 보내면 **여행이 하나인가**
    ⑥ 모델이 목록에 없는 값을 내면 **버리는가**(그리고 다 버려졌으면 그렇게 말하는가)

★이 파일은 **자기 테넌트에 자기 장소를 심는다.** `demo` 카탈로그(2,063건)에 기대면 그 표가
  바뀔 때 시험이 같이 흔들린다.
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.itinerary_checks import Part, check_itinerary
from app.modules.travel_ops.trip_api import build_trip_router
from app.presentation import security
from app.presentation.api.app import create_app

START = date(2026, 10, 5)

#: 종로구 안에 모아 둔 시험용 장소. 좌표는 서로 수백 m 이내라 도보 환산이 현실적인 값이 된다.
#: ★**이름을 일부러 갈랐다** — 선호가 없을 때의 규칙 순위는 동률이면 이름순이라, 야외가
#:   앞(ㄱ·ㄴ)·실내가 뒤(ㅎ)로 가게 두어야 「실내 위주」가 순서를 바꾼 것이 보인다.
ACTIVITIES = [
    ("가든 공원", 37.5771, 126.9801, {"district": "종로구", "indoor": False,
                                      "hours": ["09:00", "18:00"], "price_krw": 0}),
    ("고궁 뜰", 37.5758, 126.9768, {"district": "종로구", "indoor": False,
                                    "hours": ["09:00", "18:00"], "price_krw": 3000}),
    ("남산 성곽길", 37.5789, 126.9812, {"district": "종로구", "indoor": False,
                                        "hours": ["09:00", "18:00"]}),
    ("하늘 박물관", 37.5750, 126.9770, {"district": "종로구", "indoor": True,
                                        "hours": ["09:00", "18:00"], "price_krw": 5000}),
    ("학예 전시관", 37.5745, 126.9795, {"district": "종로구", "indoor": True,
                                        "hours": ["09:00", "18:00"], "price_krw": 4000}),
    ("한옥 미술관", 37.5762, 126.9782, {"district": "종로구", "indoor": True,
                                        "hours": ["09:00", "18:00"], "price_krw": 6000}),
]
#: 다섯이다. **넷은 하루 둘 × 이틀에 딱 맞아** 「매운 곳을 뺐다」와 「후보가 모자라다」를
#: 구분하지 못한다 — 하나를 더 둬야 뺀 것이 보인다.
DINING = [
    ("고소한 돈가스집", 37.5748, 126.9792, {"district": "종로구", "indoor": True,
                                            "hours": ["11:00", "21:00"], "price_krw": 11000}),
    ("담백 백반집", 37.5760, 126.9788, {"district": "종로구", "indoor": True,
                                        "hours": ["11:00", "21:00"], "price_krw": 10000}),
    ("매운 마라탕집", 37.5766, 126.9773, {"district": "종로구", "indoor": True,
                                          "hours": ["11:00", "21:00"], "price_krw": 12000}),
    ("순한 국수집", 37.5752, 126.9776, {"district": "종로구", "indoor": True,
                                        "hours": ["11:00", "21:00"], "price_krw": 9000}),
    ("온면 식당", 37.5755, 126.9784, {"district": "종로구", "indoor": True,
                                      "hours": ["11:00", "21:00"], "price_krw": 9500}),
]


class StubChat:
    """모델 흉내 — **줄 번호 순서만** 낸다. 실제 Gemma 확인은 라이브 실행에서 본다."""

    def __init__(self, reorder=None, raises: Exception | None = None) -> None:
        self.reorder, self.raises, self.calls = reorder, raises, 0
        self.seen: list[str] = []

    def json(self, system: str, user: str) -> dict:
        self.calls += 1
        self.seen.append(user)
        if self.raises is not None:
            raise self.raises
        # ★실제 모델(gemma4:12b)은 **줄 번호**를 낸다(실측). 흉내도 번호로 낸다.
        numbers = [line.split(".")[0].strip() for line in user.splitlines()
                   if line[:1].isdigit() and ". " in line]
        kinds = [line.split("| ")[0].split(". ")[1].strip() for line in user.splitlines()
                 if line[:1].isdigit() and ". " in line]
        acts = [n for n, kind in zip(numbers, kinds) if kind == "activity"]
        dine = [n for n, kind in zip(numbers, kinds) if kind == "dining"]
        if self.reorder is not None:
            return self.reorder(acts, dine)
        return {"activities": acts, "dining": dine}

    @staticmethod
    def _keys(kind: str) -> set[str]:
        return StubChat.KEYS[kind]

    KEYS: dict[str, set[str]] = {"activity": set(), "dining": set()}


@pytest.fixture()
def api(monkeypatch):
    original = settings_module.get_settings()
    tenant = "planner_" + uuid4().hex[:12]
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)
    customer = uuid4()
    keys = {"activity": set(), "dining": set()}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "planner"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)",
                    (customer, tenant, "planner-customer"))
        for kind, rows in (("activity", ACTIVITIES), ("dining", DINING)):
            for name, lat, lon, attributes in rows:
                cur.execute(
                    "INSERT INTO places (tenant_id,name,kind,latitude,longitude,attributes) "
                    "VALUES (%s,%s,%s,%s,%s,%s) RETURNING place_id",
                    (tenant, name, kind, lat, lon, __import__("json").dumps(attributes,
                                                                            ensure_ascii=False)))
                keys[kind].add(f"db_{cur.fetchone()[0]}")
    StubChat.KEYS = keys

    def build(chat=None, tour=None):
        # ★라우터가 모델을 **처음 쓸 때 한 번만** 만들어 캐시한다(`_lazy`). 그래서 모델을 바꾸려면
        #   앱을 새로 만든다 — 한 앱에서 모델을 갈아 끼우는 시험은 첫 값만 보게 된다(실측으로 겪음).
        return TestClient(create_app(
            classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
            domain_routers=[build_trip_router(
                check_factory=lambda: (lambda **_k: {"verdict": "clear"}),
                chat_factory=(lambda: chat) if chat is not None else None,
                place_factory=(lambda: tour) if tour is not None else None)]))

    client = build()

    def auth(scope):
        return {"Authorization": "Bearer " + security._development_key(scope, original.secret_key)}

    def ask(chat=None, tour=None, **override):
        body = {"request_id": override.pop("request_id", "plan-1"), "customer_id": str(customer),
                "city": "서울", "start_date": START.isoformat(), "days": 2, "party_size": 2,
                "locale": "ko"}
        body.update(override)
        target = client if (chat is None and tour is None) else build(chat, tour)
        return target.post("/v1/trips/plan", json=body, headers=auth("trip:write"))

    yield {"client": client, "auth": auth, "ask": ask, "tenant": tenant, "customer": customer,
           "keys": keys}

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for sql in ("DELETE FROM place_catalog WHERE tenant_id=%s",
                    "DELETE FROM itinerary_items WHERE tenant_id=%s",
                    "DELETE FROM itinerary_versions WHERE tenant_id=%s",
                    "DELETE FROM outbox WHERE tenant_id=%s", "DELETE FROM trips WHERE tenant_id=%s",
                    "DELETE FROM places WHERE tenant_id=%s",
                    "DELETE FROM customers WHERE tenant_id=%s",
                    "DELETE FROM tenants WHERE tenant_id=%s"):
            cur.execute(sql, (tenant,))


def _parts(draft: dict) -> list[Part]:
    from datetime import datetime

    places = {place["key"]: place for place in draft["places"]}
    return [Part(seq=item["seq"], kind=item["kind"], title=item["title"],
                 starts_at=datetime.fromisoformat(item["starts_at"]),
                 ends_at=datetime.fromisoformat(item["ends_at"]) if item["ends_at"] else None,
                 place={"name": places[item["place"]]["name"],
                        "attributes": places[item["place"]]["attributes"]},
                 route=None, detail=item["detail"])
            for item in draft["items"]]


def _indoor_count(draft: dict) -> int:
    places = {place["key"]: place for place in draft["places"]}
    return sum(1 for item in draft["items"]
               if places[item["place"]]["attributes"].get("indoor") is True)


# ── ① 초안은 등록이 쓰는 판정기를 통과한다 ─────────────────────────
def test_the_draft_passes_the_very_check_registration_runs(api):
    response = api["ask"]()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "drafted" and body["checks"]["violations"] == []
    draft = body["draft"]
    assert len(draft["items"]) == 2 * (2 + 2)                      # 2일 × (활동 2 + 식사 2)
    # ★시험이 **직접** 같은 판정기를 돌린다 — 생성기가 스스로 「통과」라고 말한 것을 믿지 않는다.
    assert check_itinerary(_parts(draft), constraints=draft["constraints"],
                           party_size=draft["party_size"]) == []
    # ★등록 계약이 받는 모양 그대로다 — 그대로 `POST /v1/trips` 에 넣으면 201 이다.
    created = api["client"].post("/v1/trips", headers=api["auth"]("trip:write"),
                                 json={"request_id": "hand-1",
                                       "customer_id": str(api["customer"]), **draft})
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 1


def test_a_violation_in_the_first_draft_is_repaired_and_rechecked(api):
    """★**판정 루프가 실제로 돈다.** 식당 전부에 12:00~13:00 브레이크타임을 넣으면 점심 칸이
    반드시 걸린다 — 고친 내역과 「다시 판정해서 깨끗하다」가 같이 나와야 한다.

    ☆이 시험이 없으면 판정 루프를 통째로 들어내도 시험이 빨개지지 않는다(실측으로 확인했다 —
      초안이 원래 깨끗해서 루프가 한 번도 안 돌고 있었다).
    """
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET attributes = attributes || "
                    "'{\"break\": [\"12:00\", \"13:00\"]}'::jsonb "
                    "WHERE tenant_id=%s AND kind='dining'", (api["tenant"],))
    body = api["ask"](request_id="p-break").json()
    assert body["checks"]["rounds"] >= 1, body["checks"]
    assert any("break_time" in line for line in body["checks"]["repairs"]), body["checks"]
    assert body["checks"]["violations"] == []
    assert check_itinerary(_parts(body["draft"]), constraints=body["draft"]["constraints"],
                           party_size=2) == []
    lunches = [item for item in body["draft"]["items"] if item["kind"] == "dining"]
    assert lunches[0]["starts_at"][11:16] == "13:00"          # 브레이크타임 뒤로 옮겼다


def test_a_draft_that_cannot_be_repaired_is_refused_with_what_we_tried(api):
    """★못 고치면 **거절**한다 — 위반을 달고 내주지 않는다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        # 점심·저녁 시간대를 통째로 덮는 브레이크타임. 어떤 식당으로 바꿔도 걸린다.
        cur.execute("UPDATE places SET attributes = attributes || "
                    "'{\"break\": [\"00:00\", \"23:59\"]}'::jsonb "
                    "WHERE tenant_id=%s AND kind='dining'", (api["tenant"],))
    response = api["ask"](request_id="p-hopeless")
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "plan_infeasible"
    assert error["violations"] and all(v["reason"] and v["remedy"] for v in error["violations"])
    assert error["repair_rounds"] >= 1 and error["remedy"]


def test_a_day_pushed_past_its_end_is_refused(api):
    """★`check_itinerary` 는 **하루가 몇 시에 끝나야 하는지 모른다** — 그건 우리 상품의 약속이지
    일정의 성립 조건이 아니다. 고치다 밀려 한밤중이 된 하루를 그냥 내주지 않는다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        # 모든 곳이 자정까지 열지만(→ `after_closing` 은 안 걸린다) 식당은 낮 내내 브레이크타임이라
        # 점심을 21:00 뒤로 밀 수밖에 없고, 그 뒤 항목이 전부 따라 넘어간다.
        cur.execute("UPDATE places SET attributes = attributes || "
                    "'{\"hours\": [\"09:00\", \"23:59\"]}'::jsonb WHERE tenant_id=%s",
                    (api["tenant"],))
        cur.execute("UPDATE places SET attributes = attributes || "
                    "'{\"break\": [\"11:00\", \"21:00\"]}'::jsonb "
                    "WHERE tenant_id=%s AND kind='dining'", (api["tenant"],))
    response = api["ask"](request_id="p-latenight")
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "day_overflow", error
    assert error["items"] and error["remedy"]


def test_registering_in_one_call_goes_through_the_same_door(api):
    body = api["ask"](request_id="plan-reg", register=True).json()
    assert body["status"] == "registered"
    assert body["trip"]["version"] == 1 and body["trip"]["plan_url"]
    assert len(body["trip"]["items"]) == len(body["draft"]["items"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 1


# ── ② 선호 ────────────────────────────────────────────────────────
def test_indoor_preference_puts_more_indoor_places_in_the_draft(api):
    plain = api["ask"](request_id="p-plain", preferences="").json()["draft"]
    indoor = api["ask"](request_id="p-indoor",
                        preferences="실내 위주로 다니고 싶어요").json()["draft"]
    # 활동 넷 중 실내가 몇인가. ★식사는 넷 다 실내라 분모를 활동으로 잡는다.
    def indoor_activities(draft):
        places = {p["key"]: p for p in draft["places"]}
        return sum(1 for item in draft["items"] if item["kind"] == "activity"
                   and places[item["place"]]["attributes"].get("indoor") is True)

    assert indoor_activities(indoor) == 3          # 실내 활동이 셋뿐이라 3/4 가 상한이다
    assert indoor_activities(plain) == 1           # 선호가 없으면 규칙 순위(이름순)대로다
    assert _indoor_count(indoor) > _indoor_count(plain)


def test_a_place_the_customer_dislikes_is_left_out(api):
    body = api["ask"](request_id="p-spicy", preferences="매운 음식 싫어요").json()
    titles = {item["title"] for item in body["draft"]["items"]}
    assert "매운 마라탕집" not in titles
    assert body["planner"]["preference"]["avoid"], body["planner"]["preference"]


def test_with_a_child_we_say_what_we_dropped_and_why(api):
    body = api["ask"](request_id="p-kid", preferences="아이 동반이에요").json()
    assert body["planner"]["preference"]["with_children"] is True
    assert "술집" in body["planner"]["preference"]["avoid"]


# ── ③ 후보가 모자라면 거절한다 ────────────────────────────────────
def test_too_few_candidates_are_refused_with_numbers_not_shrunk(api):
    response = api["ask"](request_id="p-many", days=4)      # 활동 8곳이 필요한데 6곳뿐
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "not_enough_candidates"
    assert error["need"]["activity"] == 8 and error["have"]["activity"] == 6
    assert error["remedy"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 0                      # ★거절은 아무것도 남기지 않는다


def test_a_city_we_do_not_cover_is_refused(api):
    response = api["ask"](request_id="p-busan", city="부산")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "city_not_supported"


# ── ④ 모델 ────────────────────────────────────────────────────────
def test_without_a_model_it_still_drafts_and_says_so(api):
    body = api["ask"](request_id="p-nollm").json()
    assert body["planner"]["mode"] == "rules"
    assert body["planner"]["note"] == "모델을 쓰지 않았다"
    assert body["checks"]["violations"] == []


def test_with_a_model_the_order_comes_from_the_model(api):
    """★모델이 순서를 뒤집으면 초안 순서도 뒤집힌다 — 그런데 **시각은 그대로**다.
    시각은 서버가 채우기 때문이다(모델은 id 만 낸다)."""
    ruled = api["ask"](request_id="p-ruled").json()["draft"]
    chat = StubChat(reorder=lambda acts, dine: {"activities": list(reversed(acts)),
                                                "dining": list(reversed(dine))})
    body = api["ask"](request_id="p-llm", chat=chat).json()
    assert body["planner"]["mode"] == "llm" and chat.calls == 2      # 하루에 한 번씩
    assert "Candidates (use the number" in chat.seen[0]
    assert body["checks"]["violations"] == []
    flipped = body["draft"]
    assert [item["title"] for item in flipped["items"]] != \
        [item["title"] for item in ruled["items"]]                   # 순서가 달라졌다
    assert [item["starts_at"] for item in flipped["items"]] == \
        [item["starts_at"] for item in ruled["items"]]               # ★시각은 우리가 채운 그대로


def test_a_model_that_fails_does_not_stop_us_and_the_note_says_why(api):
    body = api["ask"](request_id="p-dead", chat=StubChat(raises=RuntimeError("ollama down"))).json()
    assert body["planner"]["mode"] == "rules"
    assert "모델을 부르지 못해" in body["planner"]["note"] and "ollama down" in body["planner"]["note"]
    assert body["checks"]["violations"] == []


# ── ⑥ 모델이 없는 id 를 내면 버린다 ───────────────────────────────
def test_ids_the_model_invents_are_dropped(api):
    junk = StubChat(reorder=lambda acts, dine: {"activities": ["999", "경복궁"] + acts[:1],
                                                "dining": ["없는_식당"]})
    body = api["ask"](request_id="p-junk", chat=junk).json()
    titles = {item["title"] for item in body["draft"]["items"]}
    assert "경복궁" not in titles and "없는_식당" not in titles
    assert len(body["draft"]["items"]) == 8 and body["checks"]["violations"] == []


def test_a_model_whose_answers_are_all_unusable_is_reported_as_rules(api):
    """★★모델을 불렀는데 **쓴 것이 하나도 없으면** `mode` 는 `rules` 다.

    ☆실제로 겪었다 — gemma4:12b 가 우리 후보 키 대신 줄 번호를 내서 모든 값이 버려졌는데
      결과에는 `mode="llm"` 이라고 적혀 있었다. 신호 없는 축소는 폴백이다(`RULE.md` §3.2).
    """
    useless = StubChat(reorder=lambda acts, dine: {"activities": ["없음"], "dining": ["없음"]})
    body = api["ask"](request_id="p-useless", chat=useless).json()
    assert body["planner"]["mode"] == "rules"
    assert body["planner"]["from_model"] == 0 and body["planner"]["model_calls"] == 2
    assert "하나도 후보 목록에 없어" in body["planner"]["note"]
    assert body["checks"]["violations"] == []       # ★그래도 초안은 낸다


# ── ⑤ 멱등 ────────────────────────────────────────────────────────
def test_planning_the_same_request_twice_makes_one_trip(api):
    first = api["ask"](request_id="same-1", register=True).json()
    again = api["ask"](request_id="same-1", register=True).json()
    assert first["status"] == "registered" and again["status"] == "duplicate"
    assert again["created"] is False
    assert again["trip"]["trip_id"] == first["trip"]["trip_id"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice'",
                    (api["tenant"],))
        assert cur.fetchone()[0] == 1              # ★두 번째 요청은 통지를 또 내보내지 않는다


def test_a_draft_only_request_writes_nothing(api):
    api["ask"](request_id="dry-1")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 0


# ── 바깥 API 호출 수 ──────────────────────────────────────────────
class StubTour:
    """TourAPI 흉내. ★**몇 번 불렀는지** 센다 — 하루 한도가 있는 소스다."""

    name = "tour_api"

    def __init__(self) -> None:
        self.calls = 0

    def area_page(self, area_code: str, *, page: int, rows: int) -> dict:
        self.calls += 1
        if page > 1:
            return {"total_count": 2, "items": []}
        return {"total_count": 2, "items": [
            {"content_id": "900001", "content_type_id": "14", "title": "받아온 미술관",
             "address": "서울특별시 종로구 아무길 1", "latitude": 37.5755, "longitude": 126.9779},
            {"content_id": "900002", "content_type_id": "39", "title": "받아온 식당",
             "address": "서울특별시 종로구 아무길 2", "latitude": 37.5757, "longitude": 126.9781}]}


def test_tour_api_is_called_only_when_the_catalog_is_empty(api):
    """★바깥 소스는 **캐시가 비었을 때만** 나간다. 부른 횟수를 결과가 센다."""
    tour = StubTour()
    body = api["ask"](request_id="p-tour", tour=tour).json()
    assert tour.calls == 1 and body["calls"]["tour_api"] == 1
    assert body["candidates"]["by_source"].get("tour_api", 0) >= 0     # 순위에 따라 뽑힐 수도 아닐 수도
    assert body["candidates"]["pool"] == len(ACTIVITIES) + len(DINING) + 2

    # ★카탈로그에 한 행이라도 있으면 바깥에 나가지 않는다.
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO place_catalog (tenant_id,source,content_id,content_type_id,area_code,"
            "title,address,latitude,longitude) VALUES (%s,'tour_api','800001','14','1',"
            "'캐시된 미술관','서울특별시 종로구 캐시길 1',37.5759,126.9787)", (api["tenant"],))
    cached = StubTour()
    again = api["ask"](request_id="p-tour-2", tour=cached).json()
    assert cached.calls == 0 and again["calls"]["tour_api"] == 0
    assert "place_catalog" in again["candidates"]["by_source"] or \
        again["candidates"]["pool"] == len(ACTIVITIES) + len(DINING) + 1


# ── scope ─────────────────────────────────────────────────────────
def test_planning_needs_the_write_scope(api):
    denied = api["client"].post("/v1/trips/plan", headers=api["auth"]("trip:read"),
                                json={"request_id": "p-scope", "customer_id": str(api["customer"]),
                                      "start_date": START.isoformat(), "days": 1, "party_size": 2})
    assert denied.status_code == 403

# ── 요청을 규정에 붙인 결과가 응답에 실린다 `[2026-09-22]` ─────────
def test_the_answer_says_whether_it_read_the_rules_at_all(api):
    """★이 테넌트에는 코퍼스가 없다 — **0건이라고 적혀 나와야** 한다.

    조용히 빠지면 부르는 쪽은 규정을 보고 짠 초안과 못 보고 짠 초안을 구별할 수 없다.
    실제 코퍼스가 있는 테넌트에서 무엇이 오는지는
    `tests/integration/rag/test_travel_corpus_retrieval.py` 가 본다.
    """
    body = api["ask"](preferences="비 오면 어쩌죠").json()
    rag = body["rag"]
    assert rag["hits"] == 0 and rag["evidence"] == []
    assert "0건" in rag["note"] and "규정을 보지 않고 짰다" in rag["note"]
    assert rag["query"] == "비 오면 어쩌죠"
    assert all(scope.startswith("travel_") for scope in rag["scopes"]), rag["scopes"]
    # ★규정을 0건 읽었어도 초안은 나온다 — 규정은 초안의 성립 조건이 아니다
    assert body["checks"]["violations"] == [] and len(body["draft"]["items"]) == 8


def test_with_no_rules_found_the_prompt_carries_no_policy_section(api):
    """★0건인데 규정 절을 붙이면 모델은 **빈 규정**을 규정으로 읽는다."""
    chat = StubChat()
    assert api["ask"](chat=chat, preferences="아이 동반", request_id="plan-grounded").status_code == 200
    assert chat.calls > 0
    assert all("Operator policy" not in seen for seen in chat.seen)
    assert any("아이 동반" in seen for seen in chat.seen)      # 고객의 말은 그대로 간다

def test_rules_that_were_found_reach_both_the_model_and_the_answer(api, monkeypatch):
    """★규정을 찾았을 때 **모델 프롬프트**와 **응답의 근거** 둘 다에 실리는지 본다.

    ★이 시험이 있어야 `plan_trip` 이 규정을 모델에게 넘기는 줄을 지웠을 때 빨개진다 —
      0건 경로만 보면 지워도 초록이다.
    """
    from app.infrastructure.rag import retriever

    class Chunk:
        document_id, chunk_no, score, scope = "t_doc_12", 4, 0.77, "travel_access"
        content = "동반자가 있으면 이동 여유를 더 둔다."

        @property
        def source_id(self):
            return f"{self.document_id}#c{self.chunk_no}"

    monkeypatch.setattr(retriever, "search_policy", lambda **_: [Chunk()])
    chat = StubChat()
    body = api["ask"](chat=chat, preferences="아이 동반", request_id="plan-with-rules").json()

    assert body["rag"]["hits"] == 1
    assert body["rag"]["evidence"][0]["source_id"] == "t_doc_12#c4"
    assert body["rag"]["evidence"][0]["source_type"] == "policy"
    assert any("동반자가 있으면 이동 여유를 더 둔다." in seen for seen in chat.seen),         "규정을 찾았는데 모델에게 안 보였다"
    assert any("Operator policy" in seen for seen in chat.seen)
