"""서울 실경보 28건을 저장 XML과 명시적 시험 일정으로만 재현합니다.

외부 통신·DB·하위 프로세스를 막고 기존 UTIC/DisruptionCheck 계산을 호출합니다.
정답 검토 파일과 사건 원문은 git 밖 var에 둡니다. 제품 코드·원본을 수정하지 않습니다.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

CS = Path(__file__).resolve().parents[1]
DATA = CS / "var/alert-snapshots/analysis"
KST = ZoneInfo("Asia/Seoul")


class FutureObservation(ValueError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value):
    with path.open("x", encoding="utf-8") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


def moment(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("시간대가 필요합니다")
    return result.astimezone(KST)


def provider_time(value: str) -> datetime:
    parts = [int(p) for p in re.findall(r"\d+", value)]
    if len(parts) != 5:
        raise ValueError(f"공급자 시각 형식 오류: {value}")
    return datetime(*parts, tzinfo=KST)


def offline_boundary():
    attempts = Counter()

    def deny(kind):
        def blocked(*_args, **_kwargs):
            attempts[kind] += 1
            raise RuntimeError(f"로컬 재생에서 {kind} 호출을 차단했습니다")
        return blocked

    socket.socket.connect = deny("network")
    socket.socket.connect_ex = deny("network")
    socket.create_connection = deny("network")
    socket.getaddrinfo = deny("network")
    sqlite3.connect = deny("database")
    subprocess.Popen = deny("subprocess")
    return attempts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DATA / "2026-10-12-handoff-v1/seoul-28-candidates.json")
    parser.add_argument("--annotations", type=Path,
                        default=DATA / "2026-10-12-seoul28-replay-v1/annotations.json")
    parser.add_argument("--out", type=Path, help="새 폴더만 허용합니다. 생략하면 새 시각 폴더를 만듭니다.")
    args = parser.parse_args()
    attempts = offline_boundary()
    sys.path.insert(0, str(CS))
    from app.domains.travel_ops.ports.data_sources.base import TravelSources
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
    from app.domains.travel_ops.ports.data_sources.utic import UticIncidents, UticRouteEvents, parse_records
    import httpx

    code_files = sorted({Path(module.__file__).resolve() for name, module in list(sys.modules.items())
                         if name.startswith("app.") and getattr(module, "__file__", None)
                         and str(module.__file__).endswith(".py")})
    protected = {str(path.relative_to(CS)): sha(path) for path in code_files}
    protected[str(args.input.resolve().relative_to(CS))] = sha(args.input)
    protected[str(args.annotations.resolve().relative_to(CS))] = sha(args.annotations)
    protected[str(Path(__file__).resolve().relative_to(CS))] = sha(Path(__file__))
    original = read(args.input)
    annotations = read(args.annotations)
    labels = {row["id"]: row for row in annotations["cases"]}
    assert len(original["cases"]) == len(labels) == 28
    assert {case["incident_id"] for case in original["cases"]} == set(labels)

    snapshots = {}
    provenance_checks = []
    for case in original["cases"]:
        for observation in case["observations"]:
            collection = (CS / observation["collection"]).resolve()
            raw = (CS / observation["raw"]).resolve()
            for path in (collection, raw):
                if not path.is_relative_to((CS / "var/alert-snapshots/real").resolve()):
                    raise ValueError("원본 경로가 허용된 real 범위 밖입니다")
                protected[str(path.relative_to(CS))] = sha(path)
            if sha(collection) != observation["collection_sha256"]:
                raise ValueError("인계 이후 수집 결과 파일 해시가 달라졌습니다")
            key = observation["raw"]
            if key not in snapshots:
                bodies = read(raw)
                body = next(row for row in bodies if row["kind"] == "provider_xml")
                http = next(row for row in bodies if row["kind"] == "http_body")
                rows = parse_records(body["body"])
                if rows is None or http["http_status"] != 200 or body.get("from_cache") is not False:
                    raise ValueError("이 실행기는 성공한 새 응답 XML만 재생합니다")
                snapshots[key] = {"xml": body["body"], "rows": rows,
                                  "available_at": moment(body["confirmed_at"]),
                                  "received_at": moment(http["received_at"]),
                                  "body_sha256": body["sha256"],
                                  "raw_file_sha256": sha(raw)}
            snapshot = snapshots[key]
            record = observation["record"]
            matches = [row for row in snapshot["rows"] if row.get("incidentId") == case["incident_id"]]
            collection_rows = read(collection)["sources"]["utic"]["value"]
            if matches != [record] or record not in collection_rows:
                raise ValueError("인계 행과 원문·수집 결과가 일치하지 않습니다")
            provenance_checks.append({"incident_id": case["incident_id"], "raw": key, "passed": True})

    def available_snapshot(case, clock):
        eligible = [o for o in case["observations"] if snapshots[o["raw"]]["available_at"] <= clock]
        if not eligible:
            raise FutureObservation("재현 시각 뒤에 확보한 응답을 미리 공급할 수 없습니다")
        observation = max(eligible, key=lambda o: snapshots[o["raw"]]["available_at"])
        return observation, snapshots[observation["raw"]]

    replay_transports = Counter()

    class SavedUtic(UticIncidents):
        def __init__(self, snapshot, clock, incident_id=None):
            self.snapshot = snapshot
            self.incident_id = incident_id
            super().__init__(service_key="offline-no-credential", now=lambda: clock,
                             transport=self.saved_response)

        def saved_response(self, _url, _params):
            replay_transports["memory_xml_reads"] += 1
            return httpx.Response(200, text=self.snapshot["xml"])

        def _remember(self, _url, _params, _value):
            self._fetch_state.fetched_at = self.snapshot["available_at"]
            self._fetch_state.from_cache = False

        def records(self):
            rows = super().records()
            if rows is not None and self.incident_id is not None:
                return [row for row in rows if row["incidentId"] == self.incident_id]
            return rows

    results = []
    all_tests = []
    guards = []
    for candidate in original["cases"]:
        incident_id = candidate["incident_id"]
        label = labels[incident_id]
        first = min(candidate["observations"], key=lambda o: snapshots[o["raw"]]["available_at"])
        clock = snapshots[first["raw"]]["available_at"] + timedelta(microseconds=1)
        observation, snapshot = available_snapshot(candidate, clock)
        row = observation["record"]
        start, end = provider_time(row["startDate"]), provider_time(row["endDate"])
        if not start <= clock < end:
            raise ValueError(f"{incident_id}: 최초 관측 시점에 진행 중인 사건이 아닙니다")
        update = provider_time(row["updateDate"]) if row.get("updateDate") else None
        if update is not None and update > clock:
            raise FutureObservation("관측 시각 이후 갱신 행입니다")
        x, y = float(row["locationDataX"]), float(row["locationDataY"])
        if not (-180 <= x <= 180 and -90 <= y <= 90):
            raise ValueError("좌표 범위 오류")
        road = row["roadName"]
        match = re.match(r"\[[^]]+\]\s*" + re.escape(road) + r"\s+(.+?) 에서 (.+?) 방향", row["incidentTitle"])
        section = {"from": match[1], "to": match[2]} if match else {
            "from": "원문 구간 시작", "to": "원문 구간 끝", "unparsed": True}
        known_links = list(dict.fromkeys([part for value in (row.get("linkId", ""), row.get("lineLinkId", ""))
                                        for part in value.split(",") if part and part != "null"]))
        expected = label["expected"]
        near_impact = expected == "disruption"
        place = {"place_id": "synthetic-road-point-" + incident_id, "latitude": y, "longitude": x,
                 "weather_sensitive": False, "synthetic": True,
                 "meaning": "공급자 도로 지점. 관광지 입구 좌표가 아닙니다"}
        move_end = min(clock + timedelta(minutes=1), end)
        itinerary = {
            "origin": "explicit_synthetic_itinerary", "actual_customer_trip": False,
            "city": "서울", "travelers": 4, "purpose": label["purpose"],
            "visit_example": {"title": "서울 관광 방문(시험용)",
                              "starts_at": (clock + timedelta(minutes=90)).isoformat(),
                              "ends_at": (clock + timedelta(minutes=150)).isoformat(),
                              "opening_hours_verified": False},
            "move": {"mode": "taxi", "starts_at": clock.isoformat(), "ends_at": move_end.isoformat(),
                     "uses": ["도로:" + road], "declared_section": section,
                     "direction": "원문 진행방향", "provider_links": known_links,
                     "passes_provider_point": {"latitude": y, "longitude": x},
                     "route_geometry_verified": False, "travel_duration_verified": False,
                     "input_note": "해당 구간 통과를 시험 조건으로 명시. 실제 길찾기 결과가 아님"}}
        source = SavedUtic(snapshot, clock, incident_id)
        routes = UticRouteEvents(source)
        tests = []

        def record_test(name, wanted, actual, kind="product_rule", meaning=""):
            entry = {"name": name, "kind": kind, "expected": wanted, "actual": actual,
                     "passed": actual == wanted, "meaning": meaning}
            tests.append(entry)
            all_tests.append({"incident_id": incident_id, **entry})

        def target_level(result):
            if any(hit["incident_id"] == incident_id for hit in result["for_place"]):
                return "disruption"
            if any(hit["incident_id"] == incident_id for hit in result["advisories"]):
                return "advisory"
            return "absent"

        point_result = source.near(latitude=y, longitude=x, at=clock)
        record_test("point_at_observation", expected, target_level(point_result),
                    meaning="공급자 지점을 통과한다는 시험 조건의 사고/주의 구분")
        check_result = DisruptionCheck(TravelSources(traffic=source), limits=lambda: (60, 30),
                                       quake_rules=lambda: (4, 100, 24)).check(place=place, starts_at=clock)
        record_test("traffic_check_integration", "disrupted" if near_impact else "clear",
                    check_result["verdict"], meaning="교통 소스만 연결한 판정기. 다른 미연결 소스의 안전 통과를 뜻하지 않음")
        far = source.near(latitude=y + 0.1, longitude=x, at=clock)
        record_test("different_point", "absent", target_level(far),
                    meaning="위도 0.1도를 옮긴 명시적 시험 좌표. 실제 관광지 좌표가 아님")
        after = end + timedelta(minutes=1)
        after_point = source.near(latitude=y, longitude=x, at=after)
        record_test("after_recorded_end_point", "absent", target_level(after_point),
                    meaning="저장 종료 시각 경계만 재현. 현장의 실제 해제를 확인한 결과가 아님")
        target = "도로:" + road
        route_result = routes.affecting([target], at=clock)
        record_test("declared_road_at_observation", near_impact, target in route_result,
                    meaning="명시적으로 같은 도로를 통과하는 시험. 세부 구간·방향 검증과 구별")
        other_target = "도로:시험용_다른도로_" + incident_id
        other_route = routes.affecting([other_target], at=clock)
        record_test("different_road", {}, other_route)
        route_after = routes.affecting([target], at=after)
        record_test("after_recorded_end_route", {}, route_after,
                    meaning="기존 응답의 종료시각 계산. 새 종료 관측을 공급하지 않음")
        try:
            available_snapshot(candidate, clock - timedelta(seconds=1))
        except FutureObservation:
            guards.append({"incident_id": incident_id, "future_observation_blocked": True})
        else:
            raise AssertionError("미래 원문 차단이 작동하지 않았습니다")

        reverse_result = None
        if label["reverse"] != "not_tested":
            reverse_move = {**itinerary["move"], "direction": "원문과 반대 진행방향(명시적 시험 조건)",
                            "declared_section": {"from": section["to"], "to": section["from"]},
                            "provider_links": [], "reverse_link_verified": False}
            reverse_result = routes.affecting(reverse_move["uses"], at=clock)
            record_test("opposite_direction_acceptance", label["reverse"] == "affected",
                        target in reverse_result, kind="direction_acceptance",
                        meaning="원문 방향 반대 조건. 현재 도로명 전용 인터페이스는 방향을 전달하지 못함. 비일치는 수정 대상 자료로 보관")
        full_source = SavedUtic(snapshot, clock)
        full_near = full_source.near(latitude=y, longitude=x, at=clock)
        full_route = UticRouteEvents(full_source).affecting([target], at=clock)
        first_hit = (full_route.get(target) or {}).get("incident_id")
        limits = ["실제 고객 여행 아님. 사건 구간 통과를 명시한 시험 일정",
                  "도로 통제·사고가 관광지 폐쇄·정확한 지연시간을 증명하지 않음",
                  "원문 종료 시각은 실제 해제 관측과 구별",
                  "ITS·예보·영업시간·실제 길찾기·대체안 미검증",
                  "현재 도로명 대조는 구간·링크·방향을 판정에 사용하지 않음"]
        if label.get("pending"):
            limits.append(label["pending"])
        if label["reverse"] == "unaffected":
            limits.append("반대 방향 수용 시험 실패: 이 사례를 전체 경로 자동 변경의 확정 근거로 사용하지 않음")
        result = {
            "incident_id": incident_id, "status": label["use"], "expected_source_level": expected,
            "reason": label["reason"], "impact_scope": "시험용 선언 경로·교통 소스 한정",
            "real_customer_impact": "not_assessed", "evaluation_family": label.get("family", incident_id),
            "record": row, "record_sha256": record_sha(row),
            "starts_at": start.isoformat(), "recorded_ends_at": end.isoformat(),
            "observed_at": snapshot["available_at"].isoformat(), "replay_clock": clock.isoformat(),
            "received_at": snapshot["received_at"].isoformat(),
            "origin": {"collection": observation["collection"], "raw": observation["raw"],
                       "collection_sha256": observation["collection_sha256"],
                       "raw_file_sha256": snapshot["raw_file_sha256"],
                       "provider_body_sha256": snapshot["body_sha256"]},
            "all_observations": [{"collected_at": o["collected_at"],
                                  "available_at": snapshots[o["raw"]]["available_at"].isoformat(),
                                  "raw": o["raw"], "record_sha256": record_sha(o["record"]),
                                  "changed_from_selected": o["record"] != row}
                                 for o in candidate["observations"]],
            "itinerary": itinerary, "place_projection": place,
            "expectation_review": label, "tests": tests,
            "point_result": point_result, "check_result": check_result,
            "route_result": route_result, "reverse_route_result": reverse_result,
            "full_snapshot_diagnostic": {
                "mode": "원문 전체 행을 공급한 추가 진단",
                "target_result": target_level(full_near),
                "near_disruption_ids": [r["incident_id"] for r in full_near["for_place"]],
                "near_advisory_ids": [r["incident_id"] for r in full_near["advisories"]],
                "first_road_hit": first_hit,
                "first_hit_is_target": first_hit == incident_id,
                "meaning": "도로명이 같은 다른 구간·사건일 수 있습니다. 첫 일치 사건의 차이를 시험 실패 수에 자동 합산하지 않습니다",
            }, "limits": limits,
        }
        results.append(result)

    if attempts:
        raise AssertionError(dict(attempts))
    changed = [name for name, digest in protected.items() if sha(CS / name) != digest]
    if changed:
        raise RuntimeError("실행 중 입력 또는 제품 코드가 바뀌었습니다: " + ",".join(changed))
    core = [test for test in all_tests if test["kind"] == "product_rule"]
    direction = [test for test in all_tests if test["kind"] == "direction_acceptance"]
    counts = Counter(row["status"] for row in results)
    summary = {
        "candidates_reviewed": len(results), "candidate_denominator": 28,
        "readiness": dict(counts), "source_observations_verified": len(provenance_checks),
        "future_observation_guards_passed": len(guards),
        "product_rules_passed": sum(t["passed"] for t in core), "product_rules_executed": len(core),
        "direction_acceptance_passed": sum(t["passed"] for t in direction),
        "direction_acceptance_executed": len(direction),
        "all_tests_passed": sum(t["passed"] for t in all_tests), "all_tests_executed": len(all_tests),
        "failed_tests": [t for t in all_tests if not t["passed"]],
        "external_network_attempts": attempts["network"], "database_attempts": attempts["database"],
        "subprocess_attempts": attempts["subprocess"], "local_replay_reads": replay_transports["memory_xml_reads"],
        "actual_customer_itineraries_assessed": 0, "alternative_safety_verified": False,
        "input_file_hashes": protected,
        "policy_unchanged": {"shared_stop_ratio": 0.2, "source_daily_attempts": 2, "source_monthly_attempts": 62,
                             "note": "제한 설정·예산 DB를 읽거나 쓰지 않습니다. 새 외부 요청을 하지 않습니다"},
        "acceptance_status": "failed" if any(not t["passed"] for t in all_tests) else "passed",
    }
    out = args.out or DATA / "2026-10-12-seoul28-replay-v1/runs" / (
        datetime.now(KST).strftime("%Y-%m-%d_%H%M%S") + "_" + uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    (out / "cases").mkdir()
    for result in results:
        write_new(out / "cases" / (result["incident_id"] + ".json"), result)
    write_new(out / "cases.json", {"scope": annotations["scope"], "cases": results})
    write_new(out / "results.json", summary)
    write_new(out / "tests.json", all_tests)
    names = {"route_review": "재검토 제한 사례", "caution": "주의 제한 사례", "hold": "경로 대조 보류"}
    lines = ["# 서울 실제 경보 28건 판정표", "", "실제 고객 일정이 아닌 명시적 시험용 일정의 결과입니다.", "",
             "| 사건 | 도로 | 최초 재현 시각(KST) | 분류 | 활용 판정 | 실행 |", "|---|---|---|---|---|---|"]
    for result in results:
        success = sum(test["passed"] for test in result["tests"])
        count = len(result["tests"])
        lines.append(f"| [{result['incident_id']}](cases/{result['incident_id']}.json) | {result['record']['roadName']} | "
                     f"{moment(result['replay_clock']).strftime('%m-%d %H:%M:%S')} | "
                     f"{'재검토' if result['expected_source_level']=='disruption' else '주의'} | "
                     f"{names[result['status']]} | {success}/{count} = {success/count:.1%} |")
    write_new(out / "판정표.md", "\n".join(lines) + "\n")
    print(json.dumps({"output": str(out.relative_to(CS)).replace("\\", "/"),
                      **{k: v for k, v in summary.items() if k not in {"input_file_hashes", "failed_tests"}}},
                     ensure_ascii=False))
    return 1 if summary["acceptance_status"] == "failed" else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
