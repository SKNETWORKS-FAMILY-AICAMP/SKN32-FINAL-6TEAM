# datasets/mobility/scripts/build_stdlink_reverse_v2.py — 전국 표준 링크마다 「같은 도로의 반대 방향 링크」를 형상으로 찾는다 (2026-10-14)
#
# 왜: 표준 노드·링크는 방향마다 교차로 노드를 따로 둬서 「시작·끝 노드가 뒤바뀐 링크」로 반대 방향을 찾을 수 있는 것은 156만 개 중 790개뿐이다
#     (build_link_reverse_v1.py). 상·하행이 떨어진 도로(강변북로 등)와 연결로는 OSM 에서도 길이 따로라, 같은 지도 조각의 반대쪽 번호도 없다.
#     그래서 표준 자료 안에서 형상으로 짝을 짓는다.
# 규칙(형상·속성만 — 특정 사건 맞춤 없음):
#   · 링크 L 위에 STEP_M 간격으로 표본점을 찍고, 각 표본점에서 MAX_DIST_M 안에 있는 다른 링크 선분 중
#     도로 이름(ROAD_NAME)이 L 과 같고 진행 방향이 반대(차 180°±ANGLE_DEG)인 것을 가장 가까운 하나 고른다.
#   · 표본점의 MIN_COVER 이상에서 뽑힌 링크를 L 의 반대 방향으로 적는다(여러 개면 덮는 비율 순). 이름 없는 링크는 짝짓지 않는다.
# 한계: 기하 판정이다(공식 대응표 아님). 이름이 같은 평행 도로(예: 본선과 나란한 측도)가 있으면 그쪽이 잡힐 수 있다 — 덮는 비율을 함께 적는다.
# 입력: raw/its_nodelink_20261014_v1/extract/MOCT_LINK.{shp,dbf} — 서울(LINK_ID 앞 세 자리 100~124 — 자료에서 확인한 서울 25개 구 범위)만
# 출력: processed/mobility/stdlink_reverse_v2/stdlink_reverse_v2.csv.gz · MANIFEST.json (기존 폴더를 덮지 않는다)
import argparse, csv, gzip, hashlib, io, json, math, struct, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

from build_osm_way_seg_stdlink_v1 import ROOT, bearing, read_shp_polylines, seg_dist

STEP_M = 20.0
MAX_DIST_M = 60.0
ANGLE_DEG = 35.0
MIN_COVER = 0.3
CELL = 100.0


def dbf_attrs(path, want):
    with open(path, 'rb') as f:
        h = f.read(32)
        n, hl, rl = struct.unpack('<IHH', h[4:12])
        idx, pos = {}, 1
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            idx[d[:11].split(b'\0')[0].decode('ascii')] = (pos, pos + d[16])
            pos += d[16]
        f.seek(hl)
        for _ in range(n):
            r = f.read(rl)
            yield None if r[:1] == b'*' else {k: r[idx[k][0]:idx[k][1]].decode('cp949', 'replace').strip() for k in want}


def samples(line):
    out = []
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L // STEP_M))
        for i in range(n):
            t = (i + 0.5) / n
            out.append((ax + t * (bx - ax), ay + t * (by - ay), bearing(ax, ay, bx, by)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shp', default=str(ROOT / 'datasets/mobility/raw/its_nodelink_20261014_v1/extract/MOCT_LINK.shp'))
    ap.add_argument('--out', default=str(ROOT / 'datasets/mobility/processed/mobility/stdlink_reverse_v2'))
    ap.add_argument('--prefix-range', default='100-124')
    a = ap.parse_args()
    lo, hi = map(int, a.prefix_range.split('-'))
    out = Path(a.out)
    if (out / 'stdlink_reverse_v2.csv.gz').exists():
        raise SystemExit(f'이미 있다 — 덮지 않는다: {out}')
    links = {}
    for parts, attr in zip(read_shp_polylines(a.shp), dbf_attrs(Path(a.shp).with_suffix('.dbf'), ('LINK_ID', 'ROAD_NAME', 'CONNECT'))):
        if not parts or not attr or not lo <= int(attr['LINK_ID'][:3] or 0) <= hi:
            continue
        links[attr['LINK_ID']] = (attr['ROAD_NAME'], [p for part in parts for p in part])
    grid = defaultdict(list)
    for lid, (name, line) in links.items():
        if not name or name == '-':
            continue
        for (ax, ay), (bx, by) in zip(line, line[1:]):
            for ci in range(int(min(ax, bx) // CELL), int(max(ax, bx) // CELL) + 1):
                for cj in range(int(min(ay, by) // CELL), int(max(ay, by) // CELL) + 1):
                    grid[(ci, cj)].append((lid, ax, ay, bx, by))
    rows, stat = [], Counter(links=len(links))
    for lid, (name, line) in links.items():
        if not name or name == '-':
            stat['no_name'] += 1
            continue
        pts = samples(line)
        votes = Counter()
        for px, py, b in pts:
            best = (MAX_DIST_M + 1, None)
            ci, cj = int(px // CELL), int(py // CELL)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for other, sx, sy, tx, ty in grid.get((ci + di, cj + dj), ()):
                        if other == lid or links[other][0] != name:
                            continue
                        d = seg_dist(px, py, sx, sy, tx, ty)
                        if d >= best[0]:
                            continue
                        if abs((bearing(sx, sy, tx, ty) - b + 180) % 360 - 180) >= 180 - ANGLE_DEG:
                            best = (d, other)
            if best[1]:
                votes[best[1]] += 1
        rev = [(o, round(c / len(pts), 2)) for o, c in votes.most_common() if c / len(pts) >= MIN_COVER]
        stat['with_reverse' if rev else 'no_reverse'] += 1
        if len(rev) > 1:
            stat['multi_reverse'] += 1
        rows.append((lid, ' '.join(o for o, _ in rev), ' '.join(str(c) for _, c in rev), name))
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=buf, mode='wb', mtime=0) as gz:
        w = io.TextIOWrapper(gz, encoding='utf-8', newline='')
        cw = csv.writer(w)
        cw.writerow(['link_id', 'reverse_link_ids', 'cover', 'road_name'])
        cw.writerows(rows)
        w.flush()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'stdlink_reverse_v2.csv.gz').write_bytes(buf.getvalue())
    man = {'version': 'stdlink_reverse_v2', 'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
           'builder': 'datasets/mobility/scripts/build_stdlink_reverse_v2.py',
           'source': f'국가교통정보센터 전국표준노드링크 NODELINKDATA.zip 2026-10-14판 MOCT_LINK (서울 LINK_ID 앞 세 자리 {a.prefix_range})',
           'source_url': 'https://www.its.go.kr/nodelink/nodelinkRef',
           'rule': {'step_m': STEP_M, 'max_dist_m': MAX_DIST_M, 'angle_deg': ANGLE_DEG, 'min_cover': MIN_COVER, 'same': 'ROAD_NAME'},
           'inputs': {'MOCT_LINK.shp': hashlib.md5(Path(a.shp).read_bytes()).hexdigest()},
           'counts': dict(stat), 'files': {'stdlink_reverse_v2.csv.gz': {'md5': hashlib.md5(buf.getvalue()).hexdigest(), 'rows': len(rows)}}}
    (out / 'MANIFEST.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(stat), ensure_ascii=False))


if __name__ == '__main__':
    main()
