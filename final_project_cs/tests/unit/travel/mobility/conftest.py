# -*- coding: utf-8 -*-
"""이동 모듈 시험 폴더의 pytest 설정 — 두 층(71번 방 · 2026-09-29).

★**팀원 게이트(기본)** — `pytest tests/unit/travel/mobility -q` 로 도는 것.
  데이터 없이 도는 단위 + 회귀 게이트(주요 기능 21건 · regression_gate_v1.json). 노트북 2분 19초(데이터 있음). CI 도 이것.
★**우리 전체** — `pytest tests/unit/travel/mobility -m "mobility_full and not live" -q`(GPT 대조 ②: `-m` 을 주면 팀
  pytest.ini 의 `not live` 가 대체되므로 같이 적는다 · 지금 live 마커가 붙은 우리 시험은 없다).
  실데이터 회귀 나머지(171 − 21 = 150) + 실데이터 단위 23(plan_concurrency · plan_estimate · plan_bike 의 DATA_DIR 축).
  방을 닫을 때 우리가 돌린다. 잠그는 것은 줄이지 않았다 — 층만 나눴다.

마커 등록과 기본 실행에서의 제외를 **이 폴더 안에서만** 한다 — 팀 pytest.ini 는 만지지 않는다.
(팀장님이 원하면 pytest.ini 의 addopts 를 `-m "not live and not mobility_full"` 로 바꾸고
 markers 에 `mobility_full` 을 한 줄 더하는 것으로 이 파일의 두 훅을 대체할 수 있다.)

기본 실행에서 mobility_full 항목은 skip 이 아니라 **deselect** 다 — 요약 줄에 「N deselected」로만 보인다.
`-m` 식에 mobility_full 이 들어 있으면(예: `-m mobility_full`) 아무것도 빼지 않는다.
★`-k` 만으로 전체층 시험을 고르면 deselect 돼 「no tests ran」(exit 5) — 전체층 한 건은 `-m mobility_full -k <id>` 로.
"""
from __future__ import annotations

from pathlib import Path


HERE = Path(__file__).resolve().parent
MARK = "mobility_full"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"{MARK}: 이동 모듈 전체층 — 실데이터 회귀 나머지 + 무거운 단위. `-m {MARK}` 로만 돈다(71번 방)")


def pytest_collection_modifyitems(config, items):
    expr = config.getoption("-m") or ""          # 팀 pytest.ini 가 -m "not live" 를 늘 주므로 식은 항상 있다
    if MARK in expr:
        return
    keep, drop = [], []
    for it in items:
        under_here = Path(str(it.fspath)).resolve().is_relative_to(HERE)
        if under_here and it.get_closest_marker(MARK):
            drop.append(it)
        else:
            keep.append(it)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep
