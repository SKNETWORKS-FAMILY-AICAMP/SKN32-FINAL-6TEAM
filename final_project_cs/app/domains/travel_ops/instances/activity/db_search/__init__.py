# -*- coding: utf-8 -*-
"""우리 DB(`place_catalog` 등)를 읽는 조회 함수 모음.

★여기 함수는 **연결 공장(connection_factory)을 인자로 받는다** — 직접 접속하지
  않는다. `app/tools/read_tools.py` 의 `ReadToolbox` 가 자기 연결 공장을 넘겨
  부르고, 테스트는 가짜 연결을 넘긴다.
"""
from app.domains.travel_ops.instances.activity.db_search.place_candidates import find_place_candidates

__all__ = ["find_place_candidates"]
