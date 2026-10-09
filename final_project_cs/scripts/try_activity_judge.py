# -*- coding: utf-8 -*-
"""활동 판정 직접 돌려 보기 — develop 판 Activity Team 의 성립 판정(`activity.check_feasible`)을 원하는 입력으로 끝까지.

    python -m scripts.try_activity_judge --place 경복궁 --at "2026-11-10 14:00" \\
        --restdate "매월 둘째 주 화요일 휴무" --usetime "09:00~18:00" --weather-sensitive outdoor --forecast 20,10

    # 재난문자 넣기 — "등급|구분|본문|지역(쉼표)" · 여러 개면 여러 번
    python -m scripts.try_activity_judge --place 경복궁 --at "2026-11-10 14:00" --weather-sensitive indoor \\
        --disaster "안전안내|기타|[종로구] 세종대로 집회로 교통 혼잡|서울특별시 종로구"

    # 모드 — shadow(기본: 규칙으로 답하고 LLM 은 뒤에서 비교) · rule(LLM 안 부름)
    python -m scripts.try_activity_judge --place 서울숲 --at "2026-11-10 15:00" --forecast 10,5 --mode rule

무엇을 보여 주나
  ① 고객에게 나가는 결과(답변 · 성립 여부 · 실패 코드 · 경고)와 걸린 시간
  ② (섀도) 판정 종류별 develop 판 값 vs LLM 값 · 일치 · 실패 코드 · 지연 · 모델의 판단 이유

★`[2026-10-09]` develop 판 팀(`team.py`, D-CS-015)으로 옮겼다 — 전에는 보존본 `team_a.py` 를 돌렸다. develop 판은 `llm` 모드를
  받지 않는다(섀도까지). 판정 지점은 ① 휴무 원문 · ③ 실내외(장소 값 · 분류 모두 모를 때) · ④ 정지 대상이 아닌 미분류 재난문자 ·
  ⑤ 실시간 운영(실외이거나 72시간 안) — ② 운영시간은 부르지 않는다.
★`--at` 은 **앞으로의 시각**이어야 한다 — 지난 시각은 「이미 시작됨」에서 끝난다(위 예시 날짜도 지나면 바꿔 쓴다).
★공유 점검(`read.disruptions`)은 **실제 코드**(`DisruptionCheck`)가 돈다 — 넣는 것은 재난문자 · 예보 소스뿐이다. 재난문자는
  실제 소스와 같은 지역 판정(`disaster_msg.judge` · `seoul_districts`)을 거친다. ★실외이거나 실내외를 모르면 예보가 필요하다 —
  `--forecast` 가 없으면 develop 판은 「예보를 끝까지 못 읽음 = 치명」으로 사람에게 넘긴다(결정 15).
★운영시간 · 휴무는 `--usetime` · `--restdate` 원문을 새벽 작업과 같은 규칙(`place_hours.read_by_rule`)으로 요일표로 바꿔 넣는다.
  규칙 밖 원문은 요일표를 못 만든다(새벽 작업은 그때 모델로 읽는다 — 이 스크립트는 부르지 않는다).
★예약 · 장소는 **가짜 도구**다(DB 예약을 만들지 않는다). 장소는 CSV 장소 목록(`activity_total_data.csv`)에서 이름으로 찾아
  좌표 · 주소 · 분류를 채운다. 대체 후보 풀만 실제 DB(`place_catalog`)를 읽는다. 판정 LLM · 프롬프트(DB 등록본) · 감사 기록은 **실제**다.
★감사 기록은 `run_id` 없이 남긴다 — 이 스크립트의 작업은 `agent_runs` 에 없어 외래 키에 걸린다.
★섀도 기록 표(`activity_judge_shadow`)에는 `origin='eval'` · `eval_run='try-<시각>'` 으로 쓴다. `--no-db` 면 표에 쓰지 않는다.
★비용(추정): 원문 해석 판정은 건당 약 $0.0003, 웹 판정(실시간 운영 상태)은 약 $0.03.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
KIND_LABEL = {"closure": "휴무", "operating_hours": "운영시간", "weather_sensitive": "실내외",
              "disaster_effect": "재난문자", "live_status": "실시간(웹)"}


class Tools:
    """이름 → 값. ★실제 `ReadToolbox` 와 같은 순서로 권한·중복·예산을 본다(`tests/unit/travel/helpers.py` 와 같은 규칙)."""

    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values
        self.calls: list[str] = []

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        from app.core.contracts import ToolNotAllowed
        from app.tools.read_tools import ToolBudgetExceeded, ToolLoopExceeded

        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        signature = name + ":" + repr(sorted(arguments.items()))
        if signature in seen:
            raise ToolLoopExceeded(name)
        if budget is not None and len(seen) >= budget:
            raise ToolBudgetExceeded(f"budget {budget} exhausted before {name}")
        seen.add(signature)
        self.calls.append(name)
        value = self.values.get(name)
        # 값 대신 함수를 넣으면 인자로 답을 만든다(공유 점검 · 대체 후보)
        return value(**arguments) if callable(value) else value


class ScriptDisaster:
    """`--disaster` 문자 — 실제 재난문자 소스(`DisasterMsgApi.active`)와 같은 모양 · 같은 지역 판정 · 같은 창."""

    name = "try_activity_judge"

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def active(self, *, region: str, at: datetime, district: Any = None, **_: Any) -> dict[str, Any]:
        from app.domains.travel_ops.ports.data_sources.disaster_msg import DEFAULT_LOOKBACK_HOURS, judge

        now = datetime.now(KST)
        until = min((at if at.tzinfo else at.replace(tzinfo=KST)).astimezone(KST), now)
        messages, unclassified = judge(self.rows, region=region, district=district,
                                       window_start=until - timedelta(hours=DEFAULT_LOOKBACK_HOURS), at=until)
        return {"mode": "script", "covered": True, "region": region, "district": district, "source": self.name,
                "confirmed_at": now.isoformat(), "for_region": messages, "unclassified": unclassified}


class ScriptWeather:
    name = "try_activity_judge"

    def __init__(self, forecast: dict[str, Any] | None) -> None:
        self.value = forecast

    def forecast(self, *, latitude: float, longitude: float, at: Any = None) -> dict[str, Any] | None:
        return self.value


def parse_at(text: str) -> datetime:
    value = datetime.fromisoformat(text.strip())
    return value if value.tzinfo else value.replace(tzinfo=KST)


def parse_disaster(text: str, created_at: datetime) -> dict[str, Any]:
    """`"등급|구분|본문|지역(쉼표)"` → 실제 소스의 판정용 행(`disaster_msg.parse_row` 와 같은 모양).

    ★지역을 안 주면 「서울특별시 전체」로 둔다 — 지역 없는 문자는 실제로 오지 않는다.
    """
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        raise SystemExit(f'--disaster 는 "등급|구분|본문|지역" 모양이다: {text!r}')
    step, kind, body = parts[:3]
    regions = [r.strip() for r in parts[3].split(",") if r.strip()] if len(parts) > 3 else []
    return {"step": step, "kind": kind, "text": body, "regions": regions or ["서울특별시 전체"],
            "created_at": created_at, "serial": None}


def read_place_candidates(content_id: str | None = None, **_: Any) -> dict[str, Any] | None:
    """대체 후보 풀 — **실제 DB**(`place_catalog`)에서 읽는다. DB 에 못 붙거나 카탈로그가 비었으면 `None`(모름)."""
    from app.core.settings import get_settings
    from app.domains.travel_ops.instances.activity.db_search.place_candidates import find_place_candidates
    from app.infrastructure.db.session import get_connection

    try:
        return find_place_candidates(get_connection, get_settings().tenant_id, content_id)
    except Exception as exc:   # 스크립트다 — 원인을 보이고 모름으로 둔다
        print(f"   (대체 후보 풀을 DB 에서 못 읽었다: {type(exc).__name__})")
        return None


def _hours(usetime: str | None, restdate: str | None) -> dict[str, Any] | None:
    """`read.place_hours` 모양 — 원문을 새벽 작업과 같은 규칙으로 요일표로. 원문이 없으면 `None`(모름)."""
    if usetime is None and restdate is None:
        return None
    from app.domains.travel_ops.components.places.place_hours import read_by_rule

    read = read_by_rule(usetime, restdate)
    week = read.week if read is not None else {}
    return {"known": bool(week), "attributes": {"hours_week": week} if week else {}, "source": "try_activity_judge",
            "why_unknown": None if week else "규칙으로 요일표를 못 만들었다(새벽 작업은 모델로 읽는다)",
            "conditions": list(read.conditions) if read is not None else [],
            "usetime_text": usetime, "restdate_text": restdate}


def build_values(args: argparse.Namespace, starts: datetime) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class
    from app.domains.travel_ops.instances.activity.csv_places import CsvPlaceLookup
    from app.domains.travel_ops.ports.data_sources.disaster_msg import seoul_districts
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

    lookup = CsvPlaceLookup()
    found = lookup.find(args.place)
    row = lookup.find_by_content_id(found["content_id"]) if found else None
    latitude, longitude = (found or {}).get("latitude"), (found or {}).get("longitude")
    district = (seoul_districts(float(latitude), float(longitude), (found or {}).get("address"))[0]
                if latitude is not None and longitude is not None else None)
    place: dict[str, Any] = {"place_id": "try-place", "name": args.place, "kind": "activity",
                             "weather_sensitive": {"outdoor": True, "indoor": False}.get(args.weather_sensitive),
                             "latitude": latitude, "longitude": longitude, "district": district,
                             "source_content_id": (found or {}).get("content_id")}
    now = datetime.now(KST).isoformat()
    forecast = None
    if args.forecast:
        pop, _, wind = args.forecast.partition(",")
        forecast = {"matched_hour": starts.strftime("%H:00"), "precipitation_probability": int(pop),
                    "wind_speed_kmh": int(wind or 0), "source": "try_activity_judge", "confirmed_at": now}
    disaster = None
    if args.disaster or args.no_disaster_messages:
        created = datetime.now(KST)
        disaster = ScriptDisaster([parse_disaster(d, created) for d in args.disaster or []])
    check = DisruptionCheck(SimpleNamespace(weather=ScriptWeather(forecast), disaster=disaster, unavailable={}))

    def read_disruptions(*, starts_at=None, region="서울", **target: Any) -> dict[str, Any]:
        return check.check(place=target, starts_at=parse_at(starts_at) if isinstance(starts_at, str) else starts_at,
                           region=region)

    lcls1, lcls2 = (row or {}).get("lclsSystm1"), (row or {}).get("lclsSystm2")
    place_class = ({"content_id": found["content_id"], "lcls1": lcls1, "lcls2": lcls2,
                    "address": found.get("address"), "weather_sensitive": weather_from_class(lcls1, lcls2)}
                   if found else None)
    values = {
        "read.booking": {"booking_id": "try-booking", "place_id": "try-place", "starts_at": starts,
                         "party_size": args.party, "capacity": args.capacity},
        "read.policy": [{"note": "try_activity_judge"}],
        "read.place": place,
        "read.disruptions": read_disruptions,
        "read.place_hours": _hours(args.usetime, args.restdate),
        "read.place_class": place_class,
        "read.holiday": None,
        "read.place_candidates": read_place_candidates,
    }
    return values, found


def make_task(team_cls):
    from app.core.contracts import ContextPack, TeamTask

    context = ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id="activity", tenant_id="try-activity-judge",
                          knowledge_scope=["travel_activity"], current_state={"status": "running"},
                          estimated_input_tokens=10)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=context.case_id, team_id="activity",
                    capability="activity.check_feasible", case_version=1, input_text="성립 점검(try_activity_judge)",
                    context=context, allowed_tools=list(team_cls.manifest.allowed_tools),
                    deadline_at=datetime.now(UTC) + timedelta(seconds=90))


def make_judge_llm(outputs: dict[str, Any]):
    """실제 판정 어댑터. 감사 기록은 `run_id` 없이 남기고, 응답(판정 · 이유)을 화면에 보여 주려고 담아 둔다."""
    from app.infrastructure.db.session import get_connection
    from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM

    class Capturing(OpenAIResponsesJudgeLLM):
        async def judge(self, prompt_key, payload, **kwargs):
            kwargs["run_id"] = None
            call = await super().judge(prompt_key, payload, **kwargs)
            outputs[payload["kind"]] = call.output
            return call

    return Capturing(connection_factory=get_connection)


def make_sink(records: list[dict[str, Any]], *, write_db: bool, eval_run: str):
    db_sink = None
    if write_db:
        from app.composition import build_activity_judge_shadow_sink
        db_sink = build_activity_judge_shadow_sink()

    def sink(record: dict[str, Any]) -> None:
        record = {**record, "origin": "eval", "eval_run": eval_run, "eval_case": "try"}
        records.append(record)
        if db_sink is not None:
            db_sink(record)

    return sink


def print_result(result, elapsed: float) -> None:
    decision = (result.decisions or [{}])[0]
    print("\n① 고객에게 나가는 결과" + f"  ({elapsed:.2f}초)")
    print(f"   결과: {result.outcome}   다음: {getattr(result.next_action, 'value', result.next_action)}")
    print(f"   성립: {decision.get('feasible')}   사유: {decision.get('reason') or decision.get('status')}   "
          f"실패 코드: {decision.get('failure_code') or result.failure_code}")
    print(f"   답변: {result.answer}")
    for warning in result.warnings:
        print(f"   경고: {warning}")


def print_judgments(records: list[dict[str, Any]], outputs: dict[str, Any]) -> None:
    print("\n② 판정 종류별 비교  (섀도 — 고객 결과에는 develop 판 값이 쓰였다)")
    if not records:
        print("   (불린 판정이 없다 — 휴무 원문 · 미분류 재난문자 · 실외/72시간 조건을 보라)")
    for r in sorted(records, key=lambda r: r["kind"]):
        mark = "일치" if r.get("agree") else ("비교불가" if not r.get("comparable") else "불일치")
        fail = r.get("llm_failure_code") or ""
        err = f"({r['llm_error']})" if r.get("llm_error") else ""
        print(f"   {KIND_LABEL[r['kind']]:<9} develop={r['rule']:<11} LLM={str(r.get('llm')):<11} {mark:<5} "
              f"{fail}{err}  {r.get('latency_ms') or '-'}ms")
    for kind, out in outputs.items():
        cites = [c.get("url") for c in out.get("citations") or []]
        print(f"   · {KIND_LABEL[kind]} — LLM 이유: {out.get('reason')}")
        if out.get("quotes"):
            print(f"       인용: {out['quotes']}")
        if cites:
            print(f"       출처: {cites}")


def wait_for_shadow(timeout: float = 180.0) -> bool:
    from app.domains.travel_ops.instances.activity.judge import modes

    runner = modes.default_runner()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if runner._pending == 0:
            return True
        time.sleep(0.5)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="활동 판정 직접 돌려 보기(develop 판)")
    parser.add_argument("--place", required=True, help="장소 이름 — CSV 장소 목록에서 찾는다")
    parser.add_argument("--at", required=True, help='예약 시각 — "2026-11-10 14:00"(한국 시각) 또는 ISO')
    parser.add_argument("--restdate", help="휴무 원문 (예: 매주 월요일 휴무)")
    parser.add_argument("--usetime", help="운영시간 원문 (예: 09:00~18:00)")
    parser.add_argument("--disaster", action="append", help='재난문자 "등급|구분|본문|지역" — 여러 번 줄 수 있다')
    parser.add_argument("--no-disaster-messages", action="store_true", help="재난문자 0건(조회는 됐다)으로 둔다")
    parser.add_argument("--weather-sensitive", choices=["outdoor", "indoor"],
                        help="장소에 적힌 실내외 값. 없으면 관광공사 분류 → 모름(섀도 ③)")
    parser.add_argument("--forecast", help='예보 "강수확률,풍속" (예: 70,25). 실외 · 모름이면 필요하다')
    parser.add_argument("--party", type=int, default=2)
    parser.add_argument("--capacity", type=int, default=10)
    parser.add_argument("--mode", choices=["shadow", "rule"], default="shadow")
    parser.add_argument("--no-db", action="store_true", help="섀도 기록 표에 쓰지 않는다")
    args = parser.parse_args(argv)

    from app.domains.travel_ops.instances.activity import ActivityTeam

    starts = parse_at(args.at)
    values, found = build_values(args, starts)
    print(f"장소: {args.place} → " + (f"CSV {found['content_id']} · {found['address']}" if found
                                       else "CSV 에서 못 찾음(이름만으로 돈다 — 좌표 · 분류 · 주소가 없다)"))
    print(f"시각: {starts.isoformat()}   모드: {args.mode}")
    if starts <= datetime.now(KST):
        print("   ★이미 지난 시각이다 — 「이미 시작됨」에서 끝나 휴무 · 재난문자 · LLM 판정이 돌지 않는다")
    if args.weather_sensitive != "indoor" and not args.forecast:
        print("   ★실외이거나 실내외를 모르는데 --forecast 가 없다 — develop 판은 예보를 못 읽으면 치명(사람에게 넘김)이다")

    team = ActivityTeam(Tools(values))
    records: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}
    eval_run = "try-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if args.mode == "shadow":
        team.judge_llm = make_judge_llm(outputs)
        team.judge_shadow_sink = make_sink(records, write_db=not args.no_db, eval_run=eval_run)

    started = time.monotonic()
    result = asyncio.run(team.execute(make_task(ActivityTeam)))
    print_result(result, time.monotonic() - started)

    if args.mode == "shadow":
        print("\n   …뒤에서 LLM 판정을 기다린다(웹 판정이 끼면 10~40초)", flush=True)
        if not wait_for_shadow():
            print("   (시간 안에 끝나지 않았다 — 끝난 것만 보인다)")
        print_judgments(records, outputs)
        if not args.no_db:
            print(f"\n   섀도 기록 표: SELECT * FROM activity_judge_shadow WHERE eval_run='{eval_run}';")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
