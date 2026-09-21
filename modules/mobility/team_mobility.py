# -*- coding: utf-8 -*-
"""이동·동선 Team 모듈 — **껍데기**. 팀 저장소의 Team 모듈 자리에 놓는다.

이 파일만 계약을 만진다. 본체(`final_project_cs/app/modules/travel_ops/mobility_engine/adapter.py`)는 계약을 모른다.
계약이 바뀌면 **여기만** 바뀐다.

등록: config/project.yaml 에 한 줄.
    - team_id: mobility
      active: true
      implementation_ref: app.modules.<여행모듈경로>.mobility:MobilityTeam
  ※ 모듈 경로는 문서마다 다르다(아키텍처 v2 는 travel_ops/, 폴더 도면은 customer_ops/team_modules/).
    **어느 쪽이든 이 파일은 안 바뀐다** — 경로는 project.yaml 한 줄이 정한다.

라우팅: **두 축이다.** [확정 · 팀 develop d57b751 실물 · 2026-09-20]
    팀 선택   case_type = issue_code 의 접두(`mobility_*` → `mobility`). accepted_case_types 와 맞춘다.
    갈래 선택 intent = 요청 종류 5종(itinerary_submit·incident_report·confirm_request·adjust_reject·other).
              `mobility` 라는 intent 는 없다 → 네임스페이스 매칭은 절대 안 걸린다.
              그래서 **이 클래스의 select_capability()** 가 intent → capability 를 정한다.
    ※ 코어 훅이 아니다. registry.capability_for() 가 모듈 메서드를 먼저 묻는다. 코어 수정 0.
    ※ 9/14 의 「훅이 필요 없다」는 커머스 판(case_type == intent) 근거였고 여행 판에서 틀렸다.
"""
from __future__ import annotations

from typing import Any

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask

from app.modules.travel_ops.mobility_engine.adapter import MobilityAdapter

# ★ 두 값이 우연히 같은 글자일 뿐 **다른 축**이다. 9/14 판은 INTENT 하나로 둘을 겸해서 갈래가 안 갈렸다.
CASE_TYPE = "mobility"      # issue_code 접두 — 팀을 고른다 [feedback.ISSUE_CODES]
NS = "mobility"             # capability 네임스페이스 — 팀장 뼈대 이름을 따른다(◆7 기본값)
CAPS = [f"{NS}.check_route", f"{NS}.exception", f"{NS}.status"]

# ★ intent → capability. 여기 없는 intent 는 None → default_capability(check_route).
#   [결정 2026-09-20] 문구 표식("놓쳤"…)이 아니라 **intent 로만** 가른다 —
#   controller 는 ROUTED 이벤트 자리에서 input_text 없이 capability_for() 를 부른다.
#   문구로 가르면 이벤트 기록과 실제 task 의 capability 가 갈린다. intent 는 두 자리에 똑같이 온다.
#   점검: tests/mobility/contract/check_routing.py (분류기 어휘가 바뀌면 거기서 깨진다)
BY_INTENT = {
    "incident_report": f"{NS}.exception",   # 사건 신고 → 차질 반영 재판정
    "confirm_request": f"{NS}.status",      # 확인 요청 → 재확인(F2)
}

class MobilityTeam:
    manifest = TeamManifest(
        team_id="mobility",
        display_name="이동·동선",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=CAPS,
        accepted_case_types=[CASE_TYPE],  # resolve() 는 정확히 하나로 안 좁혀지면 RegistryError
        required_context=["case_state"],   # 시간표는 우리 저장소에서 읽는다 — db_facts 불필요
        allowed_tools=[],                  # 경로 API 를 호출하지 않는다(지도 링크는 좌표로 조립)
        knowledge_scope=["mobility.timetable", "mobility.rules"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-20",
        default_capability=CAPS[0],        # 폴백을 「첫 번째라서」가 아니라 선언으로 둔다
    )

    @staticmethod
    def select_capability(intent: str | None, input_text: str) -> str | None:
        """intent → capability. input_text 는 **일부러 안 본다**(위 BY_INTENT 주석)."""
        return BY_INTENT.get(intent or "")

    def __init__(self, verifier: Any = None) -> None:
        # 판정기는 시간표 195MB 를 든다 — 프로세스 수명 동안 **하나만** 만든다.
        if verifier is None:
            from app.modules.travel_ops.mobility_engine.runtime import get_verifier     # 무거운 것은 늦게 든다
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
