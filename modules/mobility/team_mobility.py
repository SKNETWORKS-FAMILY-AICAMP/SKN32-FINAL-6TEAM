# -*- coding: utf-8 -*-
"""이동·동선 Team 모듈 — **껍데기**. 팀 저장소의 Team 모듈 자리에 놓는다.

이 파일만 계약을 만진다. 본체(`modules/mobility/adapter.py`)는 계약을 모른다.
계약이 바뀌면 **여기만** 바뀐다.

등록: config/project.yaml 에 한 줄.
    - team_id: mobility
      active: true
      implementation_ref: app.modules.<여행모듈경로>.mobility:MobilityTeam
  ※ 모듈 경로는 문서마다 다르다(아키텍처 v2 는 travel_ops/, 폴더 도면은 customer_ops/team_modules/).
    **어느 쪽이든 이 파일은 안 바뀐다** — 경로는 project.yaml 한 줄이 정한다.

라우팅: 훅이 필요 없다. [로컬 코드 registry.capability_for()]
    intent 와 같거나 'intent.' 로 시작하는 capability 를 코어가 알아서 고른다.
    → INTENT 를 코어 분류기 값에 맞추기만 하면 된다.
"""
from __future__ import annotations

from typing import Any

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask

from modules.mobility.adapter import MobilityAdapter

# ★ 코어 분류기가 이동으로 주는 intent 값. 여기 한 줄이 라우팅 전부다.
#   [결정 2026-09-14] 아키텍처 기반으로 'mobility' 를 가정한다. 분류기 값이 다르면 이 한 줄만 고친다.
INTENT = "mobility"
CAPS = [f"{INTENT}.check_route", f"{INTENT}.exception", f"{INTENT}.status"]


class MobilityTeam:
    manifest = TeamManifest(
        team_id="mobility",
        display_name="이동·동선",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=CAPS,                 # 첫 것이 기본값이 된다(capability_for)
        accepted_case_types=[INTENT],      # [로컬 코드] resolve() 는 정확히 하나로 안 좁혀지면 RegistryError
        required_context=["case_state"],   # 시간표는 우리 저장소에서 읽는다 — db_facts 불필요
        allowed_tools=[],                  # 경로 API 를 호출하지 않는다(지도 링크는 좌표로 조립)
        knowledge_scope=["mobility.timetable", "mobility.rules"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-14",
    )

    def __init__(self, verifier: Any = None) -> None:
        # 판정기는 시간표 195MB 를 든다 — 프로세스 수명 동안 **하나만** 만든다.
        if verifier is None:
            from modules.mobility.runtime import get_verifier     # 무거운 것은 늦게 든다
            verifier = get_verifier()      # 프로세스당 하나 — 약 33초 · 상주 약 91MB
        self._adapter = MobilityAdapter(
            verifier.verify_case,
            basis={"timetable_built_at": verifier.timetable_built_at,
                   "rules_version": verifier.rules_version},
            capabilities=tuple(CAPS),
        )

    async def execute(self, task: TeamTask) -> TeamResult:
        out = self._adapter.run(task)          # dict. 계약을 모르는 본체가 만든다
        return TeamResult(
            task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
            outcome=out["outcome"],
            answer=out.get("answer"),
            confidence=out["confidence"],
            evidence=[Evidence(**e) for e in out["evidence"]],
            decisions=out.get("decisions") or [],
            action_proposals=[],               # [결정 v7 B-4] 이동 모듈은 제안을 내지 않는다
            next_action=NextAction(out["next_action"]),
            failure_code=out.get("failure_code"),
            warnings=out.get("warnings") or [],
        )


__all__ = ["MobilityTeam"]
