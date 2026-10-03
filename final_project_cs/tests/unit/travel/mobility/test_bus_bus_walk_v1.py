# -*- coding: utf-8 -*-
"""버스↔버스 환승 도보(규칙 v0.9.2 transfer.bus_bus_walk · 78 「73 후속」) — 정류장 행 좌표·ID 경계.

GPT 대조(78 Q1): 같은 station_id 는 좌표보다 먼저 보는 독립 근거다(한쪽 좌표가 비어도 0 m 확정) · 좌표는 lat·lng 둘 다
유한한 수여야 한다(lng=None · NaN 은 근거없음). 실데이터 판정기에 정류장 행만 바꿔 끼운다.
"""
from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.mobility_full        # 실데이터 판정기를 올린다 — 팀원 게이트가 아니라 우리 전체층(conftest)

_RT = None


def _v():
    global _RT
    if _RT is None:
        from app.modules.travel_ops.mobility.engine.runtime import build_verifier
        try:
            _RT = build_verifier(quiet=True)
        except RuntimeError as e:
            _RT = e
    if isinstance(_RT, Exception):
        pytest.skip("시간표 없음(DATA_DIR) — 데이터 축 SKIP")
    return _RT._v


def _row(sid, lat, lng, nm="정류장"):
    return {"station_id": sid, "station_nm": nm, "lat": lat, "lng": lng, "direction": "x", "seq": 1,
            "fetched_at": "2026-09-10"}


def _walk(monkeypatch, a, b):
    import copy
    v = copy.copy(_v())
    rows = {"to": a, "from": b}
    monkeypatch.setattr(v, "_bus_stop_row", lambda leg, which: rows[which])
    return v._bus_bus_walk({"mode": "bus", "route": "A", "to": "x"}, {"mode": "bus", "route": "B", "from": "y"}, {})


def test_same_id_before_coords(monkeypatch):
    r = _walk(monkeypatch, _row("1", None, None), _row("1", 37.5, 127.0))
    assert r["verdict"] == "feasible" and r["walk_min"] == 0 and r["grade"] == "확정", r


@pytest.mark.parametrize("bad", [(37.5, None), (None, 127.0), (float("nan"), 127.0), (37.5, "x")])
def test_missing_or_bad_coords_unknown(monkeypatch, bad):
    r = _walk(monkeypatch, _row("1", *bad), _row("2", 37.5, 127.0))
    assert r["verdict"] == "unknown" and r["walk_min"] is None
    assert [w["code"] for w in r["warnings"]] == ["MOB_W_TRANSFER_COORD_MISSING"]


def test_distance_and_limit(monkeypatch):
    near = _walk(monkeypatch, _row("1", 37.5, 127.0), _row("2", 37.5009, 127.0))     # ≈100 m
    assert near["verdict"] == "feasible" and near["grade"] == "추정"
    assert math.isclose(near["walk_min"], math.ceil(near["dist_m"] * 1.4 / 1.04 / 60 * 10) / 10, abs_tol=0.11)
    far = _walk(monkeypatch, _row("1", 37.5, 127.0), _row("2", 37.515, 127.0))       # ≈1.67 km
    assert far["verdict"] == "infeasible"
    edge = _walk(monkeypatch, _row("1", 37.5, 127.0), _row("2", 37.5 + 1200 / 111_320, 127.0))
    assert edge["verdict"] == "unknown", "상한 ±20 m 는 근거없음"
