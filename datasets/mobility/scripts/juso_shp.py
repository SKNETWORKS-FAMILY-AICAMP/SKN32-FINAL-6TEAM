# datasets/mobility/scripts/juso_shp.py — 도로명주소 누리집 전자지도(SHP) 읽기 도구 (2026-10-14)
#
# 외부 라이브러리 없이 shp/dbf 를 읽고, 좌표를 위경도로 바꾼다.
#   · 좌표계: 도로명주소 전자지도는 UTM-K(GRS80, 원점 38N·127.5E, 축척 0.9996, 가산 1,000,000 / 2,000,000 — EPSG:5179)를 쓴다.
#     zip 에 .prj 가 없어, 값 범위(서울 x 94만~100만 · y 191만~198만)와 역변환 결과가 서울 안에 떨어지는지로 확인했다(REPORT.md).
#   · dbf 문자열은 CP949. 빈칸이 NUL(\x00)로 채워진 칸은 빈 문자열로 돌려준다.
import math
import struct

_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_K0 = 0.9996
_LAT0, _LON0, _FE, _FN = math.radians(38.0), math.radians(127.5), 1000000.0, 2000000.0


def _m(phi):
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    return _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                 + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi) - (35 * e6 / 3072) * math.sin(6 * phi))


_M0 = _m(_LAT0)


def utmk_to_lonlat(x, y):
    """UTM-K(EPSG:5179) → (경도, 위도). Snyder 역변환식."""
    m = _M0 + (y - _FN) / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    s, c, t = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = _A / math.sqrt(1 - _E2 * s * s)
    r1 = _A * (1 - _E2) / (1 - _E2 * s * s) ** 1.5
    T1, C1 = t * t, _EP2 * c * c
    d = (x - _FE) / (n1 * _K0)
    lat = phi1 - (n1 * t / r1) * (d * d / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * _EP2) * d ** 4 / 24
                                  + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * _EP2 - 3 * C1 * C1) * d ** 6 / 720)
    lon = _LON0 + (d - (1 + 2 * T1 + C1) * d ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * _EP2 + 24 * T1 * T1) * d ** 5 / 120) / c
    return math.degrees(lon), math.degrees(lat)


def read_shp(path):
    """도형마다 점(1) → [(x,y)] · 선/면(3·5) → [[(x,y)…] 부분…] · 빈 도형 → None."""
    out = []
    with open(path, 'rb') as f:
        f.seek(100)
        while True:
            h = f.read(8)
            if len(h) < 8:
                return out
            _num, ln = struct.unpack('>ii', h)
            body = f.read(ln * 2)
            st = struct.unpack('<i', body[:4])[0]
            if st == 0:
                out.append(None)
            elif st == 1:
                out.append([struct.unpack('<2d', body[4:20])])
            elif st in (3, 5):
                nparts, npts = struct.unpack('<ii', body[36:44])
                parts = struct.unpack(f'<{nparts}i', body[44:44 + 4 * nparts])
                off = 44 + 4 * nparts
                xy = struct.unpack(f'<{2 * npts}d', body[off:off + 16 * npts])
                pts = [(xy[2 * i], xy[2 * i + 1]) for i in range(npts)]
                out.append([pts[parts[i]:(parts[i + 1] if i + 1 < nparts else npts)] for i in range(nparts)])
            else:
                raise ValueError(f'모르는 도형 종류 {st}: {path}')


def read_dbf(path):
    with open(path, 'rb') as f:
        h = f.read(32)
        n, hl, rl = struct.unpack('<IHH', h[4:12])
        fields, pos = [], 1
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            fields.append((d[:11].split(b'\0')[0].decode('ascii'), pos, pos + d[16]))
            pos += d[16]
        f.seek(hl)
        rows = []
        for _ in range(n):
            r = f.read(rl)
            if r[:1] == b'*':
                rows.append(None)
                continue
            rows.append({k: r[a:b].replace(b'\0', b' ').decode('cp949', 'replace').strip() for k, a, b in fields})
        return rows


def read_layer(folder, name):
    """(도형, 속성) 쌍 목록 — 지운 행은 뺀다."""
    shapes = read_shp(f'{folder}/{name}.shp')
    rows = read_dbf(f'{folder}/{name}.dbf')
    if len(shapes) != len(rows):
        raise ValueError(f'{name}: 도형 {len(shapes)}개 · 속성 {len(rows)}개가 다르다')
    return [(s, r) for s, r in zip(shapes, rows) if r is not None]
