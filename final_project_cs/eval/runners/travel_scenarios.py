# -*- coding: utf-8 -*-
"""여행 평가 — 시나리오를 흘리고 **적용된 모든 일정 버전**에서 필수 조건 위반을 센다(v11 §12 DoD-22).

    python -m eval.runners.travel_scenarios
    python -m eval.runners.travel_scenarios --case t-cash-only --keep     # 한 건만, 테넌트 남기기

★`[2026-09-22]` 전에는 이 항목이 **미측정**이었다. 골든셋 72건은 쇼핑몰 시절 것이고 여행용은 0건이라,
  「평가 시나리오에서 필수 조건 위반 0건」을 잴 분모 자체가 없었다.

★**무엇을 재나.** 확정 시나리오 하루(`app/modules/travel_ops/scenarios/seoul_day_taiwan_friends.json`)를
  변형해 흘리고, 우리가 **만든 모든 일정 버전**을 등록 때와 **같은 판정기**(`itinerary_checks`)로 다시 본다.
  고친 결과가 규정을 깨면 그 자리에서 잡힌다 — 겹침 · 이동 소요 · 영업시간 · 브레이크 · 결제 수단 · 예산.

★**LLM 을 부르지 않는다.** 분류·신고 추출은 흉내이고 감시 소스는 재생이다. 이 측정이 보는 것은
  **판단과 적용**이지 모델의 말솜씨가 아니다. 모델까지 넣은 실측은 따로 잰다(이식 검증 §7).

★**표본이 작다.** 시나리오 10건 · 하루 1종 · 서울 1도시다. 이 수치는 **이 시나리오들에서 위반이
  나오지 않는다**는 뜻이지, 다른 일정에서도 안 난다는 뜻이 아니다(`CLAUDE.md` §4 — 표본이 작으면 작다고 말한다).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_PATH = ROOT / "app" / "modules" / "travel_ops" / "scenarios" / "seoul_day_taiwan_friends.json"
DATASET = ROOT / "eval" / "datasets" / "travel_scenarios.jsonl"
REPORTS = ROOT / "eval" / "reports"
KST = ZoneInfo("Asia/Seoul")


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _classifier(message: str) -> dict[str, str]:
    """★실제 gemma4:12b 가 붙이는 라벨을 흉내 낸다(2026-09-17 실측) — 접두가 자주 빗나간다."""
    if "늦" in message:
        return {"intent": "incident_report", "issue_code": "activity_time_conflict", "sentiment": "negative"}
    if "휴무" in message:
        return {"intent": "incident_report", "issue_code": "dining_other", "sentiment": "negative"}
    if any(word in message for word in ("바꿔", "되돌려")):
        return {"intent": "adjust_reject", "issue_code": "booking_change_request", "sentiment": "neutral"}
    return {"intent": "other", "issue_code": "other", "sentiment": "neutral"}


def _extractor_for(data: dict[str, Any]):
    reports = {report["type"]: report for report in data["customer_reports"]}

    def extract(message: str) -> dict[str, Any]:
        import re

        if "되돌려" in message:
            return {"type": "rollback", "to_version": int(re.findall(r"\d+", message)[0])}
        if "바꿔" in message:
            return {"type": "change"}
        for kind, report in reports.items():
            if report["message"] in message:
                minutes = report.get("minutes")
                tail = re.findall(r"\((\d+)분\)", message)          # 늦음 분을 바꿔 보낸 경우
                return {"type": kind, "minutes": int(tail[0]) if tail else minutes,
                        "products": report.get("products", [])}
        return {"type": "other"}

    return extract


def _seed(tenant: str, data: dict[str, Any], constraints: dict[str, Any]):
    """확정 시나리오의 장소·일정을 이 테넌트에 넣는다(등록 API 와 같은 모양)."""
    from app.infrastructure.db.session import get_connection
    from app.modules.travel_ops.itinerary import Item, TripStore

    day = data["trip"]["date"]

    def at(hhmm: str) -> datetime:
        return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=KST)

    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "travel eval"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "eval"))
            customer = cur.fetchone()[0]
            place_ids = {}
            for place in data["places"]:
                cur.execute(
                    "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING place_id",
                    (tenant, place["name"], place["kind"], place["lat"], place["lon"],
                     place["weather_sensitive"], json.dumps(place["attributes"], ensure_ascii=False)))
                place_ids[place["key"]] = cur.fetchone()[0]
        store = TripStore(tenant)
        items = [Item(item_id=uuid4(), seq=it["seq"], kind=it["kind"], title=it["title"],
                      place_id=place_ids.get(it.get("place")), starts_at=at(it["start"]),
                      ends_at=at(it["end"]),
                      detail={**it.get("detail", {}),
                              **({"route": it["route"], "route_def": data["routes"][it["route"]]}
                                 if "route" in it else {})})
                 for it in data["items"]]
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title=data["trip"]["title"],
                                           locale=data["trip"]["locale"],
                                           party_size=data["trip"]["party_size"], items=items,
                                           constraints=constraints)
    return store, customer, trip_id, at


#: 사건을 「없던 일」로 만들 때 쓰는 평상 수치. ★빼는 것과 다르다 — 빼면 그 시간대에 **값이 없어**
#: 소스가 답하지 않은 것이 되고(결정 15 의 치명), 그건 「사건이 없는 하루」가 아니다. 첫 두 실행에서
#: 실제로 그렇게 났다(대기질 사건을 빼자 09:00 송파구 값이 사라져 치명).
CALM = {"air_quality": {"pm10Value": "48", "pm25Value": "22", "pm10Grade": "2", "pm25Grade": "2"}}


def _calm_or_drop(event: dict[str, Any]) -> dict[str, Any] | None:
    """평상 수치가 있는 종류면 값을 바꾸고, 없으면 뺀다(경로 사건은 없는 것이 곧 평상이다)."""
    calm = CALM.get(str(event.get("kind")))
    if calm is None:
        return None
    return {**event, "value": {**(event.get("value") or {}), **calm}, "_scene": None}


def _engine(tenant: str, data: dict[str, Any], drop_scenes: list[str], clock: Clock):
    from app.infrastructure.travel.base import TravelSources
    from app.infrastructure.travel.disruptions import DisruptionCheck
    from app.infrastructure.travel.replay import (ReplayAir, ReplayRouteEvents, ReplayTimeline,
                                                  ReplayWarning, ReplayWeather)
    from app.modules.travel_ops.case_engine import CaseEngine

    # ★**사건만 뺀다**(`_scene` 이 붙은 항목). 종류를 통째로 빼면 그 소스가 **답하지 않는 것**이 되어
    #   대체까지 실패(결정 15 의 치명)로 읽힌다 — 첫 실행에서 실제로 그렇게 났다. 평상값은 남긴다.
    events = []
    for event in data["timeline"]:
        if any(scene in str(event.get("_scene") or "") for scene in drop_scenes):
            calmed = _calm_or_drop(event)
            if calmed is not None:
                events.append(calmed)
            continue
        events.append(event)
    timeline = ReplayTimeline(events, clock)
    sources = TravelSources(weather=ReplayWeather(timeline), warning=ReplayWarning(timeline),
                            air=ReplayAir(timeline))
    check = DisruptionCheck(sources, limits=lambda: (60, 30)).check
    return CaseEngine(tenant_id=tenant, check=check, route_events=ReplayRouteEvents(timeline),
                      classifier=_classifier, report_extractor=_extractor_for(data), clock=clock)


def _violations(store, trip_id, data) -> list[dict[str, Any]]:
    """★적용된 **모든 버전**을 등록 때와 같은 판정기로 다시 본다 — 마지막 것만 보면 중간에 깬 것을 놓친다."""
    from app.infrastructure.db.session import get_connection
    from app.modules.travel_ops.itinerary_checks import check_itinerary, parts_from_items

    trip_constraints, found = None, []
    with get_connection() as conn:
        trip, _ = store.latest(conn, trip_id)
        trip_constraints = trip["constraints"] or {}
        for version in range(1, trip["version"] + 1):
            items = store.items(conn, trip_id, version)
            for violation in check_itinerary(parts_from_items(items, data["routes"]),
                                             constraints=trip_constraints,
                                             party_size=trip.get("party_size")):
                found.append({"version": version, **violation.as_dict()})
    return found


def run_case(spec: dict[str, Any], *, keep: bool = False) -> dict[str, Any]:
    from app.infrastructure.db.session import get_connection
    from app.modules.travel_ops.case_engine import cleanup_tenant

    data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    reports = {report["type"]: report for report in data["customer_reports"]}
    tenant = "eval_" + uuid4().hex[:10]
    store, customer, trip_id, at = _seed(tenant, data, spec.get("constraints") or {})
    clock = Clock(at("08:00"))
    engine = _engine(tenant, data, spec.get("drop_scenes") or [], clock)
    outcome = {"case_id": spec["case_id"], "what": spec.get("what", ""), "tenant": tenant,
               "steps": [], "cases": {"resolved": 0, "escalated": 0}, "fatal": 0}
    try:
        for step in spec["steps"]:
            outcome["steps"].append(_step(step, engine=engine, store=store, trip_id=trip_id,
                                          customer=customer, clock=clock, at=at, reports=reports,
                                          counts=outcome))
        outcome["violations"] = _violations(store, trip_id, data)
        with get_connection() as conn:
            trip, items = store.latest(conn, trip_id)
            outcome["versions"] = trip["version"]
            outcome["last_items"] = [f"{item.seq} {item.title}" for item in sorted(items, key=lambda i: i.seq)]
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice'", (tenant,))
                outcome["notices"] = cur.fetchone()[0]
    finally:
        if not keep:
            cleanup_tenant(tenant)
            with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
    outcome["verdict"] = _verdict(outcome, spec.get("expect") or {})
    return outcome


def _step(step: str, *, engine, store, trip_id, customer, clock, at, reports, counts) -> dict[str, Any]:
    kind, _, rest = step.partition(":")
    if kind == "tick":
        clock.now = at(rest)
        result = engine.tick()
        for run in result.ran:
            counts["cases"]["resolved" if run.get("status") == "resolved" else "escalated"] += 1
        counts["fatal"] += len(result.fatal)
        return {"step": step, "opened": len(result.opened), "fatal": len(result.fatal)}
    if kind == "say":
        name, _, minutes = rest.partition(":")
        report = reports[name]
        clock.now = at(report["at"])
        text = report["message"] + (f" ({minutes}분)" if minutes else "")
        view = engine.message(customer_id=customer, trip_id=trip_id, text=text,
                              request_id=f"eval-{name}-{uuid4().hex[:6]}")
        counts["cases"]["resolved" if view["case_status"] == "resolved" else "escalated"] += 1
        return {"step": step, "status": view["case_status"], "team": view["owner_team_id"]}
    if kind in ("swap", "rollback"):
        from app.infrastructure.db.session import get_connection

        with get_connection() as conn:
            trip, items = store.latest(conn, trip_id)
        if kind == "swap":
            target = next(item for item in items if item.seq == int(rest))
            view = engine.message(customer_id=customer, trip_id=trip_id, text="화면에서 다른 안 선택",
                                  request_id=f"eval-swap-{uuid4().hex[:6]}", part_id=target.item_id,
                                  base_version=trip["version"], request={"type": "change"})
        else:
            view = engine.message(customer_id=customer, trip_id=trip_id,
                                  text=f"{rest}번 일정으로 되돌려 주세요",
                                  request_id=f"eval-back-{uuid4().hex[:6]}", base_version=trip["version"],
                                  request={"type": "rollback", "to_version": int(rest)})
        counts["cases"]["resolved" if view["case_status"] == "resolved" else "escalated"] += 1
        return {"step": step, "status": view["case_status"], "team": view["owner_team_id"]}
    raise ValueError(f"모르는 단계: {step}")


def _verdict(outcome: dict[str, Any], expect: dict[str, Any]) -> dict[str, Any]:
    """★기대와 다르면 **왜 다른지**를 남긴다. 「통과/실패」만 적으면 다음 사람이 다시 판다."""
    failures = []
    if len(outcome["violations"]) > int(expect.get("violations", 0)):
        failures.append(f"필수 조건 위반 {len(outcome['violations'])}건")
    if "min_versions" in expect and outcome["versions"] < expect["min_versions"]:
        failures.append(f"일정 버전 {outcome['versions']} < 기대 {expect['min_versions']}")
    if "max_versions" in expect and outcome["versions"] > expect["max_versions"]:
        failures.append(f"일정 버전 {outcome['versions']} > 기대 {expect['max_versions']}")
    if outcome["fatal"]:
        failures.append(f"소스가 대체까지 실패 {outcome['fatal']}건(결정 15)")
    return {"passed": not failures, "failures": failures}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--case", default=None, help="이 case_id 하나만 돌린다")
    parser.add_argument("--keep", action="store_true", help="테넌트를 지우지 않는다(들여다볼 때)")
    parser.add_argument("--out", default=None, help="보고서 경로. 기본은 eval/reports/travel_scenarios_<run>.json")
    args = parser.parse_args()

    specs = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.case:
        specs = [spec for spec in specs if spec["case_id"] == args.case]
    run_id = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    results = []
    print(f"여행 평가 — 시나리오 {len(specs)}건 (run {run_id})")
    for spec in specs:
        outcome = run_case(spec, keep=args.keep)
        results.append(outcome)
        mark = "통과" if outcome["verdict"]["passed"] else "실패"
        print(f"  {outcome['case_id']:<16} 버전 {outcome['versions']} · 통지 {outcome['notices']} · "
              f"Case 해결 {outcome['cases']['resolved']}/사람 {outcome['cases']['escalated']} · "
              f"위반 {len(outcome['violations'])} · {mark}"
              + ("" if outcome["verdict"]["passed"] else " — " + ", ".join(outcome["verdict"]["failures"])))
        for violation in outcome["violations"]:
            print(f"      v{violation['version']} {violation['code']}: {violation['reason']}")

    passed = sum(result["verdict"]["passed"] for result in results)
    total_violations = sum(len(result["violations"]) for result in results)
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else REPORTS / f"travel_scenarios_{run_id}.json"
    out.write_text(json.dumps({"run_id": run_id, "dataset": args.dataset, "llm": "흉내(분류·추출)",
                               "sources": "재생", "results": results,
                               "summary": {"cases": len(results), "passed": passed,
                                           "violations": total_violations}},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"통과 {passed}/{len(results)} · 필수 조건 위반 **{total_violations}건**  → {out}")
    print("★표본은 시나리오 " + str(len(results)) + "건 · 하루 1종 · 서울 1도시다. 다른 일정을 대표하지 않는다.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
