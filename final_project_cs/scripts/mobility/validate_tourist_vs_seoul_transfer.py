# -*- coding: utf-8 -*-
"""#19 — 관광 구간 대중교통 소요: 우리 계산기 vs 서울시 대중교통 환승경로(공공데이터포털 15000414) (2026-10-04).

실행(final_project_cs 에서 · 공통 키 ACOP_DATA_GO_KR_KEY 는 **디코딩해서** 보낸다 — 값은 출력하지 않는다 · 쌍당 호출 1회 · 하루 1,000건 한도):
  python scripts/mobility/validate_tourist_vs_seoul_transfer.py
이 서비스는 출발 시각을 받지 않는다(정적 추정) — 우리 값은 평일 12시 출발의 p50 이다. 응답은 소요(분)·거리만 쓰고 저장하지 않는다.
독립 **참고값**이다(정답 아님) — 구글 대조(validate_tourist_vs_google.py)와 같은 쌍으로 비교한다."""
import json, math, random, re, statistics as st, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, ".")
from app.modules.travel_ops.mobility.engine.runtime import build_verifier
from app.modules.travel_ops.mobility.engine.plan_estimate import Estimator
from app.modules.travel_ops.mobility.engine.car import hav
ENV = {}
for f in (Path(".env.apikeys"), Path(".env")):
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", line)
            if m and m.group(2): ENV.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
KEY = urllib.parse.unquote(ENV["ACOP_DATA_GO_KR_KEY"])
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


def transfer(pa, pb):
    q = urllib.parse.urlencode({"serviceKey": KEY, "startX": pa["lon"], "startY": pa["lat"], "endX": pb["lon"], "endY": pb["lat"], "resultType": "json"})
    try:
        with urllib.request.urlopen("http://ws.bus.go.kr/api/rest/pathinfo/getPathInfoByBusNSub?" + q, timeout=25) as r:
            d = json.load(r)
    except Exception:                                             # noqa: BLE001
        return None, None
    items = (d.get("msgBody") or {}).get("itemList") or []
    times = [int(i["time"]) for i in items if str(i.get("time", "")).isdigit()]
    return (times[0], min(times)) if times else (None, None)


rt = build_verifier(quiet=True, local_router=True)
rows = []
for a, b in pairs:
    pa = {"name": a, "lat": SPOTS[a][0], "lon": SPOTS[a][1]}; pb = {"name": b, "lat": SPOTS[b][0], "lon": SPOTS[b][1]}
    try:
        o = Estimator(rt, modes=["subway", "bus", "walk"]).estimate(pa, pb, "2026-10-07", "오후", window=(720, 735))
        ours = (o.get("eta") or {}).get("p50_min")
    except Exception:                                             # noqa: BLE001
        ours = None
    first, best = transfer(pa, pb)
    rows.append((a, b, ours, first, best))
    time.sleep(0.15)
ok = [r for r in rows if r[2] is not None and r[3] is not None]
print("쌍", len(rows), "· 둘 다 값", len(ok), "· 우리만 못 냄", sum(1 for r in rows if r[2] is None and r[3]), "· 환승경로 못 냄", sum(1 for r in rows if r[3] is None))
for label, idx in (("환승경로 첫 경로", 3), ("환승경로 최단", 4)):
    pr = [(r[2], r[idx]) for r in ok if r[idx]]
    d = [x - g for x, g in pr]; ra = [x / g for x, g in pr]
    print(f"[{label}] n={len(pr)} 우리−상대 중앙 {st.median(d):+.1f}분 · 평균 {st.mean(d):+.1f} · 우리/상대 중앙 {st.median(ra):.2f} · ±25% 안 {sum(1 for x in ra if .75 <= x <= 1.25)}/{len(ra)} · ±15% 안 {sum(1 for x in ra if .85 <= x <= 1.15)}/{len(ra)}")
