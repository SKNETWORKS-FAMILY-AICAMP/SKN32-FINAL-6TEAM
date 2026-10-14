# datasets/mobility/scripts/build_osm_way_seg_stdlink_v1.py — OSM 도로 조각 × 진행 방향 → 전국 표준 링크 번호 (2026-10-14)
#
# 왜: 경찰청 UTIC 도로 사건 원문의 구간 번호(linkId · lineLinkId)는 **전국 표준 링크 번호**다(서울 실경보 28건의 번호 133개 중 132개가
#     국가교통정보센터 표준 노드·링크에 있음). 택시 경로의 `링크:` 는 지금 서울시 교통 속도(TOPIS) 대응표 번호라 원문 번호와 133개 중 20개만 겹친다.
#     표준 링크는 진행 방향마다 따로 있으므로, 길 조각마다 방향별 표준 링크를 붙이면 경로의 구간 번호가 원문과 같은 체계가 되고
#     사건 구간의 반대 방향 번호도 같은 조각의 반대쪽에서 바로 나온다(표준 자료는 방향마다 교차로 노드가 달라 「노드가 뒤바뀐 링크」로는 못 찾음).
# 규칙(기하만 — 특정 사건 맞춤 없음):
#   · 좌표: OSM 위경도를 표준 자료와 같은 GRS80 중부원점 횡메르카토르(원점 38N·127E, 가산 200000/600000, 축척 1)로 바꿔 미터로 잰다.
#   · 조각(way 형상의 점 k→k+1) 가운데 점에서 MAX_DIST_M 안의 표준 링크 선분 중, 방향이 ANGLE_DEG 안으로 같으면 정방향(fwd) 후보,
#     180°±ANGLE_DEG 이면 역방향(bwd) 후보. 방향마다 가장 가까운 링크 하나를 붙인다. 없으면 그 방향은 비운다(지어내지 않음).
# 입력: processed/mobility/graph/osm_way_geom_v1.csv · raw/its_nodelink_20261014_v1/extract/MOCT_LINK.{shp,dbf}
# 출력: processed/mobility/stdlink_v1/osm_way_seg_stdlink_v1.csv(.gz) · MANIFEST.json — 기존 TOPIS 대응표와 같은 칸(osm_way_id, seg_idx, dir, link_id) + dist_m
import argparse, csv, gzip, hashlib, io, json, math, struct, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX_DIST_M = 20.0
ANGLE_DEG = 35.0
CELL = 50.0

# ── GRS80 중부원점 TM 정방향(Snyder 식) ──
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_LAT0, _LON0, _FE, _FN = math.radians(38.0), math.radians(127.0), 200000.0, 600000.0


def _m(phi):
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    return _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                 + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi) - (35 * e6 / 3072) * math.sin(6 * phi))


_M0 = _m(_LAT0)


def tm(lon, lat):
    phi, lam = math.radians(lat), math.radians(lon)
    s, c, t = math.sin(phi), math.cos(phi), math.tan(phi)
    n = _A / math.sqrt(1 - _E2 * s * s)
    T, C, A = t * t, _EP2 * c * c, (lam - _LON0) * c
    x = _FE + n * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * _EP2) * A ** 5 / 120)
    y = _FN + (_m(phi) - _M0 + n * t * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24
                                      + (61 - 58 * T + T * T + 600 * C - 330 * _EP2) * A ** 6 / 720))
    return x, y


def read_shp_polylines(path):
    with open(path, 'rb') as f:
        f.seek(100)
        while True:
            h = f.read(8)
            if len(h) < 8:
                return
            _num, ln = struct.unpack('>ii', h)
            body = f.read(ln * 2)
            st = struct.unpack('<i', body[:4])[0]
            if st == 0:
                yield None
                continue
            nparts, npts = struct.unpack('<ii', body[36:44])
            parts = struct.unpack(f'<{nparts}i', body[44:44 + 4 * nparts])
            off = 44 + 4 * nparts
            xy = struct.unpack(f'<{2 * npts}d', body[off:off + 16 * npts])
            pts = [(xy[2 * i], xy[2 * i + 1]) for i in range(npts)]
            yield [pts[parts[i]:(parts[i + 1] if i + 1 < nparts else npts)] for i in range(nparts)]


def read_dbf_ids(path):
    with open(path, 'rb') as f:
        h = f.read(32)
        n, hl, rl = struct.unpack('<IHH', h[4:12])
        fields, pos = {}, 1
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            name, ln = d[:11].split(b'\0')[0].decode('ascii'), d[16]
            fields[name] = (pos, pos + ln)
            pos += ln
        f.seek(hl)
        a, b = fields['LINK_ID']
        for _ in range(n):
            r = f.read(rl)
            yield None if r[:1] == b'*' else r[a:b].decode('ascii', 'replace').strip()


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def bearing(ax, ay, bx, by):
    return math.degrees(math.atan2(by - ay, bx - ax)) % 360.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--geom', default=str(ROOT / 'datasets/mobility/processed/mobility/graph/osm_way_geom_v1.csv'))
    ap.add_argument('--shp', default=str(ROOT / 'datasets/mobility/raw/its_nodelink_20261014_v1/extract/MOCT_LINK.shp'))
    ap.add_argument('--out', default=str(ROOT / 'datasets/mobility/processed/mobility/stdlink_v1'))
    a = ap.parse_args()
    out = Path(a.out)
    if (out / 'osm_way_seg_stdlink_v1.csv.gz').exists():
        raise SystemExit(f'이미 있다 — 덮지 않는다: {out}')
    out.mkdir(parents=True, exist_ok=True)
    ways = {}
    for r in csv.DictReader(open(a.geom, encoding='utf-8')):
        pts = [tuple(map(float, p.split(','))) for p in r['pts'].split(' ')]
        ways[int(r['osm_way_id'])] = [tm(lon, lat) for lon, lat in pts]
    xs = [p[0] for w in ways.values() for p in w]
    ys = [p[1] for w in ways.values() for p in w]
    box = (min(xs) - 200, min(ys) - 200, max(xs) + 200, max(ys) + 200)
    grid = defaultdict(list)            # 칸 → [(link_id, ax, ay, bx, by)]
    nlinks = 0
    for parts, lid in zip(read_shp_polylines(a.shp), read_dbf_ids(Path(a.shp).with_suffix('.dbf'))):
        if not parts or not lid:
            continue
        flat = [p for part in parts for p in part]
        if not any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in flat):
            continue
        nlinks += 1
        for part in parts:
            for (ax, ay), (bx, by) in zip(part, part[1:]):
                for ci in range(int(min(ax, bx) // CELL), int(max(ax, bx) // CELL) + 1):
                    for cj in range(int(min(ay, by) // CELL), int(max(ay, by) // CELL) + 1):
                        grid[(ci, cj)].append((lid, ax, ay, bx, by))
    rows, stat = [], {'ways': len(ways), 'std_links_in_box': nlinks, 'segments': 0, 'fwd': 0, 'bwd': 0}
    for way, pts in ways.items():
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
                if lid:
                    rows.append((way, k, side, lid, round(d, 1)))
                    stat[side] += 1
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=buf, mode='wb', mtime=0) as gz:
        w = io.TextIOWrapper(gz, encoding='utf-8', newline='')
        cw = csv.writer(w)
        cw.writerow(['osm_way_id', 'seg_idx', 'dir', 'link_id', 'dist_m'])
        cw.writerows(rows)
        w.flush()
    (out / 'osm_way_seg_stdlink_v1.csv.gz').write_bytes(buf.getvalue())
    man = {'version': 'stdlink_v1', 'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
           'builder': 'datasets/mobility/scripts/build_osm_way_seg_stdlink_v1.py',
           'source': '국가교통정보센터 전국표준노드링크 NODELINKDATA.zip 2026-10-14판 MOCT_LINK · OSM 조각 형상 graph/osm_way_geom_v1.csv',
           'source_url': 'https://www.its.go.kr/nodelink/nodelinkRef',
           'rule': {'max_dist_m': MAX_DIST_M, 'angle_deg': ANGLE_DEG, 'projection': 'GRS80 TM 38N 127E FE200000 FN600000 k1'},
           'inputs': {'osm_way_geom_v1.csv': hashlib.md5(Path(a.geom).read_bytes()).hexdigest(),
                      'MOCT_LINK.shp': hashlib.md5(Path(a.shp).read_bytes()).hexdigest()},
           'counts': stat, 'files': {'osm_way_seg_stdlink_v1.csv.gz': {'md5': hashlib.md5(buf.getvalue()).hexdigest(), 'rows': len(rows)}}}
    (out / 'MANIFEST.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == '__main__':
    main()
