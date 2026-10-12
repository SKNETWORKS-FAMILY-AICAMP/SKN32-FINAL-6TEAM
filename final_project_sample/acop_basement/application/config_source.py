"""설정이 정한 출처에서 선언을 읽는다 — 파일이냐 중앙 저장소냐.

★왜 core 가 아니라 여기인가

  중앙 저장소를 고르려면 DB 커넥션이 필요하고, 그건 `infrastructure` 다.
  `acop_basement/core/**` 는 `infrastructure` 를 import 할 수 없다
  (`tests/contract/test_core_isolation.py` 가 강제한다 — 2026-08-30 에 이
  규칙을 어긴 판을 실제로 그 테스트가 잡았다). 그래서 "어디서 읽을지" 를
  정하는 해석기는 한 층 위인 application 에 둔다.

  core 의 `load_project_config(path)` 는 여전히 **파일만** 읽는다. 그건
  도메인·인프라를 모르는 순수한 로더로 남는다.

★결정 근거: `program/plan/A-COP_Composer_중앙설정저장소_결정.md`
"""
from __future__ import annotations

from pathlib import Path

from acop_basement.core.config_store import ConfigStore, PostgresConfigStore
from acop_basement.core.project_config import (
    ProjectConfig,
    config_from_declaration,
    load_project_config,
)
from acop_basement.core.settings import get_settings
from acop_basement.infrastructure.db.session import get_connection


def configured_store() -> ConfigStore | None:
    """설정이 중앙 저장소를 가리키면 그 저장소를, 아니면 `None`(=파일 모드).

    ★`config_source="central"` 인데 `deployment_id` 가 없으면 **여기서
      실패한다.** 어느 대상의 선언인지 모르는 채로 기동하면 안 된다.
    """
    settings = get_settings()
    if settings.config_source != "central":
        return None
    return PostgresConfigStore(get_connection, settings.deployment_id)


def load_active_config(path: str | Path | None = None) -> ProjectConfig:
    """지금 이 대상이 따라야 할 선언.

    경로를 주면 **언제나 그 파일**이다 — 테스트와 검증 도구가 특정 선언을
    직접 지목할 수 있어야 한다. 경로가 없으면 설정이 정한 출처를 쓴다.

    ★중앙 저장소에 못 붙거나 이 대상의 선언이 없으면 **기동을 거부한다**
      (fail-fast). 마지막 설정으로 계속 도는 캐시는 두지 않았다 — 무엇이
      켜져 있는지 모르는 채로 고객 트래픽을 받는 것이 더 위험하다.

      ★대가: 중앙 저장소가 죽으면 대상이 기동하지 못한다. 이 가용성 결합은
      결정 문서 §8 에 미해결로 적혀 있다. 캐시를 넣는다면 `degraded` 를
      반드시 함께 신호해야 한다 — 신호 없는 축소는 폴백이다(`RULE.md` §3.2).
    """
    if path is None:
        store = configured_store()
        if store is not None:
            # ★캐시하지 않는다. 중앙 선언은 언제든 바뀔 수 있고, 낡은 값을
            #   조용히 돌려주면 "바꿨는데 왜 그대로냐" 가 된다.
            deployment_id = getattr(store, "deployment_id", "?")
            return config_from_declaration(
                store.read(), source=f"<central:{deployment_id}>")
    return load_project_config(path)


__all__ = ["configured_store", "load_active_config"]
