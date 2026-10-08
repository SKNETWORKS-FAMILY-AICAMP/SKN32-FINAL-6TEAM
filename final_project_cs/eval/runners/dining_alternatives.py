# -*- coding: utf-8 -*-
"""대체 식당 평가 — 고정 시나리오(`eval/datasets/dining_alternatives_v1.jsonl`)로 「무엇으로 바꾸나」를 잰다. `[2026-10-07]`

    python -m eval.runners.dining_alternatives --label v0-develop [--out REPORT.json]

★무엇을 재나
    식당 대체 계산 셋(`itinerary_changes.plan_closed_on_day` 새벽 휴무 확인 · `plan_closed` 고객 휴무 신고 · `plan_delay` 늦음)에
    시나리오의 일정 · 장소를 넣고, 고른 가게가 정답인지 본다. **순수 계산**이다 — DB · 외부 API · 모델을 부르지 않는다.
    장소는 지은 것이다(이름 · 좌표 · 영업시간 · 종류). 그래서 같은 코드면 늘 같은 결과가 나온다.
    ★고정 · 예약 일정의 「바꾸지 않음」은 계산 뒤 `pending.protected_reason` 이 「묻기」로 돌린다 — 이 평가 밖이다.

★판정(시나리오마다 하나)
    correct             정답(`accept`)을 골랐다
    ok                  차선(`ok`)을 골랐다 — 틀리지는 않았지만 더 나은 곳이 있었다
    correct_no_change   바꾸지 않아야 할 때 바꾸지 않았다
    wrong_violation     ★고른 곳으로 가면 다음 일정에 **원래 식당보다 더 늦게** 닿는다(도보 기준) — 가장 나쁘다. 목표 0
    wrong               다른 곳을 골랐다
    missed              골라야 하는데 바꾸지 않았다
    wrong_change        바꾸지 않아야 하는데 바꿨다

★동선(평가기가 따로 잰다 — 계산 코드를 믿지 않는다)
    도보 분 = ceil(거리 / 80m)(`replan.walk_minutes` 와 같은 속도).
    다음 일정 늦음 = 식사 끝 + 후보→다음 도보 − 다음 일정 시작(0 이상). 원래 식당(원래 시각)으로 잰 늦음보다 크면 위반.
    앞 일정 → 식당 늦음은 보고만 한다(위반 아님) — 식당 입장 몇 분은 다음 일정을 놓치는 것과 다르다(`replan.MealRoute`).
    늘어난 이동 = (앞→후보 + 후보→다음) − (앞→원래 + 원래→다음). 앞 · 다음이 없으면 그 쪽은 0.

★이동 계산기 묶음(`needs: mobility`, transit) — 실제 좌표(`latlng`)로 놓고 `--mobility <이동 자료 폴더>` 를 줄 때만 잰다.
  그 시나리오만 계산기를 쓴다(계산 코드 · 평가기 모두) — 다른 시나리오는 지은 좌표라 도보 기준으로 정답을 정했다.
  계산기를 안 켜면 그 묶음은 `skipped` 로 따로 세고 점수에서 뺀다.
★장소 id 를 바꿔 가며 여러 번 돈다(`--seeds`, 기본 5). 순위가 같을 때 마지막 기준이 장소 id 라서(`replan.Candidate.rank`),
  id 하나로만 재면 우연히 맞은 것을 정답으로 센다. **모든 판에서 같은 판정**일 때만 그 판정이고, 갈리면 `unstable` 이다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "datasets" / "dining_alternatives_v1.jsonl"
KST = ZoneInfo("Asia/Seoul")
DAY = date(2026, 10, 21)                       # 수요일
BASE = (37.5700, 126.9800)                     # 시나리오 좌표 (동 m, 북 m) 의 원점
DEFAULT_HOURS = ["10:00", "22:00"]
WALK_M_PER_MIN = 80
NS = uuid.UUID("6c1d7a2e-0000-4000-8000-000000000da1")

LABELS = ("correct", "ok", "correct_no_change", "wrong_violation", "wrong", "missed", "wrong_change", "unstable")
_LEG: dict[str, Any] = {"leg": None}            # --mobility 로 켠 이동 계산기(needs: mobility 시나리오에서만 쓴다)
GOOD = frozenset({"correct", "correct_no_change"})


def load_cases(path: Path = DATASET) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _at(hhmm: str) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=KST)


def _latlng(east_north: list[float]) -> tuple[float, float]:
    east, north = east_north
    return (BASE[0] + north / 111_000, BASE[1] + east / (111_000 * math.cos(math.radians(BASE[0]))))


def _metres(a: dict[str, Any], b: dict[str, Any]) -> float:
    p = math.pi / 180
    h = (math.sin((b["latitude"] - a["latitude"]) * p / 2) ** 2
         + math.cos(a["latitude"] * p) * math.cos(b["latitude"] * p)
         * math.sin((b["longitude"] - a["longitude"]) * p / 2) ** 2)
    return 12_742_000 * math.asin(math.sqrt(h))


def walk_min(a: dict[str, Any], b: dict[str, Any]) -> int:
    return max(1, math.ceil(_metres(a, b) / WALK_M_PER_MIN))


def build(case: dict[str, Any], seed: int = 0) -> tuple[dict[str, Any], list[Any], dict[str, dict[str, Any]]]:
    """시나리오 → (trip, items, 장소 key→장소). 장소 id 는 key 로 정해진다(uuid5) — 실행마다 같다."""
    from app.domains.travel_ops.components.itinerary.itinerary import Item

    places: dict[str, dict[str, Any]] = {}
    for spec in case["places"]:
        lat, lng = tuple(spec["latlng"]) if "latlng" in spec else _latlng(spec["at"])
        kind = spec.get("kind", "dining")
        attributes: dict[str, Any] = {}
        if kind == "dining":
            attributes["hours"] = spec.get("hours", DEFAULT_HOURS)
        for name in ("break", "payment", "cuisine", "price_krw"):
            if name in spec:
                attributes[name] = spec[name]
        places[spec["key"]] = {"place_id": str(uuid.uuid5(NS, f"{seed}:{case['id']}:{spec['key']}")), "name": spec["name"],
                               "kind": kind, "latitude": lat, "longitude": lng, "attributes": attributes,
                               "key": spec["key"]}
    items = []
    for spec in case["items"]:
        place = places[spec["place"]]
        items.append(Item(item_id=uuid.uuid5(NS, f"{case['id']}:item:{spec['seq']}"), seq=spec["seq"], kind=spec["kind"],
                          title=spec["title"], place_id=uuid.UUID(place["place_id"]), starts_at=_at(spec["start"]),
                          ends_at=_at(spec["end"]), locked=bool(spec.get("locked")), detail=dict(spec.get("detail") or {}),
                          place=place))
    trip = {"trip_id": str(uuid.uuid5(NS, case["id"])), "constraints": case.get("constraints") or {}}
    return trip, items, places


def plan(case: dict[str, Any], trip: dict[str, Any], items: list[Any], places: dict[str, dict[str, Any]]) -> Any:
    from app.domains.travel_ops.components.itinerary import itinerary_changes as changes

    engine = _LEG["leg"] if case.get("needs") == "mobility" else None
    original_engine = changes._leg_engine
    changes._leg_engine = lambda trip: engine            # 이 시나리오에만 — 다른 시나리오는 도보 기준이다
    try:
        return _plan(case, trip, items, places, changes)
    finally:
        changes._leg_engine = original_engine


def _plan(case, trip, items, places, changes) -> Any:

    pool = list(places.values())
    meal = next(i for i in items if i.seq == case["meal"])
    if case["path"] == "closed_on_day":
        return changes.plan_closed_on_day(trip=trip, items=items, places=pool, meal=meal, source="eval",
                                          detail="평가 시나리오 휴무", checked_at=_at("03:00"))
    if case["path"] == "closed_now":
        return changes.plan_closed(trip=trip, items=items, places=pool, at=_at(case["at"]),
                                   message="오늘 휴무래요", request_id=None)
    if case["path"] == "delay":
        return changes.plan_delay(trip=trip, items=items, places=pool, at=_at(case["at"]),
                                  minutes=case["delay_min"], message=f"{case['delay_min']}분 늦어요", request_id=None)
    raise ValueError(f"모르는 경로: {case['path']}")


def chosen(result: Any, places: dict[str, dict[str, Any]]) -> tuple[str | None, Any]:
    """고른 가게의 key 와 바뀐 항목. 바꾸지 않았으면 (None, None)."""
    replacements = getattr(result, "replacements", None) or {}
    for item in replacements.values():
        if item.kind == "dining" and item.place:
            by_id = {p["place_id"]: key for key, p in places.items()}
            return by_id.get(str(item.place["place_id"])), item
    return None, None


def route_check(case: dict[str, Any], items: list[Any], places: dict[str, dict[str, Any]], key: str,
                new_item: Any) -> dict[str, Any]:
    """고른 곳으로 갔을 때의 동선 — 평가기가 따로 잰다."""
    meal = next(i for i in items if i.seq == case["meal"])
    before = [i for i in items if i.seq < meal.seq and i.kind != "mobility"]
    after = [i for i in items if i.seq > meal.seq and i.kind != "mobility"]
    prev, nxt = (before[-1] if before else None), (after[0] if after else None)
    cand, orig = places[key], meal.place
    starts, ends = new_item.starts_at, new_item.ends_at or new_item.starts_at
    out: dict[str, Any] = {"late_arrival_min": 0, "late_next_min": 0, "planned_late_next_min": 0}
    added = 0
    if prev is not None and case["path"] != "closed_now":          # 가게 앞 신고는 고객이 이미 원래 식당에 있다
        arrive = (prev.ends_at or prev.starts_at) + timedelta(minutes=walk_min(prev.place, cand))
        out["late_arrival_min"] = max(0, int((arrive - starts).total_seconds() // 60))
        added += walk_min(prev.place, cand) - walk_min(prev.place, orig)
    elif case["path"] == "closed_now":
        added += walk_min(orig, cand)
    if nxt is not None:
        to_next, from_orig = walk_min(cand, nxt.place), walk_min(orig, nxt.place)
        if case.get("needs") == "mobility":
            to_next, from_orig = _eta(cand, nxt.place, nxt.starts_at, ends), _eta(orig, nxt.place, nxt.starts_at,
                                                                                    meal.ends_at or meal.starts_at)
            out["basis"] = "mobility"
        reach = ends + timedelta(minutes=to_next)
        out["late_next_min"] = max(0, int((reach - nxt.starts_at).total_seconds() // 60))
        planned = (meal.ends_at or meal.starts_at) + timedelta(minutes=from_orig)
        out["planned_late_next_min"] = max(0, int((planned - nxt.starts_at).total_seconds() // 60))
        added += to_next - from_orig
    out["added_walk_min"] = added
    out["violation"] = out["late_next_min"] > out["planned_late_next_min"]
    return out


def _eta(a: dict[str, Any], b: dict[str, Any], arrive: datetime, leave: datetime) -> int:
    """평가기 쪽 이동 계산기 소요(분). 못 재면 시나리오가 잘못된 것이다 — 멈춘다."""
    here = {"key": a["key"], "name": a["name"], "lat": a["latitude"], "lon": a["longitude"]}
    there = {"key": b["key"], "name": b["name"], "lat": b["latitude"], "lon": b["longitude"]}
    got, why = None, None
    for window in (90, 180):                       # 소요만 묻는다 — 늦는지는 여기서 잰다(replan.TRANSIT_WINDOWS_MIN 과 같은 방식)
        got, why = _LEG["leg"](here, there, leave + timedelta(minutes=window), leave)
        if got is not None or not (isinstance(why, dict) and why.get("code") == "arrive_late"):
            break
    if not got:
        raise RuntimeError(f"이동 계산기가 {a['name']} → {b['name']} 를 못 쟀다: {why}")
    return int(got["eta_min"])


def score_case(case: dict[str, Any], key: str | None, route: dict[str, Any] | None) -> str:
    expect = case["expect"]
    if expect.get("no_change"):
        return "correct_no_change" if key is None else "wrong_change"
    if key is None:
        return "missed"
    if route and route["violation"]:
        return "wrong_violation"
    if key in expect.get("accept", []):
        return "correct"
    if key in expect.get("ok", []):
        return "ok"
    return "wrong"


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def ratio(num: int, den: int) -> dict[str, Any]:
        return {"num": num, "den": den, "rate": round(num / den, 3) if den else None}

    skipped = [r["id"] for r in results if r["label"] == "skipped"]
    results = [r for r in results if r["label"] != "skipped"]
    total = len(results)
    counts = Counter(r["label"] for r in results)
    added = [r["route"]["added_walk_min"] for r in results if r.get("route")]
    return {
        "accuracy": ratio(sum(counts[label] for label in GOOD), total),
        "acceptable": ratio(sum(counts[label] for label in GOOD | {"ok"}), total),
        "violations": ratio(counts["wrong_violation"], total),
        # 판 하나라도 동선을 깬 시나리오 — unstable 안에 숨은 위반
        "violations_any_seed": ratio(sum(r["label"] == "wrong_violation"
                                         or any(s.endswith(":wrong_violation") for s in r.get("by_seed") or [])
                                         for r in results), total),
        "labels": {label: counts.get(label, 0) for label in LABELS},
        "by_group": {group: ratio(sum(r["label"] in GOOD for r in results if r["group"] == group),
                                  sum(r["group"] == group for r in results))
                     for group in sorted({r["group"] for r in results})},
        "added_walk_min_mean": round(sum(added) / len(added), 1) if added else None,
        "skipped": skipped,
    }


def run_once(case: dict[str, Any], seed: int) -> dict[str, Any]:
    trip, items, places = build(case, seed)
    result = plan(case, trip, items, places)
    key, new_item = chosen(result, places)
    route = route_check(case, items, places, key, new_item) if key else None
    return {"picked": key, "picked_name": places[key]["name"] if key else None,
            "status": getattr(result, "status", None) or "changed", "route": route,
            "label": score_case(case, key, route)}


def run_case(case: dict[str, Any], seeds: int = 5) -> dict[str, Any]:
    """판마다 장소 id 를 바꿔 돈다. 판정이 모두 같으면 그 판정, 갈리면 unstable(고른 곳들을 남긴다)."""
    if case.get("needs") == "mobility" and _LEG["leg"] is None:
        return {"id": case["id"], "group": case["group"], "why": case["why"], "picked": None, "label": "skipped"}
    runs = [run_once(case, seed) for seed in range(seeds)]
    labels = {r["label"] for r in runs}
    first = runs[0]
    out = {"id": case["id"], "group": case["group"], "why": case["why"], **first,
           "label": first["label"] if len(labels) == 1 else "unstable"}
    if len(labels) > 1:
        out["by_seed"] = [f"{r['picked']}:{r['label']}" for r in runs]
    return out


def enable_mobility(data_dir: str) -> None:
    """이동 계산기를 켠다(`mobility.wiring.configure`). 자료 확인이 실패하면 멈춘다(지어낸 소요로 재지 않는다)."""
    from app.domains.travel_ops.instances.mobility import wiring

    wiring.configure(data_dir=str(Path(data_dir).resolve()), verify_hash=False)
    _LEG["leg"] = wiring.leg_planner(None, {})


def run(*, label: str, dataset: Path = DATASET, seeds: int = 5) -> dict[str, Any]:
    def git(*args: str) -> str | None:
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:   # noqa: BLE001
            return None

    results = []
    for case in load_cases(dataset):
        try:
            results.append(run_case(case, seeds))
        except Exception as exc:   # noqa: BLE001 — 한 시나리오가 죽어도 나머지는 잰다
            results.append({"id": case["id"], "group": case["group"], "why": case["why"], "picked": None,
                            "label": "missed", "error": f"{type(exc).__name__}: {exc}"[:200]})
        r = results[-1]
        print(f"{r['id']} {r['label']:<18} → {r.get('picked_name')} {r.get('by_seed') or ''} {r.get('error', '')}",
              file=sys.stderr)
    return {"eval": "dining_alternatives", "dataset": dataset.name,
            "dataset_sha": hashlib.sha256(dataset.read_bytes()).hexdigest()[:16], "label": label, "seeds": seeds, "mobility": _LEG["leg"] is not None,
            "env": {"run_at": datetime.now(KST).isoformat(timespec="seconds"), "git_commit": git("rev-parse", "--short", "HEAD"),
                    "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                    "git_dirty": bool(git("status", "--porcelain", "--", "app"))},
            "summary": summarize(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seeds", type=int, default=5, help="장소 id 를 바꿔 도는 판 수")
    parser.add_argument("--mobility", help="이동 자료 폴더(datasets/mobility/processed) — 주면 transit 묶음도 잰다")
    args = parser.parse_args(argv)
    if args.mobility:
        enable_mobility(args.mobility)
    report = run(label=args.label, dataset=args.dataset, seeds=args.seeds)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
