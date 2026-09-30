# datasets/mobility/scripts/build_road_graph_v1.py — 서울(+인접·공항) 차도·자전거 그래프 파일 (76번 방 · 2026-09-29)
#
# 목적: GraphHopper 서버 없이도 택시·자동차(·자전거) 경로를 파이썬에서 계산하게(77 서버 없는 라우터) 도로망을
#       노드·간선 표로 싣는다. **경로는 저장하지 않는다** — 지도 데이터(OSM 공표)만.
# 입력: raw/mobility/osm/south-korea-latest.osm.pbf (Geofabrik · ODbL · GH 그래프와 같은 파일 md5 b4aac996…)
# 출력: processed/mobility/road_graph_v1/
#         nodes.jsonl.gz     {"id","lat","lon","r"}                — 간선 끝점(교차점·way 끝)만 · r=1 범위 안(0 = 3 km 여백)
#         edges.jsonl.gz     {"u","v","way","sa","sb","len","ow","hw","ms","car","bike","bow","g","main","bmain"}
#         region_v1.geojson  범위 다각형(서울+인접 8시+영종구+공항고속도로 회랑)
#         MANIFEST.json      md5·행수·원자료·확인 시각 · build_report.json(수·크기·결정)
#   간선 = way 를 그래프 노드(교차점·끝점)에서 자른 조각. sa/sb = way 노드 순번 구간 [sa, sb] (sa<sb) —
#   osm_way_seg_topis_link_v1.csv 의 seg_idx(= way 안 i 번째 노드→i+1) 와 같은 기준이라 TOPIS 링크로 바로 이어진다.
#   ow: 차량 일방 0=양방향 · 1=u→v 만(way 방향) · -1=v→u 만.  bow: 자전거 일방(같은 뜻 · oneway:bicycle=no 면 0).
#   g: 형상 polyline(정밀도 1e-6 · 끝점 포함 · Google encoded polyline) — 좌표→간선 스냅용.
#   회전 제약(turn restriction)은 싣지 않는다(생략 · 77 등급 = 추정).
# 규칙 26: import 는 값만 정한다. 쓰기 직전에 ensure_dirs(). 기본 경로는 _paths(DATA_DIR → 없으면 REPO_ROOT/data).
# 실행: python datasets/mobility/scripts/build_road_graph_v1.py [--src <pbf>] [--out <폴더>] [--no-service]
import argparse, gzip, hashlib, json, math, sys, time, datetime as dt
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "final_project_cs" / "app").is_dir())   # 82: 저장소 루트를 위로 찾는다(자리 datasets/mobility/scripts/)
for _p in (REPO, Path(__file__).resolve().parent):          # 82: 옆 _paths.py 를 부른다
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

VERSION = "road_graph_v1"
# ── 범위(담당자 결정 76 · 근거 = 같은 pbf 의 OSM 행정경계 relation · 확정) ──
REGION_ADMIN = {            # 이름 → (admin_level, 기대 relation id — 다르면 멈춘다)
    "서울특별시": ("4", 2297418),
    "고양시": ("6", 2409166), "성남시": ("6", 2409180), "과천시": ("6", 2409169),
    "하남시": ("6", 2409172), "구리시": ("6", 2409168), "광명시": ("6", 2409171),
    "부천시": ("6", 2409162), "김포시": ("6", 2409165),
    "영종구": ("6", 13349474),   # 인천공항(2026-07 인천 행정개편으로 중구에서 분리) — 섬 전체
}
AIRPORT_CORRIDOR_NAMES = ("인천국제공항고속도로",)   # 이 이름 motorway 양옆 CORRIDOR_M 회랑(서구·계양구 통과 구간)
CORRIDOR_M = 500
MARGIN_M = 3000            # 싣는 범위 = 범위 + 3 km 여백. 경계에서 잘린 일방통행이 막다른 길(강연결 끊김)이 되는 것을
                           # 질의 범위 밖으로 밀어낸다(76 검수: 여백 0 이면 353 도로 끝점 5곳이 최대 강연결 성분 밖)

CAR_HW = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
          "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
          "residential", "living_street", "road", "service"}
SERVICE_DROP = {"parking_aisle", "drive-through", "emergency_access"}   # 주차장 통로 등은 택시 경로가 아니다
BIKE_ONLY_HW = {"cycleway"}
BIKE_IF_TAGGED_HW = {"path", "footway", "pedestrian", "track", "bridleway"}   # bicycle=yes/designated 일 때만
BIKE_NO_HW = {"motorway", "motorway_link", "trunk", "trunk_link"}   # 자동차전용도로 — bicycle=yes 없으면 불가
YES = {"yes", "designated", "permissive", "destination"}
NO = {"no", "private"}


def hav(lat1, lon1, lat2, lon2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(d))


def enc_polyline(coords, prec=6):
    f = 10 ** prec
    out, plat, plon = [], 0, 0
    for lat, lon in coords:
        ilat, ilon = int(round(lat * f)), int(round(lon * f))
        for v in (ilat - plat, ilon - plon):
            v = ~(v << 1) if v < 0 else (v << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63)); v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def parse_maxspeed(v):
    if not v:
        return None
    v = v.strip().lower()
    try:
        if v.endswith("mph"):
            return int(round(float(v[:-3]) * 1.609))
        return int(float(v.split()[0].replace("km/h", "")))
    except ValueError:
        return None


def oneway_of(tags, hw):
    ow = tags.get("oneway", "")
    if ow in ("yes", "1", "true"):
        return 1
    if ow in ("-1", "reverse"):
        return -1
    if ow == "no":
        return 0
    if hw in ("motorway", "motorway_link") or tags.get("junction") in ("roundabout", "circular"):
        return 1
    return 0


def classify(tags):
    """(car_ok, bike_ok) — 둘 다 False 면 싣지 않는다."""
    hw = tags.get("highway")
    if not hw or tags.get("area") == "yes":
        return False, False
    acc = tags.get("access", "")
    mv = tags.get("motor_vehicle", tags.get("motorcar", ""))
    bic = tags.get("bicycle", "")
    car = hw in CAR_HW
    if car and hw == "service" and tags.get("service") in SERVICE_DROP:
        car = False
    if car:
        if mv in NO:
            car = False
        elif acc in NO and mv not in YES:
            car = False
    if hw in BIKE_ONLY_HW:
        bike = bic not in NO
    elif hw in BIKE_IF_TAGGED_HW:
        bike = bic in YES
    elif hw in BIKE_NO_HW:
        bike = bic in YES
    elif hw in CAR_HW:
        bike = bic not in NO and not (acc in NO and bic not in YES)
    else:
        bike = False
    return car, bike


def build_region(src, log):
    import osmium
    from shapely import wkb as swkb
    from shapely.ops import unary_union
    from shapely.geometry import LineString
    wkbf = osmium.geom.WKBFactory()
    want = {v[1]: k for k, v in REGION_ADMIN.items()}
    polys, found = {}, {}
    fp = osmium.FileProcessor(src).with_areas(osmium.filter.TagFilter(("boundary", "administrative")))
    for o in fp:
        if isinstance(o, osmium.osm.Area) and not o.from_way() and o.orig_id() in want:
            nm = o.tags.get("name")
            if nm != want[o.orig_id()] or o.tags.get("admin_level") != REGION_ADMIN[nm][0]:
                raise SystemExit(f"경계 relation {o.orig_id()} 이름/레벨 불일치: {nm}")
            polys[nm] = swkb.loads(wkbf.create_multipolygon(o), hex=True)
            found[nm] = o.orig_id()
    miss = set(REGION_ADMIN) - set(polys)
    if miss:
        raise SystemExit(f"경계 relation 을 못 찾음: {miss}")
    # 공항고속도로 회랑 — 도(度) 단위 버퍼를 위도 37.5 기준 m 로 환산(가로·세로 다른 비율 → 짧은 축 기준 보수적)
    lines = []
    for w in osmium.FileProcessor(src).with_locations().with_filter(osmium.filter.KeyFilter("highway")):
        if isinstance(w, osmium.osm.Way) and w.tags.get("name") in AIRPORT_CORRIDOR_NAMES:
            try:
                lines.append(LineString([(n.lon, n.lat) for n in w.nodes]))
            except osmium.InvalidLocationError:
                pass
    deg = CORRIDOR_M / 111320.0 / math.cos(math.radians(37.5))
    corridor = unary_union(lines).buffer(deg)
    region = unary_union(list(polys.values()) + [corridor])
    log["region"] = {"admin_relations": found, "corridor_ways": len(lines), "corridor_m": CORRIDOR_M,
                     "area_km2_approx": round(region.area * 111.32 * 111.32 * math.cos(math.radians(37.5)), 1),
                     "bounds": [round(x, 5) for x in region.bounds]}
    return region, polys, corridor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--out")
    ap.add_argument("--no-service", action="store_true", help="highway=service 제외(크기 초과 시)")
    ap.add_argument("--no-geom", action="store_true", help="형상 g 제외(크기 비교용)")
    a = ap.parse_args()
    if not (a.src and a.out):
        from _paths import RAW_MOBILITY, PROCESSED, ensure_dirs
        ensure_dirs()
        a.src = a.src or str(RAW_MOBILITY / "osm" / "south-korea-latest.osm.pbf")
        a.out = a.out or str(PROCESSED / "mobility" / VERSION)
    import osmium
    import numpy as np
    import shapely
    from shapely.geometry import mapping

    t0 = time.time()
    src = Path(a.src)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log = {"version": VERSION, "src": src.name, "src_bytes": src.stat().st_size,
           "built_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")}
    h = hashlib.md5()
    with open(src, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    log["src_md5"] = h.hexdigest()
    hdr = osmium.io.Reader(str(src), osmium.osm.osm_entity_bits.NOTHING).header()
    log["osmosis_replication_timestamp"] = hdr.get("osmosis_replication_timestamp", "")

    region, polys, corridor = build_region(str(src), log)
    load = region.buffer(MARGIN_M / 111320.0 / math.cos(math.radians(37.5))) if MARGIN_M else region
    shapely.prepare(load)
    minx, miny, maxx, maxy = load.bounds
    log["region"]["margin_m"] = MARGIN_M
    print(f"[범위] {log['region']} ({time.time()-t0:.0f}s)")

    # ── 1패스: 차도·자전거 way 수집(노드 좌표 포함) ──
    ways = []   # (way_id, [node ids], [(lat,lon)], tags dict subset, car, bike)
    keep_tags = ("highway", "oneway", "oneway:bicycle", "maxspeed", "junction", "service", "name", "ref")
    n_seen = 0
    for w in osmium.FileProcessor(str(src)).with_locations().with_filter(osmium.filter.KeyFilter("highway")):
        if not isinstance(w, osmium.osm.Way):
            continue
        n_seen += 1
        tags = dict(w.tags)
        if a.no_service and tags.get("highway") == "service":
            continue
        car, bike = classify(tags)
        if not (car or bike):
            continue
        try:
            nids = [n.ref for n in w.nodes]
            ll = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError:
            continue
        if len(nids) < 2:
            continue
        if not any(miny <= la <= maxy and minx <= lo <= maxx for la, lo in ll):
            continue
        lats = np.fromiter((p[0] for p in ll), float); lons = np.fromiter((p[1] for p in ll), float)
        if not shapely.contains_xy(load, lons, lats).any():
            continue
        ways.append((w.id, nids, ll, {k: tags[k] for k in keep_tags if k in tags}, car, bike))
    print(f"[way] 보유 highway {n_seen:,} → 범위 안 차도·자전거 {len(ways):,} ({time.time()-t0:.0f}s)")

    # ── 그래프 노드 = way 끝점 + 두 번 이상 쓰인 노드 ──
    cnt = {}
    for _, nids, _, _, _, _ in ways:
        for i, n in enumerate(nids):
            cnt[n] = cnt.get(n, 0) + (2 if i in (0, len(nids) - 1) else 1)
    gnode = {n for n, c in cnt.items() if c >= 2}
    coord = {}
    edges = []
    for wid, nids, ll, tg, car, bike in ways:
        hw = tg["highway"]
        ow = oneway_of(tg, hw) if car else 0
        bow = oneway_of(tg, hw) if bike else 0
        if tg.get("oneway:bicycle") == "no":
            bow = 0
        elif hw in BIKE_ONLY_HW and "oneway" not in tg:
            bow = 0
        ms = parse_maxspeed(tg.get("maxspeed"))
        start = 0
        for i in range(1, len(nids)):
            if nids[i] in gnode or i == len(nids) - 1:
                seg = ll[start:i + 1]
                L = sum(hav(*seg[k], *seg[k + 1]) for k in range(len(seg) - 1))
                u, v = nids[start], nids[i]
                coord[u] = ll[start]; coord[v] = ll[i]
                e = {"u": u, "v": v, "way": wid, "sa": start, "sb": i, "len": round(L, 1), "ow": ow,
                     "hw": hw, "ms": ms, "car": int(car), "bike": int(bike), "bow": bow}
                if not a.no_geom:
                    e["g"] = enc_polyline(seg)
                edges.append(e)
                start = i
    print(f"[그래프] 노드 {len(coord):,} · 간선 {len(edges):,} ({time.time()-t0:.0f}s)")

    # ── 표시: 차량 최대 강연결 성분(main) · 자전거 최대 약연결 성분(bmain) · 노드가 범위 안(r) ──
    #   주차장 통로(parking_aisle 제외)·access=no 로 끊긴 섬, 여백 끝의 막다른 일방통행은 main=0 — 77 은 main=1 에만 스냅한다.
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    ids = list(coord); ix = {n: i for i, n in enumerate(ids)}

    def comp(sel, owkey, directed):
        us, vs = [], []
        for e in edges:
            if not e[sel]:
                continue
            u, v, o = ix[e["u"]], ix[e["v"]], e[owkey]
            if not directed or o in (0, 1): us.append(u); vs.append(v)
            if not directed or o in (0, -1): us.append(v); vs.append(u)
        M = coo_matrix((np.ones(len(us)), (us, vs)), shape=(len(ids), len(ids))).tocsr()
        _, lab = connected_components(M, directed=directed, connection="strong")
        used = np.zeros(len(ids), bool); used[us] = True
        big = np.bincount(lab[used]).argmax()
        return lab, big
    lab_c, big_c = comp("car", "ow", True)
    lab_b, big_b = comp("bike", "bow", False)
    for e in edges:
        iu, iv = ix[e["u"]], ix[e["v"]]
        e["main"] = int(bool(e["car"]) and lab_c[iu] == big_c and lab_c[iv] == big_c)
        e["bmain"] = int(bool(e["bike"]) and lab_b[iu] == big_b)
    lats = np.array([coord[n][0] for n in ids]); lons = np.array([coord[n][1] for n in ids])
    inreg = shapely.contains_xy(region, lons, lats)

    # ── 쓰기 ──
    def write_gz(path, rows):
        # mtime=0 · 파일명 없음 → 같은 입력이면 기기가 달라도 md5 가 같다(노트북 재실행 대조용)
        with open(path, "wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            for r in rows:
                gz.write((json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    write_gz(out / "nodes.jsonl.gz", ({"id": n, "lat": round(coord[n][0], 7), "lon": round(coord[n][1], 7), "r": int(inreg[ix[n]])}
                                      for n in sorted(coord)))
    edges.sort(key=lambda e: (e["way"], e["sa"]))
    write_gz(out / "edges.jsonl.gz", edges)
    reg = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": k, "relation": REGION_ADMIN[k][1]},
         "geometry": mapping(shapely.simplify(p, 0.0002))} for k, p in polys.items()] + [
        {"type": "Feature", "properties": {"name": "인천국제공항고속도로 회랑", "buffer_m": CORRIDOR_M},
         "geometry": mapping(shapely.simplify(corridor, 0.0002))}]}
    (out / "region_v1.geojson").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")

    log["counts"] = {"ways": len(ways), "nodes": len(coord), "edges": len(edges),
                     "edges_car": sum(e["car"] for e in edges), "edges_bike": sum(e["bike"] for e in edges),
                     "edges_bike_only": sum(1 for e in edges if e["bike"] and not e["car"]),
                     "len_km_car": round(sum(e["len"] for e in edges if e["car"]) / 1000, 1),
                     "edges_car_main": sum(e["main"] for e in edges), "edges_bike_main": sum(e["bmain"] for e in edges),
                     "nodes_in_region": int(inreg.sum())}
    log["options"] = {"no_service": a.no_service, "no_geom": a.no_geom, "service_drop": sorted(SERVICE_DROP),
                      "turn_restrictions": "생략"}
    log["elapsed_s"] = round(time.time() - t0, 1)
    man = {"version": VERSION, "source": "Geofabrik south-korea-latest.osm.pbf",
           "source_url": "https://download.geofabrik.de/asia/south-korea-latest.osm.pbf",
           "license": "ODbL 1.0 (© OpenStreetMap contributors)", "grade": "확정(OSM 공표)",
           "src_md5": log["src_md5"], "osm_data_at": log["osmosis_replication_timestamp"],
           "built_at": log["built_at"], "files": {}}
    for fn in ("nodes.jsonl.gz", "edges.jsonl.gz", "region_v1.geojson"):
        b = (out / fn).read_bytes()
        rows = None
        if fn.endswith(".gz"):
            rows = gzip.decompress(b).count(b"\n")
        man["files"][fn] = {"bytes": len(b), "md5": hashlib.md5(b).hexdigest(), "rows": rows}
    (out / "MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "build_report.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(man["files"], ensure_ascii=False))
    print(json.dumps(log["counts"], ensure_ascii=False), f"{log['elapsed_s']}s")


if __name__ == "__main__":
    main()
