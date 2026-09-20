# -*- coding: utf-8 -*-
"""예약 인근에 재난문자(위급재난 등급)가 발령됐을 때 일정이 가능한지 검증한다.

Activity 가 재난문자 목록을 **어떻게 쓰는지**.

★★**메시지 본문(`MSG_CN`)을 해석하지 않는다.** TourAPI 운영시간 원문과 같은
  이유다 — 자연어를 통으로 규칙화하면 위험하다. 이 Team이 보는 건 딱
  `EMRG_STEP_NM`(긴급단계) 하나이고, 그중에서도 **"위급재난"만** 판정을
  막는다(`_disaster_blocks`). "긴급재난"·"안전안내"는 근거로만 전한다.

★★**지역·주제 관련성은 확인하지 않는다.** "위급재난" 문자가 인근에 있다는
  사실 하나만으로 막고, 그 한계(실제로 이 활동과 관련 있는지 모른다는 것)를
  안내문에 반드시 남긴다 — 캐비앗이 빠지면 근사 판정이 확정 판정처럼 보인다.

★재난문자API 실제 클라이언트는 아직 없다(`TravelSources.disaster`는 항상
  `None`). 이 파일은 `FakeTools`로 `read.disaster` 응답만 직접 넣어
  판정 함수(`_disaster_blocks`·`_disaster_note`)와 배선을 검증한다 —
  API 키·DB·네트워크가 전혀 필요 없다.

★배선 경위: wiki/teams/activity.md 「재난문자 관련성」 §2026-09-20.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
UTC = timezone.utc

#: ★고정 시각. 요일 대조(별도 기능)와 겹치지 않게 요일이 중요치 않은
#:  값이면 충분하지만, 관례상 test_activity_tour_operating.py 와 같은
#:  날짜를 재사용해 두 파일을 눈으로 대조하기 쉽게 한다.
DEFAULT_STARTS_AT = datetime(2026, 10, 3, 15, tzinfo=UTC)


def _task(capability: str = "activity.check_feasible"):
    context = pack("activity", scope=["activity"])
    return task("activity", capability, context, ALLOWED)


def _show(label: str, result) -> None:
    """★`pytest -s`로 실행해야 보인다."""
    print(f"\n--- {label} ---")
    print("outcome   :", result.outcome)
    print("feasible  :", result.decisions[0].get("feasible"))
    print("answer    :", result.answer)
    print("warnings  :", result.warnings)
    print("decisions :", result.decisions[0])


def _message(sn: str, step: str, dst: str = "산불", **overrides):
    base = {"SN": sn, "CRT_DT": "20261003080000", "MSG_CN": f"[{dst} {step}] 상세 문자 원문",
            "RCPTN_RGN_NM": "서울특별시", "DST_SE_NM": dst, "EMRG_STEP_NM": step}
    base.update(overrides)
    return base


def _values(*, disaster=..., party=2, capacity=4, starts_at=DEFAULT_STARTS_AT):
    place = {"place_id": "p1", "name": "경복궁", "weather_sensitive": False,
             "latitude": 37.5796, "longitude": 126.9770}
    values = {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": starts_at, "party_size": party,
                         "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
    }
    if disaster is not ...:   # ★sentinel — 아예 안 넣는 경우와 `None`을 넣는 경우를 가른다
        values["read.disaster"] = disaster
    return values


@pytest.mark.asyncio
async def test_critical_disaster_blocks_feasibility_with_caveat():
    """"위급재난" 등급이 하나라도 있으면 `feasible: False` + 캐비앗 문구 필수."""
    disaster = {"messages": [_message("D1", "위급재난", dst="산불")],
                "source": "disaster_api", "confirmed_at": "2026-10-03T08:05:00+00:00"}
    result = await ActivityTeam(FakeTools(_values(disaster=disaster))).execute(_task())
    _show("위급재난 1건", result)

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["disaster"]["blocks"] is True
    assert "위급재난" in result.answer
    assert "지역·주제가 이 활동과" in result.answer   # ★관련성 미확인 캐비앗
    assert any("지역·주제 관련성" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_lower_grade_messages_are_surfaced_but_do_not_block():
    """"긴급재난"·"안전안내"는 근거로만 전하고 `feasible`을 안 바꾼다."""
    disaster = {"messages": [_message("D2", "긴급재난", dst="대설"),
                             _message("D3", "안전안내", dst="한파")],
                "source": "disaster_api", "confirmed_at": "2026-10-03T08:05:00+00:00"}
    result = await ActivityTeam(FakeTools(_values(disaster=disaster))).execute(_task())
    _show("긴급재난·안전안내 (막지 않음)", result)

    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["disaster"]["blocks"] is False
    assert "재난문자 2건" in result.answer
    assert "판정에 영향을 주는 등급은 아닙니다" in result.answer
    assert not any("지역·주제 관련성" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_no_disaster_messages_says_none_confirmed():
    """소스는 응답했는데 목록이 비어 있으면(`messages: []`) "없다"고 정직하게 말한다."""
    disaster = {"messages": [], "source": "disaster_api",
                "confirmed_at": "2026-10-03T08:05:00+00:00"}
    result = await ActivityTeam(FakeTools(_values(disaster=disaster))).execute(_task())
    _show("재난문자 없음(빈 목록)", result)

    assert result.decisions[0]["feasible"] is True
    assert "확인 범위 내 재난문자는 없습니다" in result.answer
    assert result.decisions[0]["disaster"]["messages"] == []


@pytest.mark.asyncio
async def test_no_disaster_source_does_not_claim_it_was_checked():
    """★소스가 안 붙어 있으면(`read.disaster` → `None`) 아무 말도 안 만든다.

    지금 실제 상태와 같다 — `TravelSources.disaster`가 항상 `None`이라
    실제 서비스에서도 이 갈래를 탄다.
    """
    result = await ActivityTeam(FakeTools(_values(disaster=None))).execute(_task())
    _show("재난문자 소스 없음", result)

    assert result.decisions[0]["feasible"] is True
    assert "재난문자" not in result.answer
    assert "disaster" not in result.decisions[0]
    assert "tool:activity:read.disaster" not in [e.evidence_id for e in result.evidence]


@pytest.mark.asyncio
async def test_disaster_tool_is_not_even_declared_in_the_fake_when_omitted():
    """`FakeTools`에 `read.disaster` 키 자체를 안 넣어도(옛 테스트 호환) 죽지 않는다."""
    values = _values()   # disaster 인자를 안 줌 — sentinel이 걸러서 키 자체가 없다
    assert "read.disaster" not in values
    result = await ActivityTeam(FakeTools(values)).execute(_task())
    _show("read.disaster 키 자체가 없음", result)

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is True
