# -*- coding: utf-8 -*-
"""
python -m app.modules.travel_ops.activity

customer_travel.json 의 일정으로 ActivityTeam.check_feasible 을 데모 실행한다.
실 DB·API 없이 JSON 데이터와 TourAPI 가데이터를 주입한다.

tour_api_content_id 가 있는 장소는 _KNOWN_OPERATING 에서 운영시간을 주입한다.
나머지는 operating=None — TourAPI 언급 없이 판정한다.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

KST = timezone(timedelta(hours=9))
_HERE = Path(__file__).parent

# ── 가짜 도구 ─────────────────────────────────────────────────────

class _DemoTools:
    """TravelTeamBase._read() 가 기대하는 .call() 인터페이스를 구현.

    ★FakeTools(tests/unit/travel/helpers.py)와 같은 순서로
      권한·중복·예산을 검사한다.
    """

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses

    def call(self, name: str, context: Any, arguments: dict[str, Any],
             allowed_tools: list[str], seen: set[str],
             budget: int | None = None) -> Any:
        from app.core.contracts import ToolNotAllowed
        from app.tools.read_tools import ToolBudgetExceeded, ToolLoopExceeded

        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        sig = name + ":" + repr(sorted(arguments.items()))
        if sig in seen:
            raise ToolLoopExceeded(name)
        if budget is not None and len(seen) >= budget:
            raise ToolBudgetExceeded(f"budget {budget} exhausted before {name}")
        seen.add(sig)
        return self._responses.get(name)


# ── TourAPI 가데이터 (content_id 별로 추가 가능) ──────────────────

_KNOWN_OPERATING: dict[str, dict[str, Any]] = {
    "126508": {   # 경복궁
        "content_id": "126508",
        "usetime_text": "09:00~18:00(입장마감 17:00)",
        "restdate_text": "매주 화요일 휴무. 단 공휴일과 겹치면 개방",
        "parsed": False,
        "answers_open_at_slot": False,
        "source": "tour_api",
        "confirmed_at": "2026-09-22T06:00:00+00:00",
    },
}


# ── 도구·태스크 생성 ───────────────────────────────────────────────

def _build_tools(act: dict) -> _DemoTools:
    """활동 항목 하나 → _DemoTools.

    JSON 이 바뀌면 place·예약 정보가 자동 반영된다.
    tour_api_content_id 가 _KNOWN_OPERATING 에 없으면 operating=None.
    """
    starts_at = datetime.fromisoformat(act["time"])
    operating = _KNOWN_OPERATING.get(act.get("tour_api_content_id") or "")
    place: dict[str, Any] = {
        "place_id": act["id"],
        "name": act["name"],
        "weather_sensitive": False,
        "latitude": act.get("lat"),
        "longitude": act.get("lng"),
    }
    if operating:
        place["operating"] = operating
    return _DemoTools({
        "read.booking": {
            "booking_id": act["id"],
            "place_id": act["id"],
            "starts_at": starts_at,
            "party_size": 2,
            "capacity": 30,
        },
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
        "read.disaster": None,
    })


def _build_context():
    from app.core.contracts import ContextPack
    return ContextPack(
        pack_id=uuid4(), case_id=uuid4(), team_id="activity",
        tenant_id="demo", knowledge_scope=["activity"],
        current_state={"customer_id": "cust_001", "status": "running"},
        estimated_input_tokens=10, degraded=False, omissions=[])


def _build_task(act: dict, context):
    from app.core.contracts import TeamTask
    from app.modules.travel_ops.activity import ActivityTeam
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=context.case_id,
        team_id="activity", capability="activity.check_feasible",
        case_version=1, input_text=f"{act['name']} 활동이 성립하나요?",
        context=context, allowed_tools=ActivityTeam.manifest.allowed_tools,
        deadline_at=datetime.now(UTC) + timedelta(seconds=90))


# ── 결과 출력 ──────────────────────────────────────────────────────

_WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]


def _print_result(act: dict, result) -> None:
    decs = result.decisions[0] if result.decisions else {}
    feasible = decs.get("feasible")
    mark = "[OK]" if feasible is True else "[NG]" if feasible is False else "[??]"

    starts_at = datetime.fromisoformat(act["time"])
    print(f"\n{'─' * 60}")
    print(f"{mark}  {act['id']}  {act['name']}")
    print(f"     {starts_at.strftime('%Y-%m-%d %H:%M')} ({_WEEKDAY[starts_at.weekday()]}요일) KST")
    print(f"     {result.answer}")
    for w in result.warnings:
        print(f"     !  {w}")
    if "operating" in decs:
        print(f"     operating.weekday_match = {decs['operating'].get('weekday_match')}")
    if "disaster" in decs:
        print(f"     disaster.blocks = {decs['disaster'].get('blocks')}")


# ── 진입점 ─────────────────────────────────────────────────────────

async def _run() -> int:
    from app.modules.travel_ops.activity import ActivityTeam

    json_path = _HERE / "customer_travel.json"
    if not json_path.exists():
        print(f"[FAIL] {json_path} 없음", file=sys.stderr)
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    itinerary: list[dict] = data.get("itinerary", [])
    if not itinerary:
        print("[FAIL] itinerary 가 비어 있다", file=sys.stderr)
        return 1

    print(f"고객: {data.get('customer_id', '?')}  여행: {data.get('trip_id', '?')}")
    print(f"일정 {len(itinerary)}건  -  ActivityTeam.check_feasible 데모")

    errors = 0
    for act in itinerary:
        context = _build_context()
        tools = _build_tools(act)
        task = _build_task(act, context)
        try:
            result = await ActivityTeam(tools).execute(task)
            _print_result(act, result)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[ERR] {act['id']}  {type(exc).__name__}: {exc}")
            errors += 1

    print(f"\n{'─' * 60}")
    print(f"완료{'.' if not errors else f' (오류 {errors}건)'}")
    return errors


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
