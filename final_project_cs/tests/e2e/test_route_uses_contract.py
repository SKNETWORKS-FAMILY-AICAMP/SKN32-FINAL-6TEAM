# -*- coding: utf-8 -*-
"""`routes{<키>}.options[].uses` 표기 — **받을 때 거절한다**. `[2026-09-23]`

★★왜. `uses` 는 운행·통제 사건과 **문자열로 대조**된다. 표기가 다르면 사건이 있어도 못 잡고
  오류도 안 난다. 전에는 등록이 아무 모양이나 받았다 — `잠실역`·`02호선`·`버스:성수동` 을
  받아 두고 **나중에 조용히 놓쳤다.** 계약은 `wiki/external/rest-endpoints.md`
  「`routes{<키>}.options[].uses`」 절, 인계는 `wiki/delivery/open-items.md`(문서 세션 → 코드).

★이 파일의 거절 시험 셋은 **검사를 붙이기 전에 먼저 빨갰다**(2026-09-23, 셋 다 201 로 받았다).

재현:

    python -m pytest tests/e2e/test_route_uses_contract.py -v
"""
from __future__ import annotations

import copy
import json

import pytest

from app.modules.travel_ops.route_uses import problem, route_problems
from app.modules.travel_ops.scenario_mode import SCENARIO_PATH

from .test_trip_api import _body, api  # noqa: F401 — 픽스처를 그대로 쓴다

SCENARIO = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def _with_uses(customer, uses: list[str], request_id: str):
    body = _body(customer, request_id=request_id)
    body["routes"] = copy.deepcopy(body["routes"])
    body["routes"]["jamsil_to_seongsu"]["options"][0]["uses"] = uses
    return body


@pytest.mark.parametrize("bad, why", [
    ("잠실역", "모양"),                 # 종류가 없다
    ("02호선:잠실", "`2호선`"),         # 내부 키 모양이 바깥으로 샜다
    ("버스:성수동", "노선번호"),         # 동네 이름
])
def test_a_misspelled_target_is_refused_with_the_reason(api, bad, why):
    """★받으면 그 구간의 사건을 **나중에 조용히 놓친다** — 그래서 받을 때 막는다."""
    response = api["client"].post("/v1/trips", json=_with_uses(api["customer"], [bad], f"bad-{bad}"),
                                  headers=api["auth"]("trip:write"))
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_route_uses"
    assert error["problems"][0]["value"] == bad
    assert error["problems"][0]["route"] == "jamsil_to_seongsu"
    assert why in error["problems"][0]["reason"]


def test_every_bad_value_is_listed_not_just_the_first(api):
    """고치고 다시 보냈더니 다음 것이 걸리는 왕복을 줄인다."""
    body = _with_uses(api["customer"], ["2호선:잠실역", "도보:서울역", "도로:대로"], "bad-many")
    error = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write")).json()["error"]
    assert [p["value"] for p in error["problems"]] == ["2호선:잠실역", "도보:서울역", "도로:대로"]


def test_nothing_is_stored_when_refused(api):
    """★거절했는데 여행이 생기면 거절이 아니다."""
    from app.infrastructure.db.session import get_connection

    api["client"].post("/v1/trips", json=_with_uses(api["customer"], ["잠실역"], "bad-store"),
                       headers=api["auth"]("trip:write"))
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 0


# ── 확정 시나리오가 계약을 지키는가 ────────────────────────────────
def test_the_confirmed_scenario_follows_the_contract():
    """★시연 데이터가 계약을 어기면 시연이 계약 위반을 가르친다."""
    assert route_problems(SCENARIO["routes"]) == []


def test_the_scenario_still_carries_the_targets_the_replay_events_hit():
    """★재생 타임라인의 사건 대상은 **바꾸지 않는다** — 바꾸면 시연 사건이 안 걸린다."""
    targets = {(event.get("match") or {}).get("target") for event in SCENARIO["timeline"]
               if isinstance(event, dict) and event.get("kind") == "route_event"}
    used = {value for route in SCENARIO["routes"].values()
            for option in route["options"] for value in option["uses"]}
    assert targets and targets <= used, (targets, sorted(used))


def test_a_transfer_station_is_written_for_both_lines():
    """★갈아탄 역은 **두 노선으로 각각** — 어느 노선의 무정차든 환승이 깨진다."""
    palace = SCENARIO["routes"]["seongsu_to_palace"]["options"][0]["uses"]
    assert {"2호선:을지로3가", "3호선:을지로3가"} <= set(palace)
    dinner = {o["id"]: o["uses"] for o in SCENARIO["routes"]["palace_to_dinner"]["options"]}
    assert {"3호선:충무로", "4호선:충무로"} <= set(dinner["subway_transfer"])


# ── 표기 규칙 하나하나 ──────────────────────────────────────────────
@pytest.mark.parametrize("good", ["2호선:잠실", "4호선:서울역", "경의중앙선:용산", "공항철도:홍대입구",
                                  "버스:2224", "버스:N26", "버스:성동10", "도로:세종대로", "도로:올림픽대로"])
def test_the_contract_examples_are_accepted(good):
    assert problem(good) is None


@pytest.mark.parametrize("bad", ["2호선:잠실역", "3호선:경복궁(정부서울청사)", "4호선:서울", "도보:서울역",
                                 "도로:대로", "무슨선:어디", "버스:", 42])
def test_the_contract_counterexamples_are_refused(bad):
    assert problem(bad) is not None


def test_a_bus_leg_also_names_the_road_it_runs_on():
    """★계약 「버스 구간이 지나는 주요 도로도 `도로:` 로 함께 적는다」 — 도로 통제는 버스도 막는다.

    근거(2026-09-23) — 서울시 TOPIS 정류소별 경유 노선으로 번호를, 카카오 역지오코딩으로 정류소 주변
    도로명을 확인했다. 건대입구역1번출구 아차산로 10/11 · 성수역1번출구 7/10 · 뚝섬역5번출구 5/9 ·
    시청앞.덕수궁 세종대로 15/15.
    """
    for route in SCENARIO["routes"].values():
        for option in route["options"]:
            buses = [v for v in option["uses"] if v.startswith("버스:")]
            roads = [v for v in option["uses"] if v.startswith("도로:")]
            if buses:
                assert roads, (option["id"], option["uses"])
