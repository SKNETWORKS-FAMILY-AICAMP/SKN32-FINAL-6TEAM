# -*- coding: utf-8 -*-
"""활동 판정 직접 돌려 보기 — Activity Team 의 성립 판정(`activity.check_feasible`)을 원하는 입력으로 끝까지.

    python -m scripts.try_activity_judge --place 경복궁 --at "2026-10-13 14:00" \\
        --restdate "매월 둘째 주 화요일 휴무" --usetime "09:00~18:00(입장마감 17:00)"

    # 재난문자 넣기 — "등급|구분|본문|지역(쉼표)" · 여러 개면 여러 번
    python -m scripts.try_activity_judge --place 경복궁 --at "2026-10-07 14:00" \\
        --disaster "위급재난|호우|[부산시] 해운대구 침수, 접근 금지|부산광역시 해운대구"

    # 모드 — shadow(기본: 규칙으로 답하고 LLM 은 뒤에서 비교) · llm(LLM 으로 답) · rule(LLM 안 부름)
    python -m scripts.try_activity_judge --place 서울숲 --at "2026-10-08 15:00" --mode llm

무엇을 보여 주나
  ① 고객에게 나가는 결과(답변 · 성립 여부 · 실패 코드 · 경고)와 걸린 시간
  ② 판정 종류별 규칙 값 vs LLM 값 · 일치 · 실패 코드 · 지연 · 모델의 판단 이유

★`--at` 은 **앞으로의 시각**이어야 한다 — 지난 시각은 「이미 시작됨」에서 끝난다(위 예시 날짜도 지나면 바꿔 쓴다).
★재난문자는 실제 소스와 **같은 지역 판정**을 거친다 — 장소 좌표의 서울 자치구로 온 문자만 판정에 들어간다
  (부산 문자는 경복궁에 안 들어간다). 지역을 비우면 「서울특별시 전체」다.
★예약·장소·재난문자는 **가짜 도구**로 넣는다(DB 예약을 만들지 않는다). 판정 LLM · 프롬프트(DB 등록본) ·
  감사 기록(`llm_calls`)은 **실제**다. 장소는 CSV 장소 목록(`activity_total_data.csv`)에서 이름으로 찾아
  좌표 · 주소 · 분류를 채운다 — 못 찾으면 이름만으로 돈다.
★감사 기록은 `run_id` 없이 남긴다 — 이 스크립트의 작업은 `agent_runs` 에 없어 외래 키에 걸린다(4단계 실측).
★섀도 기록 표(`activity_judge_shadow`)에는 `origin='eval'` · `eval_run='try-<시각>'` 으로 쓴다 — 운영(`live`)
  집계에 섞이지 않게. `--no-db` 면 표에 쓰지 않는다.
★비용(추정): 원문 해석 판정은 건당 약 $0.0003, 웹 판정(실시간 운영 상태)은 약 $0.03. 웹 판정은 실외이거나
  시작까지 72시간 안일 때만 불린다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
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
        # 값 대신 함수를 넣으면 인자로 답을 만든다(재난문자 — 좌표마다 지역이 다르다)
        return value(**arguments) if callable(value) else value


class ScriptDisaster:
    """`--disaster` 문자를 **실제 재난문자 소스와 같은 지역 판정**으로 거른다. `[2026-10-07]`

    ★예전에는 넣은 문자를 「이 지역 문자」(`for_region`)에 그대로 넣었다 — 부산 문자가 경복궁 판정에 들어갔다.
      지금은 실제 소스(`DisasterMsgApi.near`)처럼 좌표 → 서울 자치구 → 그 구로 온 문자만 남긴다
      (`disaster_msg.judge` · `_lat_lon_to_gu` 를 그대로 쓴다). 창도 같다 — 지금과 일정 시각 중 이른 쪽에서 6시간.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def near(self, latitude: Any, longitude: Any, at: Any) -> dict[str, Any] | None:
        from app.infrastructure.travel.disaster_msg import DEFAULT_LOOKBACK_HOURS, _lat_lon_to_gu, judge

        if latitude is None or longitude is None:
            return None       # ★실제 도구와 같다 — 어디인지 모르면 묻지 않는다
        now = datetime.now(KST)
        when = at if isinstance(at, datetime) else now
        until = min(when.astimezone(KST), now)
        window_start = until - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
        district = _lat_lon_to_gu(float(latitude), float(longitude))
        messages, unclassified = judge(self.rows, region="서울", district=district,
                                       window_start=window_start, at=until)
        return {"region": "서울", "district": district, "for_region": messages, "unclassified": unclassified,
                "confirmed_at": now.isoformat(), "source": "try_activity_judge"}

    def read_disaster(self, latitude=None, longitude=None, at=None, **_: Any):
        return self.near(latitude, longitude, at)

    def read_points(self, points=None, at=None, **_: Any):
        if not isinstance(points, list):
            return None
        return {"points": [self.near(*(list(p) + [None, None])[:2], at) for p in points]}


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


def build_values(args: argparse.Namespace, starts: datetime) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from app.modules.travel_ops.activity.feasibility import _csv_lookup

    found = _csv_lookup.find(args.place)
    now = datetime.now(KST).isoformat()
    place: dict[str, Any] = {"place_id": "try-place", "name": args.place, "kind": "activity",
                             "weather_sensitive": {"outdoor": True, "indoor": False}.get(args.weather_sensitive),
                             "latitude": (found or {}).get("latitude"), "longitude": (found or {}).get("longitude"),
                             "source_content_id": (found or {}).get("content_id")}
    if args.restdate is not None or args.usetime is not None:
        place["operating"] = {"usetime_text": args.usetime, "restdate_text": args.restdate,
                              "source": "try_activity_judge", "confirmed_at": now}
    disaster = points = None
    if args.disaster or args.no_disaster_messages:
        created = datetime.now(KST)
        source = ScriptDisaster([parse_disaster(d, created) for d in args.disaster or []])
        disaster, points = source.read_disaster, source.read_points
    forecast = None
    if args.forecast:
        pop, _, wind = args.forecast.partition(",")
        forecast = {"matched_hour": starts.strftime("%H:00"), "precipitation_probability": int(pop),
                    "wind_speed_kmh": int(wind or 0), "source": "try_activity_judge", "confirmed_at": now}
    values = {
        "read.booking": {"booking_id": "try-booking", "place_id": "try-place", "starts_at": starts,
                         "party_size": args.party, "capacity": args.capacity},
        "read.policy": [{"note": "try_activity_judge"}],
        "read.place": place,
        "read.disaster": disaster,
        "read.disaster_points": points,
        "read.weather": forecast,
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
    print(f"   성립: {decision.get('feasible')}   상태: {decision.get('status')}   실패 코드: {decision.get('failure_code')}")
    print(f"   답변: {result.answer}")
    for warning in result.warnings:
        print(f"   경고: {warning}")


def print_judgments(records: list[dict[str, Any]], outputs: dict[str, Any], mode: str) -> None:
    print("\n② 판정 종류별 비교" + ("  (섀도 — 고객 결과에는 규칙 값이 쓰였다)" if mode == "shadow" else ""))
    if mode == "shadow":
        if not records:
            print("   (불린 판정이 없다 — 원문·재난문자를 넣었는지 보라)")
        for r in sorted(records, key=lambda r: r["kind"]):
            mark = "일치" if r.get("agree") else ("비교불가" if not r.get("comparable") else "불일치")
            fail = r.get("llm_failure_code") or ""
            err = f"({r['llm_error']})" if r.get("llm_error") else ""
            print(f"   {KIND_LABEL[r['kind']]:<9} 규칙={r['rule']:<11} LLM={str(r.get('llm')):<11} {mark:<5} "
                  f"{fail}{err}  {r.get('latency_ms') or '-'}ms")
    for kind, out in outputs.items():
        cites = [c.get("url") for c in out.get("citations") or []]
        print(f"   · {KIND_LABEL[kind]} — LLM 이유: {out.get('reason')}")
        if out.get("quotes"):
            print(f"       인용: {out['quotes']}")
        if cites:
            print(f"       출처: {cites}")


def wait_for_shadow(timeout: float = 180.0) -> bool:
    from app.modules.travel_ops.activity.judge import modes

    runner = modes.default_runner()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if runner._pending == 0:
            return True
        time.sleep(0.5)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="활동 판정 직접 돌려 보기")
    parser.add_argument("--place", required=True, help="장소 이름 — CSV 장소 목록에서 찾는다")
    parser.add_argument("--at", required=True, help='예약 시각 — "2026-10-13 14:00"(한국 시각) 또는 ISO')
    parser.add_argument("--restdate", help="휴무 원문 (예: 매주 월요일)")
    parser.add_argument("--usetime", help="운영시간 원문 (예: 09:00~18:00(입장마감 17:00))")
    parser.add_argument("--disaster", action="append", help='재난문자 "등급|구분|본문|지역" — 여러 번 줄 수 있다')
    parser.add_argument("--no-disaster-messages", action="store_true", help="재난문자 0건(조회는 됐다)으로 둔다")
    parser.add_argument("--weather-sensitive", choices=["outdoor", "indoor"],
                        help="DB 실내외 값을 정해 둔다. 없으면 판정한다")
    parser.add_argument("--forecast", help='예보 "강수확률,풍속" (예: 70,25). 없으면 예보를 못 읽은 것으로 둔다')
    parser.add_argument("--party", type=int, default=2)
    parser.add_argument("--capacity", type=int, default=10)
    parser.add_argument("--mode", choices=["shadow", "llm", "rule"], default="shadow")
    parser.add_argument("--no-db", action="store_true", help="섀도 기록 표에 쓰지 않는다")
    args = parser.parse_args(argv)

    from app.modules.travel_ops.activity import ActivityTeam

    starts = parse_at(args.at)
    values, found = build_values(args, starts)
    print(f"장소: {args.place} → " + (f"CSV {found['content_id']} · {found['address']}" if found
                                       else "CSV 에서 못 찾음(이름만으로 돈다 — 실내외·주소 단서가 줄어든다)"))
    print(f"시각: {starts.isoformat()}   모드: {args.mode}")
    if starts <= datetime.now(KST):
        print("   ★이미 지난 시각이다 — 「이미 시작됨」에서 끝나 휴무·재난문자·LLM 판정이 돌지 않는다")

    team = ActivityTeam(Tools(values))
    records: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}
    eval_run = "try-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if args.mode != "rule":
        team.judge_llm = make_judge_llm(outputs)
        team.judge_mode = args.mode
        team.judge_shadow_sink = make_sink(records, write_db=not args.no_db, eval_run=eval_run)

    started = time.monotonic()
    result = asyncio.run(team.execute(make_task(ActivityTeam)))
    print_result(result, time.monotonic() - started)

    if args.mode == "shadow":
        print("\n   …뒤에서 LLM 판정을 기다린다(웹 판정이 끼면 10~40초)", flush=True)
        if not wait_for_shadow():
            print("   (시간 안에 끝나지 않았다 — 끝난 것만 보인다)")
    if args.mode != "rule":
        print_judgments(records, outputs, args.mode)
        if args.mode == "shadow" and not args.no_db:
            print(f"\n   섀도 기록 표: SELECT * FROM activity_judge_shadow WHERE eval_run='{eval_run}';")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
