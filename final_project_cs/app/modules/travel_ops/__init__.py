# -*- coding: utf-8 -*-
"""여행 도메인 Team 모듈 (계획서 v10 §5).

★**Registry 등록형이라 코어는 한 줄도 안 바뀐다** — 이 아키텍처가 도메인 교체를
  견딘다는 주장을 실제로 시험한 자리다. 2026-09-09 에 등록을 여기로 옮기고
  2026-09-10 에 커머스 구현(`app/modules/customer_ops/`, 1,585줄)을 걷어냈는데,
  `app/core`·`app/domain`·`app/application` 은 **라우팅 축 한 줄**을 빼고
  손대지 않았다(`app/application/routing.py`, v11 §5-B).

  실측(2026-09-09): 교체 대상은 `app/modules` 1,585줄 = 저장소의 5.9% 이고
  나머지 94.1%(코어·인프라·평가 하네스·도메인 무관 테스트 8,730줄)는 그대로 산다.
  저장소를 새로 파면 94% 를 옮겨 다시 증명하고 6% 를 갈아끼우는 셈이다.

★옛 커머스 구현이 필요하면 2026-09-10 이전 커밋을 본다. 「같은 엔진이 다른
  도메인도 섬긴다」는 대조군은 코드가 아니라 검사로 남겼다 —
  `tests/architecture/test_engine_serves_another_domain.py`.
"""
from .activity import ActivityTeam
from .booking_handoff import BookingHandoffTeam
from .dining import DiningTeam
from .locked_bookings import FlightTeam, LodgingTeam
from .mobility import MobilityTeam

__all__ = [
    "ActivityTeam",
    "BookingHandoffTeam",
    "DiningTeam",
    "FlightTeam",
    "LodgingTeam",
    "MobilityTeam",
]
