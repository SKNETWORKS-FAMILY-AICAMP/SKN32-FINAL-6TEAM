# -*- coding: utf-8 -*-
"""낮 감시가 **식사 항목**을 재난문자로 깨졌다고 보면 — 식당 Team 이 받아 근처 식당으로 바꾼다. `[2026-09-29]`

☆왜(사용자 지적 · ui 세션 전달 「낮에 식당에 재난·휴무가 생기면 대체가 되나요?」). 전에는 감시(1분마다, 90분 앞)가
  식사 항목을 `unhandled` 로 **세기만** 했다 — 식당 Team 에 감시 Case 처리가 없었다. 같은 재난문자에 걸린 활동은
  바뀌고 바로 옆 식당은 그대로였다.

★재난문자만 재생 소스로 넣는다(행안부 실키 발급 전 — 실제 재난을 일으킬 수 없다). 감시 · Case · Controller ·
  식당 Team · 적용 · 통지는 실제 코드다(`CaseEngine`, 시나리오 하루 데이터).
★재난문자는 **구 단위**다 — 같은 구의 옆집도 걸린다. 그래서 대체 후보도 같은 점검을 다시 통과해야 한다.

재현:

    python -m pytest tests/scenario/test_case_watch_dining.py -v
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
from app.domains.travel_ops.scenarios.case_engine import CaseEngine, cleanup_tenant

from .test_case_version_day import SCENARIO, Clock, _at, _classifier, _extractor, _seed

LUNCH = next(p for p in SCENARIO["places"] if p["key"] == "seongsu_lunch")
LUNCH_ALTERNATES = {p["name"] for p in SCENARIO["places"] if p["key"] in ("lunch_alt_a", "lunch_alt_b")}


class FireIn:
    """재생 재난문자 — 한 구에만 화재 안내가 떠 있다. 행안부 판과 같은 모양(`disaster_msg.py`)으로 답한다."""

    name = "replay_disaster"

    def __init__(self, district: str) -> None:
        self.district = district

    def active(self, *, region: str, at: datetime, district: str | None = None) -> dict:
        hits = ([{"kind": "화재", "step": "안전안내", "weather": False, "created_at": at.isoformat(),
                  "text": f"{self.district} 화재 발생 — 인근 통행을 자제해 주십시오"}]
                if district == self.district else [])
        return {"covered": True, "mode": "replay", "source": self.name, "confirmed_at": at.isoformat(),
                "for_region": hits}


def _set_district(tenant: str, name: str, district: str) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET attributes = attributes || jsonb_build_object('district', %s::text) "
                    "WHERE tenant_id=%s AND name=%s", (district, tenant, name))


def _world(fire_district: str):
    tenant = "watchdn_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("11:45"))                 # 점심(13:00)이 90분 앞 창에 들어온다
    check = DisruptionCheck(TravelSources(disaster=FireIn(fire_district)), limits=lambda: (60, 30)).check
    engine = CaseEngine(tenant_id=tenant, check=check, route_events=None, classifier=_classifier,
                        report_extractor=_extractor, clock=clock)
    return {"tenant": tenant, "store": store, "trip_id": trip_id, "engine": engine}


def _lunch(world):
    with get_connection() as conn:
        trip, items = world["store"].latest(conn, world["trip_id"])
    return trip, next(i for i in items if i.kind == "dining" and i.starts_at == _at("13:00"))


@pytest.fixture()
def fire_at_lunch_only():
    """화재는 점심 식당의 구에만 — 대체 후보는 옆 구(700m 안)로 옮겨 둔다."""
    world = _world("재난시험구")
    _set_district(world["tenant"], LUNCH["name"], "재난시험구")
    yield world
    cleanup_tenant(world["tenant"])


@pytest.fixture()
def fire_over_the_whole_block():
    """화재가 점심 식당과 대체 후보 모두의 구에 — 바꿀 곳이 없다."""
    world = _world("재난시험구")
    for name in (LUNCH["name"], *LUNCH_ALTERNATES):
        _set_district(world["tenant"], name, "재난시험구")
    yield world
    cleanup_tenant(world["tenant"])


def test_a_disaster_message_at_the_lunch_place_swaps_it_for_a_nearby_one(fire_at_lunch_only):
    world = fire_at_lunch_only
    before, lunch = _lunch(world)
    outcome = world["engine"].tick()
    assert outcome.unhandled == [], "식사 항목을 세기만 하고 넘기면 안 된다"
    assert [o["issue_code"] for o in outcome.opened] == ["dining_other"]
    assert [r["status"] for r in outcome.ran] == ["resolved"], outcome.ran
    after, now_lunch = _lunch(world)
    assert after["version"] == before["version"] + 1
    assert now_lunch.place["name"] in LUNCH_ALTERNATES and now_lunch.place["name"] != LUNCH["name"]
    assert now_lunch.starts_at == lunch.starts_at            # 고객은 아직 나서지 않았다 — 계획한 시각 그대로
    view = world["engine"].view(outcome.opened[0]["case_id"])
    assert view["owner_team_id"] == "dining" and "화재" in view["answer"]
    assert now_lunch.detail.get("alternates") is not None      # 「다른 데로 바꿔 줘」에 쓸 다른 안


def test_the_same_disaster_on_the_next_tick_does_not_open_a_second_case(fire_at_lunch_only):
    world = fire_at_lunch_only
    first = world["engine"].tick()
    second = world["engine"].tick()
    assert len(first.opened) == 1
    # 바뀐 항목은 새 id 다 — 새 식당은 불이 난 구가 아니라 다시 열 일이 없다
    assert second.opened == [] and second.unhandled == []


def test_when_every_nearby_place_is_in_the_fire_it_does_not_swap_blindly(fire_over_the_whole_block):
    world = fire_over_the_whole_block
    before, _ = _lunch(world)
    outcome = world["engine"].tick()
    assert [o["issue_code"] for o in outcome.opened] == ["dining_other"]
    after, now_lunch = _lunch(world)
    assert after["version"] == before["version"], "불이 난 구의 다른 식당으로 바꾸지 않는다"
    assert now_lunch.place["name"] == LUNCH["name"]
    view = world["engine"].view(outcome.opened[0]["case_id"])
    assert view["case_status"] == "escalated"
