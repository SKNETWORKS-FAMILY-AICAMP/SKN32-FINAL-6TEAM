# datasets/mobility/scripts/build_building_entrance_seoul_v1.py — 서울 건물 출입구 → 보행 길 진입점 (2026-10-19)
#
# 왜: 장소 좌표가 큰 건물(역사 · 대형마트 · 복합시설) 한가운데에 있으면 보행 길까지 30 m 넘게 떨어져,
#     플래너가 걷기 후보를 「보행 접근 미검증」으로 뺀다(graph_router.OPTIMISTIC_ACCESS_M). 사람은 건물 출입구로 나와 길에 오른다.
#     행정안전부 「도로명주소 건물 도형」은 건물 면 · 출입구 점 · 출입구에서 도로까지 연결선을 준다.
#     측정(서울 장소 32곳): 30 m 넘게 떨어진 10곳 중 7곳이 출입구 연결선 끝에서 30 m 안에 보행 길이 있었다
#     (records/reports/2026-10-19_building_entrance_access/REPORT.md).
# 규칙(자료 그대로 + 기하 판정 — 특정 장소 맞춤 없음):
#   1) 건물 = TL_SGCO_RNADR_MST 면. 키는 (SIG_CD, BUL_MAN_NO) — 건물 번호는 시군구 안에서만 유일하다.
#      그래도 같은 키가 서로 수 km 떨어진 면에 붙은 묶음이 있어(서울 25묶음), 출입구는 같은 키의 면 중 **가장 가까운 면**에 붙인다.
#   2) 걸러 담기: 건물 안 어느 점이든 보행 길까지 거리 ≤ (면 상자 가운데의 거리 + 상자 반대각선)이다(삼각 부등식).
#      이 상한이 OPTIMISTIC_ACCESS_M 이하인 건물은 출입구가 필요 없으므로 담지 않는다 — 크기를 줄인다(근사가 아니라 상한).
#   3) 출입구 진입점 = 출입구에서 도로까지 연결선(TL_SPOT_CNTC, 키 (SIG_CD, ENT_MAN_NO))의 출입구 반대쪽 끝.
#      그 끝이 보행 길에서 OPTIMISTIC_ACCESS_M 넘게 떨어지면 쓸모가 없어 뺀다. 출입구가 하나도 안 남은 건물은 뺀다.
#   · 연결선 길이는 도형 길이(UTM-K 미터). 출입구 구분(ENTRC_SE)은 그대로 적는다.
#   · 보행 길 = 서울 보행 그래프(walk_graph_seoul_v3)에 걸음으로 붙일 수 있는 간선 — 엔진 GraphRouter 의 붙임 규칙 그대로.
#     그래프 판이 바뀌면 다시 만든다(MANIFEST 에 입력 그래프 판과 md5).
# 입력: raw/juso_building_shape_seoul_20261001_v1/extract/ · processed/mobility/walk_graph_seoul_v3/
# 출력: processed/mobility/building_entrance_seoul_v1/{buildings.jsonl.gz, MANIFEST.json, build_report.json} (있으면 멈춘다 — 덮지 않는다)
import argparse, datetime as dt, gzip, hashlib, json, math, struct, sys, time
from collections import Counter, defaultdict
from pathlib import Path

from juso_shp import read_dbf, utmk_to_lonlat

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / 'datasets' / 'mobility' / 'raw' / 'juso_building_shape_seoul_20261001_v1' / 'extract'
PROC = ROOT / 'datasets' / 'mobility' / 'processed' / 'mobility'
Q = 1e6                                                   # 위경도 정수 저장 단위(1e-6 도 ≈ 0.1 m)


def shp_iter(path):
    """도형을 하나씩 — 점 → (x, y) · 선/면 → [[(x, y)…] 부분…] · 빈 도형 → None. 전체를 메모리에 올리지 않는다."""
    with open(path, 'rb') as f:
        f.seek(100)
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
                raise ValueError(f'모르는 도형 종류 {st}: {path}')


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def q(lonlat):
    return [int(round(lonlat[0] * Q)), int(round(lonlat[1] * Q))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cs', default=str(ROOT / 'final_project_cs'), help='엔진을 읽을 final_project_cs 폴더(붙임 규칙을 엔진과 같게)')
    ap.add_argument('--out', default=str(PROC / 'building_entrance_seoul_v1'))
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        sys.exit(f'출력 폴더가 이미 있다 — 덮지 않는다: {out}')
    sys.path.insert(0, a.cs)
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, OPTIMISTIC_ACCESS_M
    from app.domains.travel_ops.instances.mobility.engine.car import RouterDown

    t0 = time.time()
    wdir = PROC / 'walk_graph_seoul_v3'
    recs = {k: [json.loads(l) for l in gzip.open(wdir / f'{k}.jsonl.gz', 'rt', encoding='utf-8')] for k in ('nodes', 'edges')}
    wg = GraphRouter(records=recs)
    wg._load()
    del recs

    def snap_m(lon, lat):
        try:
            return wg._snap_many('foot', lon, lat)[0].dist
        except RouterDown:
            return math.inf

    rep = Counter()
    # 1) 건물 면 — 모든 면의 가운데(같은 키 묶음에서 가장 가까운 면을 고르려고) · 걸러 담은 면의 꼭짓점
    b_rows = read_dbf(str(RAW / 'TL_SGCO_RNADR_MST.dbf'))
    cent = defaultdict(list)                                 # 키 → [(가운데 x, y, 담은 번호 또는 None)]
    kept = []                                                # [키, 상자, 고리들(UTM-K)]
    for i, rings in enumerate(shp_iter(RAW / 'TL_SGCO_RNADR_MST.shp')):
        r = b_rows[i]
        if rings is None or r is None:
            rep['building_empty'] += 1
            continue
        rep['building'] += 1
        xs = [x for ring in rings for x, _y in ring]
        ys = [y for ring in rings for _x, y in ring]
        bb = (min(xs), min(ys), max(xs), max(ys))
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        key = (r['SIG_CD'], r['BUL_MAN_NO'])
        half = math.hypot(bb[2] - bb[0], bb[3] - bb[1]) / 2
        idx = None
        if snap_m(*utmk_to_lonlat(cx, cy)) + half > OPTIMISTIC_ACCESS_M:
            idx = len(kept)
            kept.append([key, bb, rings])
        cent[key].append((cx, cy, idx))
        if i % 100000 == 0:
            print(f'건물 {i:,} · 담음 {len(kept):,} · {time.time() - t0:.0f}s', flush=True)
    rep['building_kept_by_bound'] = len(kept)
    rep['key_groups_multi_far'] = sum(1 for v in cent.values()
                                      if len(v) > 1 and max(math.dist(p[:2], q2[:2]) for p in v for q2 in v) > 500)
    del b_rows

    # 2) 출입구 — 같은 키의 면 중 가장 가까운 면(담지 않은 면이 가장 가까우면 버린다)
    e_rows = read_dbf(str(RAW / 'TL_SPBD_ENTRC.dbf'))
    ents = defaultdict(list)                                 # 담은 번호 → [(출입구 키, 구분, (x, y))]
    for i, xy in enumerate(shp_iter(RAW / 'TL_SPBD_ENTRC.shp')):
        r = e_rows[i]
        if xy is None or r is None:
            continue
        cs = cent.get((r['SIG_CD'], r['BUL_MAN_NO']))
        if not cs:
            rep['entrance_no_building'] += 1
            continue
        near = min(cs, key=lambda c: math.dist(c[:2], xy))
        if near[2] is not None:
            ents[near[2]].append(((r['SIG_CD'], r['ENT_MAN_NO']), r['ENTRC_SE'], xy))
    del e_rows, cent
    want = {e[0] for v in ents.values() for e in v}

    # 3) 연결선 — 출입구 반대쪽 끝과 도형 길이
    c_rows = read_dbf(str(RAW / 'TL_SPOT_CNTC.dbf'))
    road = {}
    for i, parts in enumerate(shp_iter(RAW / 'TL_SPOT_CNTC.shp')):
        r = c_rows[i]
        if not parts or r is None:
            continue
        k = (r['SIG_CD'], r['ENT_MAN_NO'])
        if k in want:
            pts = [p for part in parts for p in part]
            road[k] = (pts, sum(math.dist(pts[j], pts[j + 1]) for j in range(len(pts) - 1)))
    del c_rows

    # 4) 진입점 붙임 · 쓰기
    out.mkdir(parents=True)
    n_out, n_ent, kinds = 0, 0, Counter()
    tmp = out / 'buildings.jsonl.gz.tmp'
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for idx, (key, bb, rings) in enumerate(kept):
            usable = []
            for ek, kind, xy in ents.get(idx, ()):
                if ek not in road:
                    rep['entrance_no_connect'] += 1
                    continue
                pts, ln = road[ek]
                far = pts[-1] if math.dist(pts[0], xy) <= math.dist(pts[-1], xy) else pts[0]
                flon, flat = utmk_to_lonlat(*far)
                d = snap_m(flon, flat)
                if d > OPTIMISTIC_ACCESS_M:
                    rep['entrance_road_end_far'] += 1
                    continue
                usable.append([*q(utmk_to_lonlat(*xy)), int(round(flon * Q)), int(round(flat * Q)), round(ln, 1), kind])
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
    tmp.replace(out / 'buildings.jsonl.gz')

    wm = json.loads((wdir / 'MANIFEST.json').read_text(encoding='utf-8'))
    manifest = {
        'version': 'building_entrance_seoul_v1',
        'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
        'builder': 'datasets/mobility/scripts/build_building_entrance_seoul_v1.py',
        'source': '행정안전부 도로명주소 건물 도형(2026-10-01 기준 · 서울) — 건물 면 · 출입구 · 출입구→도로 연결선',
        'source_url': 'https://business.juso.go.kr/addrlink/elctrnMapProvd/geoDBDwldList.do',
        'license': '주소기반산업지원서비스 제공 자료(출처: 행정안전부)',
        'grade': '공공 원자료 + 기하 판정(가장 가까운 면 · 연결선 끝 붙임)',
        'rules': {'optimistic_access_m': OPTIMISTIC_ACCESS_M, 'coord_unit': '1e-6 deg (lon, lat)',
                  'filter': 'snap(box centre) + half box diagonal > optimistic_access_m',
                  'entrance_fields': ['entrance_lon', 'entrance_lat', 'road_end_lon', 'road_end_lat', 'connect_m', 'ENTRC_SE']},
        'inputs': {'walk_graph': {'version': wm.get('version'), 'built_at': wm.get('built_at'),
                                  'edges_md5': md5(wdir / 'edges.jsonl.gz'), 'nodes_md5': md5(wdir / 'nodes.jsonl.gz')},
                   'juso_building_shape': {n: md5(RAW / f'{n}.shp') for n in ('TL_SGCO_RNADR_MST', 'TL_SPBD_ENTRC', 'TL_SPOT_CNTC')}},
        'counts': {'buildings': n_out, 'entrances': n_ent, 'entrance_kinds': dict(kinds)},
        'output_md5': md5(out / 'buildings.jsonl.gz'),
    }
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'build_report.json').write_text(json.dumps(dict(rep, seconds=round(time.time() - t0)), ensure_ascii=False, indent=1),
                                           encoding='utf-8')
    print(json.dumps(manifest['counts'], ensure_ascii=False), dict(rep))


if __name__ == '__main__':
    main()
