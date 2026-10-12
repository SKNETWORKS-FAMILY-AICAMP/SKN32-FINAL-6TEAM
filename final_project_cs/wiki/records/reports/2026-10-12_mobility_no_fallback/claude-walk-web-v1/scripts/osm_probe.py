"""카카오 구간 중 제품이 크게 돌아가는 곳 주변의 OSM 원자료 태그를 읽는다 — 읽기 전용."""
import json, math, sys
from pathlib import Path
import osmium

ROOT = Path(r"C:\Users\playdata2\Documents\final_workspace")
OBS = json.loads((ROOT / "datasets/mobility/raw/mobility_walk_web_20261012_v3/kakao-walk-observed-v1.json").read_text(encoding="utf-8"))
PBF = Path(sys.argv[1])
OUT = Path(sys.argv[2])
# (OD, 안내 seq) — 분석에서 제품/카카오 비가 큰 구간
TARGETS = [("W01", 7), ("W01", 9), ("W01", 11), ("W02", 2), ("W03", 5), ("W03", 7), ("W03", 9), ("W02", 5)]
R_M = 45.0


def hav(a, b):
    R = 6371008.8
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


pairs = []
for r in OBS["rows"]:
    for k in ("from", "to"):
        q = r["request"][k]
        pairs.append((q["wcong"][0], q["wcong"][1], q["lat"], q["lon"]))
x0, y0 = 500000.0, 1128000.0


def lstsq(rows, ys):
    n = 3
    A = [[sum(a[i] * a[j] for a in rows) for j in range(n)] for i in range(n)]
    b = [sum(a[i] * y for a, y in zip(rows, ys)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (b[i] - sum(A[i][c] * x[c] for c in range(i + 1, n))) / A[i][i]
    return x


rows = [((x - x0) / 1000, (y - y0) / 1000, 1.0) for x, y, _, _ in pairs]
clat, clon = lstsq(rows, [p[2] for p in pairs]), lstsq(rows, [p[3] for p in pairs])


def w2g(x, y):
    a = ((x - x0) / 1000, (y - y0) / 1000, 1.0)
    return (sum(c * v for c, v in zip(clon, a)), sum(c * v for c, v in zip(clat, a)))


targets = []
for od, seq in TARGETS:
    row = next(r for r in OBS["rows"] if r["id"] == od)
    g = next(x for x in row["shortest_guides"] if x["seq"] == seq)
    pts = [w2g(*map(float, p.split(","))) for p in g["pts"].split("|")]
    targets.append({"od": od, "seq": seq, "ment": g["ment"], "kakao_pts": [[round(p[0], 7), round(p[1], 7)] for p in pts]})

lon_min = min(p[0] for t in targets for p in t["kakao_pts"]) - 0.002
lon_max = max(p[0] for t in targets for p in t["kakao_pts"]) + 0.002
lat_min = min(p[1] for t in targets for p in t["kakao_pts"]) - 0.002
lat_max = max(p[1] for t in targets for p in t["kakao_pts"]) + 0.002


def near_target(ll):
    hits = []
    for i, t in enumerate(targets):
        kp = t["kakao_pts"]
        for q in kp:
            if hav(ll, q) <= R_M:
                hits.append(i)
                break
    return hits


KEEP = ("highway", "footway", "crossing", "crossing:markings", "foot", "access", "area", "bridge", "tunnel", "layer",
        "name", "sidewalk", "sidewalk:both", "sidewalk:left", "sidewalk:right", "service", "man_made", "leisure",
        "opening_hours", "indoor", "level", "area:highway", "oneway")
found = {i: {"ways": [], "nodes": []} for i in range(len(targets))}
for o in osmium.FileProcessor(str(PBF)).with_locations():
    if isinstance(o, osmium.osm.Node):
        if not (lon_min <= o.location.lon <= lon_max and lat_min <= o.location.lat <= lat_max):
            continue
        tg = dict(o.tags)
        if not any(k in tg for k in ("highway", "crossing", "barrier", "entrance")):
            continue
        for i in near_target((o.location.lon, o.location.lat)):
            found[i]["nodes"].append({"id": o.id, "ll": [round(o.location.lon, 7), round(o.location.lat, 7)],
                                      "tags": {k: v for k, v in tg.items() if k in KEEP + ("barrier", "entrance")}})
    elif isinstance(o, osmium.osm.Way):
        tg = dict(o.tags)
        if not any(k in tg for k in ("highway", "area:highway", "man_made", "leisure")):
            continue
        try:
            ll = [(n.lon, n.lat) for n in o.nodes]
        except osmium.InvalidLocationError:
            continue
        if not any(lon_min <= a <= lon_max and lat_min <= b <= lat_max for a, b in ll):
            continue
        hit = set()
        for p in ll:
            hit.update(near_target(p))
        # 꼭짓점이 멀어도 선분이 지나가면 잡는다 — 선분 중간점 표본
        for k in range(len(ll) - 1):
            a, b = ll[k], ll[k + 1]
            L = hav(a, b)
            n = int(L // 10)
            for s in range(1, n):
                t = s / n
                hit.update(near_target((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))))
        for i in hit:
            found[i]["ways"].append({"id": o.id, "n_nodes": len(ll), "tags": {k: v for k, v in tg.items() if k in KEEP},
                                     "len_m": round(sum(hav(ll[k], ll[k + 1]) for k in range(len(ll) - 1)), 1)})

out = []
for i, t in enumerate(targets):
    out.append(dict(t, osm=found[i]))
OUT.write_text(json.dumps({"pbf": PBF.name, "radius_m": R_M, "targets": out}, ensure_ascii=False, indent=1), encoding="utf-8")
for t in out:
    print(f"== {t['od']} seq{t['seq']} {t['ment'][:40]}")
    for w in t["osm"]["ways"]:
        tg = w["tags"]
        print("   way", w["id"], w["len_m"], {k: tg[k] for k in tg if k not in ("name",)}, tg.get("name", ""))
    for n in t["osm"]["nodes"]:
        print("   node", n["id"], n["tags"])
