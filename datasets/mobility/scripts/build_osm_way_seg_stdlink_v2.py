# datasets/mobility/scripts/build_osm_way_seg_stdlink_v2.py — OSM 도로 조각 × 진행 방향 → 전국 표준 링크 번호, 경로 계산 도로망 전체판 (2026-10-14)
#
# 왜 v2: v1 은 조각 형상을 graph/osm_way_geom_v1.csv(TOPIS 속도 자료가 붙은 way 8,664개)에서만 읽었다. 경로 계산기(road_graph_v2)의
#        차도 way 는 15만 2천 개라, 고가도로 연결로(trunk_link 등)처럼 TOPIS 대응이 없는 큰길은 표준 번호가 비었다
#        (예: 서울 실경보 내부순환도로 사건의 연결로 링크 1120033100 — v1 표에 0건).
# 무엇이 같나: 판정 규칙은 v1 과 같다(조각 가운데 20 m · 방향 35° · 방향마다 가장 가까운 링크 하나 · 없으면 비움). 좌표 변환·shp/dbf 읽기도 v1 함수를 쓴다.
# 무엇이 다른가:
#   · 대상 way = v1 형상 파일의 way 전부 ∪ road_graph_v2 의 차도(car=1) 중 큰길 등급과 그 연결로(TARGET_HW). 골목(residential·service 등)은
#     v1 에 있던 것만 둔다 — 큰길 옆 골목에 큰길 번호가 잘못 붙지 않게.
#   · 형상은 road_graph_v2 간선(점 번호 sa..sb · 폴리라인 g)으로 way 를 다시 잇는다. v1 형상 파일과 점 번호가 같은지 겹치는 way 전부로 검사한다.
#   · 일방통행 way(road_graph_v2 의 ow=1 정방향만 · ow=-1 역방향만)는 차가 갈 수 있는 방향에만 번호를 붙인다. v1 은 일방통행 길에도
#     반대쪽 번호를 찾아, 고가 연결로 아래 다른 도로의 번호가 「거꾸로 지날 때」 칸에 들어갔다(예: 연결로 way 204781426 ↔ 홍은중앙로).
#   · 출력에 way 형상(osm_way_geom_std_v2.csv.gz)을 함께 둔다 — 경로 계산(car.py)이 v1 형상에 없는 way 의 조각 번호를 찾을 때 쓴다.
# 입력: processed/mobility/road_graph_v2/edges.jsonl.gz · graph/osm_way_geom_v1.csv · raw/its_nodelink_20261014_v1/extract/MOCT_LINK.{shp,dbf}
# 출력: processed/mobility/stdlink_v2/osm_way_seg_stdlink_v2.csv.gz · osm_way_geom_std_v2.csv.gz · MANIFEST.json (기존 폴더를 덮지 않는다)
import argparse, csv, gzip, hashlib, io, json, datetime as dt
from collections import defaultdict
from pathlib import Path

from build_osm_way_seg_stdlink_v1 import (ANGLE_DEG, CELL, MAX_DIST_M, ROOT, bearing, read_dbf_ids, read_shp_polylines,
                                          seg_dist, tm)

TARGET_HW = {"motorway", "trunk", "primary", "secondary", "tertiary",
             "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}


def decode_polyline6(s):
    idx = lat = lng = 0
    out = []
    while idx < len(s):
        vals = []
        for _ in (0, 1):
            shift = res = 0
            while True:
                b = ord(s[idx]) - 63
                idx += 1
                res |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            vals.append(~(res >> 1) if res & 1 else res >> 1)
        lat += vals[0]
        lng += vals[1]
        out.append((lng / 1e6, lat / 1e6))
    return out


def gz_csv(rows, header):
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=buf, mode='wb', mtime=0) as gz:
        w = io.TextIOWrapper(gz, encoding='utf-8', newline='')
        cw = csv.writer(w)
        cw.writerow(header)
        cw.writerows(rows)
        w.flush()
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    mob = ROOT / 'datasets/mobility'
    ap.add_argument('--edges', default=str(mob / 'processed/mobility/road_graph_v2/edges.jsonl.gz'))
    ap.add_argument('--geom-v1', default=str(mob / 'processed/mobility/graph/osm_way_geom_v1.csv'))
    ap.add_argument('--shp', default=str(mob / 'raw/its_nodelink_20261014_v1/extract/MOCT_LINK.shp'))
    ap.add_argument('--out', default=str(mob / 'processed/mobility/stdlink_v2'))
    a = ap.parse_args()
    out = Path(a.out)
    if (out / 'osm_way_seg_stdlink_v2.csv.gz').exists():
        raise SystemExit(f'이미 있다 — 덮지 않는다: {out}')

    v1 = {}
    for r in csv.DictReader(open(a.geom_v1, encoding='utf-8')):
        v1[int(r['osm_way_id'])] = (r['highway'], [tuple(map(float, p.split(','))) for p in r['pts'].split(' ')])
    rg = defaultdict(dict)                       # way → {점 번호: (lon, lat)}
    rg_hw = {}
    oneway = {}                                  # way → ow (0 양방향 · 1 정방향만 · -1 역방향만), road_graph_v2 차도 간선 기준
    for line in gzip.open(a.edges, 'rt', encoding='utf-8'):
        e = json.loads(line)
        if e['car']:
            oneway[e['way']] = e['ow']
        if not e['car'] or not (e['hw'] in TARGET_HW or e['way'] in v1):
            continue
        pts = decode_polyline6(e['g'])
        lo, hi = min(e['sa'], e['sb']), max(e['sa'], e['sb'])
        if hi - lo != len(pts) - 1:
            continue
        if e['sa'] > e['sb']:
            pts = pts[::-1]
        for k, p in enumerate(pts):
            rg[e['way']].setdefault(lo + k, p)
        rg_hw[e['way']] = e['hw']
    # 점 번호 일치 검사(v1 형상과 겹치는 way) — 어긋나면 그 way 는 v1 형상을 쓴다
    stat = {'ways_v1': len(v1), 'ways_road_graph_target': len(rg), 'index_checked': 0, 'index_mismatch': 0}
    ways = {}
    for way, (hw, pts) in v1.items():
        ways[way] = (hw, pts)
        got = rg.get(way)
        if got:
            stat['index_checked'] += 1
            if any(abs(got[i][0] - pts[i][0]) > 2e-6 or abs(got[i][1] - pts[i][1]) > 2e-6 for i in got if i < len(pts)):
                stat['index_mismatch'] += 1
    for way, idx in rg.items():
        if way in ways:
            continue
        n = max(idx) + 1
        if len(idx) != n:                         # 점 번호에 빈칸이 있으면(일부 간선만 차도) 번호가 어긋나니 쓰지 않는다
            stat.setdefault('skipped_gap', 0)
            stat['skipped_gap'] += 1
            continue
        ways[way] = (rg_hw[way], [idx[i] for i in range(n)])
    stat['ways'] = len(ways)

    tmw = {w: [tm(lon, lat) for lon, lat in pts] for w, (_, pts) in ways.items()}
    xs = [p[0] for w in tmw.values() for p in w]
    ys = [p[1] for w in tmw.values() for p in w]
    box = (min(xs) - 200, min(ys) - 200, max(xs) + 200, max(ys) + 200)
    grid = defaultdict(list)
    nlinks = 0
    for parts, lid in zip(read_shp_polylines(a.shp), read_dbf_ids(Path(a.shp).with_suffix('.dbf'))):
        if not parts or not lid:
            continue
        if not any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for part in parts for x, y in part):
            continue
        nlinks += 1
        for part in parts:
            for (ax, ay), (bx, by) in zip(part, part[1:]):
                for ci in range(int(min(ax, bx) // CELL), int(max(ax, bx) // CELL) + 1):
                    for cj in range(int(min(ay, by) // CELL), int(max(ay, by) // CELL) + 1):
                        grid[(ci, cj)].append((lid, ax, ay, bx, by))
    stat.update(std_links_in_box=nlinks, segments=0, fwd=0, bwd=0, oneway_side_skipped=0)
    rows, used = [], set()
    for way, pts in tmw.items():
        for k in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[k], pts[k + 1]
            if (ax, ay) == (bx, by):
                continue
            stat['segments'] += 1
            mx, my = (ax + bx) / 2, (ay + by) / 2
            b = bearing(ax, ay, bx, by)
            best = {'fwd': (MAX_DIST_M + 1, None), 'bwd': (MAX_DIST_M + 1, None)}
            ci, cj = int(mx // CELL), int(my // CELL)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for lid, sx, sy, tx, ty in grid.get((ci + di, cj + dj), ()):
                        d = seg_dist(mx, my, sx, sy, tx, ty)
                        if d > MAX_DIST_M:
                            continue
                        diff = abs((bearing(sx, sy, tx, ty) - b + 180) % 360 - 180)
                        side = 'fwd' if diff <= ANGLE_DEG else 'bwd' if diff >= 180 - ANGLE_DEG else None
                        if side and d < best[side][0]:
                            best[side] = (d, lid)
            for side, (d, lid) in best.items():
                if lid and oneway.get(way, 0) == (1 if side == 'bwd' else -1):
                    stat['oneway_side_skipped'] += 1
                    continue
                if lid:
                    rows.append((way, k, side, lid, round(d, 1)))
                    stat[side] += 1
                    used.add(way)
    out.mkdir(parents=True, exist_ok=True)
    seg_bytes = gz_csv(rows, ['osm_way_id', 'seg_idx', 'dir', 'link_id', 'dist_m'])
    geom_rows = [(w, ways[w][0], ' '.join(f'{lon:.7f},{lat:.7f}' for lon, lat in ways[w][1])) for w in sorted(used) if w not in v1]
    geom_bytes = gz_csv(geom_rows, ['osm_way_id', 'highway', 'pts'])
    (out / 'osm_way_seg_stdlink_v2.csv.gz').write_bytes(seg_bytes)
    (out / 'osm_way_geom_std_v2.csv.gz').write_bytes(geom_bytes)
    stat['ways_with_match'] = len(used)
    stat['geom_rows_outside_v1'] = len(geom_rows)
    man = {'version': 'stdlink_v2', 'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
           'builder': 'datasets/mobility/scripts/build_osm_way_seg_stdlink_v2.py',
           'source': '국가교통정보센터 전국표준노드링크 NODELINKDATA.zip 2026-10-14판 MOCT_LINK · OSM 조각 형상 graph/osm_way_geom_v1.csv + road_graph_v2/edges.jsonl.gz',
           'source_url': 'https://www.its.go.kr/nodelink/nodelinkRef',
           'rule': {'max_dist_m': MAX_DIST_M, 'angle_deg': ANGLE_DEG, 'projection': 'GRS80 TM 38N 127E FE200000 FN600000 k1',
                    'ways': 'osm_way_geom_v1 전부 + road_graph_v2 차도 중 ' + ','.join(sorted(TARGET_HW))},
           'inputs': {k: hashlib.md5(Path(p).read_bytes()).hexdigest() for k, p in
                      (('edges.jsonl.gz', a.edges), ('osm_way_geom_v1.csv', a.geom_v1), ('MOCT_LINK.shp', a.shp))},
           'counts': stat,
           'files': {'osm_way_seg_stdlink_v2.csv.gz': {'md5': hashlib.md5(seg_bytes).hexdigest(), 'rows': len(rows)},
                     'osm_way_geom_std_v2.csv.gz': {'md5': hashlib.md5(geom_bytes).hexdigest(), 'rows': len(geom_rows)}}}
    (out / 'MANIFEST.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == '__main__':
    main()
