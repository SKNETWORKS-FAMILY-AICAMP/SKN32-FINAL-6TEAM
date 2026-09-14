# -*- coding: utf-8 -*-
"""고정 IP 서버 경유 — **이름이 맞는 소스만** 프록시로 나가는가.

★왜(2026-09-14 사용자 지시). UTIC 는 등록한 IP 에서만 호출된다. 개발 장소가 바뀌어도
  되게 고정 IP 서버(SSH SOCKS 터널)를 거쳐 부른다. 전부 경유시키면 터널이 끊길 때 모든
  소스가 한꺼번에 실패해 치명이 되므로 기본은 IP 에 묶인 것만이다.
"""
from __future__ import annotations

import importlib.util

import httpx

from app.infrastructure.travel import base as base_module
from app.infrastructure.travel.air_quality import FallbackAir
from app.infrastructure.travel.base import TravelSource, TravelSources, apply_outbound_proxy


class _Src(TravelSource):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name


def _sources():
    utic, its, a, b = _Src("utic"), _Src("its"), _Src("airkorea"), _Src("open_meteo_air")
    return TravelSources(traffic=its, route_events=utic, air=FallbackAir([a, b])), (utic, its, a, b)


def test_only_named_sources_get_the_proxy():
    sources, (utic, its, a, b) = _sources()
    assert apply_outbound_proxy(sources, url="http://127.0.0.1:8888", names="utic") is None
    assert utic._proxy == "http://127.0.0.1:8888"
    assert its._proxy is a._proxy is b._proxy is None


def test_sources_inside_a_chain_are_matched_by_their_own_name():
    sources, (_, _, a, b) = _sources()
    apply_outbound_proxy(sources, url="http://127.0.0.1:8888", names="airkorea")
    assert a._proxy == "http://127.0.0.1:8888" and b._proxy is None


def test_a_star_routes_every_source():
    sources, all_four = _sources()
    apply_outbound_proxy(sources, url="http://127.0.0.1:8888", names="*")
    assert all(s._proxy == "http://127.0.0.1:8888" for s in all_four)


def test_an_empty_url_routes_nothing():
    sources, all_four = _sources()
    assert apply_outbound_proxy(sources, url="", names="*") is None
    assert all(s._proxy is None for s in all_four)


def test_socks_without_socksio_is_not_applied_and_says_why(monkeypatch):
    """★걸면 요청 순간 ImportError 로 점검이 통째로 죽는다 — 걸지 않고 이유를 남긴다."""
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name == "socksio" else real(name, *a, **k))
    sources, (utic, *_rest) = _sources()
    reason = apply_outbound_proxy(sources, url="socks5://127.0.0.1:1080", names="utic")
    assert reason is not None and "socksio" in reason
    assert utic._proxy is None


def _built_utic(**overrides):
    from app.core.settings import Settings
    from app.infrastructure.travel.base import build_travel_sources

    settings = Settings.model_construct(**{"its_api_key": "", "utic_api_key_1": "key-one",
                                           "utic_api_key_2": "key-two", **overrides})
    return build_travel_sources(settings).traffic


def test_the_utic_key_follows_the_road_out():
    """★UTIC 키는 IP 에 묶여 있다 — 서버를 거치면 key 2, 바로 나가면 key 1(실측: 반대로 쓰면 03 거절)."""
    proxied = _built_utic(outbound_proxy_url="http://127.0.0.1:8888", outbound_proxy_sources="utic")
    assert proxied._key == "key-two" and proxied._proxy == "http://127.0.0.1:8888"
    direct = _built_utic(outbound_proxy_url="", outbound_proxy_sources="utic")
    assert direct._key == "key-one" and direct._proxy is None
    not_listed = _built_utic(outbound_proxy_url="http://127.0.0.1:8888", outbound_proxy_sources="its")
    assert not_listed._key == "key-one" and not_listed._proxy is None


def test_the_proxy_is_actually_passed_to_the_request(monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))
    monkeypatch.setattr(base_module.httpx, "get", fake_get)
    source = _Src("utic")
    source._proxy = "http://127.0.0.1:8888"
    source._http_get("https://x", {})
    assert seen["proxy"] == "http://127.0.0.1:8888"

    seen.clear()
    _Src("its")._http_get("https://x", {})
    assert "proxy" not in seen                     # ★안 걸린 소스는 바로 나간다
