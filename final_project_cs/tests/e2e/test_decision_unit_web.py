# -*- coding: utf-8 -*-
"""결정 단위 — 웹 채팅이 **여행 상태를 보며** 한 번에 해석하고, 서버가 확인해 실행한다. `[2026-09-29 사용자 지시 · Codex 합의]`

★여기서 해석 모델은 **자동 시험용 고정 규칙**이다(실제 모델 아님) — 받은 입력(일정 목록 · 변경 이력 · 앞 대화)에서 id 를 찾아 고른다.
  그래서 이 시험은 ①서버가 모델에 무엇을 넘기는지(대화 기록 · 변경 id) ②모델이 고른 id 를 서버가 어떻게 확인 · 실행하는지를 본다.
  실제 모델의 정확도는 재생 시험(`tests/live/test_decision_unit_live.py`)이 잰다.
"""
from __future__ import annotations

import re
from datetime import timedelta

import pytest

from app.infrastructure.db.session import get_connection

from .test_web_api import _fresh_limit_cache, _h, _session, _web_body, api  # noqa: F401 — 시험 준비물


class _Decider:
    """해석 모델 흉내 — 문장 → (할 일, 대상 이름 조각, 사실 종류). 대상 id 는 **받은 일정 목록**에서 찾는다."""

    def __init__(self):
        self.prompts: list[str] = []

    @staticmethod
    def _alias(user: str, name: str) -> str:
        for line in user.split("\n"):
            if re.match(r"i\d+ \|", line) and name in line:
                return line.split(" |")[0]
        return "none"

    def structured(self, system, user, schema, *, num_predict=160):
        self.prompts.append(user)
        message = user.rsplit("고객 문장:", 1)[1].strip()
        none = {"target_change": "none", "fact": "none", "minutes": 0, "question": ""}
        if "고장" in message:
            raise RuntimeError("model is down")
        if "알려줘" in message and "성수 점심" in message:
            return {**none, "action": "answer_fact", "target_item": self._alias(user, "성수 점심"), "fact": "detail"}
        if "위치에서 성수 점심" in message:
            return {**none, "action": "answer_fact", "target_item": self._alias(user, "성수 점심"), "fact": "route_here"}
        if "근처 식당" in message:
            return {**none, "action": "answer_fact", "target_item": "none", "fact": "nearby_dining"}
        if "근처 볼거리" in message:
            return {**none, "action": "answer_fact", "target_item": "none", "fact": "nearby_activity"}
        if "예약 표시" in message:
            lunch, dinner = self._alias(user, "성수 점심"), self._alias(user, "· 저녁")
            return {**none, "action": "clarify", "target_item": "none",
                    "choices": [{"action": "answer_fact", "target_item": lunch, "target_change": "none", "fact": "booking"},
                                {"action": "answer_fact", "target_item": dinner, "target_change": "none", "fact": "booking"}]}
        if "그 식당 어딨어" in message:
            return {**none, "action": "answer_fact", "target_item": self._alias(user, "성수 점심"), "fact": "address"}
        if "그 식당 전화번호" in message:
            talk = user.split("직전 대화:", 1)[1].split("화면에서 고른 일정:", 1)[0]
            target = self._alias(user, "성수 점심") if "성수 점심" in talk else "none"
            return {**none, "action": "answer_fact", "target_item": target, "fact": "phone"}
        if "점심 다른 데로 바꿔" in message:
            return {**none, "action": "apply_change", "target_item": self._alias(user, "성수 점심")}
        if "저녁 다른 데로 바꿔" in message:
            return {**none, "action": "apply_change", "target_item": self._alias(user, "· 저녁")}
        if "원래대로" in message:
            changes = re.findall(r"^(c\d+) \|", user, re.M)
            return {**none, "action": "rollback", "target_item": "none", "target_change": changes[-1] if changes else "none"}
        if "바꿔" == message:
            return {**none, "action": "clarify", "target_item": "none", "question": "어떤 일정을 바꿔 드릴까요?"}
        if "없는 번호" in message:
            return {**none, "action": "apply_change", "target_item": "i99"}
        return {**none, "action": "other", "target_item": "none"}


@pytest.fixture()
def decided(api, monkeypatch):
    from fastapi.testclient import TestClient

    from app.domains.travel_ops.components.conversation import trip_messages
    from app.domains.travel_ops.entry.trip_api import build_trip_router
    from app.presentation.api.app import create_app

    from app.domains.travel_ops.modules.web_account import web_guard

    decider = _Decider()
    monkeypatch.setattr(trip_messages, "_decision_mode", lambda chat, tenant=None: "on")
    real = web_guard.values          # ★해석 결과(`decision`)는 개발 모드일 때만 웹에 실린다 — 이 시험은 그 칸을 본다
    monkeypatch.setattr(web_guard, "values", lambda tenant: {**real(tenant), "web.dev_mode": "on"})
    client = TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(classifier_factory=lambda: (lambda m: {"intent": "other",
                                                                                 "issue_code": "other",
                                                                                 "sentiment": "neutral"}),
                                          chat_factory=lambda: decider)]))
    me = _session(api)
    trip = client.post("/v1/web/trips", json=_web_body(api, request_id="du-1"), headers=_h(me["user_key"])).json()
    yield {"client": client, "key": me["user_key"], "trip": trip, "decider": decider}


def _say(decided, text, request_id, **extra):
    response = decided["client"].post(f"/v1/web/trips/{decided['trip']['trip_id']}/messages",
                                      headers=_h(decided["key"]),
                                      json={"request_id": request_id, "message": text,
                                            "at": "2030-01-01T09:00:00+09:00", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_a_place_question_is_answered_from_the_item_the_model_picked(decided):
    body = _say(decided, "성수 점심 식당 알려줘", "du-a")
    assert body["status"] == "answered" and body["decision"]["action"] == "answer_fact", body
    assert "성수 점심" in body["answer"] and "규정" not in body["answer"]
    assert body["classification"] == {"intent": "confirm_request", "issue_code": "dining_other"}


def test_the_previous_turn_is_given_to_the_model_so_that_that_restaurant_resolves(decided):
    _say(decided, "성수 점심 식당 알려줘", "du-b1")
    body = _say(decided, "그 식당 전화번호 알려줘", "du-b2")
    assert "고객: 성수 점심 식당 알려줘" in decided["decider"].prompts[-1]          # 서버가 앞 대화를 넘겼다
    assert body["decision"]["fact"] == "phone" and "성수 점심" in body["answer"], body
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat",
                                  headers=_h(decided["key"])).json()["turns"]
    assert [t["role"] for t in turns] == ["customer", "assistant", "customer", "assistant"]


def test_change_then_undo_without_a_number_goes_back_by_the_change_id(decided):
    changed = _say(decided, "점심 다른 데로 바꿔", "du-c1")
    assert changed["status"] == "adjusted", changed
    undone = _say(decided, "원래대로 돌려 줘", "du-c2")
    assert undone["status"] == "rolled_back" and re.match(r"c\d+", undone["decision"]["change"]), undone
    assert "되돌렸어요" in undone["answer"] and "버전" not in undone["answer"]


def test_an_unclear_request_is_asked_back_and_nothing_changes(decided):
    body = _say(decided, "바꿔", "du-d")
    # ★모델이 후보를 안 내도 서버가 고를 수 있는 일정을 버튼으로 싣는다(「다음 중 하나인가요?」)
    assert body["status"] == "clarify" and body["choices"] and "다음 중 하나인가요" in body["answer"], body
    view = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()
    assert view["version"] == 1


def test_a_model_failure_or_an_id_outside_the_list_changes_nothing_and_does_not_fall_back_to_rules(decided):
    down = _say(decided, "고장 났을 때 점심 바꿔", "du-e1")
    assert down["status"] == "escalated" and down["reason"] == "decision_failed", down
    assert "일정은 바꾸지 않았어요" in down["answer"]
    outside = _say(decided, "없는 번호 바꿔", "du-e2")
    assert outside["status"] == "escalated" and "목록 밖" in outside["failure"], outside
    view = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()
    assert view["version"] == 1
    with get_connection() as conn, conn.cursor() as cur:        # 실패도 기록에 남는다(오류 리포트)
        cur.execute("SELECT state_json->'decision' FROM customer_cases WHERE case_id=%s", (down["case_id"],))
        assert "failed" in cur.fetchone()[0]


def test_the_configured_mode_is_really_on_and_a_bare_yaml_on_is_not_read_as_off():
    """`[2026-09-29]` 설정의 `mode: on` 이 YAML 에서 참(True)으로 읽혀 결정 단위가 꺼진 채로 돌았다(실서버)."""
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.conversation import trip_messages
    from app.domains.travel_ops.modules.web_account import web_guard

    assert get_guardrails().get("travel.decision_unit.mode") == "on"
    assert web_guard._mode_text(True) == "on" and web_guard._mode_text("shadow") == "shadow"

    class Structured:
        def structured(self, *a, **k):
            return {}

    assert trip_messages._decision_mode(Structured()) == "on"


def test_undoing_an_older_change_asks_once_and_a_yes_then_undoes_it(decided):
    """뒤에 다른 변경이 있는 옛 변경을 되돌리라면 한 번 묻고(버전 번호 없이), 「네」면 되돌린다 — 다시 묻지 않는다."""
    _say(decided, "점심 다른 데로 바꿔", "du-f1")                       # c2 — 점심
    _say(decided, "저녁 다른 데로 바꿔", "du-f2")                       # c3 — 저녁(점심 변경은 그대로 살아 있다)
    decider = decided["decider"]
    first_change = lambda user: re.findall(r"^(c\d+) \|", user, re.M)[0]  # noqa: E731

    original = decider.structured

    def older(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        return {"action": "rollback", "target_item": "none", "target_change": first_change(user), "fact": "none",
                "minutes": 0, "choices": []}

    decider.structured = older
    asked = _say(decided, "처음 바꾼 거 되돌려", "du-f3")
    assert asked["status"] == "ask_rollback" and "그래도 되돌릴까요" in asked["answer"] and "번 일정" not in asked["answer"]
    yes = _say(decided, "네, 되돌려 줘", "du-f4")
    decider.structured = original
    assert yes["status"] == "rolled_back", yes


def test_looking_for_options_never_offers_the_original_place(decided):
    """`[2026-09-29 ui 세션 지적]` 「알아봐 줘」 후보에 원래 곳(「3) 금용문」)이 섞였다 — 되돌리기용 기록이 고를 안으로 새었다."""
    decider = decided["decider"]
    original = decider.structured

    def propose(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        return {"action": "propose_alternatives", "target_item": decider._alias(user, "성수 점심"),
                "target_change": "none", "fact": "none", "minutes": 0, "choices": []}

    decider.structured = propose
    body = _say(decided, "점심 다른 데 알아봐 줘", "du-g1")
    decider.structured = original
    assert body["status"] == "asked", body
    names = [o["name"] for o in body["outcome"]["options"]]
    assert names and "성수 점심 식당" not in names and "성수 점심 식당" not in body["answer"].split("—", 1)[1]
    assert [o["rank"] for o in body["outcome"]["options"]] == list(range(1, len(names) + 1))


def test_undoing_a_change_that_is_already_undone_asks_instead(decided):
    """`[2026-09-29 ui 세션 지적]` 이미 되돌린 변경을 또 되돌리자고 했다(「바꿔」에) — 되돌리지 않고 「다음 중 하나인가요?」."""
    _say(decided, "점심 다른 데로 바꿔", "du-h1")                        # c2
    _say(decided, "원래대로 돌려 줘", "du-h2")                            # c3 — c2 를 되돌림
    decider = decided["decider"]
    original = decider.structured

    def stale(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        first = re.findall(r"^(c\d+) \|", user, re.M)[0]
        return {"action": "rollback", "target_item": "none", "target_change": first, "fact": "none", "minutes": 0,
                "choices": [{"action": "apply_change", "target_item": decider._alias(user, "성수 점심"),
                             "target_change": "none", "fact": "none"}]}

    decider.structured = stale
    body = _say(decided, "바꿔 줘", "du-h3")
    decider.structured = original
    assert "지금 일정에 없음" in decider.prompts[-1]                        # 모델에게도 알려 준다
    assert body["status"] == "clarify" and "다음 중 하나인가요" in body["answer"], body
    assert body["choices"] and "다른 곳으로 바꿔 줘" in body["choices"][0]["message"]
    view = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}", headers=_h(decided["key"])).json()
    assert view["version"] == 3                                              # 아무것도 안 바뀌었다


def test_when_the_model_gives_no_choices_the_server_still_offers_some(decided):
    """`[2026-09-29 ui 세션 지적]` 되물을 때 후보가 비면 웹에 버튼이 없다 — 서버가 바꿀 수 있는 가까운 일정 셋을 버튼으로 싣는다."""
    decider = decided["decider"]
    original = decider.structured

    def unclear(system, user, schema, *, num_predict=160):
        decider.prompts.append(user)
        return {"action": "clarify", "target_item": "none", "target_change": "none", "fact": "none", "minutes": 0,
                "choices": []}

    decider.structured = unclear
    body = _say(decided, "음", "du-i1")
    decider.structured = original
    assert body["status"] == "clarify" and 1 <= len(body["choices"]) <= 3, body
    assert all(c["message"].endswith("다른 곳으로 바꿔 줘") for c in body["choices"])
    assert "다음 중 하나인가요" in body["answer"]


def test_where_is_it_gets_one_line_and_a_map_link_not_the_whole_description(decided):
    """☆`[2026-09-29 ui 세션 — 사용자 실사용 결함]` 「그건 어딧는거야」에 장소·주소·운영시간·예약·오는 길까지 열 줄이 나갔다.
    위치를 물으면 주소(또는 모름)와 **지도 앱 링크**만."""
    body = _say(decided, "그 식당 어딨어", "du-where")
    assert body["decision"]["fact"] == "address", body
    assert "https://www.google.com/maps/search/" in body["answer"], body["answer"]
    assert "예약" not in body["answer"].split("혹시")[0] and "다음 일정" not in body["answer"]
    assert "more" not in body
    # ★`[2026-09-29 사용자 지시]` 답하면서 「혹시 이런 뜻이었나요?」 — 가까운 질문을 버튼으로
    assert body["choices_title"] == "혹시 이런 뜻이었나요?" and 1 <= len(body["choices"]) <= 3, body
    assert any("가는 길" in c["message"] for c in body["choices"])
    # ★`[2026-09-29 ui 세션 요청]` 웹 답 문장에는 목록이 없다(버튼으로 그린다) — 대화 기록(글만)에는 목록이 남는다
    assert "혹시 이런 뜻이었나요?" not in body["answer"]
    turns = decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}/chat", headers=_h(decided["key"])).json()
    assert "혹시 이런 뜻이었나요?" in turns["turns"][-1]["text"], turns


def test_when_every_reading_is_a_question_it_answers_first_and_offers_the_rest(decided):
    """☆`[2026-09-29 사용자 지시]` 「예약 표시 알려 줘」를 두 일정 중 어느 것이냐고 되물었다 — 사실 질문은 잘못 짚어도 잃는 것이
    없으니 첫 해석으로 **먼저 답하고** 나머지를 「혹시 이런 뜻이었나요?」로. 바꾸기는 지금처럼 묻는다."""
    body = _say(decided, "예약 표시 알려 줘", "du-book")
    assert body["status"] == "answered" and body["decision"]["action"] == "answer_fact", body
    assert body["decision"]["fact"] == "booking" and "성수 점심" in body["decision"]["item"]
    assert any("저녁" in c["message"] or "예약" in c["message"] for c in body["choices"]), body
    unclear = _say(decided, "바꿔", "du-book-2")
    assert unclear["status"] == "clarify"                                   # 바꾸기는 여전히 되묻는다


def test_a_general_question_answers_the_core_first_and_keeps_the_rest_for_more(decided):
    """☆`[2026-09-29 ui 세션 요청]` 전반을 물어도 핵심(무엇 · 어디 · 그날 영업 · 다음 일정)만 먼저 — 나머지는 「더 보기」(`more`)."""
    body = _say(decided, "성수 점심 식당 알려줘", "du-core")
    assert "· 어디:" in body["answer"] and "· 다음 일정:" in body["answer"], body["answer"]
    assert "· 예약:" not in body["answer"] and "더 보기" not in body["answer"]
    assert "· 예약:" in body["more"], body


# ── 현재 위치 (2026-09-30 사용자 지시 — ui 세션 전달: 브라우저 Geolocation → 채팅 요청의 `location`) ──────────────────────
#: 시험용 좌표 — 자릿수를 겹치지 않게 골라, 어디에든 남았다면 문자열 검색으로 잡힌다(성수동 부근)
HERE = {"lat": 37.544719, "lng": 127.055731, "accuracy_m": 20.0}
HERE_TEXTS = ("37.544719", "127.055731", "37.5447", "127.0557")
NOON = "2030-01-01T12:00:00+09:00"


def _version(decided) -> int:
    return decided["client"].get(f"/v1/web/trips/{decided['trip']['trip_id']}",
                                 headers=_h(decided["key"])).json()["version"]


def test_a_location_question_without_a_location_asks_for_it_and_changes_nothing(decided):
    """①: 위치가 필요한 질문인데 `location` 이 없으면 일정은 그대로, 한 문장과 `needs_location: true`."""
    before = _version(decided)
    for n, text in enumerate(("지금 위치에서 성수 점심 어떻게 가", "여기서 가까운 근처 식당 알려줘", "근처 볼거리 뭐 있어")):
        body = _say(decided, text, f"loc-no-{n}", at=NOON)
        assert body["status"] == "answered" and body["needs_location"] is True, body
        assert "현재 위치를 알려 주시면" in body["answer"], body["answer"]
    assert _version(decided) == before


def test_the_location_is_the_origin_of_the_route(decided, monkeypatch):
    """②: 위치를 실으면 그 좌표가 이동 계산기의 출발지로 쓰인다."""
    from app.domains.travel_ops.instances.mobility import wiring

    seen = []

    def fake_planner(party, constraints, **_):
        def leg(a_place, b_place, arrive_dt, not_before_dt=None):
            seen.append((a_place["lat"], a_place["lon"], b_place["name"]))
            return {"route": {"planned": "w", "options": [{"id": "w", "label": "지하철 2호선", "eta_min": 17}]},
                    "starts_at": arrive_dt - timedelta(minutes=27), "ends_at": arrive_dt - timedelta(minutes=10),
                    "eta_min": 17, "left_out": []}, None
        return leg

    monkeypatch.setattr(wiring, "leg_planner", fake_planner)
    body = _say(decided, "지금 위치에서 성수 점심 어떻게 가", "loc-route", at=NOON, location=HERE)
    assert body["status"] == "answered" and "needs_location" not in body, body
    assert seen and seen[0][0] == HERE["lat"] and seen[0][1] == HERE["lng"] and "성수 점심" in seen[0][2], seen
    assert "지하철 2호선" in body["answer"] and "17분" in body["answer"] and "시간표 기준" in body["answer"], body["answer"]


def test_without_the_timetable_calculator_the_route_is_an_estimate_and_says_so(decided):
    body = _say(decided, "지금 위치에서 성수 점심 어떻게 가", "loc-estimate", at=NOON, location=HERE)
    assert "지금 위치에서 성수 점심" in body["answer"] and "[추정" in body["answer"], body["answer"]


def test_nearby_places_are_listed_from_the_location_without_changing_the_trip(decided):
    before = _version(decided)
    dining = _say(decided, "여기서 가까운 근처 식당", "loc-near-d", at=NOON, location=HERE)
    assert dining["status"] == "answered" and "needs_location" not in dining
    assert dining["answer"].startswith("지금 위치") and "식당" in dining["answer"], dining["answer"]
    sights = _say(decided, "근처 볼거리 알려줘", "loc-near-a", at=NOON, location=HERE)
    assert sights["status"] == "answered" and "볼거리" in sights["answer"], sights["answer"]
    assert _version(decided) == before                                   # 알아보기만 한다 — 일정은 그대로


def test_the_raw_coordinates_are_stored_and_logged_nowhere(decided, caplog):
    """③: 원 좌표(와 동네 수준으로 줄인 값도)는 응답 문장 · Case · 대화 기록 · 바깥함 · 로그 어디에도 없다."""
    import logging

    caplog.set_level(logging.DEBUG)
    bodies = [_say(decided, "지금 위치에서 성수 점심 어떻게 가", "loc-priv-1", at=NOON, location=HERE),
              _say(decided, "여기서 가까운 근처 식당", "loc-priv-2", at=NOON, location=HERE),
              _say(decided, "근처 볼거리 알려줘", "loc-priv-3", at=NOON, location=HERE)]
    with get_connection() as conn, conn.cursor() as cur:
        dumps = []
        for sql in ("SELECT payload_json::text FROM case_events", "SELECT state_json::text FROM customer_cases",
                    "SELECT text FROM trip_chat_turns", "SELECT payload_json::text FROM outbox",
                    "SELECT attributes::text FROM places WHERE trip_scope IS NOT NULL",
                    "SELECT subject FROM customer_cases"):
            cur.execute(sql)
            dumps += [str(row[0]) for row in cur.fetchall()]
    haystack = "\n".join(dumps + [str(b) for b in bodies] + [r.getMessage() for r in caplog.records])
    for needle in HERE_TEXTS:
        assert needle not in haystack, needle


def test_a_location_outside_seoul_or_too_vague_is_not_used_and_says_why(decided):
    far = _say(decided, "여기서 가까운 근처 식당", "loc-far", at=NOON, location={"lat": 35.1796, "lng": 129.0756})
    assert "서울 밖" in far["answer"] and "needs_location" not in far, far["answer"]
    vague = _say(decided, "여기서 가까운 근처 식당", "loc-vague", at=NOON, location={**HERE, "accuracy_m": 5000})
    assert "정확도" in vague["answer"] and "너무 낮아" in vague["answer"], vague["answer"]
    rough = _say(decided, "지금 위치에서 성수 점심 어떻게 가", "loc-rough", at=NOON, location={**HERE, "accuracy_m": 800})
    assert "±800m" in rough["answer"] and "조금 다를 수" in rough["answer"], rough["answer"]


def test_a_bad_location_value_is_refused_without_echoing_it(decided):
    body = {"request_id": "loc-bad", "message": "근처 식당", "location": {"lat": 999, "lng": 127.05}}
    response = decided["client"].post(f"/v1/web/trips/{decided['trip']['trip_id']}/messages", headers=_h(decided["key"]),
                                      json=body)
    assert response.status_code == 422
    assert "127.05" not in response.text                                 # 검증 오류가 실은 좌표 값을 되돌려 주지 않는다


def test_a_request_without_a_location_is_unchanged(decided):
    body = _say(decided, "성수 점심 식당 알려줘", "loc-none", at=NOON)
    assert body["status"] == "answered" and "needs_location" not in body


def test_the_location_module_neither_stores_nor_logs():
    """구조 보장 — 위치를 다루는 모듈은 DB · 로그를 가져다 쓰지 않는다(좌표를 남길 길이 없다)."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "app/domains/travel_ops/components/conversation/trip_here.py").read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {"logging", "psycopg", "sqlite3", "json", "pickle"} & imported
    assert not any(m.startswith(("app.infrastructure", "app.core.settings")) for m in imported)
    from app.domains.travel_ops.components.conversation.trip_here import Fix

    assert "37.5" not in repr(Fix(lat=37.544719, lon=127.055731))


def test_the_nearby_sentence_reads_naturally_and_leaves_out_price_warnings():
    from types import SimpleNamespace as S

    from app.domains.travel_ops.components.conversation.trip_here import Fix, nearby

    fix = Fix(lat=37.5, lon=127.0)
    sights = [S(place={"name": "덕수궁"}, name="덕수궁", walk_min=None, distance_m=640.0,
                warnings=["가격을 몰라 추가 비용을 계산할 수 없다"])]
    text = nearby("nearby_activity", fix, found=sights, radius_m=1500, sought=3)
    assert text == "지금 위치에서 가까운 볼거리예요 — 1) 덕수궁 (도보 약 8분)", text        # 조사 · 도보 분 · 가격 경고 없음
    meals = [S(place={"name": "이북만두"}, name="이북만두", walk_min=2, distance_m=150.0,
               warnings=["14:30 브레이크타임 1시간 안에 식사가 끝나요"])]
    assert nearby("nearby_dining", fix, found=meals, radius_m=700, sought=1) == \
        "지금 위치에서 가까운 식당이에요 — 1) 이북만두 (도보 약 2분) — 14:30 브레이크타임 1시간 안에 식사가 끝나요"
    assert "찾지 못했어요" in nearby("nearby_dining", fix, found=[], radius_m=3000, sought=4)
