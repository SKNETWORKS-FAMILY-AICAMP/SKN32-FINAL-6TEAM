"""Official-page text evidence, bounded redirects and plain-HTTP official reads (2026-10-26).

Offline: no DB, model or network. Fixture HTML is synthetic.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.domains.travel_ops.ports.data_sources import activity_public_web as m
from app.domains.travel_ops.ports.data_sources import public_web_transport as tr

IDENTITY = {'canonical_id': 'fixture:museum', 'name': '공개박물관', 'aliases': [], 'address': '서울 종로구 공개길 1',
            'official_hosts': ['museum.example', 'www.museum.example'], 'provenance': 'public_catalog',
            'district': '서울 종로구', 'homepage': 'http://www.museum.example/'}
CFG = {'enabled': True, 'backend': 'ddgs', 'search_hosts': ['duckduckgo.com'], 'identities': [IDENTITY],
       'max_pages': 4, 'total_seconds': 10, 'coordinate_tolerance': 0.001,
       'ddgs': {'backends': ['duckduckgo'], 'region': 'kr-kr', 'safesearch': 'moderate', 'max_results': 5},
       'official_text': True, 'official_http': True, 'official_max_redirects': 2}
LIMITS = {'timeout_seconds': 2, 'max_response_bytes': 20000, 'max_url_chars': 2048}
PAGE = ('<html><head><title>공개박물관</title><script>var t="운영시간 01:00~02:00"</script></head><body>'
        '<h1>공개박물관 관람안내</h1><dl><dt>관람시간</dt><dd>화~일 10:00~18:00 (입장마감 17:30)</dd>'
        '<dt>휴관일</dt><dd>매주 월요일, 1월 1일</dd></dl></body></html>')


class Client:
    def __init__(self, hits):
        self.hits, self.queries = hits, []

    def __call__(self, timeout):
        return self

    def text(self, query, **kw):
        self.queries.append(query)
        return self.hits


def provider(pages, *, hits=(), cfg=None):
    calls = []

    def fetch(url, hosts, **kw):
        calls.append((url, kw))
        body = pages[url]
        if isinstance(body, Exception):
            raise body
        page = tr.Page(body)
        page.url = kw.get('final', url)
        return page
    p = m.ActivityPublicWeb(cfg or CFG, limits=LIMITS, limiter=SimpleNamespace(acquire=lambda name: None),
                            cache=None, fetch=fetch, ddgs_client=Client([{'href': h} for h in hits]))
    return p, calls


# --- rule parser -----------------------------------------------------------------------------

def parse(html):
    from app.domains.travel_ops.ports.data_sources import official_hours_text as t
    text, _ = t.visible(html)
    return t.parse(text), text


def test_parser_reads_labelled_hours_and_weekly_closure_with_verbatim_quotes():
    out, text = parse(PAGE)
    assert out['hours'] == [{'days': ['tue', 'wed', 'thu', 'fri', 'sat', 'sun'], 'open': '10:00', 'close': '18:00'}]
    assert out['closed'] == ['mon']
    assert all(q in text for q in out['quotes'])
    assert '01:00' not in json.dumps(out)  # script text is not visible evidence


@pytest.mark.parametrize('html,expected', [
    ('<p>운영시간 : 평일 09:00~20:00 / 주말·공휴일 09:00~17:00</p><p>휴관일 : 매주 화요일</p>',
     [{'days': ['mon', 'wed', 'thu', 'fri'], 'open': '09:00', 'close': '20:00'},
      {'days': ['sat', 'sun'], 'open': '09:00', 'close': '17:00'}]),
    ('<p>관람시간 오전 10시 ~ 오후 6시</p>', [{'days': None, 'open': '10:00', 'close': '18:00'}]),
    ('<p>이용시간 09:00~18:00 (준비 시간 12:00~13:00)</p>', [{'days': None, 'open': '09:00', 'close': '18:00'}]),
])
def test_parser_supported_forms(html, expected):
    assert parse(html)[0]['hours'] == expected


@pytest.mark.parametrize('html,reason', [
    ('<p>관람시간 하절기(3월~10월) 06:00~18:00</p><p>관람시간 동절기(11월~2월) 07:00~17:00</p>', 'conditional_hours'),
    ('<p>운영시간 10:00~18:00</p><p>운영시간 11:00~20:00</p>', 'conflicting_hours'),
    ('<p>운영시간 월요일 09:00~20:00</p><p>휴관일 : 매주 월요일</p>', 'closed_conflict'),
    ('<p>오시는 길 10:00~18:00 주차 가능</p>', 'no_hours'),
    ('<p>운영시간 25:00~26:00</p>', 'invalid_time'),
    # Real-page regressions (2026-10-26 accuracy run): a dated notice and a half-day-less close time.
    ('<h2>2026년 9월 3일(목) 공개박물관 관람시간 단축 안내</h2><p>관람시간 10:00~17:00</p>', 'dated_notice'),
    ('<p>관람시간 월~금 오전 10시 ~ 4시</p>', 'invalid_time'),
    ('<p>관람시간 평일 10시 - 16시</p><p>관람시간 10:00~17:00</p>', 'mixed_day_scope'),
])
def test_parser_ambiguous_or_unsupported_stays_unknown(html, reason):
    assert parse(html)[0] == {'ambiguous': reason}


# --- provider: text evidence ----------------------------------------------------------------

def test_text_evidence_from_official_page_carries_quote_source_time_and_kind():
    p, calls = provider({'http://www.museum.example/': PAGE})
    out = p.lookup('공개박물관')
    fact = out['facts']['business_hours']
    assert fact['evidence'] == 'text' and fact['confidence'] == 'official_text'
    assert fact['value']['closed'] == ['mon']
    assert fact['source_url'] == 'http://www.museum.example/' and fact['scheme'] == 'http'
    assert fact['checked_at'] and fact['quotes'] and fact['body_sha256']
    assert out['confidence'] == 'official_text' and out['needs_question'] is True
    assert 'date_specific' in out['unknown'] and 'business_hours' not in out['unknown']
    assert calls[0][1] == {'redirects': 2, 'http_ok': True, 'subdomains': True}


def test_text_evidence_is_off_unless_configured():
    p, _ = provider({'http://www.museum.example/': PAGE}, cfg={**CFG, 'official_text': False})
    out = p.lookup('공개박물관')
    assert out['facts'] == {} and out['status'] == 'unknown'


def test_text_evidence_requires_identity_name_on_page():
    other = PAGE.replace('공개박물관', '다른전시관')
    p, _ = provider({'http://www.museum.example/': other})
    out = p.lookup('공개박물관')
    assert out['facts'] == {} and out['reason'] == 'identity_unverified'


def test_quote_must_exist_in_page_text_server_side():
    from app.domains.travel_ops.ports.data_sources import official_hours_text as t
    p, _ = provider({'http://www.museum.example/': PAGE})
    real = t.parse
    with patch.object(t, 'parse', lambda text: {**real(text), 'quotes': ['관람시간 09:00~21:00']}):
        out = p.lookup('공개박물관')
    assert out['facts'] == {} and out['reason'] == 'quote_unverified'


def test_conflicting_pages_stay_unknown():
    other = PAGE.replace('10:00~18:00', '09:00~17:00')
    p, _ = provider({'http://www.museum.example/': PAGE, 'https://www.museum.example/guide': other},
                    hits=['https://www.museum.example/guide'])
    out = p.lookup('공개박물관')
    assert out['reason'] == 'conflicting_sources' and out['facts'] == {}


def test_guide_link_on_official_page_is_followed_within_official_hosts_only():
    home = ('<html><body><p>공개박물관</p><a href="/info/guide">관람안내</a>'
            '<a href="https://evil.example/hours">관람안내</a></body></html>')
    p, calls = provider({'http://www.museum.example/': home, 'http://www.museum.example/info/guide': PAGE})
    out = p.lookup('공개박물관')
    assert out['facts']['business_hours']['source_url'] == 'http://www.museum.example/info/guide'
    assert [c[0] for c in calls] == ['http://www.museum.example/', 'http://www.museum.example/info/guide']


def test_search_failure_still_reads_reviewed_homepage_and_reports_it():
    p, _ = provider({'http://www.museum.example/': PAGE})
    out = p.lookup('공개박물관')  # Client returns no hits -> search_no_results
    assert out['facts']['business_hours']['value']['closed'] == ['mon']
    assert out['search_failure'] == 'search_no_results'


def test_http_official_is_refused_without_opt_in():
    p, calls = provider({'http://www.museum.example/': PAGE}, cfg={**CFG, 'official_http': False})
    out = p.lookup('공개박물관')
    assert out['facts'] == {} and calls == []


# --- transport: redirects, http, robots 404, charset -----------------------------------------

class Resp:
    def __init__(self, status, body=b'', headers=None):
        self.status, self.body, self.headers = status, body, {'Content-Type': 'text/html', **(headers or {})}

    def getheader(self, key, default=''):
        return self.headers.get(key, default)

    def read(self, n):
        return self.body


def wire(routes):
    sent = []

    class Conn:
        sock = None

        def __init__(self, host, ip, **kw):
            self.host = host

        def request(self, method, target, headers):
            sent.append((self.scheme, self.host, method, target, headers))

        def getresponse(self):
            return routes[(self.scheme, self.host, sent[-1][3])]

        def close(self):
            pass

    class Https(Conn):
        scheme = 'https'

    class Http(Conn):
        scheme = 'http'
    return sent, Https, Http


def run(routes, url, hosts, **kw):
    sent, https, http = wire(routes)
    t = tr.PublicWebTransport(LIMITS)
    with patch.object(tr.social_links, '_public_addresses', return_value=['93.184.216.34']), \
            patch.object(tr.social_links, '_PinnedHTTPSConnection', https), \
            patch.object(tr, '_PinnedHTTPConnection', http):
        return t(url, hosts, allow=lambda: True, **kw), sent


def test_redirect_inside_official_hosts_is_followed_and_final_url_kept():
    routes = {('http', 'museum.example', '/robots.txt'): Resp(404),
              ('http', 'museum.example', '/'): Resp(301, headers={'Location': 'https://www.museum.example/main'}),
              ('https', 'www.museum.example', '/main'): Resp(200, '<p>공개박물관</p>'.encode())}
    body, sent = run(routes, 'http://museum.example/', ['museum.example'], redirects=2, http_ok=True, subdomains=True)
    assert body == '<p>공개박물관</p>' and body.url == 'https://www.museum.example/main'
    assert all(s[2] == 'GET' and set(s[4]) == {'Accept', 'Accept-Encoding', 'User-Agent'} for s in sent)


@pytest.mark.parametrize('location', ['https://evil.example/', 'https://museum.example.evil/', 'ftp://museum.example/'])
def test_redirect_outside_official_hosts_is_blocked(location):
    routes = {('https', 'museum.example', '/robots.txt'): Resp(200, b''),
              ('https', 'museum.example', '/'): Resp(302, headers={'Location': location})}
    with pytest.raises(tr.WebFailure, match='redirect_blocked'):
        run(routes, 'https://museum.example/', ['museum.example'], redirects=2, http_ok=True, subdomains=True)


def test_redirect_hop_limit():
    routes = {('https', 'museum.example', '/robots.txt'): Resp(200, b''),
              ('https', 'museum.example', '/'): Resp(302, headers={'Location': '/a'}),
              ('https', 'museum.example', '/a'): Resp(302, headers={'Location': '/b'}),
              ('https', 'museum.example', '/b'): Resp(200, b'ok')}
    with pytest.raises(tr.WebFailure, match='redirect_blocked'):
        run(routes, 'https://museum.example/', ['museum.example'], redirects=1, http_ok=True, subdomains=True)


def test_default_reader_still_refuses_redirect_http_and_robots_404():
    routes = {('https', 'museum.example', '/robots.txt'): Resp(200, b''),
              ('https', 'museum.example', '/'): Resp(301, headers={'Location': '/x'})}
    with pytest.raises(tr.WebFailure, match='redirect_blocked'):
        run(routes, 'https://museum.example/', ['museum.example'])
    with pytest.raises(tr.WebFailure, match='source_url_rejected'):
        run(routes, 'http://museum.example/', ['museum.example'])
    with pytest.raises(tr.WebFailure, match='http_404'):
        run({('https', 'museum.example', '/robots.txt'): Resp(404)}, 'https://museum.example/', ['museum.example'])


def test_robots_server_error_still_stops_opt_in_reader():
    routes = {('http', 'museum.example', '/robots.txt'): Resp(503)}
    with pytest.raises(tr.WebFailure, match='http_503'):
        run(routes, 'http://museum.example/', ['museum.example'], redirects=1, http_ok=True)


def test_euc_kr_page_decodes_and_unknown_charset_is_unreadable():
    body = '<p>관람시간 10:00~18:00</p>'.encode('cp949')
    routes = {('https', 'museum.example', '/robots.txt'): Resp(200, b''),
              ('https', 'museum.example', '/'): Resp(200, body, {'Content-Type': 'text/html; charset=euc-kr'})}
    assert run(routes, 'https://museum.example/', ['museum.example'])[0] == '<p>관람시간 10:00~18:00</p>'
    routes[('https', 'museum.example', '/')] = Resp(200, body, {'Content-Type': 'text/html; charset=shift_jis'})
    with pytest.raises(tr.WebFailure, match='charset_unsupported'):
        run(routes, 'https://museum.example/', ['museum.example'])


# --- customer display ------------------------------------------------------------------------

def test_review_line_shows_official_homepage_basis_and_checked_time():
    from app.domains.travel_ops.components.intake import review
    p, _ = provider({'http://www.museum.example/': PAGE})
    web = p.lookup('공개박물관')
    text = review.public_web_hours_text(web)
    assert '공식 홈페이지 기준' in text and '확인 시각' in text and '10:00~18:00' in text and '월' in text
    assert review.public_web_hours_text({'facts': {}}) is None


def test_opt_in_official_reads_accept_query_urls_and_keep_search_failure_visible():
    seed = 'https://www.museum.example/contents.do?mid=449'
    p, calls = provider({seed: PAGE.replace('관람시간', '안내')}, cfg={**CFG, 'identities': [{**IDENTITY, 'homepage': seed}]})
    out = p.lookup('공개박물관')
    assert [c[0] for c in calls] == [seed]
    assert out['facts'] == {} and out['reason'] == 'search_no_results'


def test_review_line_names_kakao_miss_and_source_kind():
    from app.domains.travel_ops.components.intake import review
    p, _ = provider({'http://www.museum.example/': PAGE})
    web = p.lookup('공개박물관')
    assert web['facts']['business_hours']['source_kind'] == 'official_homepage'
    pw = {**web, 'upstream_status': 'not_found', 'upstream_blocked': []}
    row = {'title': '공개박물관', 'kind': 'activity', 'claims': {'place': {'evidence': {'public_web': pw}}}}
    line = json.dumps(review._place_line(row, 'unresolved', None), ensure_ascii=False)
    assert '카카오에서 확인되지 않음' in line and '공식 홈페이지 기준' in line and '확인 시각' in line
    assert '방문일 운영 여부는 확정하지 않았어요' in line
    assert review.kakao_unverified_text({**web, 'upstream_status': 'not_found', 'upstream_blocked': []}) == '카카오에서 확인되지 않음'
    assert review.kakao_unverified_text({**web, 'upstream_status': 'unknown', 'upstream_blocked': ['http_503']}) == '카카오 조회가 막혀 확인되지 않음'
    assert review.public_web_hours_text(web).startswith('공식 홈페이지 기준')
    google = {'facts': {'business_hours': {**web['facts']['business_hours'], 'source_kind': 'google_places'}}}
    assert review.public_web_hours_text(google).startswith('구글 지도 기준')


def test_one_unreadable_official_page_makes_the_place_unknown():
    bad = PAGE.replace('화~일 10:00~18:00', '월~금 오전 10시 ~ 4시')
    p, _ = provider({'http://www.museum.example/': PAGE, 'https://www.museum.example/visit': bad},
                    hits=['https://www.museum.example/visit'])
    out = p.lookup('공개박물관')
    assert out['facts'] == {} and out['reason'] == 'ambiguous_hours'
