# -*- coding: utf-8 -*-
"""booking · offers — 예매가 필요한 것(항공 · 숙소, 차후 철도 · 활동 · 식당)을 여러 판매처에서 찾아 비교하고 판매처 링크를 준다. `[2026-10-10]`

★`components/booking/` 에는 이미 잡은 예약의 변경 링크(`change_link.py`) · 위임 범위(`delegation.py`)가 있다 — 예약을 「관리」하는 쪽이다.
  이 폴더는 예약 **전**에 「찾고 비교하는」 쪽이라 같은 booking 아래 하위 폴더로 둔다(그 둘은 건드리지 않는다).

에이전트 → booking 모듈의 비교 부분(이 폴더, `components/booking/offers/`) → 어댑터(`ports/data_sources/`) → 결과. 결제 · 예약은 하지 않는다(판매처 사이트에서).
위치 · 경로 계산은 이동 모듈이 맡는다. 도구 이름은 `read.booking_search_flights` · `read.booking_search_stays` —
이미 있는 `read.booking`(잠긴 예약 조회)과 겹치지 않게 동사를 붙였다.
"""
from .flights import search_flights
from .stays import search_stays

__all__ = ["search_flights", "search_stays"]
