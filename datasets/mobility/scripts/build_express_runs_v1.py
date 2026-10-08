# datasets/mobility/scripts/build_express_runs_v1.py — 9호선(급행 있는 노선) 열차 단위 운행표
# 실행: 저장소 루트에서  python datasets/mobility/scripts/build_express_runs_v1.py   (호출 = 9호선 38역 × 요일 3 × 방향 2 = 228회 / 일 1,000)
#
# 왜: 통합 시간표(timetable_v1)는 열차번호·급행 표시를 줄이는 과정에서 버렸다(TAGO 에는 처음부터 없다). 그래서 판정기는 9호선의
#     급행을 모르고 모든 열차가 모든 역에 선다고 계산한다 — 급행 구간은 늦게(안전한 쪽), 급행이 안 서는 역으로 가는 급행은 틀리게
#     「성립」으로 낸다. 서울 열린데이터광장 역별 시간표(OA-101)는 열차번호(TRAIN_NO)와 EXPRESS_YN(G 일반 · D 급행)을 준다 —
#     열차번호로 역마다 시각을 이어 **열차 한 대의 정차역·시각**을 만든다.
# 산출: final_project_cs/app/domains/travel_ops/instances/mobility/engine/rules/express_runs_v1.json.gz (앱에 실려 나간다 — 작다)
#       원본 응답은 DATA_DIR/travel/raw/mobility/seoul_express_line9.jsonl 에도 남긴다(다시 만들 때 호출을 아끼려고).
# 1호선 급행(코레일 구간)은 이 스크립트가 다루지 않는다 — 열린데이터광장이 1호선 전체를 주지만 호출이 600회라 따로 정한다.
import argparse, gzip, json, os, time
from datetime import datetime, timedelta, timezone

import requests

from _paths import RAW_MOBILITY, REPO_ROOT, ensure_dirs

ap = argparse.ArgumentParser()
ap.add_argument("--line", default="09호선")
ap.add_argument("--from-raw", action="store_true", help="호출 없이 저장해 둔 원본에서 다시 만든다")
args = ap.parse_args()
LINE = args.line
KST = timezone(timedelta(hours=9))

KEY = os.environ.get("SEOUL_OPENAPI_KEY") or os.environ.get("ACOP_SEOUL_OPENAPI_KEY")
BASE = f"http://openapi.seoul.go.kr:8088/{KEY}/json"
SVC_STN, SVC_TT = "SearchSTNBySubwayLineInfo", "SearchSTNTimeTableByIDService"
RAW = RAW_MOBILITY / f"seoul_express_line{LINE[:2]}.jsonl"
OUT = (REPO_ROOT / "final_project_cs" / "app" / "domains" / "travel_ops" / "instances" / "mobility" / "engine" / "rules"
       / f"express_runs_line{LINE[:2]}_v1.json.gz")
DAY = {"1": "weekday", "2": "saturday", "3": "holiday"}


def sec(t):
    """'HH:MM:SS'(24 시 이상 가능) → 초. 값이 없거나 00:00:00(출발 없음 표기)이면 None."""
    if not t:
        return None
    h, m, s = (int(x) for x in t.split(":"))
    v = h * 3600 + m * 60 + s
    return None if v == 0 else v


def fetch(cd, wk, updn):
    j = requests.get(f"{BASE}/{SVC_TT}/1/1000/{cd}/{wk}/{updn}/", timeout=30).json()
    time.sleep(0.15)
    return (j.get(SVC_TT) or {}).get("row") or []


ensure_dirs()
rows = []
if args.from_raw:
    rows = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
else:
    if not KEY:
        raise SystemExit("SEOUL_OPENAPI_KEY(또는 ACOP_SEOUL_OPENAPI_KEY)가 없다 — .env.apikeys 를 확인한다")
    st = requests.get(f"{BASE}/{SVC_STN}/1/1000/", timeout=30).json()
    st = (st.get(SVC_STN) or {}).get("row") or []
    stations = [s for s in st if s["LINE_NUM"] == LINE]
    print(f"{LINE} 역 {len(stations)}개 — 호출 {len(stations) * 6}회 예상")
    with RAW.open("w", encoding="utf-8") as f:
        for i, s in enumerate(stations, 1):
            n = 0
            for wk in DAY:
                for updn in ("1", "2"):
                    for r in fetch(s["STATION_CD"], wk, updn):
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                        rows.append(r)
                        n += 1
            print(f"  [{i}/{len(stations)}] {s['STATION_NM']}: {n}행")

# ── 열차 단위로 잇는다 ──
runs = {}                                    # (요일, 열차번호) → {express, dir, stops{역: [도착초, 출발초]}}
for r in rows:
    if r.get("LINE_NUM") != LINE:
        continue
    key = (DAY.get(r["WEEK_TAG"]), r["TRAIN_NO"])
    run = runs.setdefault(key, {"express": False, "dir": "U" if r["INOUT_TAG"] == "1" else "D", "stops": {}})
    if r.get("EXPRESS_YN") == "D":
        run["express"] = True
    a, d = sec(r.get("ARRIVETIME")), sec(r.get("LEFTTIME"))
    run["stops"][r["STATION_NM"]] = [a, d]

names = sorted({nm for run in runs.values() for nm in run["stops"]})
idx = {nm: i for i, nm in enumerate(names)}
out_runs = {d: [] for d in DAY.values()}
skipped = 0
for (day, tno), run in sorted(runs.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])):
    if day is None:
        continue
    seq = []
    alltimes = sorted(x for a, d in run["stops"].values() for x in (a, d) if x is not None)
    if not alltimes:
        skipped += 1
        continue
    med = alltimes[len(alltimes) // 2]
    fix = lambda t: (t + 86400 if t is not None and med - t > 12 * 3600 else t)   # 자정을 넘긴 시각(00:10 으로 적힌 24:10)은 하루를 더한다
    for nm, (a, d) in run["stops"].items():
        a, d = fix(a), fix(d)
        t = a if a is not None else d
        if t is None:
            continue
        seq.append((t, nm, a, d))
    seq.sort()
    if len(seq) < 2:
        skipped += 1
        continue
    out_runs[day].append([tno, 1 if run["express"] else 0, run["dir"],
                          [[idx[nm], a, d] for _t, nm, a, d in seq]])
doc = {"_meta": {"line": LINE, "source": "서울 열린데이터광장 지하철 역별 시간표(OA-101 · SearchSTNTimeTableByIDService)",
                 "built_at": datetime.now(KST).isoformat(timespec="seconds"),
                 "note": "stops 의 [역번호, 도착초, 출발초] — 시각은 운행일 0 시부터의 초(24 시 이상 가능). express=1 이면 급행(EXPRESS_YN=D)",
                 "runs": {d: len(v) for d, v in out_runs.items()}, "skipped_single_stop": skipped},
       "stations": names, "runs": out_runs}
OUT.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(OUT, "wt", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
exp = {d: sum(1 for r in v if r[1]) for d, v in out_runs.items()}
print(f"→ {OUT}  ({OUT.stat().st_size // 1024} KB) · 열차 {doc['_meta']['runs']} · 급행 {exp}")
