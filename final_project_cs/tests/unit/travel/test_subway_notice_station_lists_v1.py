"""다역 표기 누락 재현. 과거 보고 문구와 통제 공지이며 실제 탐지율 표본이 아닙니다."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.ports.data_sources.subway_notice import (
    SubwayNotices,
    SubwayRouteEvents,
    mentions_station,
)

KST = ZoneInfo('Asia/Seoul')
NOW = datetime(2026, 9, 22, 21, 30, tzinfo=KST)
RECORDED_TITLE = '4호선 시위로 혜화, 한성대입구역(하선) 무정차 통과'


@pytest.mark.parametrize('separator', [', ', ',', '·', 'ㆍ', '、', ' / '])
def test_a_shared_station_suffix_covers_each_list_member(separator):
    title = f'4호선 혜화{separator}한성대입구역(하선) 무정차 통과'
    assert mentions_station(title, '혜화')
    assert mentions_station(title, '한성대입구')


@pytest.mark.parametrize('station', ['성신여대입구', '혜화', '한성대입구'])
def test_three_members_and_optional_station_suffix(station):
    assert mentions_station('4호선 성신여대입구, 혜화, 한성대입구역 무정차 통과', station)
    assert mentions_station('4호선 성신여대입구역, 혜화역, 한성대입구역 무정차 통과', station)


@pytest.mark.parametrize(('title', 'station'), [
    ('2호선 신대방, 구로디지털단지역 무정차', '대방'),
    ('4호선 한성대입구, 혜화역 무정차', '성대입구'),
    ('4호선 혜화동, 한성대입구역 무정차', '혜화'),
    ('4호선 혜화 앞, 한성대입구역 무정차', '혜화'),
    ('4호선 혜화, 집회 안내로 한성대입구역 무정차', '혜화'),
    ('4호선 혜화. 한성대입구역 무정차', '혜화'),
    ('4호선 혜화, 한성대입구 무정차', '혜화'),
    ('4호선 혜화, 한성대입구역사 안내', '혜화'),
    ('4호선 혜화, 한성대입구역할 안내', '혜화'),
    ('4호선 혜화, 한성대입구역 무정차', '종로3가'),
    ('4호선 혜화, 한성대입구역 무정차', ''),
])
def test_lists_do_not_expand_suffixes_or_unrelated_prose(title, station):
    assert not mentions_station(title, station)


@pytest.mark.parametrize('particle', ['은', '는', '이', '가', '을', '를', '의', '에서', '에', '으로'])
def test_shared_station_suffix_before_a_korean_particle(particle):
    assert mentions_station(f'혜화, 한성대입구역{particle} 무정차 통과', '혜화')


def _row(title, when='2026-09-22T21:22:23', line='4호선', content=''):
    return {'noftTtl': title, 'noftCn': content, 'noftOcrnDt': when, 'lineNmLst': line}


def _events(rows):
    notices = SubwayNotices(service_key='', now=lambda: NOW)
    notices.records = lambda: rows
    return SubwayRouteEvents(notices)


def test_the_recorded_list_title_produces_both_station_events():
    events = _events([_row(RECORDED_TITLE)])
    found = events.affecting(['4호선:혜화', '4호선:한성대입구'], NOW)
    assert list(found) == ['4호선:혜화', '4호선:한성대입구']
    assert {item['effect'] for item in found.values()} == {'skip_station'}
    assert {item['title'] for item in found.values()} == {RECORDED_TITLE}


def test_the_newer_list_end_notice_clears_both_station_events():
    events = _events([
        _row(RECORDED_TITLE),
        _row('4호선 혜화, 한성대입구역 무정차 통과 종료', '2026-09-22T21:28:00'),
    ])
    assert events.affecting(['4호선:혜화', '4호선:한성대입구'], NOW) == {}


def test_an_end_notice_for_one_station_does_not_clear_another():
    events = _events([
        _row(RECORDED_TITLE),
        _row('4호선 한성대입구역 정상운행', '2026-09-22T21:28:00'),
    ])
    assert list(events.affecting(['4호선:혜화', '4호선:한성대입구'], NOW)) == ['4호선:혜화']


def test_a_list_in_notice_content_uses_the_same_station_matcher():
    events = _events([_row('4호선 열차 무정차 통과', content='혜화, 한성대입구역(하선)')])
    assert list(events.affecting(['4호선:혜화', '4호선:한성대입구'], NOW)) == ['4호선:혜화', '4호선:한성대입구']


@pytest.mark.parametrize('when', ['2026-09-22T18:29:00', '2026-09-22T21:31:00'])
def test_list_matching_does_not_bypass_the_event_time_window(when):
    events = _events([_row(RECORDED_TITLE, when)])
    assert events.affecting(['4호선:혜화', '4호선:한성대입구'], NOW) == {}


def test_list_matching_does_not_bypass_the_line_filter():
    events = _events([_row(RECORDED_TITLE)])
    assert events.affecting(['3호선:혜화', '3호선:한성대입구'], NOW) == {}
