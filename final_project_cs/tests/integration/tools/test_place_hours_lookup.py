# -*- coding: utf-8 -*-
"""`read.place_hours` — 성립 판정의 휴무 · 운영시간을 **DB 에 읽어 둔 값**으로 댄다(team 통합 ①, `[2026-10-09]`).

장소 행 → 관광공사 운영시간 표(`catalog_hours`, 새벽 작업)의 요일표와 휴무 원문을 실제 DB 로 읽고, 그 값으로 활동 팀이
「매월 둘째 주 화요일 휴무」를 막는지 끝까지 본다. 통합 ① 커밋 때는 로컬 DB 에 `catalog_hours` 가 없어 미뤘던 확인이다.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ReadToolbox, ToolContext

from tests.unit.travel.helpers import FakeTools, pack, task

KST = timezone(timedelta(hours=9))
SECOND_TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)     # 11/3 이 첫째 화요일
THIRD_TUESDAY = datetime(2026, 11, 17, 14, 0, tzinfo=KST)
WEEK = {day: {"open": "09:00", "close": "18:00"} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


@pytest.fixture()
def world():
    tenant = "hours_" + uuid4().hex[:10]
    content_id = "it-" + uuid4().hex[:12]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "hours"))
        cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,source_content_id) "
                    "VALUES (%s,'시험 박물관','activity',37.5,127.0,false,%s) RETURNING place_id", (tenant, content_id))
        place_id = cur.fetchone()[0]
        cur.execute("INSERT INTO catalog_hours (tenant_id,source,content_id,hours_week,hours_read,hours_origin,read_at) "
                    "VALUES (%s,'tour_api',%s,%s,'{}'::jsonb,%s,now())",
                    (tenant, content_id, json.dumps(WEEK),
                     json.dumps({"usetime": "09:00~18:00", "restdate": "매월 둘째 주 화요일 휴무"}, ensure_ascii=False)))
        # ★`[2026-10-09]` 통합 ⑤ — 실내외를 관광공사 분류로(EX02 = 실내 전시, develop `WEATHER_BY_MIDDLE_CLASS`)
        cur.execute("INSERT INTO place_catalog (tenant_id,source,content_id,title,raw_json) VALUES (%s,'tour_api',%s,%s,%s)",
                    (tenant, content_id, "시험 박물관", json.dumps({"lclsSystm1": "EX", "lclsSystm2": "EX02"})))
    scope = ToolContext(tenant_id=tenant, customer_id=uuid4(), case_id=uuid4(), knowledge_scope=[])
    yield {"tools": ReadToolbox(get_connection), "scope": scope, "place_id": place_id}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for table in ("catalog_hours", "place_catalog", "places", "tenants"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))


def test_the_tool_reads_the_week_and_the_closure_text_from_the_db(world):
    found = world["tools"].place_hours(world["scope"], place_id=str(world["place_id"]), at=SECOND_TUESDAY)

    assert found["known"] is True and found["source"] == "tour_api"
    assert found["attributes"]["hours_week"]["tue"] == {"open": "09:00", "close": "18:00"}
    assert found["restdate_text"] == "매월 둘째 주 화요일 휴무"


def test_the_class_tool_reads_the_tour_class_and_applies_the_develop_rule(world):
    found = world["tools"].place_class(world["scope"], place_id=str(world["place_id"]))

    assert found["lcls1"] == "EX" and found["lcls2"] == "EX02" and found["weather_sensitive"] is False


def test_the_class_tool_says_unknown_for_a_place_off_the_catalog(world):
    assert world["tools"].place_class(world["scope"], place_id=str(uuid4())) is None


def test_an_unknown_place_is_none(world):
    assert world["tools"].place_hours(world["scope"], place_id=None, at=SECOND_TUESDAY) is None


def _judge(world, starts_at):
    hours = world["tools"].place_hours(world["scope"], place_id=str(world["place_id"]), at=starts_at)
    clear = {"verdict": "clear", "disruptions": [], "advisories": [], "failed_categories": [], "not_connected": [],
             "checks": []}
    tools = FakeTools({"read.booking": {"booking_id": "b1", "place_id": str(world["place_id"]), "starts_at": starts_at,
                                        "party_size": 2, "capacity": 4},
                       "read.policy": [],
                       "read.place": {"place_id": str(world["place_id"]), "weather_sensitive": False,
                                      "latitude": 37.5, "longitude": 127.0},
                       "read.disruptions": clear, "read.place_hours": hours})
    request = task("activity", "activity.check_feasible", pack("activity", scope=["activity"]),
                   ActivityTeam.manifest.allowed_tools)
    return asyncio.run(ActivityTeam(tools).execute(request))


def test_the_team_blocks_the_second_tuesday_from_the_db_text(world):
    decision = _judge(world, SECOND_TUESDAY).decisions[0]

    assert decision["feasible"] is False and decision["reason"] == "closed_weekday"
    assert decision["hours"]["closure_reason"] is not None


def test_the_team_lets_the_third_tuesday_through(world):
    decision = _judge(world, THIRD_TUESDAY).decisions[0]

    assert decision["feasible"] is True and decision["hours"]["within_hours"] is True
