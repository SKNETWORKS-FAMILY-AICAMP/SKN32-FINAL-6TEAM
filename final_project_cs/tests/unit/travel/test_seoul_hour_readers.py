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


# ── 검증 세션의 두 번째 지적(알림 문구 · 지도 날짜 · 변경 링크 · 날씨) ──────────────────
def test_the_replan_clock_helpers_read_seoul_time():
    from app.modules.travel_ops.replan import _hm, _part_of_day

    noon_in_utc = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)                  # 서울 12:00
    assert _hm(noon_in_utc) == "12:00" and _part_of_day(noon_in_utc) == "오후"
    assert _part_of_day(datetime(2026, 10, 6, 0, 30, tzinfo=UTC)) == "오전"   # 서울 09:30


def test_the_item_view_carries_seoul_times_so_the_map_groups_days_in_seoul():
    """지도의 날짜 묶음은 `starts_at[:10]` 이다 — UTC 로 적힌 서울 아침 8시(전날 23:00Z)가 전날로 묶이던 것을 막는다."""
    from app.modules.travel_ops.trip_api import _item_view

    morning = _item(1, "activity", "경복궁", "08:00", day=6, tz=UTC)
    view = _item_view(morning)
    assert view["starts_at"].startswith("2026-10-06T08:00") and view["starts_at"].endswith("+09:00")


def test_the_change_link_page_prints_seoul_clock_times():
    from app.modules.travel_ops.change_link import _when

    start = datetime(2026, 10, 6, 3, 0, tzinfo=UTC).isoformat()            # 서울 12:00
    end = datetime(2026, 10, 6, 4, 0, tzinfo=UTC).isoformat()              # 서울 13:00
    assert _when(start, end) == "2026-10-06 12:00–13:00"
    assert _when(start, None) == "2026-10-06 12:00" and _when(None, None) is None
    assert _when("not-a-time", None) == "not-a-time"                       # 읽을 수 없으면 있는 그대로(지어내지 않는다)


def test_the_open_meteo_source_picks_the_forecast_slot_in_seoul_time(monkeypatch):
    """`astimezone()`(인자 없음)은 **서버 PC 의 시간대**로 바꾼다 — 서울이 아닌 서버에서는 예보 칸이 어긋난다. 서울로 바꿔 고른다.
    (이 PC 가 서울이라 옛 코드도 여기서는 통과한다 — 서울이 아닌 서버를 흉내 낼 수 없어, 고른 칸의 시각을 직접 본다.)"""
    from app.infrastructure.travel.open_meteo import OpenMeteoWeather

    seen = []
    source = OpenMeteoWeather.__new__(OpenMeteoWeather)
    monkeypatch.setattr(OpenMeteoWeather, "_days_needed", lambda self, target: seen.append(target))
    monkeypatch.setattr(OpenMeteoWeather, "_miss", lambda self, *a, **k: None, raising=False)
    source.forecast(latitude=37.5, longitude=127.0, at=datetime(2026, 10, 6, 3, 0, tzinfo=UTC))
    assert seen == [datetime(2026, 10, 6, 12, 0)]


def test_no_notice_text_formats_a_zoned_time_without_converting_it_to_seoul():
    """정적 시험(위 시험의 확장) — 알림 문구에서 변수에 담은 시각(`{starts:%H:%M}`)도 서울 변환을 거쳐야 한다. 앞 판은 `객체.starts_at:%` 꼴만 잡아 변수 꼴이 빠져나갔다.
    허용: 바로 앞에서 서울로 바꿔 둔 값(`first` · `arrival` · `start` — 각 줄 위에서 `seoul(...)`/`astimezone(kst)` 로 바꾼다)."""
    import re
    from pathlib import Path

    from app.modules.travel_ops import itinerary_changes, replan

    allowed = ("{first:%H:%M} {later[0].title}", "{arrival:%H:%M}(으)로 늦어져", "{start:%H:%M} 일정")
    bare = []
    for module in (itinerary_changes, replan):
        for line in Path(module.__file__).read_text(encoding="utf-8").splitlines():
            if re.search(r"\{(?:\w+\.)?(?:starts_at|ends_at|starts?|ends?|arrival|moment|first)(?:\[\d+\])?:%", line) and "seoul(" not in line \
                    and not any(fragment in line for fragment in allowed):
                bare.append(f"{Path(module.__file__).name}: {line.strip()[:100]}")
    assert bare == [], f"서울 변환 없이 시각을 서식에 넣는 줄: {bare}"


def test_the_open_meteo_forecast_range_counts_days_from_seoul_today(monkeypatch):
    """예보 범위(`_days_needed`)가 **서버 PC 의 오늘**(`datetime.now()`)로 센다 — 서버가 UTC 면 서울이 이미 다음 날인 시각(서울 07:00 = UTC 전날 22:00)에 하루 늦게 센다.
    서버 시계를 UTC 로 흉내 내 재현한다(이 PC 가 서울이라 진짜 시간대로는 안 된다)."""
    from app.infrastructure.travel import open_meteo

    class UtcServerClock(datetime):
        @classmethod
        def now(cls, tz=None):
            base = datetime(2026, 10, 6, 22, 0, tzinfo=UTC)               # 서울 2026-10-07 07:00
            return base.astimezone(tz) if tz else base.replace(tzinfo=None)

    monkeypatch.setattr(open_meteo, "datetime", UtcServerClock)
    assert open_meteo.OpenMeteoWeather._days_needed(datetime(2026, 10, 7, 9, 0)) == 1      # 서울 오늘 → 예보 하루
    assert open_meteo.OpenMeteoWeather._days_needed(datetime(2026, 10, 8, 9, 0)) == 2
    assert open_meteo.OpenMeteoWeather._days_needed(datetime(2026, 10, 6, 23, 0)) is None  # 서울 어제 — 범위 밖
