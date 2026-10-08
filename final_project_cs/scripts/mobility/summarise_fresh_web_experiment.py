"""고정 실험의 기능별 집계와 공유 가능한 그림을 만든다. 계수 재학습 없음."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / "datasets/mobility/raw/kakao_golden"


def stats(values, tolerance):
    x = np.asarray(values, dtype=float)
    if not len(x):
        return {"n": 0}
    rng = np.random.default_rng(20261008)
    medians = np.median(rng.choice(x, (2000, len(x))), axis=1)
    return {"n": len(x), "median": float(np.median(x)), "mean": float(np.mean(x)),
            "mae": float(np.mean(np.abs(x))), "p10": float(np.percentile(x, 10)),
            "p90": float(np.percentile(x, 90)), "within": int(np.sum(np.abs(x) <= tolerance)),
            "tolerance": tolerance, "median_bootstrap95": np.percentile(medians, [2.5, 97.5]).tolist()}


def paired(ours, reference, tolerance=5):
    if any(b <= 0 for b in reference):
        raise ValueError("차이 비율의 기준값은 0보다 커야 합니다")
    return {"ours_median": float(np.median(ours)), "reference_median": float(np.median(reference)),
            "absolute": stats([a-b for a, b in zip(ours, reference, strict=True)], tolerance),
            "percent": stats([(a/b-1)*100 for a, b in zip(ours, reference, strict=True)], 10)}


def kind(o):
    return "bus" if o["id"].startswith("bus_") else "subway"


def selected(row):
    obj = row["transit"]
    if "route" not in obj:
        return None
    route = obj["route"]
    opt = next(o for o in route["options"] if o["id"] == route["planned"])
    trace = next(o for o in obj["comparison"]["options"] if o["id"] == route["planned"])
    return {**opt, **trace}


def analyse(refs, transit, taxi, bus):
    from app.modules.travel_ops.mobility.engine.car import taxi_planning_fare
    rows, budget_old, budget_new, estimates, reference_fares = [], [], [], [], []
    out = {"n": len(refs), "reserve_rate_frozen": .37, "target_coverage": .9,
           "transit_cards": sum(r[6] for r in refs)}
    for ref in refs:
        pid = ref[0]
        tx, ot = taxi[pid]["taxi"], selected(transit[pid])
        previous, _ = taxi_planning_fare(tx["meter_won"], tx["toll_won"], reserve_rate=.1,
                                        minimum_reserve_won=1000, round_unit_won=100)
        rows.append({"id": pid, "bucket": transit[pid]["bucket"], "reference": ref, "ours": transit[pid],
                     "planned": ot, "taxi": tx, "previous_budget": previous})
        budget_old.append(previous)
        budget_new.append(tx["fare_won"])
        estimates.append(tx["meter_won"] + tx["toll_won"])
        reference_fares.append(ref[2][2])
    for key, values in (("taxi_meter", estimates), ("taxi_budget10", budget_old), ("taxi_budget37", budget_new)):
        out[key] = paired(values, reference_fares, 1000)
        out[key]["coverage"] = sum(a >= b for a, b in zip(values, reference_fares, strict=True))
    out["taxi_by_bucket"] = {}
    for bucket in ("short", "mid", "long"):
        rr = [r for r in rows if r["bucket"] == bucket]
        out["taxi_by_bucket"][bucket] = {"n": len(rr),
            "covered": sum(r["taxi"]["fare_won"] >= r["reference"][2][2] for r in rr),
            "percent": stats([(r["taxi"]["fare_won"]/r["reference"][2][2]-1)*100 for r in rr], 10)}
    out["taxi_time"] = paired([r["taxi"]["topis_time_s"]/60 for r in rows], [r["reference"][2][0] for r in rows])
    out["taxi_distance"] = paired([r["taxi"]["distance_m"]/1000 for r in rows], [r["reference"][2][1] for r in rows], .5)
    out["transit"] = {}
    rr = [r for r in rows if r["planned"] is not None]
    for index, label in ((0, "best"), (1, "recommended")):
        for wait, name in ((True, "with_wait"), (False, "without_wait")):
            group = [r for r in rr if wait or r["planned"].get("wait_min") is not None]
            out["transit"][label + "_" + name] = paired(
                [r["planned"]["eta_min"] - (0 if wait else r["planned"]["wait_min"]) for r in group],
                [r["reference"][3][index][0] for r in group])
    out["transit"]["transfers_vs_recommended"] = stats([r["planned"]["transfers"]-r["reference"][3][1][2] for r in rr], 0)
    walk_group = [r for r in rr if r["planned"].get("walk_m") is not None]
    out["transit"]["walking_vs_recommended"] = paired([r["planned"]["walk_m"]/(4/3.6)/60 for r in walk_group],
                                                        [r["reference"][3][1][1] for r in walk_group])
    out["modal"] = {}
    for modality, index, source in (("subway", 3, transit), ("bus", 2, bus)):
        both, options = [], []
        eligible = sum(r["reference"][3][index] is not None for r in rows)
        for r in rows:
            obj = source[r["id"]]["transit"]
            candidates = [o for o in obj.get("route", {}).get("options", []) if kind(o) == modality]
            if not candidates or r["reference"][3][index] is None:
                continue
            opt = min(candidates, key=lambda o: o["eta_min"])
            tr = next(o for o in obj["comparison"]["options"] if o["id"] == opt["id"])
            if tr.get("wait_min") is None:
                continue
            both.append(r)
            options.append({**opt, **tr})
        out["modal"][modality] = {"reference_available": eligible, "ours_comparable": len(both)}
        if both:
            out["modal"][modality]["time_without_wait"] = paired(
                [o["eta_min"]-o["wait_min"] for o in options], [r["reference"][3][index][0] for r in both])
            out["modal"][modality]["fare_in_reference_range"] = sum(
                r["reference"][3][index][3] <= o["fare_krw"] <= r["reference"][3][index][4]
                for o, r in zip(options, both, strict=True) if o.get("fare_krw") is not None)
            out["modal"][modality]["fare_known"] = sum(o.get("fare_krw") is not None for o in options)
            out["modal"][modality]["fare_missing"] = sum(o.get("fare_krw") is None for o in options)
            out["modal"][modality]["transfers_difference"] = stats(
                [o["transfers"]-r["reference"][3][index][2] for o, r in zip(options, both, strict=True)], 0)
    short = [r for r in rows if r["reference"][4] is not None]
    out["walk"] = paired([r["ours"]["walk"]["m"]/1000 for r in short],
                          [next(x[2] for x in r["reference"][4] if x[0] == "최단거리") for r in short], .25)
    out["walk_time_current"] = paired([r["ours"]["walk"]["min"] for r in short],
                                       [next(x[1] for x in r["reference"][4] if x[0] == "최단거리") for r in short])
    out["walk_time_same_speed"] = paired([r["ours"]["walk"]["m"]/(4/3.6)/60 for r in short],
                                          [next(x[1] for x in r["reference"][4] if x[0] == "최단거리") for r in short])
    out["bike"] = paired([r["ours"]["bike"]["distance_m"]/1000 for r in short],
                          [next(x[2] for x in r["reference"][5] if x[0] == "최단거리") for r in short], .25)
    out["bike_time_current"] = paired([r["ours"]["bike"]["time_s"]/60 for r in short],
                                       [next(x[1] for x in r["reference"][5] if x[0] == "최단거리") for r in short])
    out["bike_time_same_speed"] = paired([r["ours"]["bike"]["distance_m"]/(20/3.6)/60 for r in short],
                                          [next(x[1] for x in r["reference"][5] if x[0] == "최단거리") for r in short])
    out["compute_seconds"] = stats([r["ours"]["elapsed_s"] for r in rows], 10)
    return out, rows


def plot(summary, rows, folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
    plt.rcParams.update({"font.family": font.get_name(), "axes.unicode_minus": False, "font.size": 11})
    blue, orange, gray = "#2166ac", "#d6604d", "#555555"
    fig, axs = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    keys = ["taxi_meter", "taxi_budget10", "taxi_budget37"]
    ax = axs[0, 0]
    values = [summary[k]["coverage"] for k in keys]
    ax.bar(["미터 계산", "기존 여유 10%", "고정 여유 37%"], values, color=[gray, orange, blue])
    ax.axhline(90, ls="--", color=gray, lw=1, label="사전 기준 90/100")
    for i, v in enumerate(values):
        ax.text(i, v+1, f"{v}/100 = {v}%", ha="center")
    ax.set(ylim=(0, 110), ylabel="카카오 예상액 이상인 경로 (%)", title="택시: 새 100쌍에서 예산 부족 방지")
    ax.legend(fontsize=9)
    ax = axs[0, 1]
    labels = ["짧은 30쌍", "중간 40쌍", "긴 30쌍"]
    groups = [summary["taxi_by_bucket"][k] for k in ("short", "mid", "long")]
    med = [g["percent"]["median"] for g in groups]
    intervals = np.array([g["percent"]["median_bootstrap95"] for g in groups])
    ax.bar(labels, med, color=blue, yerr=np.array([np.array(med)-intervals[:, 0], intervals[:, 1]-np.array(med)]), capsize=4)
    for i, g in enumerate(groups):
        ax.text(i, med[i]/2, f"{med[i]:+.1f}%\n충족 {g['covered']}/{g['n']}", ha="center", color="white")
    ax.axhline(0, color=gray, lw=1)
    ax.set(ylabel="(우리 예산 / 카카오 예상액 - 1) × 100 (%)", title="택시: 부족을 줄인 대신 예산이 높아짐")
    ax = axs[1, 0]
    tr = summary["transit"]
    vals = [tr["best_with_wait"]["absolute"]["within"], tr["best_without_wait"]["absolute"]["within"]]
    ax.bar(["대기 포함", "우리 대기 제거"], vals, color=[orange, blue])
    for i, v in enumerate(vals):
        a = tr[["best_with_wait", "best_without_wait"][i]]["absolute"]
        p = tr[["best_with_wait", "best_without_wait"][i]]["percent"]
        ax.text(i, v+1, f"{v}/{a['n']} = {v/a['n']*100:.0f}%\n중앙 차이 {a['median']:+.1f}분 / {p['median']:+.1f}%", ha="center")
    ax.set(ylim=(0, 105), ylabel="카카오 최단과 ±5분 이내 (%)", title="대중교통: 100쌍의 시간 차이")
    ax = axs[1, 1]
    vals = [summary[k]["percent"]["median"] for k in ("taxi_distance", "walk", "bike")]
    ax.bar(["자동차 100쌍", "도보 30쌍", "자전거 30쌍"], vals, color=blue)
    for i, v in enumerate(vals):
        ax.text(i, v/2, f"{v:+.1f}%", ha="center", color="white", va="center")
    ax.axhline(0, color=gray, lw=1)
    ax.set(ylabel="(우리 거리 / 카카오 거리 - 1) × 100 (%)", title="경로 거리: 중앙 차이 (시간 속도와 분리)")
    fig.suptitle("triPilot 이동 기능 · 카카오 웹 기준 새 경로 대조", fontsize=18)
    fig.supxlabel("2026-10-08 · 서울 · 기존 200쌍과 경로 중복 없음 · 계수 재조정 없음\n표본 결과이며 실제 택시 미터·실시간 운행 정확도 검증은 아님", fontsize=10)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(folder / f"mobility-fresh-100-overview.{ext}", dpi=170)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 6), layout="constrained")
    names = ["자동차 시간 (100)", "대중교통 대기 제거 (100)", "도보 현재 속도 (30)", "도보 4km/h (30)", "자전거 현재 속도 (30)", "자전거 20km/h (30)"]
    metrics = [summary["taxi_time"], tr["best_without_wait"], summary["walk_time_current"],
               summary["walk_time_same_speed"], summary["bike_time_current"], summary["bike_time_same_speed"]]
    for i, m in enumerate(metrics):
        d = m["percent"]
        ax.plot([d["p10"], d["p90"]], [i, i], color=blue, lw=4, alpha=.35)
        ax.scatter([d["median"]], [i], color=blue, s=55)
        ax.annotate(f"中央 {d['median']:+.1f}%".replace("中央", "중앙"), (d["median"], i), xytext=(0, 10), textcoords="offset points", ha="center")
    ax.axvline(0, color=gray, lw=1)
    ax.set(yticks=range(len(names)), yticklabels=names, xlabel="(우리 시간 / 카카오 시간 - 1) × 100 (%)",
           title="소요 시간 차이의 분포 · 굵은 선 P10~P90, 점 중앙값")
    ax.invert_yaxis()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(folder / f"mobility-fresh-100-time-distribution.{ext}", dpi=170)
    plt.close(fig)
    fig, axs = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    modalities = [summary["modal"][k] for k in ("subway", "bus")]
    for ax, field, title in ((axs[0], "ours_comparable", "수단별로 대조 가능한 경로"),
                            (axs[1], "fare_in_reference_range", "요금 값이 있는 경로의 웹 범위 일치")):
        denominator = [m["reference_available"] if field == "ours_comparable" else m["fare_known"] for m in modalities]
        value = [m[field] for m in modalities]
        ax.bar(["지하철", "버스만 허용"], [v/n*100 for v, n in zip(value, denominator, strict=True)], color=blue)
        for i, (v, n) in enumerate(zip(value, denominator, strict=True)):
            ax.text(i, v/n*100+1, f"{v}/{n} = {v/n*100:.1f}%", ha="center")
        ax.set(ylim=(0, 110), ylabel="비율 (%)", title=title)
    fig.supxlabel("서로 다른 경로끼리의 비용 비교 · 동일 승차 경로의 요금 정답률 아님\n"
                  f"요금 누락: 지하철 {modalities[0]['fare_missing']}/{modalities[0]['ours_comparable']}, "
                  f"버스 {modalities[1]['fare_missing']}/{modalities[1]['ours_comparable']} · "
                  "버스는 0~1회 환승 후보 제한 등 제품 조건 적용", fontsize=10)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(folder / f"mobility-fresh-100-modal-coverage.{ext}", dpi=170)
    plt.close(fig)


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        ap.error("기존 산출물을 덮어쓰지 않습니다. 새 출력 폴더를 지정하세요")
    refs = json.loads((RAW / "fresh_web_100_v1.json").read_text(encoding="utf-8"))
    def load(name):
        return {r["id"]: r for r in json.loads((RAW / name).read_text(encoding="utf-8"))["rows"]}
    summary, rows = analyse(refs, load("fresh_ours_transit_100_v1.json"), load("fresh_ours_taxi_100_v1.json"), load("fresh_ours_bus_100_v1.json"))
    args.out.mkdir(parents=True, exist_ok=True)
    summary["input_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.glob("fresh_*_100_v1.json")}
    joined = RAW / "fresh_comparison_rows_v1.json"
    if joined.exists():
        if json.loads(joined.read_text(encoding="utf-8")) != rows:
            ap.error("기존 경로별 결과와 다릅니다. 원자료를 덮어쓰지 않습니다")
    else:
        with joined.open("x", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    with (args.out / "summary.json").open("x", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    plot(summary, rows, args.out)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
