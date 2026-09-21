# -*- coding: utf-8 -*-
"""`config/project.yaml` 이 쓰는 구현 참조가 **Composer 로 저장 가능한지** 본다.

★2026-09-09 실제 사고. 등록을 여행으로 갈아끼우면서
  `KNOWN_IMPLEMENTATION_REFS`(코어 allowlist)와 `IMPLEMENTATIONS`(Composer
  카탈로그)를 **둘 다 안 고쳤다.** 그런데:

    - `build_registry()` 는 이 표를 **보지 않는다** → 앱이 멀쩡히 뜬다
    - `python -m pytest` 도 대부분 초록이었다
    - `/composer/apply` 만 422 `invalid_declaration` 로 거부했다

  즉 **지금 도는 선언을 Composer 로는 저장할 수 없는 상태**였고, 그것을
  잡은 것은 e2e 하나뿐이었다. 그 e2e 는 동시성을 보는 테스트라 실패 메시지가
  `[422, 422] != [200, 409]` 였다 — 원인을 전혀 말해 주지 않았다.

★그래서 **선언 → allowlist → 카탈로그** 세 곳의 어긋남을 직접 센다.
  `tests/architecture/test_composer_stays_out_of_this_repo.py` 는
  allowlist 와 카탈로그 **둘 사이**만 봤고, 정작 **선언**은 아무도 안 봤다.
"""
from __future__ import annotations

from app.composer_host import IMPLEMENTATIONS
from app.core.project_config import KNOWN_IMPLEMENTATION_REFS, load_project_config


def test_every_declared_ref_is_in_the_core_allowlist():
    config = load_project_config()
    declared = {team.implementation_ref for team in config.teams}
    missing = sorted(declared - set(KNOWN_IMPLEMENTATION_REFS))
    assert not missing, (
        f"config/project.yaml 이 쓰는데 allowlist 에 없는 참조: {missing}\n"
        f"  → `/composer/apply` 가 이 선언을 422 로 거부한다. "
        f"`app/core/project_config.py` 의 KNOWN_IMPLEMENTATION_REFS 에 넣는다.")


def test_every_declared_ref_is_offered_by_the_composer_catalog():
    config = load_project_config()
    declared = {team.implementation_ref for team in config.teams}
    missing = sorted(declared - {item.ref for item in IMPLEMENTATIONS})
    assert not missing, (
        f"config/project.yaml 이 쓰는데 Composer 카탈로그에 없는 참조: {missing}\n"
        f"  → 콘솔에서 이 팀을 고를 수 없다. "
        f"`app/composer_host.py` 의 IMPLEMENTATIONS 에 넣는다.")


def test_the_declaration_is_not_empty():
    """★위 두 검사는 선언이 비면 공집합끼리 비교해 통과한다."""
    assert load_project_config().teams, "config/project.yaml 에 Team 선언이 없다."
