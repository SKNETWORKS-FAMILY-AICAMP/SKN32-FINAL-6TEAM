from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.composition import build_registry
from acop_basement.core.contracts import ContextPack, TeamTask
from acop_basement.core.settings import get_guardrails, get_settings
from acop_basement.infrastructure.db.session import get_connection
from app.modules.customer_ops.read_tools import build_read_tool_functions
from acop_basement.tools.read_tools import ReadToolbox


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    tenant_id = get_settings().tenant_id
    task_id, run_id, case_id = uuid4(), uuid4(), uuid4()
    team_id = "feedback_analytics"
    task = TeamTask(
        task_id=task_id,
        run_id=run_id,
        case_id=case_id,
        team_id=team_id,
        capability="voc.aggregate_and_alert",
        case_version=1,
        input_text=f"Run daily VOC feedback analytics for {args.date.isoformat()}.",
        context=ContextPack(
            pack_id=uuid4(),
            case_id=case_id,
            team_id=team_id,
            tenant_id=tenant_id,
            knowledge_scope=["voc"],
            current_state={"report_date": args.date.isoformat()},
            estimated_input_tokens=0,
        ),
        allowed_tools=[],
        # ★"지금" 을 마감으로 주면 만들자마자 지난 마감이 된다.
        #   Controller 가 Team 을 부를 때와 같은 규칙(team_timeout_seconds)을 쓴다.
        deadline_at=datetime.now(UTC) + timedelta(
            seconds=get_guardrails().get("reliability.team_timeout_seconds")),
    )
    team = build_registry(tools=ReadToolbox(tool_functions=build_read_tool_functions(
        get_connection), connection_factory=get_connection)).get(team_id).module
    result = asyncio.run(team.execute(task))

    # ★v7 은 "배치가 이 Team 의 실행 형태" 라고 했다 — 실행 경로가 Team 을 거치라는
    #   뜻이지, CLI 가 내던 출력을 바꾸라는 뜻이 아니다. TeamResult 봉투를 그대로
    #   찍으면 이 명령의 출력을 실측으로 삼은 DoD-10 증거 문서가 전부 어긋난다.
    #   원래 report 는 evidence[0].value 에 있다 — run_daily_feedback() 을 다시
    #   부르지 않고 그 값을 그대로 복원해서 찍는다.
    report = result.evidence[0].value
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
