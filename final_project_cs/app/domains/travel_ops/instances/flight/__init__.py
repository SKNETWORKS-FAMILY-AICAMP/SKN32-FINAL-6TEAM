# -*- coding: utf-8 -*-
"""Flight Team 폴더 — 항공편 찾기(2026-10-08). 본체는 `team.py`, 모델 출력 검증은 `interpret.py`.

등록 문자열은 `app.domains.travel_ops.instances.flight:FlightTeam` 이다(`config/project.yaml`).
"""
from .team import FlightTeam

__all__ = ["FlightTeam"]
