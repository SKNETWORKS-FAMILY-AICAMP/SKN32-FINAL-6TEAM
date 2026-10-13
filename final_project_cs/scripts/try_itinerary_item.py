"""일정 숙소 · 항공편 항목의 「바꿔 줘」(`lodging.itinerary` · `flight.itinerary`)를 한 번 직접 돌려 본다 — DB · 서버 · 모델 없이,
검색 소스(마이리얼트립 · 구글 · Ignav)는 실제로 부른다. `[2026-10-11]`

- 팀 본체(`LodgingTeam` · `FlightTeam`.execute)와 도구함(`ReadToolbox`) · 어댑터는 제품 코드 그대로다.
- 일정은 가짜다: 항목 하나(숙소 또는 항공편)만 든 여행을 만들어 `read.itinerary` 대신 준다(이 실행에서만). 접수 해석도 흉내 낸다
  (`interpretation.report.type = "change"`). 그래서 모델은 부르지 않는다.
- 팀이 내는 `itinerary.apply` 제안은 **적용하지 않는다**(DB 없음) — 제안에 실린 `detail.shown` 만 출력한다. 다음 「바꿔 줘」를 흉내 내려면
  출력된 이름을 `--shown` 에 넣어 다시 돌린다.
- 소스 호출: 숙소 = booking 1번(넓혀 찾으면 2번, 마이리얼트립 목록 + 구글 호텔). 항공 = booking 1번(마이리얼트립 + Ignav + 구글 항공권).
  예약 · 결제는 하지 않는다. 키 값은 출력하지 않는다.

실행 위치: final_project_cs
  python -m scripts.try_itinerary_item lodging --title "명동 숙소" --area 명동 --lat 37.5636 --lon 126.9834 --in 2026-11-06 --out 2026-11-09 --party 2
  python -m scripts.try_itinerary_item lodging ... --shown "호텔A;호텔B;호텔C"
  python -m scripts.try_itinerary_item flight --title "인천 → 나리타" --from ICN --to NRT --date 2026-11-06 --time 10:00 --party 2
  python -m scripts.try_itinerary_item flight ... --booked        # 예약한 항목 — 검색하지 않아야 한다
  python -m scripts.try_itinerary_item lodging ... --choose 1     # `[2026-10-12]` 이어서 1번 후보를 고른다(고를 때 가격 재확인까지)

`[2026-10-12]` `--choose N`: 「바꿔 줘」 제안의 항목 상세를 가짜 일정에 넣고, 같은 실행에서 N번 후보를 고르는 두 번째 일감을 돌린다
(`subject_ref.request.choice`). 고를 때 가격 재확인 — 숙소는 마이리얼트립 상세 1번(구글 호텔은 부르지 않음), 항공은 검색 1번이 더 나간다.
항공은 소스별 상태 · 걸린 시간(`elapsed`)도 찍는다.
"""
from argparse import ArgumentParser
import asyncio
from datetime import UTC, datetime, timedelta
import json
import platform
import time
from uuid import uuid4
from zoneinfo import ZoneInfo


def build_view(args) -> tuple[dict, str]:
    item_id = str(uuid4())
    detail = {"shown": [name for name in (args.shown or "").split(";") if name.strip()]}
    if args.kind == "lodging":
        place = {"place_id": str(uuid4()), "name": args.title, "kind": "lodging", "latitude": args.lat, "longitude": args.lon,
                 "district": args.area}
        item = {"item_id": item_id, "seq": 1, "kind": "lodging", "title": args.title, "place_id": place["place_id"],
                "starts_at": f"{args.check_in}T15:00:00+09:00", "ends_at": f"{args.check_out}T11:00:00+09:00",
                "place": place, "detail": {**detail, "area": args.area}}
    else:
        item = {"item_id": item_id, "seq": 1, "kind": "flight", "title": args.title, "place_id": None,
                "starts_at": f"{args.date}T{args.time}:00+09:00", "ends_at": None, "place": None,
                "detail": {**detail, "origin": args.origin, "destination": args.destination,
                           **({"direct_only": False} if args.connecting_ok else {})}}
    item.update({"locked": False, "booking_id": str(uuid4()) if args.booked else None, "replaces_item_id": None})
    return {"trip": {"trip_id": str(uuid4()), "version": 1, "party_size": args.party, "customer_id": "try", "constraints": {}},
            "items": [item]}, item_id


def main():
    from app.domains.travel_ops.ports.data_sources.base import TravelSources
    from app.domains.travel_ops.ports.data_sources.myrealtrip import MyRealTripMcp
    from app.tools.read_tools import ReadToolbox

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["lodging", "flight"])
    parser.add_argument("--title", required=True)
    parser.add_argument("--party", type=int, required=True)
    parser.add_argument("--shown", default="")
    parser.add_argument("--booked", action="store_true")
    parser.add_argument("--no-google", action="store_true")
    parser.add_argument("--area")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--in", dest="check_in")
    parser.add_argument("--out", dest="check_out")
    parser.add_argument("--from", dest="origin")
    parser.add_argument("--to", dest="destination")
    parser.add_argument("--date")
    parser.add_argument("--time", default="10:00")
    parser.add_argument("--connecting-ok", action="store_true")
    parser.add_argument("--choose", type=int, default=0)
    args = parser.parse_args()
    needed = (["area", "lat", "lon", "check_in", "check_out"] if args.kind == "lodging" else ["origin", "destination", "date"])
    missing = [name for name in needed if getattr(args, name) in (None, "")]
    if missing:
        parser.error(f"{args.kind} 에 필요한 값이 없다: {missing}")

    source = MyRealTripMcp()
    google = offers = None
    if args.kind == "lodging":
        from app.domains.travel_ops.instances.lodging import LodgingTeam as Team
        if not args.no_google:
            from app.domains.travel_ops.ports.data_sources.serpapi_hotels import SerpApiHotels
            from scripts.probe_serpapi_flights import load_key as serpapi_key
            try:
                google = SerpApiHotels(api_key=serpapi_key())
            except SystemExit as exc:
                print(f"구글 호텔 안 부름 — {exc}")
        travel = TravelSources(travel_search=source, stay_google=google)
    else:
        from app.domains.travel_ops.instances.flight import FlightTeam as Team
        from app.domains.travel_ops.ports.data_sources.ignav import IgnavMcp
        from scripts.probe_ignav_mcp import load_key
        try:
            offers = IgnavMcp(api_key=load_key())
        except SystemExit as exc:
            print(f"Ignav 안 부름 — {exc}")
        if not args.no_google:
            from app.domains.travel_ops.ports.data_sources.serpapi_flights import SerpApiFlights
            from scripts.probe_serpapi_flights import load_key as serpapi_key
            try:
                google = SerpApiFlights(api_key=serpapi_key())
            except SystemExit as exc:
                print(f"구글 항공권 안 부름 — {exc}")
        travel = TravelSources(travel_search=source, flight_offers=offers, flight_google=google)

    view, item_id = build_view(args)
    toolbox = ReadToolbox(lambda: None, travel=travel)
    toolbox.itinerary = lambda scope, **_: view          # DB 대신 가짜 일정(이 실행에서만)
    team = Team(toolbox, None)
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")
    result = run(team, args.kind, view, item_id, None, "이거 말고 다른 데로 바꿔 줘", source, offers, google)
    if not args.choose or not result.action_proposals:
        return
    held = result.action_proposals[0].arguments["replacements"][0]["item"]["detail"]
    options = held.get("alternates") or []
    if not 1 <= args.choose <= len(options):
        print(f"--choose {args.choose}: 후보가 {len(options)}개다")
        return
    view["items"][0]["detail"] = held                     # 제안을 적용한 것처럼(이 실행에서만)
    pick = options[args.choose - 1]
    print(f"\n── 이어서 {args.choose}번 고르기: {pick['name']} ──")
    run(team, args.kind, view, item_id, {"type": "change", "choice": pick["key"]}, f"{args.choose}번으로 할게", source, offers, google)


def run(team, kind, view, item_id, request, text, source, offers, google):
    from app.core.contracts import ContextPack, TeamTask

    case_id = uuid4()
    ref = {"kind": "trip", "id": view["trip"]["trip_id"], "part_id": item_id, "base_version": 1, **({"request": request} if request else {})}
    state = {"customer_id": str(uuid4()), "request_id": f"try-{uuid4().hex[:8]}", "subject_ref": ref,
             "interpretation": {"report": {"type": "change"}}}
    capability = type(team).select_capability(None, "바꿔 줘", state)
    pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id=kind, tenant_id="try", knowledge_scope=list(team.manifest.knowledge_scope),
                       current_state=state, estimated_input_tokens=1)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id=kind, capability=capability,
                    case_version=1, input_text=text, context=pack, allowed_tools=team.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(seconds=90))
    print(f"일감 {capability}")
    # `[2026-10-13]` role-manager 부터 팀이 원장 도구(`read.offers_shown`)를 부른다 — 조립 없이 돌리는 이 스크립트는 시험(conftest)처럼
    #   `standalone_services()` 안에서 돌려야 미등록 끼움 자리가 빈 값으로 지나간다(아니면 「service access requires a bound composition」)
    from app.core.service_bindings import standalone_services

    started = time.perf_counter()
    with standalone_services():
        result = asyncio.run(team.execute(task))
    took = time.perf_counter() - started
    print(f"[결과] {took:.1f}초 · outcome {result.outcome} · next_action {result.next_action.value}"
          + (f" · failure_code {result.failure_code}" if result.failure_code else "")
          + (f" · warnings {result.warnings}" if result.warnings else ""))
    print(f"[판단] {json.dumps(result.decisions[0] if result.decisions else {}, ensure_ascii=False, default=str)[:600]}")
    print(f"[근거] {[item.source_id for item in result.evidence]} · 못 가져온 것 마이리얼트립 {dict(source.misses) or '없음'}"
          + (f" · Ignav {dict(offers.misses) or '없음'}" if offers else "")
          + (f" · 구글 {dict(google.misses) or '없음'}" if google else ""))
    for item in result.evidence:
        value = item.value if isinstance(item.value, dict) else {}
        if item.source_id.startswith("read.booking_search_flights") and value.get("sources"):
            states = {name: state.get("status") for name, state in value["sources"].items()}
            print(f"[소스] {item.source_id} · 상태 {states} · 걸린 초 {value.get('elapsed')}")
    for proposal in result.action_proposals:
        asked = proposal.arguments.get("ask_options")
        if asked:
            # `[2026-10-13]` role-manager — 후보는 일정에 싣지 않고 「선택이 필요해요」 보류 제안(`ask_options`)으로 낸다(판 그대로)
            options = asked.get("options") or []
            print(f"[제안] {proposal.action_type} · ask_options(판 그대로) · 승인 필요 {proposal.approval_required} · 이유 {proposal.arguments['reason']}"
                  f" · 후보 {len(options)} · shown_key {asked.get('shown_key')}")
            print(f"[다음 --shown] {';'.join(str(o.get('name')) for o in options)}")
        else:
            new = proposal.arguments["replacements"][0]["item"]
            print(f"[제안] {proposal.action_type} · 승인 필요 {proposal.approval_required} · 이유 {proposal.arguments['reason']}"
                  f" · 항목 종류 {new['kind']} · 제목 {new['title']}")
            if proposal.arguments.get("summary", {}).get("price_check"):
                print(f"[가격 재확인] {proposal.arguments['summary']['price_check']}")
            print(f"[다음 --shown] {';'.join(new['detail'].get('shown') or [])}")
            options = new["detail"].get("alternates") or []
        for option in options:
            if option.get("sellers") or option.get("image"):
                print(f"[후보] {option.get('rank')}) {option.get('name')} · 사진 {'있음' if option.get('image') else '없음'} · "
                      f"주소 {'있음' if option.get('address') else '없음'} · 링크 {option.get('link')}")
                for seller in option.get("sellers") or []:
                    print(f"        {seller['name']} 1박 {int(seller['price_per_night']):,}원 · {seller.get('link')}")
    print("[답]")
    print(result.answer or "(없음)")
    return result

if __name__ == "__main__":
    main()
