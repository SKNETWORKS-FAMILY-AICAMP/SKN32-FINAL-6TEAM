"""시험 자료의 날짜를 **실행하는 날 기준**으로 옮기는 공용 helper.

★`[2026-10-28]` 「모든 일정이 오늘 이전」 등록 거절(`itinerary_checks.all_dates_before_today`)은 실제 시계를 읽는다.
  날짜를 박아 둔 대본·접수 자료는 그 날이 지나면 실행 날짜만으로 422 가 된다. 예전에는 `tests/conftest.py` 가 가드의 시계를
  2026-08-01 로 전역 고정했다(임시 조치). 이제는 자료 쪽을 옮긴다.

- `epoch_shift()` — 모든 시험 자료가 함께 쓰는 **한 가지 이동 폭**(7의 배수). 자료 기준일 `FIXTURE_EPOCH`(2026-08-01, 박아 둔
  어느 날짜보다 앞) 을 **오늘 + 최소 7일 이후의 같은 요일**로 보내는 날 수다. 파일끼리 자료를 import 해도 같은 폭이라 어긋나지 않고,
  요일 · 날짜 순서 · 날짜 간격이 원래 자료와 같다(요일로만 정해지는 휴무 · 영업시간 판정은 그대로다).
  ☆n번째 요일 · 특정 월 휴무 · 공휴일 · 공휴일표 범위처럼 **달력 날짜 자체**에 걸린 판정은 지키지 못한다 — 그런 시험은 옮기지 않는다(아래). 7일 여유가 있어 자정을 넘겨 도는 실행에서도 과거가 되지 않는다.
  폭은 한 실행에서 처음 부를 때 한 번 정한다.
- `day("2026-10-15")` — 그 날짜를 같은 폭만큼 옮긴 ISO 날짜. `moved(date(...))` / `moved(datetime(...))` 은 객체용.
- `shifted(value)` — dict/list/문자열 안의 **값 전체가 ISO 날짜·시각인 문자열**만(dict 키 포함) 옮긴 사본.
  `"2026-09-24.v1"` 같은 판 이름 · 문장 속 숫자는 건드리지 않는다(값 전체 일치만).
- `shift_text(text)` — 날짜가 **문장 속에** 있는 시험 입력용. ISO 날짜(`2026-10-15`)만 옮긴다.
- `weeks_ahead(anchor)` — 임의 기준일용 같은 계산. `relative_day(n)` — 서울 기준 오늘 + n일.
- `clock_class(now)` — 제품 모듈의 `datetime.now()` 를 재생 시각에 맞추는 대역(`isinstance` 판정은 그대로).

특정 날짜 자체가 의미인 시험(공휴일 표 · 특정 달력 날짜)은 이 helper 를 쓰지 말고 그 시험에서만 시계를 주입한다
(`monkeypatch.setattr(itinerary_checks, "datetime", ...)` 또는 `now=`).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

#: 값 전체가 날짜(또는 날짜+시각)인 문자열. 뒤는 그대로 둔다.
_WHOLE = re.compile(r"^(\d{4}-\d{2}-\d{2})((?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?)$")
_INLINE = re.compile(r"(?<![\d-])(\d{4}-\d{2}-\d{2})(?![\d])")


#: 박아 둔 시험 날짜 중 가장 이른 날(2026-08-17)보다 앞선 기준일 — 예전 전역 시계 고정 값과 같다.
FIXTURE_EPOCH = date(2026, 8, 1)


def today() -> date:
    """서울 기준 오늘."""
    return datetime.now(KST).date()


def relative_day(n: int) -> date:
    return today() + timedelta(days=n)


def weeks_ahead(anchor: date | str, *, min_days: int = 7) -> int:
    """`anchor + 반환값` 이 `오늘 + min_days` 이후의 같은 요일이 되는 가장 작은 7의 배수(음수일 수 있다)."""
    first = date.fromisoformat(anchor) if isinstance(anchor, str) else anchor
    floor = relative_day(min_days)
    weeks = -((first - floor).days // 7)   # ceil((floor - first) / 7)
    return weeks * 7


_SESSION: dict[str, int] = {}


def epoch_shift() -> int:
    """모든 시험 자료가 함께 쓰는 이동 폭. 한 실행(프로세스)에서 **처음 부른 순간** 한 번 정하고 계속 같은 값을 준다 —
    자정을 넘겨 도는 실행에서 먼저 import 한 파일과 나중 파일의 폭이 갈리면 import 해 쓰는 자료끼리 어긋나기 때문이다."""
    if "days" not in _SESSION:
        _SESSION["days"] = weeks_ahead(FIXTURE_EPOCH)
    return _SESSION["days"]


def _days(days: int | None) -> int:
    return epoch_shift() if days is None else days


def day(text: str, days: int | None = None) -> str:
    """ISO 날짜 하나를 옮긴다 — `day("2026-10-15")`."""
    return _shift_day(text, _days(days))


def moved(value: date | datetime, days: int | None = None) -> date | datetime:
    """date/datetime 객체를 옮긴다 — 시각 · 시간대는 그대로."""
    return value + timedelta(days=_days(days))


#: 진짜 datetime — 이 모듈의 `datetime` 이름은 시험이 시계 대역으로 바꿔 끼울 수 있다(`_AnyDatetime` 판정은 진짜 형으로).
_REAL_DATETIME = datetime


class _AnyDatetime(type):
    """`isinstance(x, 바꾼_datetime)` 이 보통 datetime 에도 참이 되게 한다 — 모듈의 `datetime` 이름을 바꿔 끼워도
    그 모듈의 `isinstance(at, datetime)` 판정은 그대로다."""

    def __instancecheck__(cls, obj):
        return isinstance(obj, _REAL_DATETIME)

    def __subclasscheck__(cls, sub):
        return issubclass(sub, _REAL_DATETIME)


def clock_class(now: Callable[[], datetime]) -> type:
    """`now()` 만 주어진 시계를 따르는 datetime 대역 — `monkeypatch.setattr(모듈, "datetime", clock_class(...))` 용.

    재생 시험이 제품 모듈의 벽시계를 재생 시각으로 맞출 때 쓴다(예: 대기질 예보 범위 72시간 판정).
    ☆`now(tz)` 는 그 시각을 `tz` 로 바꿔 준다. `now()`(시간대 없음)는 시스템 지역 시각이 아니라 **주어진 시각의 벽시계 값**에서
      시간대만 뗀 것이다 — 바꿔 끼우는 모듈이 `now(UTC)` 처럼 시간대를 넘기는지 먼저 확인한다."""

    class Clocked(_REAL_DATETIME, metaclass=_AnyDatetime):
        @classmethod
        def now(cls, tz=None):
            moment = now()
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

    return Clocked


def _shift_day(text: str, days: int) -> str:
    return (date.fromisoformat(text) + timedelta(days=days)).isoformat()


def shift_iso(text: str, days: int | None = None) -> str:
    days = _days(days)
    matched = _WHOLE.match(text)
    if not matched:
        return text
    return _shift_day(matched.group(1), days) + matched.group(2)


def shift_text(text: str, days: int | None = None) -> str:
    days = _days(days)
    return _INLINE.sub(lambda m: _shift_day(m.group(1), days), text)


def shifted(value: Any, days: int | None = None) -> Any:
    """`value` 의 사본 — 값 전체가 ISO 날짜·시각인 문자열만(dict 키 포함) `days`(기본 `epoch_shift()`) 일 옮긴다."""
    days = _days(days)
    if isinstance(value, str):
        return shift_iso(value, days)
    if isinstance(value, dict):
        return {shifted(k, days) if isinstance(k, str) else k: shifted(v, days) for k, v in value.items()}
    if isinstance(value, list):
        return [shifted(v, days) for v in value]
    if isinstance(value, tuple):
        return tuple(shifted(v, days) for v in value)
    return value
