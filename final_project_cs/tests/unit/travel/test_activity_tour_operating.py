# -*- coding: utf-8 -*-
"""고객이 입력한 장소의 영업시간·휴무 요일 기준으로 예약 가능한 일정인지 검증한다.

Activity 가 TourAPI 운영시간 원문을 **어떻게 쓰는지**.

★★**원문 전체를 boolean으로 해석하지 않는다.** `tour_api.py.operating()`이
  `usetime_text`·`restdate_text`를 자연어 그대로 주고 `answers_open_at_slot:
  False`로 명시한다 — "매주 화요일 휴무. 단 공휴일과 겹치면 개방" 같은 예외
  조건이 섞여 있어 통으로 규칙을 펴면 하나 틀린 게 고객을 문 닫힌 곳 앞에
  세운다.

★`[2026-09-20]` 딱 하나 예외가 있다 — **"요청 요일 == 정기휴무 요일"**만 좁게
  본다(`_weekday_closure_match`). 예외 조건(공휴일 등)은 여전히 안 보고,
  안 봤다는 사실을 안내문에 반드시 남긴다. 이 파일은 그 경계선을 검증한다:
  요일이 안 맞으면(또는 요일 패턴 자체가 없으면) 원문은 근거로만 쓰이고
  `feasible`은 안 바뀐다. 요일이 맞으면 `feasible: False` + 캐비앗 문구.

★배선 경위: wiki/teams/activity.md 「판정 순서」·「휴무 요일 대조」 §2026-09-20.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
UTC = timezone.utc
KST = timezone(timedelta(hours=9))

#: ★고정 시각을 쓴다(`in_hours` 같은 상대 시각 대신) — 요일 대조 로직이 생긴
#:  뒤로는 "지금부터 30시간 뒤"의 요일이 테스트 실행일마다 달라져서, 우연히
#:  화요일에 걸리면 아래 "무관한" 테스트들이 이유 없이 깨진다(flaky).
#:  2026-10-03은 `date -d "2026-10-03" +%A`로 확인한 **토요일**이다 — 기본
#:  `_operating()`의 "화요일" 텍스트와 절대 안 겹친다.
DEFAULT_STARTS_AT = datetime(2026, 10, 3, 15, tzinfo=UTC)


def _task(capability: str = "activity.check_feasible"):
    context = pack("activity", scope=["activity"])
    return task("activity", capability, context, ALLOWED)


def _operating(**overrides):
    base = {"content_id": "126508", "usetime_text": "09:00~18:00(입장마감 17:00)",
            "restdate_text": "매주 화요일 휴무. 단 공휴일과 겹치면 개방",
            "parsed": False, "answers_open_at_slot": False,
            "source": "tour_api", "confirmed_at": "2026-09-20T12:00:00+00:00"}
    base.update(overrides)
    return base


def _show(label: str, result) -> None:
    """테스트 결과를 눈으로 보게 찍는다. ★`pytest -s`로 실행해야 보인다."""
    print(f"\n--- {label} ---")
    print("outcome   :", result.outcome)
    print("feasible  :", result.decisions[0].get("feasible"))
    print("answer    :", result.answer)
    print("warnings  :", result.warnings)
    print("decisions :", result.decisions[0])


def _values(*, operating=None, party=2, capacity=4, starts_at=DEFAULT_STARTS_AT):
    place = {"place_id": "p1", "weather_sensitive": False,
             "latitude": 37.5, "longitude": 127.0}
    if operating is not None:
        place["operating"] = operating
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": starts_at, "party_size": party,
                         "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
    }


@pytest.mark.asyncio
async def test_operating_text_is_surfaced_in_the_answer():
    """원문이 있으면 안내 문구·근거·decisions에 실린다."""
    result = await ActivityTeam(FakeTools(_values(operating=_operating()))).execute(_task())
    _show("원문 있음", result)

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is True
    assert "09:00~18:00" in result.answer
    assert "매주 화요일 휴무" in result.answer
    assert "자동 해석하지 않았습니다" in result.answer
    assert any("자동 판정에 쓰지 않았다" in warning for warning in result.warnings)
    assert result.decisions[0]["operating"]["usetime_text"] == "09:00~18:00(입장마감 17:00)"
    assert "tool:activity:read.place.operating" in [e.evidence_id for e in result.evidence]


@pytest.mark.asyncio
async def test_free_text_closure_without_a_weekday_pattern_does_not_flip_feasibility():
    """★휴무를 시사하는 문구여도 **"매주 <요일> 휴무" 패턴이 아니면** `feasible`은 안 바뀐다.

    `_weekday_closure_match`가 보는 건 딱 그 패턴 하나다. "오늘은 임시휴무"처럼
    요일이 안 들어간 문구까지 "불가"로 읽기 시작하면, 그건 이 함수가 하기로
    한 것보다 넓게 파싱하는 것이다 — 그건 이 Team이 하지 않기로 한 것이다.
    """
    closed = _operating(usetime_text="", restdate_text="오늘은 임시휴무입니다")
    result = await ActivityTeam(FakeTools(_values(operating=closed))).execute(_task())
    _show("휴무를 시사하지만 요일 패턴은 없는 원문", result)

    assert result.decisions[0]["feasible"] is True
    # ★`None`이 아니라 `False`다 — restdate_text가 있으니 "모른다"가 아니라
    #   "요일이 안 맞는다"는 확정 사실이다. `restdate_text` 자체가 없을 때만
    #   `None`이다(`test_operating_present_but_empty_does_not_claim_it_was_checked`).
    assert result.decisions[0]["operating"]["weekday_match"] is False
    assert "불가" not in result.answer
    assert "휴무로 인해" not in result.answer
    assert "임시휴무" in result.answer  # 원문 자체는 전한다


@pytest.mark.asyncio
async def test_no_operating_info_does_not_claim_it_was_checked():
    """★신원이 안 해소됐거나 소스가 없으면(`operating` 없음) 아무 말도 안 만든다."""
    result = await ActivityTeam(FakeTools(_values(operating=None))).execute(_task())
    _show("operating 없음", result)

    assert result.decisions[0]["feasible"] is True
    assert "TourAPI" not in result.answer
    assert "operating" not in result.decisions[0]
    assert not any("자동 판정에 쓰지 않았다" in warning for warning in result.warnings)
    assert "tool:activity:read.place.operating" not in [e.evidence_id for e in result.evidence]


@pytest.mark.asyncio
async def test_operating_present_but_empty_does_not_claim_it_was_checked():
    """★소스가 응답은 했지만 쓸 만한 필드가 없으면 "확인했다"고 말하지 않는다."""
    empty = _operating(usetime_text=None, restdate_text=None)
    result = await ActivityTeam(FakeTools(_values(operating=empty))).execute(_task())
    _show("operating은 있는데 필드가 빔", result)

    assert result.decisions[0]["feasible"] is True
    assert "정보를 받지 못해" in result.answer
    assert any("자동 판정에 쓰지 않았다" in warning for warning in result.warnings)
    # ★`restdate_text`가 없으면 "요일이 안 맞는다"조차 모른다 — `None`이다.
    assert result.decisions[0]["operating"]["weekday_match"] is None


#: 실사용 값 — 경복궁, TourAPI에서 실제로 받아온 운영시간 원문.
REAL_PLACE_NAME = "경복궁"
REAL_OPERATING = _operating(usetime_text="09:00~18:00", restdate_text="매주 화요일 휴무")


@pytest.mark.asyncio
async def test_a_real_place_on_a_non_closure_weekday_stays_feasible():
    """경복궁 · 2026-10-03(토) 15시 — 정기휴무 요일(화)이 아니므로 원문은 근거로만 쓰인다."""
    requested_at = datetime(2026, 10, 3, 15, tzinfo=KST)   # ★실측: 토요일

    values = _values(operating=REAL_OPERATING, starts_at=requested_at)
    values["read.place"]["name"] = REAL_PLACE_NAME

    result = await ActivityTeam(FakeTools(values)).execute(_task())
    _show(f"{REAL_PLACE_NAME} @ {requested_at.isoformat()} (휴무 요일 아님)", result)

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is True
    assert result.decisions[0]["operating"]["weekday_match"] is False
    assert result.decisions[0]["operating"]["usetime_text"] == "09:00~18:00"


@pytest.mark.asyncio
async def test_a_real_place_on_its_closure_weekday_is_marked_infeasible_with_caveat():
    """경복궁 · 2026-09-22(화) 15시 — 정기휴무 요일과 일치하면 `feasible: False`.

    ★공휴일 예외는 반영하지 않았다는 캐비앗이 answer에 **반드시** 같이 나가야
      한다 — 그 캐비앗이 빠지면 "요일만 본 근사 판정"이 "확정 판정"처럼
      보이게 된다.
    """
    requested_at = datetime(2026, 9, 22, 15, tzinfo=KST)   # ★실측: 화요일

    values = _values(operating=REAL_OPERATING, starts_at=requested_at)
    values["read.place"]["name"] = REAL_PLACE_NAME

    result = await ActivityTeam(FakeTools(values)).execute(_task())
    _show(f"{REAL_PLACE_NAME} @ {requested_at.isoformat()} (휴무 요일)", result)

    assert result.outcome == "completed"
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["operating"]["weekday_match"] is True
    assert "정기휴무 요일" in result.answer
    assert "공휴일과 겹치는 경우" in result.answer   # ★예외 미반영 캐비앗
    assert any("예외 조건" in warning for warning in result.warnings)
