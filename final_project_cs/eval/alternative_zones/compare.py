# -*- coding: utf-8 -*-
"""활동 대체 장소 — 거리 구간 정렬(새) vs 구간표 이전(옛) 비교. `[2026-10-19]`

★**계산만 한다.** LLM · DB · 외부 API 를 부르지 않는다. 후보 풀은 `activity_total_data.csv`(운영은 `activity.ac_place`)다.
★옛 방식은 구간표를 넣기 직전 커밋의 `alternatives.py` 를 얼려 둔 `baseline_alternatives_2026-10-19.py` 다.
★성공 기준은 결과를 보기 전에 `criteria.json` 에 적었다. 이 스크립트는 그 기준으로 판정만 한다.

실행: `python eval/alternative_zones/compare.py [--db]`  (final_project_cs 에서)
  `--db` — 후보 풀을 운영과 같은 길(`find_place_candidates` → 활동 원장 `activity.ac_place`)로 읽는다. 없으면 CSV.
출력: `eval/alternative_zones/result.json` · `report.md` (`--db` 이면 `result_db.json` · `report_db.md`)
"""
from __future__ import annotations

import csv
import importlib.util
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.domains.travel_ops.instances.activity import alternatives as new  # noqa: E402
from app.domains.travel_ops.instances.activity.csv_places import _CSV_PATH  # noqa: E402
from app.domains.travel_ops.instances.activity.db_search.place_candidates import POOL_EXCLUDED_CLASSES  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 11, 21, 14, 0, tzinfo=KST)          # 토 14:00
SEED = 20261019
RANDOM_N = 100
PREFERENCES = (None, "activity", "mobility")
#: eval/situation_cards/bind_candidates.py ORIGIN_IDS 와 같은 25곳(고정 표본)
FIXED = {
    "경복궁": "126508", "광장시장": "132183", "국립중앙박물관": "129703", "국립현대미술관": "1934593", "낙산공원": "129501",
    "낙산성곽길": "4065859", "남산공원": "126485", "남산서울타워": "126535", "덕수궁": "126509", "동대문디자인플라자": "2470006",
    "롯데월드타워 전망대": "2492348", "명동": "264311", "북촌한옥마을": "126537", "북한산 둘레길": "1196871", "서울숲": "128611",
    "서울식물원": "2589349", "어린이대공원": "126490", "인사동 쌈지길": "128553", "리버시티수상스키장": "767780",
    "창덕궁": "1604941", "코엑스 아쿠아리움": "130284", "코엑스몰": "1984944", "하늘공원": "2654607", "북촌전통공예체험관": "2993183",
}
FAR_KM, NEAR_KM = 5.0, 3.0


def load_baseline():
    """얼려 둔 옛 파일을 활동 패키지 안의 모듈처럼 불러온다(안의 `from .closure_rules` 가 풀리게 이름을 맞춘다)."""
    name = "app.domains.travel_ops.instances.activity.alternatives_baseline"
    spec = importlib.util.spec_from_file_location(name, HERE / "baseline_alternatives_2026-10-19.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_pool() -> list[dict]:
    rows = []
    with Path(_CSV_PATH).open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if not (r.get("title") and r.get("mapx") and r.get("mapy") and (r.get("addr1") or "").startswith("서울")):
                continue
            rows.append({"brand": r.get("brand") or None, "contentid": r["contentid"], "title": r["title"],
                         "contenttypeid": r.get("contenttypeid"), "lclsSystm1": r.get("lclsSystm1"),
                         "lclsSystm2": r.get("lclsSystm2"), "lclsSystm3": r.get("lclsSystm3"),
                         "lDongSignguCd": r.get("lDongSignguCd"), "mapx": r["mapx"], "mapy": r["mapy"],
                         "closed_days": r.get("closed_days") or None, "business_hours": r.get("business_hours") or None})
    return rows


def pick_origins(pool: list[dict]) -> list[dict]:
    by_id = {c["contentid"]: c for c in pool}
    fixed = [by_id[i] for i in FIXED.values() if i in by_id]
    taken = {c["contentid"] for c in fixed}
    eligible = [c for c in pool if c["contentid"] not in taken and c["contentid"].isdigit()
                and (c["lclsSystm1"] or "") not in ("SH", "EV", "FD", "AC", "")]
    groups: dict[str, list[dict]] = {}
    for c in eligible:
        groups.setdefault(c["lclsSystm1"], []).append(c)
    rng, picked = random.Random(SEED), []
    for key in sorted(groups):
        rows = groups[key]
        rng.shuffle(rows)
        picked += rows[:min(len(rows), max(5, round(RANDOM_N * len(rows) / len(eligible))))]
    rng.shuffle(picked)
    return fixed + picked[:RANDOM_N]


def pool_for(origin: dict, pool: list[dict]) -> list[dict]:
    lat0, lat1, lng0, lng1 = new.bounding_box(float(origin["mapy"]), float(origin["mapx"]), new.RADIUS_MAX_KM)
    return [c for c in pool if c["contentid"] != origin["contentid"] and c["lclsSystm1"] not in POOL_EXCLUDED_CLASSES
            and lat0 <= float(c["mapy"]) <= lat1 and lng0 <= float(c["mapx"]) <= lng1]


def run(module, origin: dict, candidates: list[dict], pref: str | None) -> list[dict]:
    return module.rank_alternatives(origin, candidates, AT, preference=pref)["alternatives"]


def level_of(origin: dict, row: dict) -> int:
    return new.category_level(origin, row)


def flagged(origin: dict, top: list[dict], by_id: dict, candidates: list[dict]) -> bool:
    """C1 — 3km 안에 (영업 가능한) 같은 소분류·중분류가 있는데 5km 넘는 같은 소분류가 1순위인가."""
    if not top:
        return False
    first = by_id[str(top[0]["contentid"])]
    if level_of(origin, first) != 0 or new.distance_km(origin, first) <= FAR_KM:
        return False
    for c in candidates:
        d = new.distance_km(origin, c)
        if d is None or d > NEAR_KM or level_of(origin, c) > 1:
            continue
        if new.closed_on(c.get("closed_days"), AT) is True or new.open_at(c.get("business_hours"), AT) is False:
            continue
        return True
    return False


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def evaluate(use_db: bool = False) -> dict:
    old = load_baseline()
    pool = load_pool()
    origins = pick_origins(pool)
    if use_db:
        from app.domains.travel_ops.instances.activity.db_search.place_candidates import find_place_candidates
        from app.infrastructure.db.session import get_connection
    stats = {p: {"n": 0, "same_top3": 0, "changed_top1": 0, "top1_level": {"old": Counter(), "new": Counter()},
                 "far_share": {"old": [], "new": []}, "mean_dist": {"old": [], "new": []},
                 "large_match": {"old": [], "new": []}, "flagged": {"old": 0, "new": 0}, "examples": []}
             for p in PREFERENCES}
    used = []
    for origin in origins:
        if use_db:
            found = find_place_candidates(get_connection, "demo", origin["contentid"])
            if found is None:                       # 원장에 없는 표본은 건너뛴다
                continue
            origin, candidates = found["origin"], found["candidates"]
        else:
            candidates = pool_for(origin, pool)
        used.append(origin)
        by_id = {str(c["contentid"]): c for c in candidates}
        for pref in PREFERENCES:
            tops = {"old": run(old, origin, candidates, pref), "new": run(new, origin, candidates, pref)}
            s = stats[pref]
            s["n"] += 1
            s["same_top3"] += [a["contentid"] for a in tops["old"]] == [a["contentid"] for a in tops["new"]]
            if tops["old"] and tops["new"] and tops["old"][0]["contentid"] != tops["new"][0]["contentid"]:
                s["changed_top1"] += 1
                if len(s["examples"]) < 10:
                    def brief(a):
                        row = by_id[str(a["contentid"])]
                        return {"title": a["title"], "km": a["distance_km"], "level": level_of(origin, row)}
                    s["examples"].append({"origin": origin["title"], "old": brief(tops["old"][0]), "new": brief(tops["new"][0])})
            for key in ("old", "new"):
                top = tops[key]
                if top:
                    s["top1_level"][key][level_of(origin, by_id[str(top[0]["contentid"])])] += 1
                    s["flagged"][key] += flagged(origin, top, by_id, candidates)
                    s["mean_dist"][key].append(sum(a["distance_km"] for a in top) / len(top))
                    s["far_share"][key] += [a["distance_km"] > FAR_KM for a in top]
                    if origin["lclsSystm1"]:
                        s["large_match"][key] += [by_id[str(a["contentid"])]["lclsSystm1"] == origin["lclsSystm1"] for a in top]
    return {"origins": len(used), "fixed": sum(1 for o in used if o["contentid"] in FIXED.values()),
            "pool": len(pool), "at": AT.isoformat(), "stats": stats,
            "source": "활동 원장 activity.ac_place(DB, 운영과 같은 조회)" if use_db else f"CSV(서울 {len(pool)}곳)"}


def summarize(raw: dict) -> dict:
    out = {"origins": raw["origins"], "fixed": raw["fixed"], "pool": raw["pool"], "at": raw["at"],
           "source": raw["source"], "by_preference": {}}
    for pref, s in raw["stats"].items():
        total = {k: sum(v.values()) for k, v in s["top1_level"].items()}
        out["by_preference"][str(pref)] = {
            "n": s["n"], "same_top3": s["same_top3"], "changed_top1": s["changed_top1"],
            "top1_small_class_match": {k: round(s["top1_level"][k][0] / total[k], 3) if total[k] else None for k in ("old", "new")},
            "mean_top3_km": {k: mean(s["mean_dist"][k]) for k in ("old", "new")},
            "share_over_5km": {k: round(sum(s["far_share"][k]) / len(s["far_share"][k]), 3) if s["far_share"][k] else None
                               for k in ("old", "new")},
            "large_class_match": {k: round(sum(s["large_match"][k]) / len(s["large_match"][k]), 3) if s["large_match"][k] else None
                                  for k in ("old", "new")},
            "flagged_far_small_over_near_mid": s["flagged"], "examples": s["examples"]}
    a, m, n = (out["by_preference"][k] for k in ("activity", "mobility", "None"))
    out["checks"] = {
        "C1": a["flagged_far_small_over_near_mid"]["new"] == 0,
        "C2": a["large_class_match"]["new"] == 1.0,
        "C3": a["mean_top3_km"]["new"] <= a["mean_top3_km"]["old"],
        "C4": m["same_top3"] == m["n"] and n["same_top3"] == n["n"],
    }
    return out


def report(res: dict) -> str:
    a = res["by_preference"]["activity"]
    lines = ["# 활동 대체 장소 — 거리 구간 정렬 비교 (2026-10-19)", "",
             f"표본: 원래 장소 {res['origins']}곳(고정 {res['fixed']} + 무작위) · 시각 {res['at']} · 후보 풀: {res['source']}", "",
             "## 성공 기준 판정 (`criteria.json`)", "", "| 기준 | 결과 |", "|---|---|"]
    names = {"C1": "C1 가까운 중분류가 있는데 먼 소분류가 1순위 = 0건", "C2": "C2 대분류 일치 100%",
             "C3": "C3 상위 3곳 평균 거리 새 ≤ 옛", "C4": "C4 이동·무응답 결과 동일"}
    lines += [f"| {names[k]} | {'통과' if v else '**실패**'} |" for k, v in res["checks"].items()]
    lines += ["", "## 활동 우선", "", "| 지표 | 옛 | 새 |", "|---|---|---|",
              f"| 1순위 소분류 일치율 | {a['top1_small_class_match']['old']} | {a['top1_small_class_match']['new']} |",
              f"| 상위 3곳 평균 거리(km) | {a['mean_top3_km']['old']} | {a['mean_top3_km']['new']} |",
              f"| 5km 초과 추천 비율 | {a['share_over_5km']['old']} | {a['share_over_5km']['new']} |",
              f"| 대분류 일치 | {a['large_class_match']['old']} | {a['large_class_match']['new']} |",
              f"| 가까운 중분류가 있는데 먼 소분류 1순위(건) | {a['flagged_far_small_over_near_mid']['old']} | {a['flagged_far_small_over_near_mid']['new']} |",
              f"| 1순위가 바뀐 표본 | — | {a['changed_top1']} / {a['n']} |", "",
              "## 선호도별 상위 3곳이 옛 방식과 같은 표본", "", "| 선호도 | 같음 / 전체 |", "|---|---|"]
    lines += [f"| {k} | {v['same_top3']} / {v['n']} |" for k, v in res["by_preference"].items()]
    lines += ["", "## 활동 우선 — 1순위가 바뀐 대표 사례(최대 10)", "", "| 원래 장소 | 옛 1순위 | 새 1순위 |", "|---|---|---|"]
    lvl = ("소분류", "중분류", "대분류", "다름")
    lines += [f"| {e['origin']} | {e['old']['title']} ({e['old']['km']}km · {lvl[e['old']['level']]}) | "
              f"{e['new']['title']} ({e['new']['km']}km · {lvl[e['new']['level']]}) |" for e in a["examples"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    db = "--db" in sys.argv
    result = summarize(evaluate(db))
    suffix = "_db" if db else ""
    (HERE / f"result{suffix}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERE / f"report{suffix}.md").write_text(report(result), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(report(result))
