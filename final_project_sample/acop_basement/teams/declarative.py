"""선언형 Team 범용 실행기.

지금까지 새 Agent Team 을 하나 늘리려면 Python 을 새로 써서 배포해야 했다.
이 실행기를 **한 번** 배포해 두면, 이후 새 Team 은 코드 없이 선언(데이터)만으로
만든다 — `config/project.yaml` 의 `teams[].parameters` 가 그 선언이다.

★설계 경계 (`docs/plans/2026-08-28_선언형Team_카탈로그CRUD_계획.md` §2.3)

1. **읽기 전용이다.** `ActionProposal` 을 만들지 않는다. 조회·정리·초안까지다.
   side effect 가 필요하면 코드형 Team 을 써야 한다 — 선언(프롬프트)은 신뢰
   경계 밖의 입력이라, 거기서 결제·환불 제안이 나오게 두면 프롬프트 인젝션이
   곧 업무 조작이 된다.
2. **grant ceiling 은 로드 시점에 이미 걸렸다.** `allowed_tools` 가 읽기 전용
   접두사 밖이면 `load_project_config()` 가 거부한다
   (`acop_basement/core/project_config.py`). 여기서 다시 검사하는 것은
   방어적 중복이 아니라 `ReadToolbox` 가 원래 하는 일이다.
3. **근거 없으면 답을 만들지 않는다.** tool 이 아무 사실도 못 주면 escalate
   한다(`CLAUDE.md` §0.1). 조용히 일반 지식으로 메우지 않는다.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from acop_basement.core.contracts import (
    Evidence,
    NextAction,
    TeamManifest,
    TeamResult,
    TeamTask,
)
from acop_basement.core.project_config import DeclarativeTeamParameters
from acop_basement.tools.read_tools import ReadToolbox, ToolLoopExceeded, ToolNotAllowed

#: 선언에서 만들어진 manifest 임을 표시한다. 코드형 Team 의
#: `implementation_revision`("2026-08-12" 같은 날짜)과 구분된다.
DECLARATIVE_REVISION = "declarative.v1"


class LLM(Protocol):
    async def complete(self, prompt_key: str, input_text: str,
                       context: dict[str, Any]) -> dict[str, Any]: ...


class DeclarativeTeamRuntime:
    """`TeamModule` 을 만족하는 범용 실행기.

    Core 는 이 클래스가 선언에서 왔는지 코드에서 왔는지 모른다 — `manifest` 와
    `execute()` 라는 같은 창으로만 본다(`acop_basement/core/contracts.py` 의
    `TeamModule`). 그래서 Registry·Controller·승인 경계가 그대로 재사용된다.
    """

    def __init__(self, tools: ReadToolbox, llm: LLM | None = None,
                 parameters: DeclarativeTeamParameters | dict[str, Any] | None = None,
                 team_id: str = "declarative") -> None:
        if parameters is None:
            raise ValueError("DeclarativeTeamRuntime 은 parameters 가 있어야 한다")
        if not isinstance(parameters, DeclarativeTeamParameters):
            parameters = DeclarativeTeamParameters.model_validate(parameters)
        self.tools = tools
        self.llm = llm
        self.parameters = parameters
        # ★선언에 없는 필수 계약 필드는 실행기가 채운다. 선언이 계약 버전을
        #   고르게 두면 낡은 버전을 박아 넣은 선언이 조용히 살아남는다.
        self.manifest = TeamManifest(
            team_id=team_id,
            display_name=parameters.display_name,
            contract_name="a_cop.team_task",
            supported_contract_versions=["1.0"],
            capabilities=list(parameters.capabilities),
            accepted_case_types=list(parameters.accepted_case_types),
            required_context=list(parameters.required_context),
            allowed_tools=list(parameters.allowed_tools),
            knowledge_scope=list(parameters.knowledge_scope),
            max_steps=parameters.max_steps,
            active=True,
            implementation_revision=DECLARATIVE_REVISION,
        )

    # ──────────────────────────────────────────────────────────────
    def _gather(self, task: TeamTask) -> tuple[list[Evidence], list[str]]:
        """선언된 tool 을 한 번씩 호출해 사실을 모은다.

        ★실패를 조용히 삼키지 않는다 — 못 부른 tool 은 warnings 로 보고한다
          (`CLAUDE.md` §3 "조용한 스킵을 만들지 않는다").
        """
        evidence: list[Evidence] = []
        warnings: list[str] = []
        seen: set[str] = set()
        observed_at = datetime.now(UTC)

        for name in self.manifest.allowed_tools[: self.manifest.max_steps]:
            try:
                value = self.tools.call(name, task.context, {}, task.allowed_tools, seen)
            except (ToolNotAllowed, ToolLoopExceeded) as exc:
                warnings.append(f"tool '{name}' 를 부르지 못했다: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 — 어떤 실패든 세어서 보고한다
                warnings.append(f"tool '{name}' 실행 실패: {type(exc).__name__}: {exc}")
                continue
            if value in (None, [], {}, ""):
                warnings.append(f"tool '{name}' 이 빈 결과를 돌려줬다")
                continue
            evidence.append(Evidence(
                evidence_id=f"tool:{name}",
                source_type="tool_result",
                source_id=name,
                claim=f"{name} 조회 결과",
                value=value,
                confidence=1.0,
                observed_at=observed_at,
            ))
        return evidence, warnings

    async def _draft(self, task: TeamTask, evidence: list[Evidence]) -> str | None:
        """LLM 이 주입돼 있으면 초안을 만든다. 없으면 None — 폴백하지 않는다."""
        if self.llm is None:
            return None
        response = await self.llm.complete(
            self.parameters.prompt_key,
            task.input_text,
            {"evidence": [e.model_dump(mode="json") for e in evidence],
             "context": task.context.model_dump(mode="json")},
        )
        answer = response.get("answer") if isinstance(response, dict) else None
        return answer if isinstance(answer, str) and answer.strip() else None

    def _escalate(self, task: TeamTask, evidence: list[Evidence],
                  warnings: list[str], failure_code: str) -> TeamResult:
        return TeamResult(
            task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
            outcome="escalated", answer=None, confidence=0.0,
            evidence=evidence, next_action=NextAction.ESCALATE,
            failure_code=failure_code, warnings=warnings,
            decisions=[{"step": "declarative", "prompt_key": self.parameters.prompt_key}],
        )

    async def execute(self, task: TeamTask) -> TeamResult:
        evidence, warnings = self._gather(task)

        # ★근거가 하나도 없으면 답을 지어내지 않는다.
        if not evidence:
            return self._escalate(task, evidence, warnings, "no_evidence")

        try:
            answer = await self._draft(task, evidence)
        except Exception as exc:  # noqa: BLE001 — LLM 실패를 성공으로 위장하지 않는다
            warnings.append(f"초안 생성 실패: {type(exc).__name__}: {exc}")
            return self._escalate(task, evidence, warnings, "draft_failed")

        if answer is None:
            # LLM 이 없거나 빈 답을 준 경우다. 사실은 모았지만 응답을 만들지
            # 못했으므로 사람에게 넘긴다 — 근거만 붙여서.
            warnings.append("초안을 만들지 못해 사람에게 넘긴다")
            return self._escalate(task, evidence, warnings, "no_draft")

        return TeamResult(
            task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
            outcome="completed", answer=answer,
            confidence=0.6,  # 선언형은 결정론 검증을 거치지 않는다 — 과신하지 않는다
            evidence=evidence, next_action=NextAction.RESPOND,
            warnings=warnings,
            decisions=[{"step": "declarative", "prompt_key": self.parameters.prompt_key,
                        "tools_used": [e.source_id for e in evidence]}],
        )


__all__ = ["DeclarativeTeamRuntime", "DECLARATIVE_REVISION"]
