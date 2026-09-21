# -*- coding: utf-8 -*-
"""여행 Team 이 공통으로 쓰는 계약 포장.

★**왜 만드나 — 커머스 여섯 팀에서 이걸 복붙했다가 어긋났다.**
  AST 로 세어 보니 계약 처리 코드가 **315줄 복붙**돼 있었고, 그 결과 가드가
  팀마다 달랐다:

      degraded 가드     5/6 = 83%
      capability 가드   4/6 = 67%
      team_id 가드      1/6 = 17%   ← 잘못 배선된 task 가 와도 다섯 팀은 조용히 처리했다

  여행에서 같은 복붙을 하면 같은 불균일이 복제된다. 그래서 **처음부터 한 곳에** 둔다.

★**계층을 옮긴 것이 아니다.** 이 파일은 `app/modules/` 안에 있고 도메인 어휘를
  쓰지 않는다. 계약(`TeamManifest`·`TeamResult`)과 가드만 안다.
  코어로 올릴지는 별도 결정이고, 올려도 이 파일이 그대로 이사한다.

★**`execute()` 를 대신 실행하지 않는다.** 상속으로 흐름을 가로채면 어느 Team 이
  무엇을 하는지 읽기 어려워진다. 여기 있는 것은 **부품**이고, 각 Team 이
  자기 `execute()` 안에서 순서대로 부른다.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import (
    ActionProposal,
    Evidence,
    NextAction,
    TeamManifest,
    TeamResult,
    TeamTask,
)
from app.tools.read_tools import ReadToolbox


class TravelTeamBase:
    """여행 Team 의 공통 부품. `manifest` 는 각 Team 이 선언한다."""

    manifest: TeamManifest

    def __init__(self, tools: ReadToolbox, llm: Any | None = None) -> None:
        # ★도구를 스스로 만들지 않는다. 조립 지점이 넣어 준다 —
        #   그래서 테스트에서 가짜 도구를 넣을 수 있고 원격(A2A)으로도 뺄 수 있다.
        self.tools, self.llm = tools, llm

    # ── 가드 ────────────────────────────────────────────────────
    def _guard(self, task: TeamTask) -> TeamResult | None:
        """셋을 **다 본다.** 하나라도 걸리면 그 결과를 돌려주고, 아니면 `None`.

        순서에 뜻이 있다:
          1. team_id  — 남의 일이면 판단하기 전에 넘긴다
          2. capability — 못 하는 일이면 시작하지 않는다
          3. degraded — 근거가 깎였으면 확정 답을 만들지 않는다
        """
        if task.team_id != self.manifest.team_id:
            return self._result(task, outcome="handoff", confidence=1.0,
                                next_action=NextAction.HANDOFF,
                                handoff_capability=task.capability)
        if task.capability not in self.manifest.capabilities:
            return self._escalate(task, "unsupported_capability")
        if task.context.degraded:
            return self._escalate(task, "degraded_context")
        return None

    # ── 도구 ────────────────────────────────────────────────────
    def _read(self, task: TeamTask, name: str, arguments: dict[str, Any],
              seen: set[str]) -> Any:
        """도구 하나를 부른다.

        ★`budget` 을 **여기서 항상 넘긴다.** 각 Team 이 넘기게 두면 빠뜨리는
          곳이 생긴다 — 커머스에서 `max_steps` 가 선언만 되고 아무도 안 읽던
          것과 같은 모양이 된다
          (`wiki/records/reports/debugs/2026-09-09_max_steps가_강제되지_않는다.md`).
        """
        return self.tools.call(name, task.context, arguments, task.allowed_tools,
                               seen, budget=self.manifest.max_steps)

    # ── 근거 ────────────────────────────────────────────────────
    @staticmethod
    def _evidence(task: TeamTask, *, source_id: str, claim: str, value: Any,
                  base: list[Evidence] | None = None) -> list[Evidence]:
        """근거를 **누적한다.** 값이 비면 붙이지 않는다 — 빈 근거는 근거가 아니다.

        ★★2026-09-09 결함. 이 함수가 매번 `task.context.evidence` 에서 **다시
          시작해서**, 두 번째 호출이 첫 번째를 덮었다. 실 DB 종단 실행에서
          예약·규정을 둘 다 읽은 Case 의 근거가 `['read.weather']` **하나뿐**
          이었다 — 답변에 근거를 붙이는 것이 이 제품의 첫째 규칙인데
          (`CLAUDE.md` §0.1) 그 근거가 조용히 사라지고 있었다.

          단위 테스트로는 안 잡혔다. 도구를 **한 개만** 쓰는 경로만 봤기
          때문이다. 여러 도구를 실제로 부르는 종단 실행이 잡았다.

        ★`base` 를 주면 그 위에 쌓는다. 안 주면 예전처럼 컨텍스트에서 시작한다.
        """
        evidence = list(task.context.evidence if base is None else base)
        if value is not None and value != {} and value != []:
            evidence.append(Evidence(
                evidence_id=f"tool:{task.team_id}:{source_id}",
                source_type="tool_result" if source_id.startswith("read.") else "db",
                source_id=source_id, claim=claim, value=value,
                confidence=1.0, observed_at=datetime.now(UTC),
            ))
        return evidence

    # ── 반환 ────────────────────────────────────────────────────
    #: `next_action` 이 정해지면 `wait_reason` 도 **한 값으로 정해진다**(계약 §
    #: `_next_action_consistency`). 그래서 여기서 채운다.
    #: ★2026-09-10 결함. 세 제안 경로(`activity.propose_change` ·
    #:   `booking.prepare_change` · `booking.prepare_cancel`)가 전부
    #:   `wait_reason` 없이 `WAIT_FOR_APPROVAL` 을 돌려줘 **호출되는 순간
    #:   `ValidationError` 로 죽고 있었다.** 즉 여행 제품에서 승인이 필요한
    #:   모든 길이 막혀 있었다. 팀별 단위 테스트는 제안이 "나오는지" 만 봤고
    #:   계약 검증까지 태우는 검사가 없어서 아무도 못 잡았다 —
    #:   `tests/contract/test_proposal_fields_are_declared.py` 가 등록 전체를
    #:   순회하도록 바뀌면서 드러났다.
    #: ★손으로 넘긴 값이 있으면 그쪽이 이긴다. 여기서 덮어쓰면 의도를 지운다.
    _WAIT_REASON_FOR: dict[NextAction, str] = {
        NextAction.WAIT_FOR_APPROVAL: "human_approval",
        NextAction.WAIT_FOR_INPUT: "customer_input",
    }

    @staticmethod
    def _result(task: TeamTask, **kwargs: Any) -> TeamResult:
        next_action = kwargs.get("next_action")
        if kwargs.get("wait_reason") is None:
            derived = TravelTeamBase._WAIT_REASON_FOR.get(next_action)
            if derived is not None:
                kwargs["wait_reason"] = derived
        return TeamResult(task_id=task.task_id, run_id=task.run_id,
                          team_id=task.team_id, **kwargs)

    @classmethod
    def _escalate(cls, task: TeamTask, code: str,
                  evidence: list[Evidence] | None = None,
                  warnings: list[str] | None = None) -> TeamResult:
        """사람에게 넘긴다. ★`failure_code` 를 **반드시** 남긴다 — 왜 못 했는지가
        없으면 다음 사람이 같은 자리를 다시 판다."""
        return cls._result(task, outcome="escalated", confidence=0.0,
                           evidence=evidence or list(task.context.evidence),
                           next_action=NextAction.ESCALATE,
                           failure_code=code, warnings=warnings or [])

    @classmethod
    def _unknown(cls, task: TeamTask, what: str,
                 evidence: list[Evidence] | None = None) -> TeamResult:
        """★「모름」 전용 갈래.

        확인하지 못한 것을 **확인 못 했다고** 말한다. 커머스에서 이걸 빠뜨려
        제한을 안 보고 "정책 근거상 가능합니다" 라고 답한 결함이 있었다 —
        NULL 을 「없음」으로 읽으면 결함이 자리만 옮긴다.
        """
        return cls._escalate(task, f"unknown_{what}", evidence,
                             warnings=[f"{what} 을(를) 확인하지 못했다. 값이 없는 것이 "
                                       f"아니라 **모르는** 상태다."])

    # ── 제안 ────────────────────────────────────────────────────
    @staticmethod
    def _proposal(task: TeamTask, action_type: str, arguments: dict[str, Any],
                  evidence: list[Evidence], risk: str = "high") -> ActionProposal:
        """★제안까지만이다. Team 은 실행하지 않는다.

        `idempotency_key` 를 붙여 같은 요청이 두 번 나가지 않게 한다.
        """
        from app.core.idempotency import idempotency_key

        request_id = str(task.context.current_state.get("request_id") or task.case_id)
        subject = str(arguments.get("booking_id") or arguments.get("trip_id") or task.case_id)
        return ActionProposal(
            action_type=action_type, arguments=arguments,
            idempotency_key=idempotency_key(
                tenant_id=task.context.tenant_id, request_id=request_id,
                action_type=action_type, business_subject=subject),
            approval_required=True, risk_level=risk,
            rationale_evidence_ids=[item.evidence_id for item in evidence],
        )
