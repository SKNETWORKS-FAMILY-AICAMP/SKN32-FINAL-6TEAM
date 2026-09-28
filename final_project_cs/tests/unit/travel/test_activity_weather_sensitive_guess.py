# -*- coding: utf-8 -*-
"""Activity 가 `weather_sensitive`를 DB가 모를 때 **장소명으로 추정하는** 방식.

★★**왜 필요한가.** TourAPI는 실내/실외 필드를 안 주고, `places`에 실제로
  값을 쓰는 프로덕션 경로가 없다(`scripts/seed_travel.py`뿐) — 그래서
  `weather_sensitive`는 실 데이터에서 **영원히 NULL**이다. 사용자가 "실내·실외
  검증이 불가능하니 title 기준으로 새 알고리즘을 만들라"고 요청해 만들었다.

★★**근사이지 확정이 아니다.** 이름에 "공원"이 있어도 그 공원 안의 실내
  전시관일 수 있다 — `_weather_sensitive_from_title()` 단독 테스트
  (`test_weather_sensitive_from_title.py`류로 안 뺀 이유: `_check_feasible`
  경로 전체와 엮여야 "추정했다는 사실이 안내문에 남는지"까지 본다)로 분류
  자체를, 이 파일에서는 **check_feasible 통합 경로**를 검증한다.
"""
from __future__ import annotations

import pytest

from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools


def _task(capability: str = "activity.check_feasible"):
    context = pack("activity", scope=["activity"])
    return task("activity", capability, context, ALLOWED)


def _values(*, place_name, weather_sensitive=None, weather=None):
    place = {"place_id": "p1", "name": place_name,
             "latitude": 37.5, "longitude": 127.0}
    if weather_sensitive is not None:
        place["weather_sensitive"] = weather_sensitive
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": in_hours(30), "party_size": 2, "capacity": 4},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": weather,
    }


def _forecast(**overrides):
    base = {"matched_hour": "2026-10-04T15:00", "precipitation_probability": 10,
            "wind_speed_kmh": 5.0, "kind": "forecast",
            "source": "open_meteo", "confirmed_at": "2026-10-03T12:00:00+00:00"}
    base.update(overrides)
    return base


# ── 분류 함수 자체 — 사용자가 준 예시 그대로 ─────────────────────

@pytest.mark.parametrize("name,expected", [
    ("서울숲 공원", True),
    ("롯데월드타워 옥상 전망대", True),
    ("스카이워크 광장", True),
    ("남산 X 거리", True),
    ("종합운동장", True),
    ("국립중앙박물관 3층 전시실", False),
    ("컨벤션 홀", False),
    ("실내 클라이밍짐", False),
    ("B1 푸드코트", False),
    ("경복궁", None),          # ★단서 없음 — 추정하지 않는다
    (None, None),
    ("", None),
])
def test_title_classifier_matches_the_given_keyword_examples(name, expected):
    assert ActivityTeam._weather_sensitive_from_title(name) == expected


def test_conflicting_markers_are_not_guessed():
    """★상충하면(둘 다 걸림) 억지로 고르지 않는다 — 실내 기상 오판정 위험."""
    assert ActivityTeam._weather_sensitive_from_title("○○공원 3층 전시홀") is None


# ── check_feasible 통합 — DB 값이 있으면 이름을 아예 안 본다 ──────

@pytest.mark.asyncio
async def test_db_confirmed_weather_sensitive_is_never_overridden_by_title():
    """DB에 확정값이 있으면(`False`) 이름에 "공원"이 있어도 무시한다."""
    tools = FakeTools(_values(place_name="○○공원", weather_sensitive=False))
    result = await ActivityTeam(tools).execute(_task())
    assert "read.weather" not in [name for name, _ in tools.calls]
    assert not any("장소명으로 추정" in w for w in result.warnings)


# ── check_feasible 통합 — DB 값이 없으면(NULL) 이름으로 추정 ──────

@pytest.mark.asyncio
async def test_null_weather_sensitive_falls_back_to_title_and_discloses_it():
    """★핵심 동작. DB가 모르면(`weather_sensitive` 키 자체가 없음=NULL) 이름
    단서로 기상을 조회하고, 추정했다는 사실을 근거·경고에 남긴다."""
    tools = FakeTools(_values(place_name="서울숲 공원", weather=_forecast()))
    result = await ActivityTeam(tools).execute(_task())

    assert "read.weather" in [name for name, _ in tools.calls]
    assert any("장소명으로 추정" in w for w in result.warnings)
    assert result.decisions[0]["weather"]["weather_sensitive_guessed_from_title"] is True
    assert "tool:activity:activity.weather_sensitive_from_title" in \
        [e.evidence_id for e in result.evidence]


@pytest.mark.asyncio
async def test_indoor_title_with_null_db_value_never_calls_weather():
    """이름이 실내를 시사하면(NULL일 때만) 기상을 아예 안 부른다."""
    tools = FakeTools(_values(place_name="국립중앙박물관 3층 전시실"))
    result = await ActivityTeam(tools).execute(_task())

    assert "read.weather" not in [name for name, _ in tools.calls]
    assert result.outcome == "completed"


@pytest.mark.asyncio
async def test_ambiguous_title_with_null_db_value_never_calls_weather():
    """이름에 단서가 없으면(`None`) DB가 몰라도 기상을 안 부른다 — 억지 추정 없음."""
    tools = FakeTools(_values(place_name="경복궁"))
    result = await ActivityTeam(tools).execute(_task())

    assert "read.weather" not in [name for name, _ in tools.calls]
    assert not any("장소명으로 추정" in w for w in result.warnings)
