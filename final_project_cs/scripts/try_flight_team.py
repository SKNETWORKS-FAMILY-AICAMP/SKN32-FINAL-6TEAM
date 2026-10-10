"""항공 팀을 문장 하나로 직접 돌려 본다 — DB · 서버 없이, 모델과 마이리얼트립은 실제로 부른다(`try_lodging_team` 과 같은 방식).

- 문장 하나 = 모델 호출 1번 + 마이리얼트립 항공 검색 1번 + Ignav(판매처 비교) 검색 1번. 예약 · 결제는 하지 않는다.
- `[2026-10-09]` Ignav 키(ACOP_IGNAV_API_KEY, 환경변수 또는 .env.apikeys)가 없으면 마이리얼트립만 부른다. 키 값은 출력하지 않는다.
  `--no-ignav` 를 주면 키가 있어도 마이리얼트립만 부른다. `--fetch N` 은 소스마다 받는 수(기본 10).
  `[2026-10-09]` SerpApi 키(ACOP_SERPAPI_API_KEY)가 있으면 구글 항공권도 부른다 — 문장마다 1회(무료 월 250회). `--no-google` 로 끈다.
- 국내선 검색은 한 번에 10초 가까이 걸릴 수 있다(2026-10-07 17:31 playdata, 9.49초).

실행 위치: final_project_cs
  python -m scripts.try_flight_team "11월 6일 타이베이에서 인천 가는 직항 2명"
  python -m scripts.try_flight_team "김포에서 제주 11월 6일 갔다가 9일에 오는 비행기 성인 1명"
"""
import asyncio
from datetime import UTC, datetime, timedelta
import json
import platform
import sys
import time
from uuid import uuid4
from zoneinfo import ZoneInfo


def main():
    from app.core.contracts import ContextPack, TeamTask
    from app.domains.travel_ops.instances.flight import FlightTeam
    from app.domains.travel_ops.ports.data_sources.base import TravelSources
    from app.domains.travel_ops.ports.data_sources.ignav import IgnavMcp
    from app.domains.travel_ops.ports.data_sources.serpapi_flights import SerpApiFlights
    from app.domains.travel_ops.ports.data_sources.myrealtrip import MyRealTripMcp
    from app.tools.read_tools import ReadToolbox
    from scripts.try_lodging_team import FilePromptLLM

    import app.domains.travel_ops.instances.flight.team as flight_team

    args = sys.argv[1:]
    if "--fetch" in args:                             # 소스마다 받는 수를 바꿔 재 본다(기본 team.FETCH)
        at = args.index("--fetch")
        flight_team.FETCH = int(args[at + 1])
        del args[at:at + 2]
    sentences = [arg for arg in args if arg not in ("--no-ignav", "--no-google")]
    if not sentences:
        raise SystemExit(__doc__)
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")
    source = MyRealTripMcp()                          # 문장 사이에 공유한다 — 429 를 받으면 그 뒤 문장은 부르지 않는다
    offers = None
    if "--no-ignav" not in sys.argv:
        from scripts.probe_ignav_mcp import load_key
        try:
            offers = IgnavMcp(api_key=load_key())
        except SystemExit as exc:
            print(f"Ignav 안 부름 — {exc}")
    google = None
    if "--no-google" not in sys.argv:
        from scripts.probe_serpapi_flights import load_key as serpapi_key
        try:
            google = SerpApiFlights(api_key=serpapi_key())
        except SystemExit as exc:
            print(f"구글 항공권 안 부름 — {exc}")
    print("소스: 마이리얼트립" + (" + Ignav" if offers else "") + (" + 구글 항공권(SerpApi, 1회 씀)" if google else "")
          + f" · 소스마다 {flight_team.FETCH}개")
    timings: list[tuple[str, float, int | None]] = []

    def timed(label, search):                         # 소스마다 걸린 시간을 잰다 — 값은 바꾸지 않는다
        def run(**kwargs):
            started = time.perf_counter()
            found = search(**kwargs)
            timings.append((label, time.perf_counter() - started,
                            len(found.get("flights") or []) if isinstance(found, dict) else None))
            return found
        return run

    source.flight_search = timed("마이리얼트립", source.flight_search)
    if offers:
        offers.flight_search = timed("Ignav", offers.flight_search)
    if google:
        google.flight_search = timed("구글 항공권", google.flight_search)
    for text in sentences:
        timings.clear()
        llm = FilePromptLLM()
        team = FlightTeam(ReadToolbox(lambda: None, travel=TravelSources(travel_search=source, flight_offers=offers, flight_google=google)), llm)
        case_id = uuid4()
        pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="flight", tenant_id="try", knowledge_scope=["flight"],
                           current_state={"customer_id": str(uuid4())}, estimated_input_tokens=1)
        task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="flight", capability="flight.assist",
                        case_version=1, input_text=text, context=pack, allowed_tools=team.manifest.allowed_tools,
                        deadline_at=datetime.now(UTC) + timedelta(seconds=90))
        started = time.perf_counter()
        result = asyncio.run(team.execute(task))
        took = time.perf_counter() - started
        print(f"\n[문장] {text}")
        for model, seconds, raw in llm.seen:
            print(f"[해석] 모델 {model} · {seconds:.1f}초 · {json.dumps(raw, ensure_ascii=False)}")
        print(f"[결과] {took:.1f}초 · outcome {result.outcome} · next_action {result.next_action.value}"
              + (f" · failure_code {result.failure_code}" if result.failure_code else "")
              + (f" · warnings {result.warnings}" if result.warnings else ""))
        decision = (result.decisions or [{}])[0]
        print(f"[판단] task {decision.get('task')} · needs {decision.get('needs')} · found {decision.get('found')}"
              f" · 시간대 {decision.get('times')} · 빈 시간대 {decision.get('empty_bands')} · 대체 {decision.get('fallback')}")
        both = decision.get("both")
        if both is not None:
            print(f"[같은 편] 두 소스가 다 판 편 {len(both)}개 (마이리얼트립 / Ignav 최저가)")
            for row in both:
                print(f"  {row['flight']} {row['depart']} · {row['myrealtrip']} / {row['ignav']}")
        print(f"[근거] {[item.source_id for item in result.evidence]} · 못 가져온 것 마이리얼트립 {dict(source.misses) or '없음'}"
              + (f" · Ignav {dict(offers.misses) or '없음'}" if offers else "")
              + (f" · 구글 항공권 {dict(google.misses) or '없음'}" if google else ""))
        print("[소스 시간] " + (" · ".join(f"{label} {seconds:.1f}초 {count if count is not None else '실패'}개"
                                          for label, seconds, count in timings) or "부르지 않음"))
        print("[답]")
        print(result.answer or "(없음)")


if __name__ == "__main__":
    main()
