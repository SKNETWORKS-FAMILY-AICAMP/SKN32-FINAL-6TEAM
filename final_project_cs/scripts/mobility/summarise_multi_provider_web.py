"""브라우저에서 저장한 네이버·구글 경로를 대조한다. 외부 HTTP 호출은 차단한다.

원값과 구간별 결과는 git 밖 datasets에, 집계와 그림만 wiki에 저장한다.
동일 역 이름도 지도 POI·출입구와 조회 시각이 다르므로 정확도 검증과 구분한다.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / "datasets/mobility/raw/kakao_golden"
KST = timezone(timedelta(hours=9))
DURATION = re.compile(r"(?:(\d+)시간(?:\s*(\d+)분)?|([0-9]+)분)")


def duration(text):
    m = DURATION.search(text)
    if not m:
        raise ValueError("표시 소요시간을 읽지 못했습니다")
    return int(m[1] or 0) * 60 + int(m[2] or m[3] or 0)


def clock(text):
    # Google textContent에는 09:50 바로 뒤에 1호선·버스 번호가 붙는다.
    # 분은 정확히 두 자리만 읽어 노선 숫자를 시각으로 흡수하지 않는다.
    m = re.search(r"(오전|오후)\s*(\d{1,2}):(\d{2})", text)
    if not m:
        raise ValueError("표시 도착시각을 읽지 못했습니다")
    hour = int(m[2]) % 12 + (12 if m[1] == "오후" else 0)
    if not 1 <= int(m[2]) <= 12 or int(m[3]) >= 60:
        raise ValueError("표시 시각 범위가 잘못되었습니다")
    return hour * 60 + int(m[3])


def parse(read):
    if read["provider"] == "google":
        cards = read["cards"] + read.get("alternatives", [])
        if not cards:
            raise ValueError("구글 경로 카드가 없습니다")
        best = cards[0]
        # 카드의 ~ 뒤에 있는 시각이 도착이다. 아래 승차시각과 혼동하지 않는다.
        return {"min": duration(best), "shortest_min": min(map(duration, cards)),
                "arrival_min": clock(best.split("~", 1)[1]), "card_count": len(cards),
                "first_card": best, "cards": cards, "read_at": read["read_at"]}
    tail = read["text"].split("길찾기", 1)[1]
    if read["mode"] == "transit":
        tail = tail.split("최적 경로순\n펼치기", 1)[1]
    cards = tail.split("상세보기")[:-1]
    first = cards[0]
    out = {"min": duration(first), "card_count": len(cards), "first_card": first,
           "cards": cards, "read_at": read["read_at"]}
    if read["mode"] == "transit":
        out.update(arrival_min=clock(first), shortest_min=min(map(duration, cards)),
                   fare_won=int(re.search(r"([\d,]+)원", first)[1].replace(",", "")))
    else:
        m = re.search(r"(\d+(?:\.\d+)?)(km|m)", first)
        out["km"] = float(m[1]) / (1000 if m[2] == "m" else 1)
        if read["mode"] == "car":
            out["fare_won"] = int(re.search(r"택시비([\d,]+)원", first)[1].replace(",", ""))
    return out


def dump_new(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--assets", type=Path, required=True)
    args = ap.parse_args()
    folder = Path(os.path.abspath(args.input))
    if not folder.is_relative_to(RAW.resolve()):
        ap.error("원값 폴더는 datasets/mobility/raw/kakao_golden 아래여야 합니다")
    design = json.loads((folder / "design-v1.json").read_text(encoding="utf-8"))
    original = json.loads((folder / "readings-v1.json").read_text(encoding="utf-8"))
    corrected = json.loads((folder / "google-coordinate-readings-v2.json").read_text(encoding="utf-8"))
    active = [r for r in original if r["provider"] == "naver"] + corrected
    expected = {(p["id"], "naver", m) for p in design["pairs"] for m in design["naver_modes"]}
    expected |= {(p["id"], "google", "transit") for p in design["pairs"]}
    keys = [(r["id"], r["provider"], r["mode"]) for r in active]
    assert len(keys) == len(set(keys)) == 60 and set(keys) == expected
    parsed = {k: parse(r) for k, r in zip(keys, active, strict=True)}
    for p in design["pairs"]:
        for mode in design["naver_modes"]:
            r = next(x for x in active if (x["id"], x["provider"], x["mode"]) == (p["id"], "naver", mode))
            from urllib.parse import unquote
            assert p["a"] + " " in unquote(r["url"]) and p["b"] + " " in unquote(r["url"])
        r = next(x for x in corrected if x["id"] == p["id"])
        assert f"{p['alat']}, {p['alon']}" in r["title"] and f"{p['blat']}, {p['blon']}" in r["title"]

    # .env의 지도 키와 외부 라우터 주소를 사용하지 않는다. HTTP도 방어적으로 차단한다.
    blocked_http = []

    def no_http(*a, **kw):
        blocked_http.append(True)
        raise RuntimeError("이 연구에서는 HTTP/API 호출을 허용하지 않습니다")

    urllib.request.urlopen = no_http
    import requests
    requests.sessions.Session.request = no_http
    sys.path.insert(0, str(ROOT))
    from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
    from app.domains.travel_ops.instances.mobility.engine.plan import Planner
    from scripts.mobility.compare_kakao_golden import _planner_leg
    from scripts.mobility.summarise_fresh_web_experiment import paired, selected
    rules = ROOT / "app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json"
    frozen = hashlib.sha256(rules.read_bytes()).hexdigest()
    rt = build_verifier(quiet=True, local_router=True, gh_url="", seoul_key="")
    svc = rt._v.car._service()
    print("로컬 자료 로딩 완료 · 외부 HTTP 차단", flush=True)

    def run(p):
        pid = p["id"]
        a = {"key": pid + "a", "name": p["a"], "lat": p["alat"], "lon": p["alon"]}
        b = {"key": pid + "b", "name": p["b"], "lat": p["blat"], "lon": p["blon"]}
        nc = parsed[pid, "naver", "car"]
        depart = datetime.fromisoformat(nc["read_at"]).astimezone(KST)
        row = {"id": pid, "bucket": p["bucket"], "taxi": svc.leg((p["alon"], p["alat"]),
                  (p["blon"], p["blat"]), depart, taxi=True), "transit": {}}
        pl = Planner(rt, stage="planning", modes=None)
        distance, reason = pl._walk_net(a, b, p["straight_m"])
        row["walk"] = {"m": distance, "reason": reason,
                       "min": distance / pl.speed / 60 if distance is not None else None}
        row["bike"] = rt._v.bike_router.route("bike", p["alat"], p["alon"], p["blat"], p["blon"])
        for provider in ("naver", "google"):
            ref = parsed[pid, provider, "transit"]
            arrive = datetime(2026, 10, 8, tzinfo=KST) + timedelta(minutes=ref["arrival_min"])
            result, reason = _planner_leg(rt, None)(a, b, arrive)
            row["transit"][provider] = {"arrival_target": arrive.isoformat(), "result": result, "reason": reason}
        return row

    ours = []
    with (folder / "ours-v2.jsonl").open("x", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=4) as pool:
        for job in as_completed([pool.submit(run, p) for p in design["pairs"]]):
            row = job.result()
            ours.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"로컬 계산 {len(ours)}/12 {row['id']}", flush=True)
    assert not blocked_http
    assert hashlib.sha256(rules.read_bytes()).hexdigest() == frozen
    ours.sort(key=lambda r: r["id"])
    dump_new(folder / "ours-v2.json", {"rules_sha256": frozen, "http_attempts": len(blocked_http), "rows": ours})
    groups = {key: [] for key in ("taxi_meter", "taxi_budget", "taxi_distance", "taxi_time", "walk_distance", "walk_time", "bike_distance", "bike_time", "google_vs_naver")}
    transit_groups = {p: {w: [] for w in ("with_wait", "without_wait")} for p in ("naver", "google")}
    records = []
    for row in ours:
        pid, tx = row["id"], row["taxi"]
        nc, nt, gt = (parsed[pid, provider, mode] for provider, mode in (("naver", "car"), ("naver", "transit"), ("google", "transit")))
        for key, a, b in (("taxi_meter", tx["meter_won"] + tx["toll_won"], nc["fare_won"]),
                          ("taxi_budget", tx["fare_won"], nc["fare_won"]),
                          ("taxi_distance", tx["distance_m"] / 1000, nc["km"]),
                          ("taxi_time", tx["topis_time_s"] / 60, nc["min"]),
                          ("google_vs_naver", gt["min"], nt["min"])):
            groups[key].append((a, b))
        for mode, distance, time in (("walk", row["walk"]["m"], row["walk"]["min"]),
                                      ("bike", row["bike"].get("distance_m"), row["bike"].get("time_s", 0) / 60)):
            if distance is not None:
                ref = parsed[pid, "naver", mode]
                groups[mode + "_distance"].append((distance / 1000, ref["km"]))
                groups[mode + "_time"].append((time, ref["min"]))
        rec = {"id": pid, "naver": {m: parsed[pid, "naver", m] for m in design["naver_modes"]}, "google": gt, "ours": row}
        for provider in ("naver", "google"):
            result = row["transit"][provider]["result"]
            opt = selected({"transit": result}) if result else None
            if opt:
                ref = parsed[pid, provider, "transit"]["min"]
                transit_groups[provider]["with_wait"].append((opt["eta_min"], ref))
                if opt.get("wait_min") is not None:
                    transit_groups[provider]["without_wait"].append((opt["eta_min"] - opt["wait_min"], ref))
            rec[provider + "_planned"] = opt
        records.append(rec)
    summary = {"pairs": 12, "raw_observations": len(original) + len(corrected), "active_observations": len(active),
               "rules_sha256": frozen, "http_attempts": len(blocked_http), "read_range": [min(r["read_at"] for r in active), max(r["read_at"] for r in active)],
               "coverage": {"naver_car": 12, "naver_transit": 12, "naver_walk": 12, "naver_bike": 12, "google_transit": 12, "tmap": 0},
               "taxi_budget_coverage": sum(a >= b for a, b in groups["taxi_budget"])}
    for key, values in groups.items():
        tol = 1000 if key.startswith("taxi_m") or key == "taxi_budget" else .25 if key.endswith("distance") else 5
        summary[key] = paired([v[0] for v in values], [v[1] for v in values], tol)
    summary["transit"] = {}
    for provider, buckets in transit_groups.items():
        summary["transit"][provider] = {w: paired([a for a, b in values], [b for a, b in values]) for w, values in buckets.items()}
    dump_new(folder / "comparison-v1.json", records)
    args.assets.mkdir(parents=True, exist_ok=False)
    dump_new(args.assets / "summary.json", summary)
    plot(summary, records, args.assets)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def plot(summary, records, folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
    plt.rcParams.update({"font.family": font.get_name(), "axes.unicode_minus": False, "font.size": 11})
    blue, orange, gray = "#2166ac", "#d6604d", "#555555"
    fig, axs = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    ax = axs[0, 0]
    ax.barh(["네이버 자동차", "네이버 대중교통", "네이버 도보", "네이버 자전거", "구글 대중교통", "티맵 실제 경로"], [12, 12, 12, 12, 12, 0], color=blue)
    for i, n in enumerate([12, 12, 12, 12, 12, 0]):
        ax.text(n + .2, i, f"{n}건", va="center")
    ax.set(xlim=(0, 14), title="추가 대조군: 역 쌍 12개 · 유효 관측 60건")
    ax.invert_yaxis()
    ax = axs[0, 1]
    keys = ["taxi_meter", "taxi_budget"]
    vals = [summary[k]["percent"]["median"] for k in keys]
    intervals = [summary[k]["percent"]["median_bootstrap95"] for k in keys]
    errors = [[v - bounds[0] for v, bounds in zip(vals, intervals, strict=True)],
              [bounds[1] - v for v, bounds in zip(vals, intervals, strict=True)]]
    ax.bar(["미터 계산", "기존 여유 포함 예산"], vals, color=[orange, blue], yerr=errors, capsize=4)
    for i, v in enumerate(vals):
        ax.text(i, intervals[i][1] + 1, f"{v:+.1f}%", ha="center", va="bottom")
    ax.axhline(0, color=gray, lw=1)
    ax.set(ylim=(-8, 48), ylabel="(우리 값 / 네이버 예상액 - 1) × 100 (%)", title=f"택시 예산이 네이버 이상: {summary['taxi_budget_coverage']}/12")
    ax = axs[1, 0]
    keys = ["taxi_distance", "walk_distance", "bike_distance"]
    vals = [summary[k]["percent"]["median"] for k in keys]
    intervals = [summary[k]["percent"]["median_bootstrap95"] for k in keys]
    errors = [[v - bounds[0] for v, bounds in zip(vals, intervals, strict=True)],
              [bounds[1] - v for v, bounds in zip(vals, intervals, strict=True)]]
    ax.bar(["자동차", "도보", "자전거"], vals, color=blue, yerr=errors, capsize=4)
    for i, v in enumerate(vals):
        ax.text(i, intervals[i][1] + 1, f"{v:+.1f}% · n=12", ha="center", va="bottom")
    ax.axhline(0, color=gray, lw=1)
    ax.set(ylim=(-35, 23), ylabel="(우리 거리 / 네이버 추천 거리 - 1) × 100 (%)", title="추천 경로 거리 차이 · 웹 km는 반올림 표시")
    ax = axs[1, 1]
    for i, provider in enumerate(("naver", "google")):
        for j, wait in enumerate(("with_wait", "without_wait")):
            st = summary["transit"][provider][wait]["absolute"]
            x = i * 3 + j
            bounds = st["median_bootstrap95"]
            ax.bar(x, st["median"], color=[orange, blue][j],
                   yerr=[[st["median"] - bounds[0]], [bounds[1] - st["median"]]], capsize=4)
            pct = summary["transit"][provider][wait]["percent"]["median"]
            ax.text(x, bounds[1] + .3, f"{st['median']:+.1f}분\n{pct:+.1f}%\nn={st['n']}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks([0, 1, 3, 4], ["네이버\n대기 포함", "네이버\n대기 제거", "구글\n대기 포함", "구글\n대기 제거"])
    ax.axhline(0, color=gray, lw=1)
    ax.set(ylim=(-2.2, 7.5), ylabel="우리 소요 - 지도 첫 추천 소요 (분)", title="같은 도착 목표로 재계산 · 서로 다른 출발·추천안")
    fig.suptitle("triPilot 이동 · 네이버·구글 브라우저 대조군 추가", fontsize=18)
    fig.supxlabel("서울 12쌍: 짧은·중간·긴 구간 각 4쌍 · 직접 외부 API 호출 0 · 요금 규칙 변경 0\n막대: 중앙값 · 선: 부트스트랩 95% 범위 · 실제 운행 정확도 판정은 아님", fontsize=10)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(folder / f"multi-provider-overview.{ext}", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
