# -*- coding: utf-8 -*-
"""여행 도메인 외부 데이터 어댑터.

★**왜 `app/infrastructure/` 인가.** 바깥으로 나가는 I/O 는 전부 여기다.
  `app/tools/read_tools.py` 는 **이름 → 함수** 표일 뿐이고, HTTP 를 알면
  안 된다. Team 은 더더욱 모른다 — Team 이 아는 것은 `read.weather` 라는
  **이름 하나**다. 그래서 공급자를 갈아끼워도 Team 은 안 바뀐다.

★**폴백 금지**(`RULE.md` §3.2). 못 가져오면 `None`(모름)이다. 기본값·평균값·
  지난번 값으로 조용히 메우지 않는다. 그 오류는 그대로 고객 답변까지 간다.
"""
from .base import SourceMiss, TravelSource, TravelSources, build_travel_sources
from .heritage import HeritageSource
from .holiday import HolidaySource
from .open_meteo import OpenMeteoWeather

__all__ = [
    "HeritageSource",
    "HolidaySource",
    "OpenMeteoWeather",
    "SourceMiss",
    "TravelSource",
    "TravelSources",
    "build_travel_sources",
]
