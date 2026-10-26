"""Activity public-web supplement — `ddgs` discovery backend (offline; no DB, model or network).

ddgs only discovers candidate URLs from public canonical name + district. Facts still come only from
official-page structured JSON-LD through the existing pinned/robots-checked transport.
"""
import json
import pathlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from app.domains.travel_ops.ports.data_sources import activity_public_web as m
from app.domains.travel_ops.ports.data_sources.cache import ResponseCache

ROOT = pathlib.Path(__file__).resolve().parents[3]
IDENTITY = {'canonical_id': 'fixture:tower', 'name': '공개타워', 'aliases': ['N타워'],
            'address': '서울 용산구 공개길 1', 'district': '서울 용산구',
            'official_hosts': ['tower.example'], 'provenance': 'public_catalog'}
LIMITS = {'timeout_seconds': 2, 'max_response_bytes': 20000, 'max_url_chars': 2048}
DDGS = {'backends': ['duckduckgo'], 'region': 'kr-kr', 'safesearch': 'moderate', 'max_results': 5}
CFG = {'enabled': True, 'backend': 'ddgs', 'paid': False, 'approved_public_queries': True,
       'search_hosts': ['html.duckduckgo.com'], 'identities': [IDENTITY], 'max_pages': 3,
       'total_seconds': 10, 'coordinate_tolerance': 0.001, 'ddgs': DDGS,
       'daily_limits': {'activity_web_search': 10, 'activity_official_extract': 10}}
PAGE = ('<script type="application/ld+json">' + json.dumps(
    {'@type': 'TouristAttraction', 'name': '공개타워', 'address': IDENTITY['address'],
     'openingHours': '10:00-18:00'}) + '</script>')


class FakeDdgs:
    def __init__(self, hits=None, error=None):
        self.hits = hits if hits is not None else [
            {'title': 't', 'href': 'https://tower.example/info', 'body': 'SNIPPET 09:00-23:00'},
            {'title': 'blog', 'href': 'https://blog.example/post', 'body': 'blog says 08:00'}]
        self.error = error
        self.calls = []

    def __call__(self, timeout):
        self.calls.append({'timeout': timeout})
        return self

    def text(self, query, **kwargs):
        self.calls.append({'query': query, **kwargs})
        if self.error is not None:
            raise self.error
        return self.hits


def limiter(allow=True):
    def acquire(name):
        if not allow:
            from app.domains.travel_ops.ports.data_sources.ratelimit import RateLimited
            raise RateLimited(name, 1.0)
    return SimpleNamespace(meters=set(CFG['daily_limits']), _on_db_error='refuse', acquire=acquire)


def guardrails(cfg):
    return SimpleNamespace(get=lambda key: {'travel.social_dining': LIMITS,
                                            'travel.activity_public_web': cfg}.get(key))


def build(cfg=CFG, *, ddgs=None, lim=None, cache=None, hosts=('html.duckduckgo.com',)):
    ddgs = ddgs or FakeDdgs()
    with patch.object(m, '_ddgs_engine_hosts', return_value=set(hosts)), \
            patch.object(m, '_ddgs_client_factory', return_value=ddgs):
        built = m.build_activity_public_web(SimpleNamespace(), guardrails(cfg),
                                            limiter=lim or limiter(), cache=cache)
    pages = []

    def fetch(url, hosts):
        pages.append(url)
        return PAGE
    if built.config.get('enabled'):
        built.extract.fetch = fetch
    return built, ddgs, pages


def test_ddgs_backend_discovers_then_official_jsonld_supplies_facts():
    built, ddgs, pages = build()
    assert built.config.get('enabled') is True, 'ddgs backend must be accepted by the factory'
    out = built.lookup('N타워')
    assert out['facts']['business_hours']['value'] == '10:00-18:00'
    assert out['facts']['business_hours']['source_url'] == 'https://tower.example/info'
    assert out['confidence'] == 'official_structured' and out['search_backend'] == 'ddgs'
    # snippets are discovery only — never evidence, never stored
    dumped = json.dumps(out, ensure_ascii=False)
    assert 'SNIPPET' not in dumped and '09:00-23:00' not in dumped and '08:00' not in dumped
    # only the official host page is read; the blog URL is rejected by the official_hosts rule
    assert pages == ['https://tower.example/info']
    query = [c for c in ddgs.calls if 'query' in c][0]
    assert query['query'] == '공개타워 서울 용산구'  # public canonical name + district only
    assert 'N타워' not in query['query']  # never the customer's own label
    assert query['backend'] == 'duckduckgo' and query['region'] == 'kr-kr'
    assert query['max_results'] == 5 and query['safesearch'] == 'moderate'


def test_official_read_failure_outranks_filtered_non_official_urls():
    hits = [{'href': 'https://ko.wikipedia.example/wiki/x'}, {'href': 'https://tower.example/home'}]
    built, ddgs, _ = build(ddgs=FakeDdgs(hits=hits))

    def redirected(url, hosts):
        raise m.WebFailure('redirect_blocked')
    built.extract.fetch = redirected
    out = built.lookup('N타워')
    assert out['reason'] == 'extract_redirect_blocked' and out['facts'] == {}


def test_ddgs_query_never_carries_customer_or_address_fields():
    built, ddgs, _ = build()
    built.lookup('N타워')
    sent = json.dumps(ddgs.calls, ensure_ascii=False)
    for private in ('공개길 1', 'fixture:tower', 'tenant', 'customer'):
        assert private not in sent


@pytest.mark.parametrize('error,reason', [
    (type('RatelimitException', (Exception,), {})('202 Ratelimit'), 'search_http_429'),
    (type('TimeoutException', (Exception,), {})('timed out'), 'search_web_timeout'),
    (type('DDGSException', (Exception,), {})('No results found.'), 'search_no_results'),
    (type('DDGSException', (Exception,), {})('engine broke'), 'search_failed'),
])
def test_ddgs_failures_surface_as_public_web_reason_without_fallback(error, reason):
    built, ddgs, pages = build(ddgs=FakeDdgs(error=error))
    out = built.lookup('N타워')
    assert out['status'] == 'unknown' and out['needs_question'] is True and out['facts'] == {}
    assert out['reason'] == reason
    assert pages == []  # no silent fallback to other search or page reads


def test_ddgs_identity_without_district_is_not_queried():
    cfg = {**CFG, 'identities': [{k: v for k, v in IDENTITY.items() if k != 'district'}]}
    built, ddgs, _ = build(cfg)
    assert built.lookup('N타워')['reason'] == 'search_query_unconfigured'
    assert [c for c in ddgs.calls if 'query' in c] == []


def test_ddgs_budget_refusal_blocks_before_search():
    built, ddgs, _ = build(lim=limiter(allow=False))
    assert built.lookup('N타워')['reason'] == 'search_budget_blocked'
    assert ddgs.calls == []


def test_ddgs_ambient_proxy_is_refused(monkeypatch):
    monkeypatch.setenv('DDGS_PROXY', 'socks5h://127.0.0.1:9150')
    built, ddgs, _ = build()
    assert built.lookup('N타워')['reason'] == 'search_proxy_rejected'
    assert ddgs.calls == []


def test_ddgs_discovery_reuses_shared_cache():
    cache = ResponseCache(ttl_seconds=600)
    built, ddgs, _ = build(cache=cache)
    built.lookup('N타워')
    built.lookup('N타워')
    assert len([c for c in ddgs.calls if 'query' in c]) == 1


@pytest.mark.parametrize('patch_cfg,hosts', [
    ({'ddgs': {**DDGS, 'backends': ['auto']}}, ('html.duckduckgo.com',)),
    ({'ddgs': {**DDGS, 'backends': []}}, ('html.duckduckgo.com',)),
    ({'ddgs': {**DDGS, 'max_results': 0}}, ('html.duckduckgo.com',)),
    ({'ddgs': {**DDGS, 'safesearch': 'whatever'}}, ('html.duckduckgo.com',)),
    ({'search_hosts': ['other.example']}, ('html.duckduckgo.com',)),
    ({'paid': True}, ('html.duckduckgo.com',)),
    ({'approved_public_queries': False}, ('html.duckduckgo.com',)),
    ({}, ()),  # backend host unknown => not allowlisted
])
def test_ddgs_factory_refuses_unbounded_or_unapproved_config(patch_cfg, hosts):
    built, ddgs, _ = build({**CFG, **patch_cfg}, hosts=hosts)
    out = built.lookup('N타워')
    assert out['reason'] == 'web_not_configured'
    assert out['config_detail']  # the refusal is observable, not silent
    assert ddgs.calls == []


def test_ddgs_package_missing_is_observable():
    with patch.object(m, '_ddgs_engine_hosts', side_effect=ImportError('ddgs')):
        built = m.build_activity_public_web(SimpleNamespace(), guardrails(CFG), limiter=limiter(), cache=None)
    out = built.lookup('N타워')
    assert out['reason'] == 'web_not_configured' and out['config_detail'] == 'ddgs_package_missing'


def test_unknown_backend_is_refused_observably():
    built, ddgs, _ = build({**CFG, 'backend': 'hermes_gateway'})
    out = built.lookup('N타워')
    assert out['reason'] == 'web_not_configured' and out['config_detail'] == 'backend_unsupported'


def test_engine_hosts_come_from_ddgs_registry_search_url():
    class Engine:
        search_url = 'https://html.duckduckgo.com/html/'
    registry = SimpleNamespace(ENGINES={'text': {'duckduckgo': Engine}})
    with patch.dict('sys.modules', {'ddgs': SimpleNamespace(), 'ddgs.engines': registry}):
        assert m._ddgs_engine_hosts(['duckduckgo']) == {'html.duckduckgo.com'}
        with pytest.raises(KeyError):
            m._ddgs_engine_hosts(['not-an-engine'])


def test_ddgs_pinned_in_requirements_and_default_stays_off():
    req = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    pins = {line.split('==')[0].strip().lower(): line.split('==')[1].split()[0]
            for line in req.splitlines() if '==' in line and not line.lstrip().startswith('#')}
    assert pins.get('ddgs') == '9.16.1'
    assert 'primp' in pins and 'lxml' in pins
    cfg = yaml.safe_load((ROOT / 'config/guardrails.yaml').read_text(encoding='utf-8'))
    web = cfg['travel']['activity_public_web']
    assert web['enabled'] is False and web['approved_public_queries'] is False
    assert web['ddgs']['backends'] and 'auto' not in web['ddgs']['backends']
