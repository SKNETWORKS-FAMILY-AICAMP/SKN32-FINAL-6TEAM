# -*- coding: utf-8 -*-
"""판정 요청을 만든다 — Team 이 가진 값을 종류별 입력 모양으로 바꾼다.

★날짜 계산은 **코드가 한다.** 요일 · 그 달의 몇째 요일 · 마지막 주인지를 미리 넣어 준다.
  「매월 둘째 주 화요일 휴무」를 판정할 때 모델이 달력 계산을 틀리면 그 오류가 그대로 판정이 된다.
★공휴일 여부는 넣지 않는다(`is_public_holiday: None` = 모름). 이 계층은 특일 API 를 부르지 않는다 —
  「공휴일 다음날 휴무」 같은 원문은 모델이 `unknown` 으로 답해야 한다.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .types import (
    CLOSURE,
    DISASTER_EFFECT,
    LIVE_STATUS,
    OPERATING_HOURS,
    WEATHER_SENSITIVE,
    JudgeRequest,
)

KST = ZoneInfo("Asia/Seoul")
_KO_WEEKDAYS = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")


def _local(at: Any) -> datetime | None:
    """시각이 있으면 한국 시각으로. ★시간대가 없는 값은 그대로 둔다 — 현지 벽시계 시각으로 읽는다
    (`FeasibilityMixin._weekday_closure_match` 가 `starts_at.weekday()` 를 그대로 쓰는 것과 같다)."""
    if not isinstance(at, datetime):
        return None
    return at.astimezone(KST) if at.tzinfo else at


def date_facts(at: Any, *, today: date | None = None) -> dict[str, Any]:
    """시각에서 판정에 필요한 날짜 사실을 뽑는다. 시각을 모르면 시각 칸이 전부 `None`."""
    local = _local(at)
    today = today or datetime.now(KST).date()
    if local is None:
        return {"today": today.isoformat(), "starts_at": None, "date": None, "weekday": None,
                "nth_weekday_in_month": None, "is_last_weekday_in_month": None, "is_public_holiday": None}
    nth = (local.day - 1) // 7 + 1
    days_in_month = (date(local.year + local.month // 12, local.month % 12 + 1, 1) - date(local.year, local.month, 1)).days
    return {
        "today": today.isoformat(),
        "starts_at": local.isoformat(),
        "date": local.date().isoformat(),
        "weekday": _KO_WEEKDAYS[local.weekday()],
        # 「매월 둘째 주 X요일」을 위한 값 — 그 달에서 이 요일이 몇 번째인가
        "nth_weekday_in_month": nth,
        "is_last_weekday_in_month": local.day + 7 > days_in_month,
        "is_public_holiday": None,
    }


def closure(restdate_text: str | None, starts_at: Any) -> JudgeRequest:
    return JudgeRequest(CLOSURE, {"restdate_text": restdate_text, "starts_at_raw": starts_at,
                                  **date_facts(starts_at)})


def operating_hours(usetime_text: str | None, starts_at: Any) -> JudgeRequest:
    return JudgeRequest(OPERATING_HOURS, {"usetime_text": usetime_text, "starts_at_raw": starts_at,
                                          **date_facts(starts_at)})


def weather_sensitive(title: str | None, lclssystm2: str | None) -> JudgeRequest:
    return JudgeRequest(WEATHER_SENSITIVE, {"title": title, "lclssystm2": lclssystm2})


def disaster_effect(place_name: str | None, place_kind: str | None, messages: list[dict[str, Any]],
                    starts_at: Any) -> JudgeRequest:
    kept = [{key: m.get(key) for key in ("kind", "step", "text", "regions", "created_at")} for m in messages]
    return JudgeRequest(DISASTER_EFFECT, {
        "place_name": place_name, "place_kind": place_kind, "messages": kept,
        # 인용 대조용 — 문자 본문만 모은다
        "message_texts": [str(m.get("text") or "") for m in kept],
        "starts_at_raw": starts_at, **date_facts(starts_at)})


def live_status(place_name: str | None, place_kind: str | None, address: str | None,
                starts_at: Any) -> JudgeRequest:
    return JudgeRequest(LIVE_STATUS, {"place_name": place_name, "place_kind": place_kind,
                                      "address": address, "starts_at_raw": starts_at,
                                      **date_facts(starts_at)})
