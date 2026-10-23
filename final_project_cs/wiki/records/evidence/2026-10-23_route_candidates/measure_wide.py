import sys, time, json, os
from datetime import datetime, timedelta, timezone
repo = sys.argv[1]; data = sys.argv[2]; rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 3
sys.path.insert(0, repo)
from app.domains.travel_ops.instances.mobility import wiring
t0 = time.perf_counter()
wiring.configure(data_dir=data)
print("configure", round(time.perf_counter() - t0, 2), "s", wiring._STATE["mode"], flush=True)
KST = timezone(timedelta(hours=9))
A = {"key": "a", "name": "경복궁", "kind": "activity", "lat": 37.579617, "lon": 126.977041, "weather_sensitive": None, "attributes": {}}
DEST = [("국립민속박물관", 37.581888, 126.979427), ("종각", 37.570169, 126.982912), ("N서울타워", 37.551169, 126.988227),
        ("홍대입구역", 37.557192, 126.925381), ("롯데월드타워", 37.512551, 127.102544)]
arrive = datetime(2026, 10, 23, 15, 0, tzinfo=KST)
nb = datetime(2026, 10, 23, 13, 30, tzinfo=KST)
def pl(o): return {k: o.get(k) for k in ("id", "eta_min", "uses")}
rows = []
for r in range(rounds):
    for wide in (False, True):           # 번갈아 잰다(A·B·A·B)
        eng = wiring.leg_planner(None, {}, wide=wide)
        for name, lat, lon in DEST:
            wiring._LEG_CACHE.clear()
            B = {"key": "b", "name": name, "kind": "activity", "lat": lat, "lon": lon, "weather_sensitive": None, "attributes": {}}
            t = time.perf_counter()
            got, why = eng(A, B, arrive, nb)
            dt = time.perf_counter() - t
            n = len(got["route"]["options"]) if got else 0
            rows.append({"round": r, "wide": wide, "dest": name, "sec": round(dt, 2), "n_options": n,
                         "planned": got["route"]["planned"] if got else None,
                         "options": [pl(o) for o in got["route"]["options"]] if got else None, "why": why})
            print(r, "wide" if wide else "base", name, f"{dt:.2f}s", "후보", n, "계획", rows[-1]["planned"], flush=True)
json.dump(rows, open(sys.argv[4] if len(sys.argv) > 4 else "measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
