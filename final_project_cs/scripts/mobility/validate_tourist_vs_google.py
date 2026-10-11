# -*- coding: utf-8 -*-
"""#19 — 관광 구간 대중교통 소요: 우리 계산기 vs 구글 Routes(TRANSIT, 같은 출발 시각) 비교 (2026-10-04).

실행(저장소 final_project_cs 에서 · 키는 .env.apikeys 의 ACOP_GOOGLE_MAPS_API_KEY — 값은 출력하지 않는다 · 쌍당 호출 1회 · 약 32회):
  python scripts/mobility/validate_tourist_vs_google.py
구글 응답은 합계 소요 숫자만 쓰고 **파일로 저장하지 않는다**(Google Maps Platform 약관의 콘텐츠 저장 제한). 결과는 화면 출력뿐이다.
주의: 구글 합계는 걷기 속도·대기 가정이 구글 것이다 — 독립 정답이 아니라 **독립 참고값**이다(걷기만은 구글이 한국에서 빈 결과를 낸다)."""
import json, random, re, statistics as st, sys, time, urllib.error, urllib.request
from pathlib import Path
sys.path.insert(0, ".")
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.plan_estimate import Estimator
from app.domains.travel_ops.instances.mobility.engine.car import hav
ENV = {}
for f in (Path(".env.apikeys"), Path(".env")):
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
            if m and m.group(2): ENV.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
KEY = ENV["ACOP_GOOGLE_MAPS_API_KEY"]
SPOTS = {"경복궁": (37.5796, 126.9770), "남산서울타워": (37.5512, 126.9882), "명동성당": (37.5633, 126.9877), "홍대 걷고싶은거리": (37.5563, 126.9236),
         "성수 서울숲": (37.5445, 127.0374), "롯데월드타워": (37.5126, 127.1025), "코엑스": (37.5116, 127.0591), "동대문디자인플라자": (37.5672, 127.0095),
         "이태원역": (37.5345, 126.9946), "북촌한옥마을": (37.5826, 126.9835), "여의도 한강공원": (37.5284, 126.9326), "국립중앙박물관": (37.5240, 126.9803),
         "인사동": (37.5741, 126.9856), "광장시장": (37.5700, 126.9996), "창덕궁": (37.5794, 126.9910), "덕수궁": (37.5658, 126.9751),
         "서울역": (37.5547, 126.9707), "잠실 석촌호수": (37.5098, 127.1000), "압구정 로데오": (37.5272, 127.0390), "건대입구": (37.5404, 127.0692),
         "망원시장": (37.5560, 126.9060), "DMC": (37.5770, 126.8900), "고속터미널 센트럴시티": (37.5049, 127.0049), "청계천 광통교": (37.5685, 126.9795)}
names = sorted(SPOTS)
rng = random.Random(19)
pairs = []
while len(pairs) < 32:
    a, b = rng.sample(names, 2)
    d = hav((SPOTS[a][1], SPOTS[a][0]), (SPOTS[b][1], SPOTS[b][0]))
    if 1800 <= d <= 16000 and (a, b) not in pairs: pairs.append((a, b))
rt = build_verifier(quiet=True, local_router=True)
rows = []
for a, b in pairs:
    pa = {"name": a, "lat": SPOTS[a][0], "lon": SPOTS[a][1]}; pb = {"name": b, "lat": SPOTS[b][0], "lon": SPOTS[b][1]}
    try:
        o = Estimator(rt, modes=["subway", "bus", "walk"]).estimate(pa, pb, "2026-10-07", "오후", window=(720, 735))
        ours = (o.get("eta") or {}).get("p50_min"); lab = ((o.get("routes") or [{}])[0].get("label")) if o.get("routes") else None
        ver = o.get("verdict")
    except Exception as ex:
        ours, lab, ver = None, f"예외 {type(ex).__name__}", None
    body = {"origin": {"location": {"latLng": {"latitude": pa["lat"], "longitude": pa["lon"]}}},
            "destination": {"location": {"latLng": {"latitude": pb["lat"], "longitude": pb["lon"]}}},
            "travelMode": "TRANSIT", "departureTime": "2026-10-07T03:00:00Z", "languageCode": "ko"}
    req = urllib.request.Request("https://routes.googleapis.com/directions/v2:computeRoutes", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": KEY, "X-Goog-FieldMask": "routes.duration"})
    g = None
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.load(r)
        dur = ((d.get("routes") or [{}])[0]).get("duration")
        g = round(int(dur.rstrip("s")) / 60) if dur else None
    except Exception:
        g = None
    rows.append({"from": a, "to": b, "straight_m": round(hav((SPOTS[a][1], SPOTS[a][0]), (SPOTS[b][1], SPOTS[b][0]))), "ours_min": ours, "google_min": g, "verdict": ver, "ours_route": lab})
    time.sleep(0.15)
ok = [r for r in rows if r["ours_min"] is not None and r["google_min"]]
print("쌍", len(rows), "· 둘 다 값", len(ok), "· 우리만 못 냄", sum(1 for r in rows if r["ours_min"] is None and r["google_min"]), "· 구글 못 냄", sum(1 for r in rows if not r["google_min"]))
if ok:
    diff = [r["ours_min"] - r["google_min"] for r in ok]; ratio = [r["ours_min"] / r["google_min"] for r in ok]
    print("우리−구글(분) 중앙 %+.1f · 평균 %+.1f · 절대중앙 %.1f · 최대 %+d / %+d" % (st.median(diff), st.mean(diff), st.median([abs(x) for x in diff]), min(diff), max(diff)))
    print("우리/구글 중앙 %.2f · ±25%% 안 %d/%d · ±15%% 안 %d/%d" % (st.median(ratio), sum(1 for x in ratio if 0.75 <= x <= 1.25), len(ratio), sum(1 for x in ratio if 0.85 <= x <= 1.15), len(ratio)))
for r in rows: print(f"{r['from']}→{r['to']} {r['straight_m']}m 우리 {r['ours_min']} 구글 {r['google_min']} | {r['ours_route']}")
