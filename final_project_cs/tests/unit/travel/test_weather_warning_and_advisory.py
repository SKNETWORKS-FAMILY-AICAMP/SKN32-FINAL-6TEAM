# -*- coding: utf-8 -*-
"""기상특보·외교부 여행경보 — 「없음」과 「모름」을 가르는지가 핵심이다.

★실제 공급자 응답 모양(2026-09-14 실호출)을 그대로 흉내 낸다. 네트워크는 안 탄다.
"""
from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.core.contracts import ContextPack, NextAction, ToolNotAllowed
from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.kma_warning import KmaWarningSource, parse_status
from app.infrastructure.travel.mofa import MofaTravelAlarm
from app.modules.travel_ops.activity import ActivityTeam
from app.tools.read_tools import ReadToolbox, ToolContext

from .helpers import FakeTools, in_hours, pack, task


def _resp(status: int, payload=None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://x")
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload, request=request)


def _kma(items, code="00"):
    return {"response": {"header": {"resultCode": code, "resultMsg": "NORMAL_SERVICE"},
                         "body": {"items": {"item": items}}}}


# ── 특보 글 파싱 ─────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["o 없 음", "o 없음", "o 없음\r\n\r\n"])
def test_both_real_spellings_of_none_mean_no_warning(text):
    """★「없 음」(띄어 씀)과 「없음」이 실제로 섞여 온다(2026-09-14 실측)."""
    assert parse_status(text) == []


def test_multiple_kinds_paren_commas_and_wrapped_lines():
    text = ("o 호우경보 : 서울동남권, 서울동북권, 경기도(수원, 성남,\r\n"
            "  용인)\r\n"
            "o 강풍주의보 : 서해중부바깥먼바다")
    assert parse_status(text) == [
        {"kind": "호우경보", "areas": ["서울동남권", "서울동북권", "경기도(수원, 성남, 용인)"]},
        {"kind": "강풍주의보", "areas": ["서해중부바깥먼바다"]},
    ]


@pytest.mark.parametrize("text", ["특보 목록 형식이 바뀜", "o 호우경보 서울"])
def test_an_unknown_shape_is_unknown_not_none(text):
    """★모르는 모양을 「특보 없음」으로 읽으면 조용히 거짓말이 된다."""
    assert parse_status(text) is None


# ── 특보 소스 ────────────────────────────────────────────────────
def _warning_source(handler) -> KmaWarningSource:
    return KmaWarningSource(service_key="k", transport=lambda url, params: handler(url, params))


def test_the_latest_announcement_wins_and_region_matching_uses_subzones():
    items = [
        {"t6": "o 없 음", "t7": "o 없음", "tmFc": 202609140500, "tmSeq": 3, "tmEf": "202609140500"},
        {"t6": "o 호우경보 : 서울동남권, 인천", "t7": "o 없음",
         "tmFc": 202609140800, "tmSeq": 4, "tmEf": "202609140900"},
    ]
    result = _warning_source(lambda u, p: _resp(200, _kma(items))).active(region="서울")
    assert result["announced_at"] == "2026-09-14T08:00"
    assert result["effective_at"] == "2026-09-14T09:00"
    assert [w["kind"] for w in result["for_region"]] == ["호우경보"]
    assert result["source"] == "kma_warning" and result["confirmed_at"]


def test_no_warning_is_a_known_empty_list():
    items = [{"t6": "o 없 음", "t7": "o 없음", "tmFc": 202609110600, "tmSeq": 77, "tmEf": "202609110800"}]
    result = _warning_source(lambda u, p: _resp(200, _kma(items))).active()
    assert result["in_effect"] == [] and result["for_region"] == []


@pytest.mark.parametrize("payload,reason", [
    (_kma([], code="03"), "body_error"),
    ({"response": {"header": {"resultCode": "00"}, "body": {"items": ""}}}, "empty_items"),
    (_kma([{"t6": "형식이 바뀜", "tmFc": 1, "tmSeq": 1}]), "unparsed_status"),
])
def test_warning_failures_are_unknown_and_counted(payload, reason):
    source = _warning_source(lambda u, p: _resp(200, payload))
    assert source.active() is None
    assert source.misses[reason] == 1, dict(source.misses)


# ── 외교부 여행경보 ──────────────────────────────────────────────
def _mofa(items, code="0"):
    return {"response": {"header": {"resultCode": code, "resultMsg": "정상"},
                         "body": {"items": {"item": items}, "totalCount": len(items)}}}


def _mofa_source(handler) -> MofaTravelAlarm:
    return MofaTravelAlarm(service_key="k", transport=lambda url, params: handler(url, params))


def test_mofa_success_code_is_zero_not_double_zero_and_parses_the_real_japan_row():
    seen = {}

    def handler(url, params):
        seen.update(params)
        return _resp(200, _mofa([{"alarm_lvl": "3", "country_nm": "일본",
                                  "country_iso_alp2": "JP", "region_ty": "일부",
                                  "remark": "후쿠시마 원전 반경 30km 이내", "written_dt": None}]))

    result = _mofa_source(handler).country(iso2="jp")
    assert seen["cond[country_iso_alp2::EQ]"] == "JP"
    assert result["max_level"] == 3 and result["alarms"][0]["level_name"] == "출국권고"
    assert result["alarms"][0]["region_type"] == "일부"
    assert result["source"] == "mofa"


def test_a_country_without_an_alarm_is_a_known_empty_list():
    result = _mofa_source(lambda u, p: _resp(200, {"response": {
        "header": {"resultCode": "0"}, "body": {"items": "", "totalCount": 0}}})).country(iso2="KR")
    assert result["alarms"] == [] and result["max_level"] == 0


def test_a_bad_country_code_does_not_call_out():
    calls = []
    source = _mofa_source(lambda u, p: calls.append(1) or _resp(200, _mofa([])))
    assert source.country(iso2="Japan") is None
    assert calls == [] and source.misses["bad_country_code"] == 1


def test_an_unreadable_level_is_unknown_not_a_guess():
    source = _mofa_source(lambda u, p: _resp(200, _mofa([{"alarm_lvl": "특별"}])))
    assert source.country(iso2="JP") is None
    assert source.misses["bad_alarm_level"] == 1


# ── 도구 배선 — 기본값은 「바깥으로 안 나간다」 ─────────────────
SCOPE = ToolContext(tenant_id="t", customer_id=uuid4(), case_id=uuid4(),
                    knowledge_scope=["activity"])


class _Rec:
    def __init__(self, value):
        self.value, self.seen = value, []

    def active(self, *, region):
        self.seen.append(region)
        return self.value

    def country(self, *, iso2):
        self.seen.append(iso2)
        return self.value


def test_without_injection_both_tools_are_unknown():
    toolbox = ReadToolbox(lambda: None)
    assert toolbox.weather_warning(SCOPE) is None
    assert toolbox.travel_advisory(SCOPE, country_iso2="JP") is None


def test_the_tools_delegate_to_injected_sources():
    warning, advisory = _Rec({"for_region": []}), _Rec({"alarms": []})
    toolbox = ReadToolbox(lambda: None, travel=TravelSources(warning=warning, advisory=advisory))
    assert toolbox.weather_warning(SCOPE, region="서울") == {"for_region": []}
    assert toolbox.travel_advisory(SCOPE, country_iso2="JP") == {"alarms": []}
    assert toolbox.travel_advisory(SCOPE) is None      # ★나라를 모르면 묻지 않는다
    assert warning.seen == ["서울"] and advisory.seen == ["JP"]


def test_the_new_tools_still_obey_the_allowlist():
    context = ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id="activity",
                          tenant_id="t", knowledge_scope=["activity"],
                          current_state={"customer_id": str(uuid4())},
                          estimated_input_tokens=1)
    for name in ("read.weather_warning", "read.travel_advisory"):
        with pytest.raises(ToolNotAllowed):
            ReadToolbox(lambda: None).call(name, context, {}, ["read.booking"], set())


# ── Activity 가 점검 결과를 쓰는 방식 ─────────────────────────
ALLOWED = ActivityTeam.manifest.allowed_tools


def _report(verdict, *, disruptions=(), failed=()):
    return {"verdict": verdict, "disruptions": list(disruptions), "advisories": [],
            "checks": [], "failed_categories": list(failed), "not_connected": []}


def _activity_values(report):
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": in_hours(30),
                         "party_size": 2, "capacity": 4},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": {"place_id": "p1", "weather_sensitive": True,
                       "latitude": 37.5, "longitude": 127.0},
        "read.disruptions": report,
    }


def _activity_task():
    return task("activity", "activity.check_feasible",
                pack("activity", scope=["activity", "weather"]), ALLOWED)


@pytest.mark.asyncio
async def test_a_warning_in_effect_means_the_schedule_must_change():
    """★이상이 하나라도 있으면 일정 변경 대상이다(2026-09-14 사용자 결정)."""
    report = _report("disrupted", disruptions=[
        {"category": "weather_warning", "kind": "호우경보", "areas": ["서울동남권"]}])
    result = await ActivityTeam(FakeTools(_activity_values(report))).execute(_activity_task())
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].arguments["reason"].endswith("호우경보")
    assert result.decisions[0]["feasible"] is False
    assert "호우경보" in result.answer


@pytest.mark.asyncio
async def test_a_failed_category_is_fatal_not_a_schedule_change():
    """★조회 실패는 일정 변경 사유가 아니다 — 결정 15 의 치명이다."""
    report = _report("fatal", failed=["weather_warning"])
    result = await ActivityTeam(FakeTools(_activity_values(report))).execute(_activity_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "fatal_source_failure"
    assert not result.action_proposals
    assert any("weather_warning" in w and "치명" in w for w in result.warnings)
