"""여행 Team의 다시 적용 안내를 기존 계산 함수와 직접 대조한다."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from uuid import uuid4

from app.domains.travel_ops.components.itinerary.itinerary import item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_changes import plan_rollback
from tests.unit.travel.test_conversation_work import task_for


def main():
    work, task, items = task_for({"action": "redo", "to_version": 2, "confirmed": True})
    current = items[0]
    old = replace(current, item_id=uuid4(), title="다시 적용할 식당",
                  place={**current.place, "name": "다시 적용할 식당"}, detail=dict(current.detail))
    work.tools.view["trip"]["version"] = 3
    task.context.current_state["subject_ref"]["base_version"] = 3
    original = work.tools.call

    def read(name, context, arguments, allowed_tools, seen, *, budget):
        if name == "read.itinerary_version":
            return {"items": [item_to_dict(old)]}
        return original(name, context, arguments, allowed_tools, seen, budget=budget)

    work.tools.call = read
    result = asyncio.run(work.execute(task))
    expected = plan_rollback(trip_version=3, base_version=3, current_items=items,
                             old_items=[old], to_version=2, message=task.input_text,
                             request_id=None, redo=True)
    print(json.dumps({"team_answer": result.answer,
                      "prior_redo_calculator_answer": expected.notice["text"],
                      "team_proposals": len(result.action_proposals),
                      "same_answer": result.answer == expected.notice["text"]},
                     ensure_ascii=False, indent=2))
    assert len(result.action_proposals) == 1
    assert result.answer != expected.notice["text"]
    assert "되돌렸" in result.answer and "다시 적용" in expected.notice["text"]


if __name__ == "__main__":
    main()
