"""VOC / Feedback Analytics Team implementation."""
from __future__ import annotations

from datetime import UTC, date, datetime

from acop_basement.application.feedback_job import run_daily_feedback
from acop_basement.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from acop_basement.tools.read_tools import ReadToolbox


class FeedbackAnalyticsTeam:
    manifest = TeamManifest(
        team_id="feedback_analytics",
        display_name="VOC / Feedback Analytics Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["voc.aggregate_and_alert"],
        accepted_case_types=[],
        required_context=[],
        allowed_tools=[],
        knowledge_scope=["voc"],
        max_steps=1,
        active=True,
        implementation_revision="2026-08-17",
    )

    def __init__(self, tools: ReadToolbox, llm=None) -> None:
        self.tools = tools

    async def execute(self, task: TeamTask) -> TeamResult:
        """Run the existing daily job using the report date supplied by the task."""
        report_date = date.fromisoformat(task.context.current_state["report_date"])
        with self.tools.connection_factory() as conn, conn.transaction():
            report = run_daily_feedback(
                conn,
                report_date=report_date,
                tenant_id=task.context.tenant_id,
            )

        alerts = report.get("alerts") or []
        # ★value 는 report 전체를 담는다 (metrics 만이 아니다).
        #   scripts/run_daily_feedback.py 가 여기서 원래 CLI 출력 모양
        #   ({"alerts":..., "metrics":..., "period_start":...}) 을 복원한다 —
        #   run_daily_feedback() 을 두 번 부르지 않고, 한 번의 실행 결과를 재사용한다.
        evidence = [
            Evidence(
                evidence_id=f"voc:totals:{task.task_id}",
                source_type="db",
                source_id="feedback_analytics_reports",
                claim="VOC aggregation completed",
                value=report,
                confidence=1.0,
                observed_at=datetime.now(UTC),
            )
        ]
        return TeamResult(
            task_id=task.task_id,
            run_id=task.run_id,
            team_id=self.manifest.team_id,
            outcome="escalated" if alerts else "completed",
            answer=(
                f"Detected {len(alerts)} VOC alert(s)"
                if alerts
                else "No VOC alerts detected"
            ),
            confidence=1.0,
            evidence=evidence,
            decisions=[{"alert": alert, "escalate": True} for alert in alerts],
            next_action=NextAction.ESCALATE if alerts else NextAction.RESPOND,
            warnings=["VOC alerts were detected"] if alerts else [],
        )


__all__ = ["FeedbackAnalyticsTeam"]
