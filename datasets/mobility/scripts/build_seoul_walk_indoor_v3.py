# datasets/mobility/scripts/build_seoul_walk_indoor_v3.py — 서울 보행 그래프 v3: v2 + 지하철역·지하상가 안 통로(도로명주소 내부도로 전자지도) (2026-10-14)
#
# 왜: 역 접근 걷기에서 길 거리가 직선의 2배를 넘어 상한으로 자르는 경우(지하 통로·역 복합시설이 지도에 없어 큰길을 돌아감)와
#     역과 지하로 이어진 건물을 직선 × 계수로 보는 대체 계산이 남아 있다. 행정안전부 도로명주소 「내부도로 전자지도」(2025-12판)는
#     역·지하상가 층마다 통로 중심선, 계단·에스컬레이터·엘리베이터 위치와 위아래 짝, 외부 출입구, 개표구 면을 준다.
# 규칙(자료 그대로 + 기하 판정 — 특정 장소 맞춤 없음):
#   1) 통로: 내부도로 도로구간(TL_SPRD_MANAGE) 중심선. 개표구(TL_CBADDR_TCKBR)에서 끊는다 — 개표구 밖 사람이 지나갈 수 없다.
#      개표구 면에 걸친 조각 + 개표구 면이 중심선 옆(GATE_NEAR_M 안)에 있으면 중심선에서 가장 가까운 조각(대합실 가운데 선이 개표구 줄 옆을 지나는 경우).
#   2) 같은 층 이음: 통로 끝점에서 같은 위상수준(PHL_VL) 다른 통로까지 JOIN_M 안이고, 그 사이 직선이 실폭도로 면(TL_SPRD_RW, 같은 수준) 안이면 잇는다.
#      (같은 수준의 이웃 구조물 — 예: 역 대합실과 지하상가 — 도 같은 규칙으로 이어진다.)
#   3) 오르내림: 수직연결점(TL_CBADDR_VCP)을 연결선(TL_CBADDR_VCP_CNLN)으로 통로에 붙이고, 위층·아래층 짝(UVC/DVC)을 잇는다.
#      종류(VMP_CD 0 계단 · 1 에스컬레이터 · 2 엘리베이터 · 3 단차 · 4 장애인리프트 · 5 기타)를 간선에 적고, 계단은 계단 표시(st=1).
#   4) 외부 출입구(EXTRL_YN=Y): 그 수직이동통로 면(TL_CBADDR_VMP)에서 연결점과 가장 먼 꼭짓점을 지상 출구로 보고(OSM 출구 좌표와 가운데값 8 m),
#      거기서 v2 지상 보행 노드 중 가장 가까운 것(SURFACE_SNAP_M 안)에 잇는다.
#   5) 요금 구역 제외: 승강장 통로(도로명에 「승강장」)와 거기 붙은 수직연결점·오르내림은 버린다. 그 뒤 지상 출구에 닿지 않는 덩어리도 버린다.
#      개표구로 끊어도 승강장 계단 쪽과 출구 쪽이 한 덩어리로 남은 구조물(요금 구역 경계를 자료로 못 가림)은 통째로 넣지 않고 센다
#      (paid_unknown_structures) — 개표구 안을 지나는 「갈 수 없는 지름길」을 만들지 않는다.
#   · 높이: 층의 가시화 기준 높이(VSLN_HG, 지하1층 −3 m 등 — 측량값 아님). 계단·에스컬레이터 길이 = max(수평·수직 빗변, 수직 × 2)(경사 30° 가정),
#     엘리베이터 = 수평 + 수직. 모두 추정이며 간선에 근거를 적는다.
#   · 새 간선은 걸음 통행(foot=1)이지만 붙임 대상(fmain)은 0 — 지상 장소가 그 아래 지하 통로에 바로 붙지 않게 한다(지상에서 출구로 들어간다).
# 입력: processed/mobility/walk_graph_seoul_v2/ · raw/juso_internal_road_202512_v1/extract/
# 출력: processed/mobility/walk_graph_seoul_v3/{nodes,edges}.jsonl.gz · seoul_boundary.geojson · MANIFEST.json · build_report.json (기존 폴더를 덮지 않는다)
import argparse, gzip, hashlib, io, json, math, shutil, time, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

from juso_shp import read_layer, utmk_to_lonlat

ROOT = Path(__file__).resolve().parents[3]
JOIN_M = 12.0
RW_TOL_M = 1.0
GATE_STEP_M = 1.0
SURFACE_SNAP_M = 30.0
CNLN_SNAP_M = 0.5
GATE_NEAR_M = 8.0
SRC = 'juso_internal_road_202512'


def enc_polyline6(lonlat):
    out, plat, plng = [], 0, 0
    for lon, lat in lonlat:
        la, ln = round(lat * 1e6), round(lon * 1e6)
        for v in (la - plat, ln - plng):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plng = la, ln
    return ''.join(out)


def seg_closest(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    q = (a[0] + t * dx, a[1] + t * dy)
    return math.dist(p, q), t, q


def in_poly(p, poly):
    ins = False
    for ring in poly:
        j = len(ring) - 1
        for i in range(len(ring)):
            (xi, yi), (xj, yj) = ring[i], ring[j]
            if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / ((yj - yi) or 1e-12) + xi:
                ins = not ins
            j = i
    return ins


def ring_dist(p, poly):
    return min(seg_closest(p, a, b)[0] for ring in poly for a, b in zip(ring, ring[1:]))


def near_poly(p, polys, tol):
    return any(in_poly(p, P) or ring_dist(p, P) <= tol for P in polys)


def simplify(pts, tol=0.05):
    """직선 위 중간점(촘촘히 나눈 점)을 걷어낸다 — Douglas-Peucker."""
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    d, i = max((seg_closest(p, a, b)[0], k) for k, p in enumerate(pts[1:-1], 1))
    if d <= tol:
        return [a, b]
    return simplify(pts[:i + 1], tol)[:-1] + simplify(pts[i:], tol)


def densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, math.ceil(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]
    return out


def main():
    ap = argparse.ArgumentParser()
    mob = ROOT / 'datasets/mobility'
    ap.add_argument('--base', default=str(mob / 'processed/mobility/walk_graph_seoul_v2'))
    ap.add_argument('--src', default=str(mob / 'raw/juso_internal_road_202512_v1/extract'))
    ap.add_argument('--out', default=str(mob / 'processed/mobility/walk_graph_seoul_v3'))
    a = ap.parse_args()
    t0 = time.monotonic()
    out, base, src = Path(a.out), Path(a.base), a.src
    if (out / 'edges.jsonl.gz').exists():
        raise SystemExit(f'이미 있다 — 덮지 않는다: {out}')
    stat = Counter()

    # ── v2 지상 그래프 ──
    nodes = [json.loads(l) for l in gzip.open(base / 'nodes.jsonl.gz', 'rt', encoding='utf-8')]
    edges = [json.loads(l) for l in gzip.open(base / 'edges.jsonl.gz', 'rt', encoding='utf-8')]
    nll = {n['id']: (n['lon'], n['lat']) for n in nodes}
    surf = set()
    for e in edges:                                       # 지상 붙임 후보: 걸음 최대 연결 성분의 바깥 길(건물 안 · 지하철 연결 · 터널 제외)
        if e.get('fmain') and not e.get('ind') and not e.get('wn_sbwy_ntw') and not e.get('tun'):
            surf.add(e['u'])
            surf.add(e['v'])
    CELL = 0.0005
    sgrid = defaultdict(list)
    for nid in surf:
        lon, lat = nll[nid]
        sgrid[(int(lat // CELL), int(lon // CELL))].append(nid)
    next_id = max(nll) + 1
    next_way = max(e['way'] for e in edges) + 1_000_000

    # ── 내부도로 자료(서울) ──
    def layer(name):
        return [(s, r) for s, r in read_layer(src, name) if s and r['SIG_CD'].startswith('11')]
    ssc = {r['SSC_MGNO']: r for s, r in layer('TL_CBADDR_SSC')}
    lvl = {k: int(r['PHL_VL']) for k, r in ssc.items()}
    hgt = {k: abs(float(r['VSLN_HG'] or 0)) or abs(int(r['PHL_VL'])) * 3.0 for k, r in ssc.items()}
    gates = defaultdict(list)
    for s, r in layer('TL_CBADDR_TCKBR'):
        gates[r['SSC_MGNO']].append(s)
    rw = defaultdict(list)                                # 위상수준 → 실폭 면들
    for s, r in layer('TL_SPRD_RW'):
        if r['SSC_MGNO'] in lvl:
            rw[lvl[r['SSC_MGNO']]].append(s)
    vmp = {r['VMP_MGNO']: s for s, r in layer('TL_CBADDR_VMP')}

    # 노드: (구조물, 좌표 0.01 m) 열쇠 · 간선 목록(내부 좌표 UTM-K)
    nkey, npt, nssc = {}, {}, {}
    new_edges = []                                        # dict(u, v, pts(UTM-K), kind, ...)

    def node(sid, p):
        k = (sid, round(p[0], 2), round(p[1], 2))
        if k not in nkey:
            nonlocal next_id
            nkey[k] = next_id
            npt[next_id] = p
            nssc[next_id] = sid
            next_id += 1
        return nkey[k]

    # 1) 통로 — 개표구 안 조각 끊기
    chains = []                                           # (sid, [점…], 도로명, 승강장 여부)
    roads = defaultdict(list)
    for s, r in layer('TL_SPRD_MANAGE'):
        if r['SSC_MGNO'] not in lvl:
            stat['road_no_structure'] += 1
            continue
        for part in s:
            roads[r['SSC_MGNO']].append((densify(part, GATE_STEP_M) if gates.get(r['SSC_MGNO']) else part, r['RN']))
    for sid, rs in roads.items():
        cut = set()                                       # (도로 순번, 조각 순번)
        for G in gates.get(sid, ()):
            gc = (sum(x for x, _ in G[0]) / len(G[0]), sum(y for _, y in G[0]) / len(G[0]))
            best = (math.inf, None)
            for ri, (pts, rn) in enumerate(rs):
                for k, (p, q) in enumerate(zip(pts, pts[1:])):
                    mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                    if near_poly(mid, [G], 0.5):
                        cut.add((ri, k))
                        stat['gate_cut_pieces'] += 1
                    d = seg_closest(gc, p, q)[0]
                    if d < best[0]:
                        best = (d, (ri, k))
            if best[1] is not None and best[0] <= GATE_NEAR_M and best[1] not in cut:
                cut.add(best[1])
                stat['gate_cut_near'] += 1
        for ri, (pts, rn) in enumerate(rs):
            cur = [pts[0]]
            for k, (p, q) in enumerate(zip(pts, pts[1:])):
                if (ri, k) in cut:
                    if len(cur) > 1:
                        chains.append((sid, simplify(cur), rn, '승강장' in rn))
                    cur = [q]
                else:
                    cur.append(q)
            if len(cur) > 1:
                chains.append((sid, simplify(cur), rn, '승강장' in rn))
    stat['chains'] = len(chains)
    # 통로 조각을 간선으로 — 사슬 꼭짓점마다 노드(나중에 이음점에서 쪼갠다)
    segs = []                                             # (sid, a, b, chain index)
    for ci, (sid, pts, rn, plat) in enumerate(chains):
        for p, q in zip(pts, pts[1:]):
            if p != q:
                segs.append([sid, p, q, ci])
    splits = defaultdict(list)                            # seg index → [(t, 점)]

    def nearest_seg(p, level, exclude_chain=None, sid_only=None):
        best = (math.inf, None, None, None)
        for i, (sid, x, y, ci) in enumerate(segs):
            if ci == exclude_chain or lvl[sid] != level or (sid_only and sid != sid_only):
                continue
            d, t, q = seg_closest(p, x, y)
            if d < best[0]:
                best = (d, i, t, q)
        return best

    # 2) 같은 층 이음
    joins = []
    for ci, (sid, pts, rn, plat) in enumerate(chains):
        for end in (pts[0], pts[-1]):
            d, i, t, q = nearest_seg(end, lvl[sid], exclude_chain=ci)
            if i is None or d > JOIN_M:
                continue
            if d > 0.05:
                line = densify([end, q], 1.0)
                if not all(near_poly(p, rw[lvl[sid]], RW_TOL_M) for p in line):
                    stat['join_rejected_outside_rw'] += 1
                    continue
                if any(near_poly(p, gates.get(sid, []) + gates.get(segs[i][0], []), 0.5) for p in line):
                    stat['join_rejected_gate'] += 1
                    continue
            splits[i].append((t, q))
            joins.append((sid, end, segs[i][0], q))
            stat['joins'] += 1
    # 3) 연결선으로 수직연결점 붙이기
    vcp_rows = {r['VCP_MGNO']: (s[0], r) for s, r in layer('TL_CBADDR_VCP')}
    cnln = []
    for s, r in layer('TL_CBADDR_VCP_CNLN'):
        v = vcp_rows.get(r['VCP_MGNO'])
        if not v or r['SSC_MGNO'] not in lvl:
            continue
        line = s[0]
        far = line[-1] if math.dist(line[0], v[0]) <= math.dist(line[-1], v[0]) else line[0]
        d, i, t, q = nearest_seg(far, lvl[r['SSC_MGNO']], sid_only=r['SSC_MGNO'])
        if i is None or d > CNLN_SNAP_M:
            stat['cnln_unattached'] += 1
            continue
        splits[i].append((t, q))
        cnln.append((r['SSC_MGNO'], v[0], line if line[-1] == far else line[::-1], q, r['VCP_MGNO']))
    # 통로 간선 만들기(이음점에서 쪼갬)
    for i, (sid, p, q, ci) in enumerate(segs):
        cuts = sorted({round(t, 6): pt for t, pt in splits.get(i, [])}.items())
        pts = [p] + [pt for t, pt in cuts if 0 < t < 1] + [q]
        for x, y in zip(pts, pts[1:]):
            if x != y:
                new_edges.append({'u': node(sid, x), 'v': node(sid, y), 'pts': [x, y], 'kind': 'corridor',
                                  'plat': chains[ci][3], 'name': chains[ci][2]})
    for sid, end, sid2, q in joins:
        if math.dist(end, q) > 0.05:
            new_edges.append({'u': node(sid, end), 'v': node(sid2, q), 'pts': [end, q], 'kind': 'join'})
        else:
            new_edges.append({'u': node(sid, end), 'v': node(sid2, q), 'pts': [end, q], 'kind': 'join'})
    vnode = {}
    for sid, vp, line, q, vid in cnln:
        vnode[vid] = node(sid, vp)
        new_edges.append({'u': vnode[vid], 'v': node(sid, q), 'pts': line[:-1] + [q], 'kind': 'cnln'})
    # 4) 오르내림 짝
    seen = set()
    for vid, (p, r) in vcp_rows.items():
        for other in (r['UVC_MGNO'], r['DVC_MGNO']):
            if not other or other not in vcp_rows or vid not in vnode or other not in vnode:
                if other:
                    stat['vertical_unattached'] += 1
                continue
            pair = tuple(sorted((vid, other)))
            if pair in seen:
                continue
            seen.add(pair)
            q, r2 = vcp_rows[other]
            h = abs(hgt[r['SSC_MGNO']] * (1 if lvl[r['SSC_MGNO']] < 0 else -1) - hgt[r2['SSC_MGNO']] * (1 if lvl[r2['SSC_MGNO']] < 0 else -1))
            new_edges.append({'u': vnode[vid], 'v': vnode[other], 'pts': [p, q], 'kind': 'vertical', 'vmp': r['VMP_CD'], 'h': h})
    # 5) 외부 출입구 → 지상
    surface_links = []
    for vid, (p, r) in vcp_rows.items():
        if r['EXTRL_YN'] != 'Y' or vid not in vnode:
            continue
        poly = vmp.get(r['VMP_MGNO'])
        top = max((q for part in poly for q in part), key=lambda q: math.dist(q, p)) if poly else p
        lon, lat = utmk_to_lonlat(*top)
        best = (math.inf, None)
        ci, cj = int(lat // CELL), int(lon // CELL)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for nid in sgrid.get((ci + di, cj + dj), ()):
                    nlon, nlat = nll[nid]
                    d = math.hypot((nlon - lon) * 88_200, (nlat - lat) * 111_000)
                    if d < best[0]:
                        best = (d, nid)
        if best[1] is None or best[0] > SURFACE_SNAP_M:
            stat['exit_unsnapped'] += 1
            continue
        stat['exit_snapped'] += 1
        h = hgt[r['SSC_MGNO']]
        new_edges.append({'u': vnode[vid], 'v': ('top', vid), 'pts': [p, top], 'kind': 'vertical', 'vmp': r['VMP_CD'], 'h': h, 'exit': True})
        surface_links.append((vid, top, best[1], best[0]))
    stat['exit_snap_m_max'] = round(max((x[3] for x in surface_links), default=0), 1)
    tops = {}
    for vid, top, sn, d in surface_links:
        tops[('top', vid)] = node('surface', top)
    for e in new_edges:
        if isinstance(e['v'], tuple):
            e['v'] = tops[e['v']]
    for vid, top, sn, d in surface_links:
        new_edges.append({'u': tops[('top', vid)], 'v': sn, 'pts': [top, None], 'kind': 'surface_link', 'snap_m': d})

    # 6) 요금 구역 · 고립 덩어리 버리기
    par = {}

    def f(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for e in new_edges:
        if e['kind'] != 'surface_link':
            par[f(e['u'])] = f(e['v'])
    exit_roots = {f(e['u']) for e in new_edges if e['kind'] == 'surface_link'}
    mixed = {f(e['u']) for e in new_edges if e.get('plat')} & exit_roots      # 개표구로 못 가른 덩어리
    stat['paid_unknown_structures'] = len({nssc[e['u']] for e in new_edges
                                           if f(e['u']) in mixed and nssc.get(e['u']) not in (None, 'surface')})
    plat_nodes = {n for e in new_edges if e.get('plat') for n in (e['u'], e['v'])}
    plat_vcp = {n for e in new_edges if e['kind'] == 'cnln' and (e['u'] in plat_nodes or e['v'] in plat_nodes)
                for n in (e['u'], e['v'])}
    rest = []
    for e in new_edges:
        if e.get('plat') or (e['kind'] == 'cnln' and (e['u'] in plat_nodes or e['v'] in plat_nodes)) \
                or (e['kind'] == 'vertical' and (e['u'] in plat_vcp or e['v'] in plat_vcp)):
            stat['dropped_platform_edges'] += 1
            continue
        if f(e['u']) in mixed:                            # 요금 구역 경계를 못 가린 덩어리 — 개표구 안을 지나는 「갈 수 없는 지름길」이 될 수 있어 넣지 않는다
            stat['dropped_paid_unknown_edges'] += 1
            continue
        rest.append(e)
    par.clear()
    for e in rest:
        if e['kind'] != 'surface_link':
            par[f(e['u'])] = f(e['v'])
    good = {f(e['u']) for e in rest if e['kind'] == 'surface_link'}
    kept = []
    for e in rest:
        if f(e['u']) not in good:
            stat['dropped_isolated_edges'] += 1
        else:
            kept.append(e)

    # ── 출력 ──
    used = {e['u'] for e in kept} | {e['v'] for e in kept}
    out_nodes = list(nodes)
    for nid in sorted(used):
        if nid in npt:
            lon, lat = utmk_to_lonlat(*npt[nid])
            out_nodes.append({'id': nid, 'lat': round(lat, 7), 'lon': round(lon, 7), 'r': 1, 'lvl': lvl.get(nssc[nid], 0)})
    out_edges = list(edges)
    kinds = Counter()
    for e in kept:
        if e['kind'] == 'surface_link':
            lonlat = [utmk_to_lonlat(*e['pts'][0]), nll[e['v']]]
            L = e['snap_m']
        else:
            lonlat = [utmk_to_lonlat(*p) for p in e['pts']]
            horiz = sum(math.dist(p, q) for p, q in zip(e['pts'], e['pts'][1:]))
            if e['kind'] == 'vertical':
                h = e['h']
                L = horiz + h if e['vmp'] == '2' else max(math.hypot(horiz, h), 2 * h)
            else:
                L = horiz
        kinds[e['kind']] += 1
        sid = nssc.get(e['u'])
        out_edges.append({
            'u': e['u'], 'v': e['v'], 'way': next_way, 'sa': 0, 'sb': len(lonlat) - 1, 'len': round(max(L, 0.1), 1),
            'ow': 0, 'hw': 'footway', 'ms': None, 'car': 0, 'bike': 0, 'bow': 0, 'foot': 1,
            'st': 1 if e.get('vmp') == '0' else 0, 'g': enc_polyline6(lonlat),
            'lyr': lvl.get(sid, 0), 'tun': 0, 'ind': 1, 'main': 0, 'bmain': 0, 'fmain': 0,
            'src': SRC, 'kind': e['kind'], 'vmp': e.get('vmp'), 'h_m': e.get('h'), 'ssc': sid if sid != 'surface' else None,
            'name': e.get('name')})
        next_way += 1
    stat.update({f'edges_{k}': v for k, v in kinds.items()})
    stat['new_nodes'] = len(out_nodes) - len(nodes)
    stat['new_edges'] = len(out_edges) - len(edges)
    stat['structures_kept'] = len({nssc[e['u']] for e in kept if nssc.get(e['u']) not in (None, 'surface')})

    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, rows in (('nodes.jsonl.gz', out_nodes), ('edges.jsonl.gz', out_edges)):
        buf = io.BytesIO()
        with gzip.GzipFile(filename='', fileobj=buf, mode='wb', mtime=0) as gz:
            for r in rows:
                gz.write((json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8'))
        (out / name).write_bytes(buf.getvalue())
        files[name] = {'bytes': len(buf.getvalue()), 'md5': hashlib.md5(buf.getvalue()).hexdigest(), 'rows': len(rows)}
    shutil.copyfile(base / 'seoul_boundary.geojson', out / 'seoul_boundary.geojson')
    rule = {'join_m': JOIN_M, 'rw_tol_m': RW_TOL_M, 'surface_snap_m': SURFACE_SNAP_M, 'cnln_snap_m': CNLN_SNAP_M,
            'height': 'VSLN_HG(가시화 기준 높이 — 측량값 아님)', 'stairs_len': 'max(hypot(수평,수직), 2×수직)', 'elevator_len': '수평+수직'}
    rep = {'version': 'walk_graph_seoul_v3', 'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
           'rule': rule, 'counts': dict(stat), 'elapsed_s': round(time.monotonic() - t0, 1)}
    (out / 'build_report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    v2man = json.loads((base / 'MANIFEST.json').read_text(encoding='utf-8'))
    man = {'version': 'walk_graph_seoul_v3',
           'work_dates': v2man.get('work_dates'), 'osm_data_at': v2man.get('osm_data_at'), 'juso_internal_at': '2025-12',
           'source': '서울특별시 자치구별 도보 네트워크(walk_graph_seoul_v2) + 행정안전부 도로명주소 내부도로 전자지도(2025-12판, 서울)',
           'source_url': 'https://business.juso.go.kr/jst/jstAddressDetailsSearch',
           'license': 'v2 와 같음(공공누리 1유형 · OSM ODbL) + 도로명주소 전자지도(주소기반산업지원서비스 제공 — 출처: 행정안전부)',
           'grade': '공공 원자료 + 기하 판정(이음 · 출구 붙임) + 높이 추정(가시화 값)',
           'built_at': rep['built_at'], 'builder': 'datasets/mobility/scripts/build_seoul_walk_indoor_v3.py',
           'inputs': {'walk_graph_seoul_v2': v2man.get('files'),
                      'juso_internal_road_202512_v1': {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(Path(src).glob('*.shp'))}},
           'rule': rule, 'files': files}
    (out / 'MANIFEST.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(stat), ensure_ascii=False))


if __name__ == '__main__':
    main()
