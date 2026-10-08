"""인허가 좌표(EPSG:5174) → WGS84 위도 · 경도. 외부 패키지 없이 계산한다. `[2026-10-07]`

서울시 인허가 원장의 「좌표정보(X) · (Y)」는 EPSG:5174 다 — 베셀 1841 타원체, 횡메르카토르,
원점 위도 38°, 원점 경도 127°00'10.405"(= 127.0028902777…°), 축척 1, 가산 동 200000 · 북 500000.
WGS84 로는 7 매개변수 변환(PROJ 의 towgs84, Position Vector 규약)으로 옮긴다.

★EPSG:2097 로 바꾸면 256m 씩 어긋난다 — 원점 경도 10.405초 차이다(make_vegan_sql 머리말과 같은 이야기).
★검증: 원장에 이미 인허가 좌표로 들어간 가게와 맞춰 본다(tests/unit/travel/test_dining_make_nopo_sql.py).
"""
from __future__ import annotations

import math

# 베셀 1841
_A = 6377397.155
_F = 1 / 299.1528128
_E2 = 2 * _F - _F * _F
_EP2 = _E2 / (1 - _E2)
# EPSG:5174 투영
_LAT0 = math.radians(38.0)
_LON0 = math.radians(127 + 0 / 60 + 10.405 / 3600)
_K0 = 1.0
_FE, _FN = 200000.0, 500000.0
# towgs84 (m, 초, ppm) — PROJ 의 EPSG:5174 정의와 같다
_TX, _TY, _TZ = -115.80, 474.99, 674.11
_RX, _RY, _RZ = (math.radians(s / 3600) for s in (1.16, -2.31, -1.63))
_S = 6.43e-6
# WGS84
_WA = 6378137.0
_WF = 1 / 298.257223563
_WE2 = 2 * _WF - _WF * _WF


def _meridian(phi: float) -> float:
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    return _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
                 - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                 + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
                 - (35 * e6 / 3072) * math.sin(6 * phi))


def _inverse_tm(x: float, y: float) -> tuple[float, float]:
    """투영 좌표 → 베셀 위도 · 경도(라디안). Snyder 식."""
    m = _meridian(_LAT0) + (y - _FN) / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    sin1, cos1, tan1 = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    c1, t1 = _EP2 * cos1 ** 2, tan1 ** 2
    n1 = _A / math.sqrt(1 - _E2 * sin1 ** 2)
    r1 = _A * (1 - _E2) / (1 - _E2 * sin1 ** 2) ** 1.5
    d = (x - _FE) / (n1 * _K0)
    lat = phi1 - (n1 * tan1 / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * _EP2) * d ** 4 / 24
                                     + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * _EP2 - 3 * c1 ** 2)
                                     * d ** 6 / 720)
    lon = _LON0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                   + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * _EP2 + 24 * t1 ** 2) * d ** 5 / 120) / cos1
    return lat, lon


def to_wgs84(x: float, y: float) -> tuple[float, float]:
    """EPSG:5174 (x 동, y 북) → (위도, 경도) 도 단위, WGS84."""
    lat, lon = _inverse_tm(x, y)
    # 베셀 → 지심 직교
    n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    bx = n * math.cos(lat) * math.cos(lon)
    by = n * math.cos(lat) * math.sin(lon)
    bz = n * (1 - _E2) * math.sin(lat)
    # 7 매개변수(Position Vector)
    k = 1 + _S
    wx = _TX + k * (bx - _RZ * by + _RY * bz)
    wy = _TY + k * (_RZ * bx + by - _RX * bz)
    wz = _TZ + k * (-_RY * bx + _RX * by + bz)
    # 지심 직교 → WGS84 위도 · 경도(반복)
    p = math.hypot(wx, wy)
    lon_w = math.atan2(wy, wx)
    lat_w = math.atan2(wz, p * (1 - _WE2))
    for _ in range(6):
        nw = _WA / math.sqrt(1 - _WE2 * math.sin(lat_w) ** 2)
        h = p / math.cos(lat_w) - nw
        lat_w = math.atan2(wz, p * (1 - _WE2 * nw / (nw + h)))
    return math.degrees(lat_w), math.degrees(lon_w)
