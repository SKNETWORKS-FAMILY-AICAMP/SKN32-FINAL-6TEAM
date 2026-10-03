# -*- coding: utf-8 -*-
"""시각의 「시(hour)」 · 날짜를 직접 읽는 곳도 **서울 시각**으로 읽는다 — H3 의 같은 가족. `[2026-10-03 ui 검증 세션 지적]`

☆결함: 판정기(`check_itinerary`)는 2026-10-03 에 서울 시각으로 고쳤지만, 일정 항목의 `starts_at.hour` / `.date()` 를 **받은 시간대 그대로** 읽는 곳이 남아 있었다 —
화면의 끼니 이름표(`trip_api._meal_label` — 주석은 「KST」라고 했지만 `_seoul` 이 시간대 있는 값을 안 바꿨다) · 되돌리기 안내의 자리 이름표(`_slot`) · 채팅의 「점심 식당」 찾기 두 곳.
DB 세션 시간대가 서울이 아니면(UTC 서버) 서울 12:00 점심(UTC 03:00)이 「아침」으로 보이고, 「점심 식당 바꿔 줘」가 엉뚱한(또는 없는) 식사를 가리켰다.
이 PC 의 DB 세션이 서울이라 **여기서는 재현되지 않는다** — 시험은 UTC 로 온 시각으로 만든다.

재현:

    python -m pytest tests/unit/travel/test_seoul_hour_readers.py -v
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc


def _item(seq, kind, title, hhmm, *, day=6, tz=UTC):
    """서울 `hhmm` 의 항목 — 시각은 `tz` 로 적은 같은 순간."""
    hour, minute = map(int, hhmm.split(":"))
    moment = datetime(2026, 10, day, hour, minute, tzinfo=KST).astimezone(tz)
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=uuid4(), starts_at=moment,
                ends_at=moment.replace(minute=moment.minute), place={"name": title, "attributes": {}}, detail={})


def test_the_seoul_helper_converts_a_zoned_time_and_attaches_seoul_to_a_naive_one():
    from app.modules.travel_ops.trip_api import _seoul

    assert _seoul(datetime(2026, 10, 6, 3, 0, tzinfo=UTC)).hour == 12 and _seoul(datetime(2026, 10, 6, 3, 0, tzinfo=UTC)).tzinfo is not None
    assert _seoul(datetime(2026, 10, 6, 12, 0)).hour == 12 and _seoul(None) is None


def test_the_meal_label_is_the_same_whatever_zone_the_time_arrives_in():
    from app.modules.travel_ops.trip_api import _meal_label

    for tz in (KST, UTC):
        assert _meal_label(_item(1, "dining", "아침", "07:30", tz=tz)) == "아침"
        assert _meal_label(_item(2, "dining", "점심", "12:00", tz=tz)) == "점심"
        assert _meal_label(_item(3, "dining", "저녁", "19:00", tz=tz)) == "저녁"


def test_the_rollback_slot_name_is_in_seoul_time():
    from app.modules.travel_ops.itinerary_changes import _slot

    first_day = date(2026, 10, 6)
    for tz in (KST, UTC):
        assert _slot(_item(1, "dining", "점심", "12:00", tz=tz), first_day) == "1일차 점심"
        assert _slot(_item(2, "dining", "저녁", "19:00", day=7, tz=tz), first_day) == "2일차 저녁"
        assert _slot(_item(3, "activity", "경복궁", "10:00", day=7, tz=tz), first_day) == "2일차 10:00 일정"


def test_a_meal_word_in_a_question_finds_the_meal_whatever_zone_the_times_are_in():
    from app.modules.travel_ops.itinerary_team import mentioned_item

    for tz in (KST, UTC):
        lunch, dinner = _item(1, "dining", "한식당", "12:00", tz=tz), _item(2, "dining", "고깃집", "19:00", tz=tz)
        assert mentioned_item([lunch, dinner], "점심 식당 알려줘") is lunch
        assert mentioned_item([lunch, dinner], "저녁 식당 알려줘") is dinner


def test_the_change_target_finds_the_meal_by_its_meal_word_in_seoul_time():
    from app.modules.travel_ops.trip_messages import _change_target

    at = datetime(2026, 10, 6, 9, 0, tzinfo=KST)
    for tz in (KST, UTC):
        lunch, dinner = _item(1, "dining", "한식당", "12:00", tz=tz), _item(2, "dining", "고깃집", "19:00", tz=tz)
        assert _change_target([lunch, dinner], "점심 식당 바꿔 줘", None, at) is lunch
        assert _change_target([lunch, dinner], "저녁 식당 바꿔 줘", None, at) is dinner


def test_customer_notice_texts_format_clock_times_in_seoul():
    """변경 알림 문구의 「HH:MM」 · 「M월 D일」은 서울 시계로 찍는다 — 시간대 있는 값을 서식에 그대로 넣으면 DB 세션이 UTC 일 때 9시간 어긋난 시각이 고객에게 간다.
    (소스를 훑는 정적 시험 — 알림 함수마다 후보 · 원장 · 장소 표를 차려야 해서 각 문장을 따로 돌리는 것은 값이 맞지 않는다.)"""
    import re
    from pathlib import Path

    from app.modules.travel_ops import itinerary_changes

    source = Path(itinerary_changes.__file__).read_text(encoding="utf-8")
    bare = [line.strip() for line in source.splitlines() if re.search(r"\b\w+\.(starts_at|ends_at):%", line)]
    assert bare == [], f"서울 변환 없이 시각을 서식에 넣는 줄: {bare}"
