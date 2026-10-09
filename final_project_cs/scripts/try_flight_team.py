"""항공 팀을 문장 하나로 직접 돌려 본다 — DB · 서버 없이, 모델과 마이리얼트립은 실제로 부른다(`try_lodging_team` 과 같은 방식).

- 문장 하나 = 모델 호출 1번 + 마이리얼트립 항공 검색 1번 + Ignav(판매처 비교) 검색 1번. 예약 · 결제는 하지 않는다.
- `[2026-10-09]` Ignav 키(ACOP_IGNAV_API_KEY, 환경변수 또는 .env.apikeys)가 없으면 마이리얼트립만 부른다. 키 값은 출력하지 않는다.
  `--no-ignav` 를 주면 키가 있어도 마이리얼트립만 부른다.
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
    from app.domains.travel_ops.ports.data_sources.myrealtrip import MyRealTripMcp
    from app.tools.read_tools import ReadToolbox
    from scripts.try_lodging_team import FilePromptLLM

    sentences = [arg for arg in sys.argv[1:] if arg != "--no-ignav"]
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
    print(f"소스: 마이리얼트립" + (" + Ignav" if offers else " 만"))
    for text in sentences:
        llm = FilePromptLLM()
        team = FlightTeam(ReadToolbox(lambda: None, travel=TravelSources(travel_search=source, flight_offers=offers)), llm)
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
        print(f"[판단] task {decision.get('task')} · needs {decision.get('needs')} · found {decision.get('found')}")
        both = decision.get("both")
        if both is not None:
            print(f"[같은 편] 두 소스가 다 판 편 {len(both)}개 (마이리얼트립 / Ignav 최저가)")
            for row in both:
                print(f"  {row['flight']} {row['depart']} · {row['myrealtrip']} / {row['ignav']}")
        print(f"[근거] {[item.source_id for item in result.evidence]} · 못 가져온 것 마이리얼트립 {dict(source.misses) or '없음'}"
              + (f" · Ignav {dict(offers.misses) or '없음'}" if offers else ""))
        print("[답]")
        print(result.answer or "(없음)")


if __name__ == "__main__":
    main()
