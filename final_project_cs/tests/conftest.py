# -*- coding: utf-8 -*-
"""시험 공통 설정 — 로컬 `.env` 가 시험 결과를 바꾸지 않게 한다.

☆`[2026-09-29 자료 폴더 통일]` 이동 자료가 저장소 안(`datasets/mobility/processed`)에 들어오고 로컬 `.env` 에
  `ACOP_MOBILITY_DATA_DIR` 를 켜 두자, 그 값을 읽는 서버 조립(`build_registry`)을 거치는 모든 시험이 이동 계산기를 켰다 —
  일정 짜기가 어림값이 아니라 실제 시간표로 짜여 이동 길이·출발 문구가 달라지고, 시험 5개가 자료를 켠 컴퓨터에서만 실패했다.
  CI 에는 `.env` 가 없어 꺼져 있으니 **컴퓨터마다 결과가 다른** 시험이었다.

기본은 **꺼짐**이다. 계산기를 켜야 하는 시험은 스스로 켠다(`wiring.configure(...)` — 작은 가공 자료나 실제 시간표로).
셸에서 `ACOP_MOBILITY_DATA_DIR` 를 직접 내보내면 그 값이 이긴다(setdefault) — 켠 채로 전체를 돌려 보고 싶을 때.
"""
import os

os.environ.setdefault("ACOP_MOBILITY_DATA_DIR", "")
