# datasets/mobility/scripts/build_building_entrance_kr_v1.py — 전국 시도별 건물 출입구 → 도로 연결선 끝 (2026-10-19)
#
# 왜: 서울판(build_building_entrance_seoul_v1.py)과 같은 자료를 다른 시도에도 미리 만들어 둔다(2026-10-19 사용자 지시 —
#     「나중에 쓸 수도 있으니 전국을 x600 서버에 넣어 셋팅」). 지금 앱은 서울 보행 중계에서만 이 자료를 읽는다.
# 서울판과 다른 점 — 서울 밖에는 서울시 도보 그래프가 없어 「보행 길에서 멀 수 있는 건물」을 그래프로 가를 수 없다:
#   · 걸러 담기 = 건물 상자 반대각선의 절반 > MIN_HALF_DIAG_M(15 m). 서울에서 이 기준은 53,894동으로
#     그래프 상한 기준(53,893동)과 개수가 비슷했다(겹치는 정도는 재지 않았다). 크기 기준이라 작은 건물은 없다.
#   · 연결선 끝이 보행 길에서 30 m 안인지는 거르지 않는다 — 앱(walk_router._entrance_for)이 고를 때 그 자리에서 확인한다.
#   · 나머지(키 (SIG_CD, BUL_MAN_NO) · 같은 키는 가장 가까운 면 · 연결선 출입구 반대쪽 끝 · 줄 형식)는 서울판 그대로 —
#     시도 폴더 하나를 engine/building_entrances.BuildingEntrances 가 그대로 읽는다.
# 입력: 시도별 zip 폴더(datasets/travel/건물도형/) — 풀지 않고 zip 안에서 한 줄씩 읽는다(원본 zip 은 그대로 · 풀린 사본을 남기지 않는다).
# 출력: processed/mobility/building_entrance_kr_v1/<시도코드>/{buildings.jsonl.gz, build_report.json} + MANIFEST.json
#       (출력 폴더가 있으면 멈춘다 — 덮지 않는다. 만드는 동안은 <출력>.building 폴더에 쓰고 끝나면 이름을 바꾼다)
import argparse, datetime as dt, gzip, hashlib, json, math, struct, sys, time, zipfile
from collections import Counter, defaultdict
from pathlib import Path

from juso_shp import utmk_to_lonlat
from build_building_entrance_seoul_v1 import md5, q

ROOT = Path(__file__).resolve().parents[3]
ZIPS = ROOT / 'datasets' / 'travel' / '건물도형'
PROC = ROOT / 'datasets' / 'mobility' / 'processed' / 'mobility'
MIN_HALF_DIAG_M = 15.0
LAYERS = ('TL_SGCO_RNADR_MST', 'TL_SPBD_ENTRC', 'TL_SPOT_CNTC')


def shp_iter_f(f):
    """build_building_entrance_seoul_v1.shp_iter 와 같다 — 열린 파일(zip 안 파일)에서 앞으로만 읽는다."""
    f.read(100)
    while True:
        h = f.read(8)
        if len(h) < 8:
            return
        _n, ln = struct.unpack('>ii', h)
        body = f.read(ln * 2)
        st = struct.unpack('<i', body[:4])[0]
        if st == 0:
            yield None
        elif st == 1:
            yield struct.unpack('<2d', body[4:20])
        elif st in (3, 5):
            nparts, npts = struct.unpack('<ii', body[36:44])
            parts = struct.unpack(f'<{nparts}i', body[44:44 + 4 * nparts])
            off = 44 + 4 * nparts
            xy = struct.unpack(f'<{2 * npts}d', body[off:off + 16 * npts])
            pts = [(xy[2 * i], xy[2 * i + 1]) for i in range(npts)]
            yield [pts[parts[i]:(parts[i + 1] if i + 1 < nparts else npts)] for i in range(nparts)]
        else:
            raise ValueError(f'모르는 도형 종류 {st}')


def dbf_iter_f(f, want):
    """juso_shp.read_dbf 와 같은 값 — 필요한 칸만, 한 줄씩. 지운 행은 None."""
    h = f.read(32)
    n, hl, rl = struct.unpack('<IHH', h[4:12])
    head = f.read(hl - 32)                                   # 칸 설명들 + 끝 표시(0x0D) — 앞으로만 읽으니 머리를 한 번에 읽는다
    fields, pos = [], 1
    for o in range(0, len(head) - 31, 32):
        d = head[o:o + 32]
        if d[0] == 0x0D:
            break
        name = d[:11].split(b'\0')[0].decode('ascii')
        if name in want:
            fields.append((name, pos, pos + d[16]))
        pos += d[16]
    if pos != rl or len(fields) != len(want):
        raise ValueError(f'dbf 머리 해석 실패: 행 길이 {rl} · 칸 합 {pos} · 찾은 칸 {[k for k, _a, _b in fields]} / {sorted(want)}')
    for _ in range(n):
        r = f.read(rl)
        if r[:1] == b'*':
            yield None
            continue
        yield {k: r[a:b].replace(b'\0', b' ').decode('cp949', 'replace').strip() for k, a, b in fields}


class Layers:
    """zip 하나 — 층 이름으로 (도형, 속성) 을 같이 돌린다."""
    def __init__(self, zp):
        self.z = zipfile.ZipFile(zp)
        self.names = {n.split('.')[3]: n.rsplit('.', 1)[0] for n in self.z.namelist() if n.split('.')[3] in LAYERS}
        any_name = next(iter(self.names.values()))
        self.code, self.day = any_name.split('.')[-1], any_name.split('.')[2]

    def rows(self, layer, want):
        with self.z.open(self.names[layer] + '.shp') as fs, self.z.open(self.names[layer] + '.dbf') as fd:
            yield from zip(shp_iter_f(fs), dbf_iter_f(fd, want))

    def shp_md5(self, layer):
        h = hashlib.md5()
        with self.z.open(self.names[layer] + '.shp') as f:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
        return h.hexdigest()


GRID_M = 200.0                                               # 큰 묶음의 격자 칸(m)
BIG_GROUP = 32                                               # 이보다 큰 같은-키 묶음만 격자로 찾는다


def nearest_in(cs, xy, grids):
    """같은 키 면 가운데(cs) 중 xy 에 가장 가까운 것 — 결과는 min(cs, 거리) 와 같다(같은 거리면 먼저 나온 것).
    큰 묶음(번호 「0」 등 수천 개)은 격자를 한 번 만들어 가까운 칸부터 넓혀 찾는다 — 쌍 비교가 시도 하나에 억 번을 넘었다."""
    if len(cs) <= BIG_GROUP:
        return min(cs, key=lambda c: math.dist(c[:2], xy))
    g = grids.get(id(cs))
    if g is None:
        g = grids[id(cs)] = defaultdict(list)
        for i, c in enumerate(cs):
            g[(int(c[0] // GRID_M), int(c[1] // GRID_M))].append(i)
    cx, cy = int(xy[0] // GRID_M), int(xy[1] // GRID_M)
    best = None
    ring = 0
    while True:
        for gx in range(cx - ring, cx + ring + 1):
            for gy in (range(cy - ring, cy + ring + 1) if gx in (cx - ring, cx + ring) else (cy - ring, cy + ring)):
                for i in g.get((gx, gy), ()):
                    d = math.dist(cs[i][:2], xy)
                    if best is None or d < best[0] or (d == best[0] and i < best[1]):
                        best = (d, i)
        # 다음 고리의 칸은 모두 (ring × GRID_M) 보다 멀다 — 찾은 것이 그보다 가까우면 끝(묶음이 비지 않아 언젠가 끝난다)
        if best is not None and best[0] <= ring * GRID_M:
            return cs[best[1]]
        ring += 1


def build_one(L, out_dir):
    t0 = time.time()
    rep = Counter()
    cent = defaultdict(list)                                 # 키 → [(가운데 x, y, 담은 번호 또는 None)]
    kept = []                                                # [키, 상자, 고리들(UTM-K)]
    for rings, r in L.rows('TL_SGCO_RNADR_MST', {'SIG_CD', 'BUL_MAN_NO'}):
        if rings is None or r is None:
            rep['building_empty'] += 1
            continue
        rep['building'] += 1
        xs = [x for ring in rings for x, _y in ring]
        ys = [y for ring in rings for _x, y in ring]
        bb = (min(xs), min(ys), max(xs), max(ys))
        key = (r['SIG_CD'], r['BUL_MAN_NO'])
        idx = None
        if math.hypot(bb[2] - bb[0], bb[3] - bb[1]) / 2 > MIN_HALF_DIAG_M:
            idx = len(kept)
            kept.append([key, bb, rings])
        cent[key].append(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, idx))
    rep['building_kept_by_size'] = len(kept)
    # 진단만 — 같은 키 면들의 가운데가 500 m 넘는 상자에 흩어진 묶음 수(서울판의 쌍 비교는 큰 묶음에서 너무 느려 상자로 잰다)
    rep['key_groups_spread_box_over_500m'] = sum(
        1 for v in cent.values() if len(v) > 1
        and math.hypot(max(p[0] for p in v) - min(p[0] for p in v), max(p[1] for p in v) - min(p[1] for p in v)) > 500)

    # 출입구 — 같은 키의 면 중 가장 가까운 면(담지 않은 면이 가장 가까우면 버린다)
    ents = defaultdict(list)
    grids = {}
    for xy, r in L.rows('TL_SPBD_ENTRC', {'SIG_CD', 'BUL_MAN_NO', 'ENT_MAN_NO', 'ENTRC_SE'}):
        if xy is None or r is None:
            continue
        cs = cent.get((r['SIG_CD'], r['BUL_MAN_NO']))
        if not cs:
            rep['entrance_no_building'] += 1
            continue
        near = nearest_in(cs, xy, grids)
        if near[2] is not None:
            ents[near[2]].append(((r['SIG_CD'], r['ENT_MAN_NO']), r['ENTRC_SE'], xy))
    cent = None
    want = {e[0] for v in ents.values() for e in v}

    # 연결선 — 출입구 반대쪽 끝과 도형 길이
    road = {}
    for parts, r in L.rows('TL_SPOT_CNTC', {'SIG_CD', 'ENT_MAN_NO'}):
        if not parts or r is None:
            continue
        k = (r['SIG_CD'], r['ENT_MAN_NO'])
        if k in want:
            pts = [p for part in parts for p in part]
            road[k] = (pts, sum(math.dist(pts[j], pts[j + 1]) for j in range(len(pts) - 1)))

    out_dir.mkdir(parents=True)
    n_out, n_ent, kinds = 0, 0, Counter()
    tmp = out_dir / 'buildings.jsonl.gz.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for idx, (key, bb, rings) in enumerate(kept):
            usable = []
            for ek, kind, xy in ents.get(idx, ()):
                if ek not in road:
                    rep['entrance_no_connect'] += 1
                    continue
                pts, ln = road[ek]
                far = pts[-1] if math.dist(pts[0], xy) <= math.dist(pts[-1], xy) else pts[0]
                usable.append([*q(utmk_to_lonlat(*xy)), *q(utmk_to_lonlat(*far)), round(ln, 1), kind])
                kinds[kind] += 1
            if not usable:
                rep['building_no_usable_entrance'] += 1
                continue
            lo0, la0 = utmk_to_lonlat(bb[0], bb[1])
            lo1, la1 = utmk_to_lonlat(bb[2], bb[3])
            f.write(json.dumps({'k': f'{key[0]}-{key[1]}',
                                'bb': [*q((min(lo0, lo1), min(la0, la1))), *q((max(lo0, lo1), max(la0, la1)))],
                                'r': [[c for p in ring for c in q(utmk_to_lonlat(*p))] for ring in rings],
                                'e': usable}, ensure_ascii=False, separators=(',', ':')) + '\n')
            n_out += 1
            n_ent += len(usable)
    tmp.replace(out_dir / 'buildings.jsonl.gz')
    counts = {'buildings': n_out, 'entrances': n_ent, 'entrance_kinds': dict(kinds)}
    (out_dir / 'build_report.json').write_text(json.dumps(dict(rep, counts=counts, seconds=round(time.time() - t0)),
                                                          ensure_ascii=False, indent=1), encoding='utf-8')
    return counts, dict(rep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zips', default=str(ZIPS))
    ap.add_argument('--out', default=str(PROC / 'building_entrance_kr_v1'))
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        sys.exit(f'출력 폴더가 이미 있다 — 덮지 않는다: {out}')
    tmp_out = out.with_name(out.name + '.building')
    if tmp_out.exists():
        sys.exit(f'만들던 폴더가 남아 있다 — 확인 뒤 다시: {tmp_out}')
    regions = {}
    for zp in sorted(Path(a.zips).glob('*.zip')):
        t0 = time.time()
        L = Layers(zp)
        counts, rep = build_one(L, tmp_out / L.code)
        f = tmp_out / L.code / 'buildings.jsonl.gz'
        regions[L.code] = {'zip': zp.name, 'zip_bytes': zp.stat().st_size, 'source_date': L.day, 'counts': counts,
                           'buildings_in_source': rep.get('building', 0), 'bytes': f.stat().st_size, 'md5': md5(f),
                           'source_md5': {n: L.shp_md5(n) for n in LAYERS}}
        print(f"{L.code} 건물 {rep.get('building', 0):,} → {counts['buildings']:,} · 출입구 {counts['entrances']:,} · "
              f"{regions[L.code]['bytes']:,} B · {time.time() - t0:.0f}s", flush=True)
    manifest = {
        'version': 'building_entrance_kr_v1',
        'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
        'builder': 'datasets/mobility/scripts/build_building_entrance_kr_v1.py',
        'source': '행정안전부 도로명주소 건물 도형(시도별 전체분) — 건물 면 · 출입구 · 출입구→도로 연결선',
        'source_url': 'https://business.juso.go.kr/addrlink/elctrnMapProvd/geoDBDwldList.do',
        'license': '주소기반산업지원서비스 제공 자료(출처: 행정안전부)',
        'grade': '공공 원자료 + 기하 판정(크기 기준 · 가장 가까운 면 · 연결선 끝)',
        'rules': {'min_half_box_diag_m': MIN_HALF_DIAG_M, 'coord_unit': '1e-6 deg (lon, lat)',
                  'road_end_walk_check': 'not filtered here — the app checks road end <= OPTIMISTIC_ACCESS_M when choosing',
                  'entrance_fields': ['entrance_lon', 'entrance_lat', 'road_end_lon', 'road_end_lat', 'connect_m', 'ENTRC_SE'],
                  'layout': '<sido code>/buildings.jsonl.gz — same line format as building_entrance_seoul_v1'},
        'regions': regions,
        'total': {'buildings': sum(r['counts']['buildings'] for r in regions.values()),
                  'entrances': sum(r['counts']['entrances'] for r in regions.values()),
                  'bytes': sum(r['bytes'] for r in regions.values())},
    }
    (tmp_out / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp_out.replace(out)
    print(json.dumps(manifest['total'], ensure_ascii=False))


if __name__ == '__main__':
    main()
