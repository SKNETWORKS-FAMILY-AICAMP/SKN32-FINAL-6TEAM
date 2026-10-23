import sys, collections
from datetime import datetime, timedelta, timezone
repo, data = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
from app.domains.travel_ops.instances.mobility import wiring
wiring.configure(data_dir=data)
KST = timezone(timedelta(hours=9))
A = {"key": "a", "name": "경복궁", "kind": "activity", "lat": 37.579617, "lon": 126.977041, "weather_sensitive": None, "attributes": {}}
DEST = [("국립민속박물관", 37.581888, 126.979427), ("종각", 37.570169, 126.982912), ("N서울타워", 37.551169, 126.988227),
        ("홍대입구역", 37.557192, 126.925381), ("롯데월드타워", 37.512551, 127.102544)]
arrive = datetime(2026, 10, 23, 15, 0, tzinfo=KST)
nb = datetime(2026, 10, 23, 13, 30, tzinfo=KST)
for wide in (False, True):
    eng = wiring.leg_planner(None, {}, wide=wide)
    for name, lat, lon in DEST:
        B = {"key": "b", "name": name, "kind": "activity", "lat": lat, "lon": lon, "weather_sensitive": None, "attributes": {}}
        got, why = eng(A, B, arrive, nb)
        lo = got["left_out"] if got else (why or {}).get("left_out", [])
        c = collections.Counter(e.get("code") for e in lo)
        print("wide" if wide else "base", name, "start", got["starts_at"].strftime("%H:%M") if got else None,
              "opts", [(o["id"], o["eta_min"]) for o in got["route"]["options"]] if got else why, dict(c))
        for e in lo:
            if e.get("code") in ("earlier_departure", "mix_dominated", "before_prev_end", "not_confirmed"):
                print("    ", e.get("code"), e.get("label"), "|", str(e.get("reason"))[:110])
