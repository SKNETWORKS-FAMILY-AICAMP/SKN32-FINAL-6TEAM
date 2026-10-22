"""경로 후보 지연 실측 — 보통 계산(검사와 같은 것)과 넓게 찾기(더 보기)를 번갈아(A·B·A·B), 구간마다 재사용 칸을 비우고 잰다."""
import sys, time, json
from datetime import datetime, timedelta, timezone
repo, data, rounds, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
sys.path.insert(0, repo)
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.components.intake.moves import leg_between, ROUTES_FIRST
t0 = time.perf_counter()
wiring.configure(data_dir=data)
print("configure", round(time.perf_counter() - t0, 2), flush=True)
KST = timezone(timedelta(hours=9))
A = {"key": "a", "name": "경복궁", "lat": 37.579617, "lon": 126.977041}
DEST = [("국립민속박물관", 37.581888, 126.979427), ("종각", 37.570169, 126.982912), ("N서울타워", 37.551169, 126.988227),
        ("홍대입구역", 37.557192, 126.925381), ("롯데월드타워", 37.512551, 127.102544)]
a_end = datetime(2026, 10, 23, 13, 30, tzinfo=KST)
b_start = datetime(2026, 10, 23, 15, 0, tzinfo=KST)
base, wide = wiring.leg_planner(None, {}), wiring.leg_planner(None, {}, wide=True)
rows = []
for r in range(rounds):
    for name, lat, lon in DEST:
        B = {"key": "b", "name": name, "lat": lat, "lon": lon}
        for label, eng in (("base", base), ("wide", wide)):
            wiring._LEG_CACHE.clear()
            t = time.perf_counter()
            leg = leg_between(eng, A, B, a_end, b_start)
            dt = time.perf_counter() - t
            t2 = time.perf_counter()
            body = json.dumps([dict(x) for x in leg.routes[:ROUTES_FIRST]], ensure_ascii=False)
            ser = (time.perf_counter() - t2) * 1000
            rows.append({"round": r, "dest": name, "engine": label, "sec": round(dt, 3), "n_routes": len(leg.routes),
                         "first3_bytes": len(body.encode()), "serialize_ms": round(ser, 3), "capped": leg.routes_capped,
                         "routes": [{k: x[k] for k in ("key", "mode_label", "minutes", "depart", "arrive", "transfers", "early", "planned")} for x in leg.routes]})
            print(r, name, label, f"{dt:.2f}s", "후보", len(leg.routes), "앞3", len(body.encode()), "B", flush=True)
# 고른 경로(조금 일찍 떠남) 다시 세기 확인
B = {"key": "b", "name": "홍대입구역", "lat": 37.557192, "lon": 126.925381}
leg = leg_between(base, A, B, a_end, b_start)
early = next((x for x in leg.routes if x["early"]), None)
if early:
    mine = leg_between(base, A, B, a_end, b_start, prefer=early["key"])
    print("prefer", early["key"], "->", mine.route_key == early["key"], mine.depart.strftime("%H:%M"), mine.arrive.strftime("%H:%M"),
          mine.minutes, mine.mode_label, "verified", mine.verified, "ctx", bool(mine.departure_context), mine.selected_option_id)
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
