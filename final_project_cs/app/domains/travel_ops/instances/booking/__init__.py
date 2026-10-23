# -*- coding: utf-8 -*-
"""Booking Module(예약 모듈) 폴더 — 항공편 찾기(2026-10-08), `[2026-10-14]` 규칙 기반 예약 모듈로 이름을 바꿨다(옛 `instances/flight/`).
본체는 `team.py`, 규칙 해석은 `interpret_rules.py`, 해석 결과 검증은 `interpret.py`.

등록 문자열은 `app.domains.travel_ops.instances.booking:BookingTeam` 이다(`config/project.yaml`). `team_id` 는 아직 `flight`.
"""
from .team import BookingTeam, FlightTeam

__all__ = ["BookingTeam", "FlightTeam"]
