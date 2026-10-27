# -*- coding: utf-8 -*-
"""`[2026-10-27 TeamFlow ST4F-685]` 「…가동 중지될 수 있음」의 「수」는 수요일이 아니다.

공공데이터 안내 문구의 「~ㄹ 수 있음 · 없음」을 요일 「수」로 읽어 멀쩡한 수요일을 휴무로 판정했다(휴무 규칙 날짜 범위 수정 0300c735 중 발견).
요일 한 글자 뒤에 「있 · 없」이 오면 요일이 아니다 — 요일 말 읽기(`place_hours.days_in`)와 휴무 판정(`closure_rules`)이 같은 규칙을 쓴다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.places.place_hours import days_in
from app.domains.travel_ops.instances.activity.closure_rules import read_closure

KST = timezone(timedelta(hours=9))
WED = datetime(2030, 11, 6, 12, tzinfo=KST)


def no_holiday(day):
    return {"is_holiday": False, "holiday_name": None}


@pytest.mark.parametrize("text", ["기상 상황에 따라 가동 중지될 수 있음", "시설 점검 시 운영 중지될 수 있음",
                                  "우천 시 입장할 수 없음", "사정에 따라 바뀔 수 있습니다"])
def test_the_modal_su_is_not_wednesday(text):
    assert days_in(text) == set(), text
    assert read_closure(text, WED, no_holiday).value is not True, "수요일을 휴무로 판정하지 않는다"


@pytest.mark.parametrize("text", ["매주 수요일 휴무", "매주 수 휴무", "월, 수 휴관", "수~금 휴무"])
def test_a_real_wednesday_is_still_read(text):
    assert "wed" in days_in(text), text
    assert read_closure(text, WED, no_holiday).value is True
